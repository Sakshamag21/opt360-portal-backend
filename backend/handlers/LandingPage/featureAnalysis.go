package LandingPage

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"time"

	"opt360-portal-backend/cache"
	"opt360-portal-backend/config"
	"opt360-portal-backend/models"
	"opt360-portal-backend/utils"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/s3"
	"github.com/gin-gonic/gin"
)

// featureAnalysisCacheTTL is how long a cached feature analysis response is considered fresh.
const featureAnalysisCacheTTL = 10 * time.Minute

func GetFeatureAnalysis(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)

	ro := c.Query("RO")
	if ro == "" {
		ro = user.RegionalOffice
	}
	ro = utils.ToPascalCase(ro)

	// ── Cache lookup ──────────────────────────────────────────────────────────
	cacheKey := cache.GenerateKey("feature_analysis", ro)
	var cached interface{}
	if hit, err := landingCache.Get("feature_analysis", cacheKey, featureAnalysisCacheTTL, &cached); err != nil {
		log.Printf("[GetFeatureAnalysis] Cache read error for ro=%s: %v", ro, err)
	} else if hit {
		log.Printf("[GetFeatureAnalysis] Cache hit for ro=%s", ro)
		c.JSON(http.StatusOK, gin.H{
			"regional_office": ro,
			"requested_by":    user.ADID,
			"data":            cached,
		})
		return
	}

	s3Cfg := config.GetDefaultS3Config()

	s3Client, err := config.NewS3Client(s3Cfg)
	if err != nil {
		log.Printf("[GetFeatureAnalysis] S3 client error user=%s: %v", user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create S3 client", "details": err.Error()})
		return
	}

	filePath := "opt360Store/" + ro + "/featureAnalysis.json"

	result, err := s3Client.GetObject(&s3.GetObjectInput{
		Bucket: aws.String(s3Cfg.BucketName),
		Key:    aws.String(filePath),
	})
	if err != nil {
		log.Printf("[GetFeatureAnalysis] S3 fetch failed key=%s user=%s: %v", filePath, user.ADID, err)
		c.JSON(http.StatusNotFound, gin.H{
			"error":           "Feature analysis file not found",
			"regional_office": ro,
			"file_path":       filePath,
			"details":         err.Error(),
		})
		return
	}
	defer result.Body.Close()

	body, err := io.ReadAll(result.Body)
	if err != nil {
		log.Printf("[GetFeatureAnalysis] Read body failed key=%s: %v", filePath, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read file content", "details": err.Error()})
		return
	}

	var data interface{}
	if err := json.Unmarshal(body, &data); err != nil {
		log.Printf("[GetFeatureAnalysis] JSON parse failed key=%s: %v", filePath, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse feature analysis JSON", "details": err.Error()})
		return
	}

	// ── Cache write ────────────────────────────────────────────────────────────
	if err := landingCache.Set("feature_analysis", cacheKey, data); err != nil {
		log.Printf("[GetFeatureAnalysis] Cache write failed for ro=%s: %v", ro, err)
	}

	log.Printf("[GetFeatureAnalysis] Serving key=%s user=%s", filePath, user.ADID)
	c.JSON(http.StatusOK, gin.H{
		"regional_office": ro,
		"requested_by":    user.ADID,
		"data":            data,
	})
}
