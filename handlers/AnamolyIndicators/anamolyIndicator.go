package AnamolyIndicators

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"strings"

	"opt360-portal-backend/config"
	"opt360-portal-backend/models"
	"opt360-portal-backend/utils"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/s3"
	"github.com/gin-gonic/gin"
)

func GetAnamolyIndicators(c *gin.Context) {

	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}

	user := userInterface.(*models.User)

	// anomalies_insights.json is one file per RO — no global/aggregate file,
	// so a TechCentre/HeadQuarters user with no RO selected can't get a
	// "global" view here the way DB-backed endpoints can.
	ro := models.ResolveRO(strings.TrimSpace(c.Query("ro")), user)
	if ro == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Select a Regional Office — there is no global/aggregate file for this data.",
		})
		return
	}

	s3Cfg := config.GetDefaultS3Config()

	filename := "opt360Store/" + utils.ToPascalCase(ro) + "/anomalies_insights.json"

	s3Client, err := config.NewS3Client(s3Cfg)
	if err != nil {
		log.Printf("[GetAnamolyIndicators] S3 client error user=%s: %v", user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create S3 client", "details": err.Error()})
		return
	}

	result, err := s3Client.GetObject(&s3.GetObjectInput{
		Bucket: aws.String(s3Cfg.BucketName),
		Key:    aws.String(filename),
	})
	if err != nil {
		log.Printf("[GetAnamolyIndicators] S3 fetch failed key=%s user=%s: %v", filename, user.ADID, err)
		c.JSON(http.StatusNotFound, gin.H{
			"error":           "Anomalies insights file not found",
			"regional_office": ro,
			"file_path":       filename,
			"details":         err.Error(),
		})
		return
	}
	defer result.Body.Close()

	body, err := io.ReadAll(result.Body)
	if err != nil {
		log.Printf("[GetAnamolyIndicators] Read body failed key=%s: %v", filename, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read file content", "details": err.Error()})
		return
	}

	bodyStr := strings.ReplaceAll(string(body), "'", "\"")

	var jsonData interface{}
	if err := json.Unmarshal([]byte(bodyStr), &jsonData); err != nil {
		log.Printf("[GetAnamolyIndicators] JSON parse failed key=%s: %v", filename, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Invalid JSON in file", "details": err.Error(), "file_path": filename,
		})
		return
	}

	log.Printf("[GetAnamolyIndicators] Serving key=%s user=%s", filename, user.ADID)
	c.JSON(http.StatusOK, gin.H{
		"file":            filename,
		"requested_by":    user.ADID,
		"regional_office": ro,
		"data":            jsonData,
	})

}
