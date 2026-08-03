package OperatorDetailView

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"strings"

	"opt360-portal-backend/config"
	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/s3"
	"github.com/gin-gonic/gin"
)

func GetOperatorFeatures(c *gin.Context) {

	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}

	user := userInterface.(*models.User)

	optID := c.Query("opt_id") // e.g., "MH_WMIT_SN_NS046496"

	if optID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "opt_id query parameter is required",
		})
		return
	}

	dataPath, err := db.GetDataPathByOptID(optID)
	if err != nil {
		log.Printf("[GetOperatorFeatures] DataPath lookup failed opt_id=%s user=%s: %v", optID, user.ADID, err)
		c.JSON(http.StatusNotFound, gin.H{
			"error":       "Operator data path not found",
			"operator_id": optID,
			"details":     err.Error(),
		})
		return
	}

	s3Cfg := config.GetDefaultS3Config()
	fileName := strings.TrimSuffix(dataPath, "/") + "/operator_features.json"

	s3Client, err := config.NewS3Client(s3Cfg)
	if err != nil {
		log.Printf("[GetOperatorFeatures] S3 client error opt_id=%s user=%s: %v", optID, user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create S3 client", "details": err.Error()})
		return
	}

	result, err := s3Client.GetObject(&s3.GetObjectInput{
		Bucket: aws.String(s3Cfg.BucketName),
		Key:    aws.String(fileName),
	})
	if err != nil {
		log.Printf("[GetOperatorFeatures] S3 fetch failed key=%s user=%s: %v", fileName, user.ADID, err)
		c.JSON(http.StatusNotFound, gin.H{
			"error":           "Operator features file not found",
			"regional_office": user.RegionalOffice,
			"operator_id":     optID,
			"file_path":       fileName,
			"details":         err.Error(),
		})
		return
	}
	defer result.Body.Close()

	body, err := io.ReadAll(result.Body)
	if err != nil {
		log.Printf("[GetOperatorFeatures] Read body failed key=%s: %v", fileName, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read S3 data", "details": err.Error()})
		return
	}

	var originalData map[string]interface{}
	if err := json.Unmarshal(body, &originalData); err != nil {
		log.Printf("[GetOperatorFeatures] JSON parse failed key=%s: %v", fileName, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse JSON data", "details": err.Error()})
		return
	}

	// Transform the data structure
	transformedData := make(map[string]interface{})
	transformedData["opt_id"] = originalData["opt_id"]
	
	// Copy metadata if it exists
	if metadata, ok := originalData["metadata"]; ok {
		transformedData["metadata"] = metadata
	}

	// Transform kpis from nested object to flat array
	var kpisArray []map[string]interface{}
	if kpis, ok := originalData["kpis"].(map[string]interface{}); ok {
		for categoryName, categoryFeatures := range kpis {
			if featuresArray, ok := categoryFeatures.([]interface{}); ok && len(featuresArray) > 0 {
				categoryItem := map[string]interface{}{
					categoryName: featuresArray,
				}
				kpisArray = append(kpisArray, categoryItem)
			}
		}
	}
	transformedData["kpis"] = kpisArray

	log.Printf("[GetOperatorFeatures] Serving key=%s user=%s", fileName, user.ADID)
	c.JSON(http.StatusOK, transformedData)
}