package LandingPage

import (
	"encoding/json"
	"io"
	"log"
	"net/http"

	"opt360-portal-backend/config"
	"opt360-portal-backend/models"
	"opt360-portal-backend/utils"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/s3"
	"github.com/gin-gonic/gin"
)

func GetKPIData(c *gin.Context) {
	// Get user from context (set by auth middleware)
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}

	user := userInterface.(*models.User)

	// Get S3 configuration
	s3Cfg := config.GetDefaultS3Config()

	// Build file path based on user's regional office
	// Format: opt360Store/{RegionalOffice}/kpi.json
	fileName := "opt360Store/" + utils.ToPascalCase(user.RegionalOffice) + "/kpi.json"

	// Create S3 client
	s3Client, err := config.NewS3Client(s3Cfg)
	if err != nil {
		log.Printf("[GetKPIData] S3 client error user=%s: %v", user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to create S3 client",
			"details": err.Error(),
		})
		return
	}

	// Get the object from S3
	result, err := s3Client.GetObject(&s3.GetObjectInput{
		Bucket: aws.String(s3Cfg.BucketName),
		Key:    aws.String(fileName),
	})
	if err != nil {
		log.Printf("[GetKPIData] S3 fetch failed key=%s user=%s: %v", fileName, user.ADID, err)
		c.JSON(http.StatusNotFound, gin.H{
			"error":           "KPI file not found",
			"regional_office": user.RegionalOffice,
			"file_path":       fileName,
			"details":         err.Error(),
		})
		return
	}
	defer result.Body.Close()

	// Read the file content
	body, err := io.ReadAll(result.Body)
	if err != nil {
		log.Printf("[GetKPIData] Read body failed key=%s: %v", fileName, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to read file content",
			"details": err.Error(),
		})
		return
	}

	var kpiData models.KPIResponse
	if err := json.Unmarshal(body, &kpiData); err != nil {
		log.Printf("[GetKPIData] JSON parse failed key=%s: %v", fileName, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Invalid JSON in file",
			"details": err.Error(),
		})
		return
	}

	log.Printf("[GetKPIData] Serving key=%s user=%s", fileName, user.ADID)
	c.JSON(http.StatusOK, kpiData)
}
