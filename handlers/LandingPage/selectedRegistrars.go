package LandingPage

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"sort"

	"opt360-portal-backend/config"
	"opt360-portal-backend/models"
	"opt360-portal-backend/utils"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/s3"
	"github.com/gin-gonic/gin"
)

// Request structure for selected Registrars
type SelectedRegistrarsRequest struct {
	SelectedRegistrars []string `json:"selected_registrars" binding:"required"`
}

// Registrar distribution structure
type RegistrarDistribution struct {
	HighRisk int `json:"high_risk"`
	MedRisk  int `json:"med_risk"`
	LowRisk  int `json:"low_risk"`
	NoRisk   int `json:"no_risk"`
}

// Audit data structure for registrars
type AuditDataRegistrar struct {
	RegDistribution map[string]RegistrarDistribution `json:"reg_distribution"`
}

func GetSelectedRegistrars(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)

	var req SelectedRegistrarsRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		log.Printf("[GetSelectedRegistrars] Invalid request body user=%s: %v", user.ADID, err)
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body", "details": err.Error()})
		return
	}
	if len(req.SelectedRegistrars) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "selected_registrars array cannot be empty"})
		return
	}

	s3Cfg := config.GetDefaultS3Config()
	fileName := "opt360Store/" + utils.ToPascalCase(user.RegionalOffice) + "/audit.json"

	s3Client, err := config.NewS3Client(s3Cfg)
	if err != nil {
		log.Printf("[GetSelectedRegistrars] S3 client error user=%s: %v", user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create S3 client", "details": err.Error()})
		return
	}

	result, err := s3Client.GetObject(&s3.GetObjectInput{
		Bucket: aws.String(s3Cfg.BucketName),
		Key:    aws.String(fileName),
	})
	if err != nil {
		log.Printf("[GetSelectedRegistrars] S3 fetch failed key=%s user=%s: %v", fileName, user.ADID, err)
		c.JSON(http.StatusNotFound, gin.H{
			"error": "Audit file not found", "regional_office": user.RegionalOffice,
			"file_path": fileName, "details": err.Error(),
		})
		return
	}
	defer result.Body.Close()

	body, err := io.ReadAll(result.Body)
	if err != nil {
		log.Printf("[GetSelectedRegistrars] Read body failed key=%s: %v", fileName, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read S3 data", "details": err.Error()})
		return
	}

	var auditData AuditDataRegistrar
	if err = json.Unmarshal(body, &auditData); err != nil {
		log.Printf("[GetSelectedRegistrars] JSON parse failed key=%s: %v", fileName, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse audit data", "details": err.Error()})
		return
	}

	filteredDistribution := make(map[string]RegistrarDistribution)
	for _, registrarName := range req.SelectedRegistrars {
		if distribution, ok := auditData.RegDistribution[registrarName]; ok {
			filteredDistribution[registrarName] = distribution
		}
	}

	log.Printf("[GetSelectedRegistrars] Returning %d registrars for user=%s", len(filteredDistribution), user.ADID)
	c.JSON(http.StatusOK, gin.H{"reg_distribution": filteredDistribution})
}

func GetAllRegistrars(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)

	s3Cfg := config.GetDefaultS3Config()
	fileName := "opt360Store/" + utils.ToPascalCase(user.RegionalOffice) + "/audit.json"

	s3Client, err := config.NewS3Client(s3Cfg)
	if err != nil {
		log.Printf("[GetAllRegistrars] S3 client error user=%s: %v", user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create S3 client", "details": err.Error()})
		return
	}

	result, err := s3Client.GetObject(&s3.GetObjectInput{
		Bucket: aws.String(s3Cfg.BucketName),
		Key:    aws.String(fileName),
	})
	if err != nil {
		log.Printf("[GetAllRegistrars] S3 fetch failed key=%s user=%s: %v", fileName, user.ADID, err)
		c.JSON(http.StatusNotFound, gin.H{
			"error": "Audit file not found", "regional_office": user.RegionalOffice,
			"file_path": fileName, "details": err.Error(),
		})
		return
	}
	defer result.Body.Close()

	body, err := io.ReadAll(result.Body)
	if err != nil {
		log.Printf("[GetAllRegistrars] Read body failed key=%s: %v", fileName, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read S3 data", "details": err.Error()})
		return
	}

	var auditData AuditDataRegistrar
	if err = json.Unmarshal(body, &auditData); err != nil {
		log.Printf("[GetAllRegistrars] JSON parse failed key=%s: %v", fileName, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse audit data", "details": err.Error()})
		return
	}

	registrarNames := make([]string, 0, len(auditData.RegDistribution))
	for registrarName := range auditData.RegDistribution {
		registrarNames = append(registrarNames, registrarName)
	}
	sort.Strings(registrarNames)

	log.Printf("[GetAllRegistrars] Returning %d registrars for user=%s", len(registrarNames), user.ADID)
	c.JSON(http.StatusOK, gin.H{"registrars": registrarNames, "count": len(registrarNames)})
}
