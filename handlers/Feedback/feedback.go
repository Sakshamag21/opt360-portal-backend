package Feedback

import (
	"bytes"
	"encoding/json"
	"log"
	"net/http"
	"strings"
	"time"

	"opt360-portal-backend/config"
	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/s3"
	"github.com/gin-gonic/gin"
)


func SubmitFeedback(c *gin.Context) {
	// Get user from context
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}

	user := userInterface.(*models.User)

	// Parse request body
	var feedbackData map[string]interface{}
	if err := c.ShouldBindJSON(&feedbackData); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid JSON in request body",
			"details": err.Error(),
		})
		return
	}

	// Get required parameter from request body
	optID, optIDExists := feedbackData["opt_id"].(string)

	if !optIDExists || optID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "opt_id is required in request body",
		})
		return
	}

	dataPath, err := db.GetDataPathByOptID(optID)
	if err != nil {
		log.Printf("[SubmitFeedback] DataPath lookup failed opt_id=%s user=%s: %v", optID, user.ADID, err)
		c.JSON(http.StatusNotFound, gin.H{
			"error":       "Operator data path not found",
			"operator_id": optID,
			"details":     err.Error(),
		})
		return
	}

	s3Cfg := config.GetDefaultS3Config()

	s3Client, err := config.NewS3Client(s3Cfg)
	if err != nil {
		log.Printf("[SubmitFeedback] S3 client error user=%s: %v", user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create S3 client", "details": err.Error()})
		return
	}

	currentDate := time.Now().Format("2006_01_02")
	fileName := strings.TrimSuffix(dataPath, "/") + "/" + currentDate + "_" + user.ADID + ".json"

	jsonData, err := json.MarshalIndent(feedbackData, "", "  ")
	if err != nil {
		log.Printf("[SubmitFeedback] JSON marshal error user=%s: %v", user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to marshal feedback data to JSON", "details": err.Error()})
		return
	}

	log.Printf("[SubmitFeedback] Uploading feedback key=%s user=%s", fileName, user.ADID)
	_, err = s3Client.PutObject(&s3.PutObjectInput{
		Bucket:      aws.String(s3Cfg.BucketName),
		Key:         aws.String(fileName),
		Body:        bytes.NewReader(jsonData),
		ContentType: aws.String("application/json"),
	})
	if err != nil {
		log.Printf("[SubmitFeedback] S3 upload failed key=%s user=%s: %v", fileName, user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to upload feedback file to S3", "details": err.Error()})
		return
	}

	log.Printf("[SubmitFeedback] Feedback stored key=%s user=%s", fileName, user.ADID)
	c.JSON(http.StatusOK, gin.H{
		"message":         "Feedback submitted successfully",
		"regional_office": user.RegionalOffice,
		"operator_id":     optID,
		"file_path":       fileName,
		"date":            currentDate,
		"submitted_by":    user.ADID,
	})
}