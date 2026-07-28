package LandingPage

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"sort"
	"strings"

	"opt360-portal-backend/config"
	"opt360-portal-backend/models"
	"opt360-portal-backend/utils"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/s3"
	"github.com/gin-gonic/gin"
)

// Request structure for selected EAs
type SelectedEAsRequest struct {
	SelectedEAs []string `json:"selected_eas" binding:"required"`
	RO          string   `json:"ro"`
}

// resolveROOrRespond resolves the RO to use for an S3-file-per-RO lookup
// (audit.json/kpi.json-style endpoints, which have no global/aggregate
// file). If the resolved RO is empty (a TechCentre/HeadQuarters user with no
// override), it writes a 400 and returns ok=false so the caller can bail out
// immediately instead of building a bogus opt360Store//... path.
func resolveROOrRespond(c *gin.Context, explicitRO string, user *models.User) (ro string, ok bool) {
	ro = models.ResolveRO(explicitRO, user)
	if ro == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Select a Regional Office — there is no global/aggregate file for this data.",
		})
		return "", false
	}
	return ro, true
}

// EA distribution structure
type EADistribution struct {
	HighRisk int `json:"high_risk"`
	MedRisk  int `json:"med_risk"`
	LowRisk  int `json:"low_risk"`
	NoRisk   int `json:"no_risk"`
}

// Audit data structure
type AuditData struct {
	EADistribution map[string]EADistribution `json:"ea_distribution"`
}

func GetSelectedEAs(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)

	var req SelectedEAsRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		log.Printf("[GetSelectedEAs] Invalid request body user=%s: %v", user.ADID, err)
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body", "details": err.Error()})
		return
	}
	if len(req.SelectedEAs) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "selected_eas array cannot be empty"})
		return
	}
	ro, ok := resolveROOrRespond(c, strings.TrimSpace(req.RO), user)
	if !ok {
		return
	}

	s3Cfg := config.GetDefaultS3Config()
	fileName := "opt360Store/" + utils.ToPascalCase(ro) + "/audit.json"

	s3Client, err := config.NewS3Client(s3Cfg)
	if err != nil {
		log.Printf("[GetSelectedEAs] S3 client error user=%s: %v", user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create S3 client", "details": err.Error()})
		return
	}

	result, err := s3Client.GetObject(&s3.GetObjectInput{
		Bucket: aws.String(s3Cfg.BucketName),
		Key:    aws.String(fileName),
	})
	if err != nil {
		log.Printf("[GetSelectedEAs] S3 fetch failed key=%s user=%s: %v", fileName, user.ADID, err)
		c.JSON(http.StatusNotFound, gin.H{
			"error": "Audit file not found", "regional_office": ro,
			"file_path": fileName, "details": err.Error(),
		})
		return
	}
	defer result.Body.Close()

	body, err := io.ReadAll(result.Body)
	if err != nil {
		log.Printf("[GetSelectedEAs] Read body failed key=%s: %v", fileName, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read S3 data", "details": err.Error()})
		return
	}

	var auditData AuditData
	if err = json.Unmarshal(body, &auditData); err != nil {
		log.Printf("[GetSelectedEAs] JSON parse failed key=%s: %v", fileName, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse audit data", "details": err.Error()})
		return
	}

	filteredDistribution := make(map[string]EADistribution)
	for _, eaName := range req.SelectedEAs {
		if distribution, ok := auditData.EADistribution[eaName]; ok {
			filteredDistribution[eaName] = distribution
		}
	}

	log.Printf("[GetSelectedEAs] Returning %d EAs for user=%s", len(filteredDistribution), user.ADID)
	c.JSON(http.StatusOK, gin.H{"ea_distribution": filteredDistribution})
}

func GetAllEAs(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)
	ro, ok := resolveROOrRespond(c, strings.TrimSpace(c.Query("ro")), user)
	if !ok {
		return
	}

	s3Cfg := config.GetDefaultS3Config()
	fileName := "opt360Store/" + utils.ToPascalCase(ro) + "/audit.json"

	s3Client, err := config.NewS3Client(s3Cfg)
	if err != nil {
		log.Printf("[GetAllEAs] S3 client error user=%s: %v", user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create S3 client", "details": err.Error()})
		return
	}

	result, err := s3Client.GetObject(&s3.GetObjectInput{
		Bucket: aws.String(s3Cfg.BucketName),
		Key:    aws.String(fileName),
	})
	if err != nil {
		log.Printf("[GetAllEAs] S3 fetch failed key=%s user=%s: %v", fileName, user.ADID, err)
		c.JSON(http.StatusNotFound, gin.H{
			"error": "Audit file not found", "regional_office": ro,
			"file_path": fileName, "details": err.Error(),
		})
		return
	}
	defer result.Body.Close()

	body, err := io.ReadAll(result.Body)
	if err != nil {
		log.Printf("[GetAllEAs] Read body failed key=%s: %v", fileName, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read S3 data", "details": err.Error()})
		return
	}

	var auditData AuditData
	if err = json.Unmarshal(body, &auditData); err != nil {
		log.Printf("[GetAllEAs] JSON parse failed key=%s: %v", fileName, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse audit data", "details": err.Error()})
		return
	}

	eaNames := make([]string, 0, len(auditData.EADistribution))
	for eaName := range auditData.EADistribution {
		eaNames = append(eaNames, eaName)
	}
	sort.Strings(eaNames)

	log.Printf("[GetAllEAs] Returning %d EAs for user=%s", len(eaNames), user.ADID)
	c.JSON(http.StatusOK, gin.H{"eas": eaNames, "count": len(eaNames)})
}
