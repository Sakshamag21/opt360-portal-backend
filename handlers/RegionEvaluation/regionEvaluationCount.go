package RegionEvaluation

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"strings"

	"opt360-portal-backend/cache"
	"opt360-portal-backend/config"
	"opt360-portal-backend/models"
	"opt360-portal-backend/utils"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/s3"
	"github.com/gin-gonic/gin"
)

var regionCache = cache.NewFileCache(cache.CacheConfig{})

func GetRegionEvaluationCount(c *gin.Context) {
	// Get user from context
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}

	user := userInterface.(*models.User)

	// Get required query parameters
	regionalOffice := c.Query("regional_office")
	optState := c.Query("opt_state")
	optDistrict := c.Query("opt_district")

	// Validate required parameter
	if regionalOffice == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "regional_office query parameter is required",
		})
		return
	}

	roForPath := utils.ToPascalCase(regionalOffice)
	var fileName string
	if optState != "" && optDistrict != "" {
		fileName = "opt360Store/" + roForPath + "/" + utils.ToPascalCase(optState) + "/" + utils.ToPascalCase(optDistrict) + "/audit.json"
	} else if optState != "" {
		fileName = "opt360Store/" + roForPath + "/" + utils.ToPascalCase(optState) + "/audit.json"
	} else {
		fileName = "opt360Store/" + roForPath + "/audit.json"
	}

	// ------------------------------------------------------------------
	// ClickHouse — opt_distribution shaped per drill level, matching what
	// GeographicAnalysisTab.jsx expects: state-list (no opt_state) or
	// district-list (opt_state given, no opt_district). A specific district
	// (both given) isn't requested by that UI, so it keeps the old
	// single-row lookup.
	// ------------------------------------------------------------------

	log.Printf(
		"[GetRegionEvaluationCount] Trying ClickHouse first (ro=%s state=%s district=%s)",
		regionalOffice,
		optState,
		optDistrict,
	)

	roUpper := strings.ToUpper(regionalOffice)

	var (
		distribution map[string]interface{}
		found        bool
		err          error
	)

	switch {
	case optState == "":
		distribution, found, err = GetRegionStateDistributionFromClickHouse(roUpper)
	case optDistrict == "":
		distribution, found, err = GetRegionDistrictDistributionFromClickHouse(roUpper, optState)
	default:
		var data map[string]interface{}
		data, found, err = GetRegionEvaluationFromClickHouse(roUpper, optState, optDistrict)
		distribution = data
	}

	if err != nil {

		log.Printf(
			"[GetRegionEvaluationCount] ClickHouse lookup failed: %v. Falling back to S3.",
			err,
		)

	} else if found {

		cacheKey := cache.GenerateKey(regionalOffice, optState, optDistrict)
		if cacheErr := regionCache.Set("region_evaluation", cacheKey, distribution); cacheErr != nil {
			log.Printf("[GetRegionEvaluationCount] Cache write failed: %v", cacheErr)
		}

		responseData := map[string]interface{}{
			"opt_distribution": distribution,
		}
		if optState != "" && optDistrict != "" {
			// Specific-district case still returns the flat single-row shape.
			responseData = distribution
		}

		c.JSON(http.StatusOK, gin.H{
			"regional_office": regionalOffice,
			"opt_state":       optState,
			"opt_district":    optDistrict,
			"file":            "Clickhouse",
			"data":            responseData,
			"requested_by":    user.ADID,
		})

		return

	} else {

		log.Printf(
			"[GetRegionEvaluationCount] No ClickHouse metrics found. Falling back to S3.",
		)
	}

	// ------------------------------------------------------------------
	// Existing S3 fallback
	// ------------------------------------------------------------------

	s3Cfg := config.GetDefaultS3Config()
	s3Client, err := config.NewS3Client(s3Cfg)
	if err != nil {
		log.Printf(
			"[GetRegionEvaluationCount] S3 client error user=%s: %v",
			user.ADID,
			err,
		)

		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to create S3 client",
			"details": err.Error(),
		})

		return
	}

	result, err := s3Client.GetObject(&s3.GetObjectInput{
		Bucket: aws.String(s3Cfg.BucketName),
		Key:    aws.String(fileName),
	})

	if err != nil {

		log.Printf(
			"[GetRegionEvaluationCount] S3 fetch failed key=%s user=%s: %v",
			fileName,
			user.ADID,
			err,
		)

		c.JSON(http.StatusNotFound, gin.H{
			"error":           "Audit file not found",
			"regional_office": regionalOffice,
			"file_path":       fileName,
			"details":         err.Error(),
		})

		return
	}

	defer result.Body.Close()

	body, err := io.ReadAll(result.Body)
	if err != nil {

		log.Printf(
			"[GetRegionEvaluationCount] Read body failed key=%s: %v",
			fileName,
			err,
		)

		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to read S3 data",
			"details": err.Error(),
		})

		return
	}

	var jsonData interface{}

	if err := json.Unmarshal(body, &jsonData); err != nil {

		log.Printf(
			"[GetRegionEvaluationCount] JSON parse failed key=%s: %v",
			fileName,
			err,
		)

		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to parse JSON data",
			"details": err.Error(),
		})

		return
	}

	log.Printf(
		"[GetRegionEvaluationCount] Returning S3 response key=%s user=%s",
		fileName,
		user.ADID,
	)

	c.JSON(http.StatusOK, gin.H{
		"regional_office": regionalOffice,
		"opt_state":       optState,
		"opt_district":    optDistrict,
		"file":            fileName,
		"data":            jsonData,
		"requested_by":    user.ADID,
	})
}
