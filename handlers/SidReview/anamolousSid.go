package SidReview

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"strconv"
	"strings"

	"opt360-portal-backend/config"
	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/s3"
	"github.com/gin-gonic/gin"
)

func GetAnamolousSIDs(c *gin.Context) {
	// Get user from context
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}

	user := userInterface.(*models.User)

	// Get pagination parameters
	page := 1
	pageSize := 20
	if pageParam := c.Query("page"); pageParam != "" {
		if p, err := strconv.Atoi(pageParam); err == nil && p > 0 {
			page = p
		} else {
			page = 1
		}
	}
	if pageSizeParam := c.Query("page_size"); pageSizeParam != "" {
		if ps, err := strconv.Atoi(pageSizeParam); err == nil && ps > 0 && ps <= 1000 {
			pageSize = ps
		} else {
			pageSize = 20
		}
	}

	optID := c.Query("opt_id") // e.g., "MH_WMIT_SN_NS046496"

	// Get optional filter parameter
	anomalyCategoryFilter := c.Query("anomaly_category") // e.g., "work", "hardware", "suspicious", "document", "biometrics" (optional)

	if optID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "opt_id query parameter is required",
		})
		return
	}

	// ------------------------------------------------------------------
	// Try ClickHouse first
	// ------------------------------------------------------------------
	log.Printf(
		"[GetAnamolousSIDs] Looking up anomalous packets in ClickHouse (opt_id=%s, page=%d, page_size=%d, category=%q)",
		optID,
		page,
		pageSize,
		anomalyCategoryFilter,
	)

	records, totalRecords, err := GetAnomalousSIDsFromClickHouse(
		optID,
		anomalyCategoryFilter,
		page,
		pageSize,
	)

	if err != nil {
		log.Printf(
			"[GetAnamolousSIDs] ClickHouse lookup failed for opt_id=%s: %v. Falling back to S3.",
			optID,
			err,
		)
	} else if totalRecords > 0 {

		totalPages := (totalRecords + pageSize - 1) / pageSize

		log.Printf(
			"[GetAnamolousSIDs] Returning %d/%d anomalous packets from ClickHouse for opt_id=%s",
			len(records),
			totalRecords,
			optID,
		)

		c.JSON(http.StatusOK, gin.H{
			"regional_office": user.RegionalOffice,
			"operator_id":     optID,

			// Keep response structure unchanged.
			// Frontend can still display this field if needed.
			"file": "clickhouse",

			"anomaly_category_filter": anomalyCategoryFilter,

			"pagination": gin.H{
				"page":          page,
				"page_size":     pageSize,
				"total_records": totalRecords,
				"total_pages":   totalPages,
				"has_next":      page < totalPages,
				"has_previous":  page > 1,
			},

			"count":        len(records),
			"data":         records,
			"requested_by": user.ADID,
		})

		return
	}

	log.Printf(
		"[GetAnamolousSIDs] No ClickHouse data found for opt_id=%s. Falling back to anomaly_sid.json.",
		optID,
	)

	// ------------------------------------------------------------------
	// Existing S3 fallback starts here
	// ------------------------------------------------------------------

	dataPath, err := db.GetDataPathByOptID(optID)

	if err != nil {
		log.Printf("[GetAnamolousSIDs] DataPath lookup failed opt_id=%s user=%s: %v", optID, user.ADID, err)
		c.JSON(http.StatusNotFound, gin.H{
			"error":       "Operator data path not found",
			"operator_id": optID,
			"details":     err.Error(),
		})
		return
	}

	s3Cfg := config.GetDefaultS3Config()
	fileName := strings.TrimSuffix(dataPath, "/") + "/anomaly_sid.json"

	s3Client, err := config.NewS3Client(s3Cfg)
	if err != nil {
		log.Printf("[GetAnamolousSIDs] S3 client error opt_id=%s user=%s: %v", optID, user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create S3 client", "details": err.Error()})
		return
	}

	result, err := s3Client.GetObject(&s3.GetObjectInput{
		Bucket: aws.String(s3Cfg.BucketName),
		Key:    aws.String(fileName),
	})
	if err != nil {
		log.Printf("[GetAnamolousSIDs] S3 fetch failed key=%s user=%s: %v", fileName, user.ADID, err)
		c.JSON(http.StatusNotFound, gin.H{
			"error":           "Anomalous SIDs file not found",
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
		log.Printf("[GetAnamolousSIDs] Read body failed key=%s: %v", fileName, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read S3 data", "details": err.Error()})
		return
	}

	var rawData map[string]interface{}
	if err := json.Unmarshal(body, &rawData); err != nil {
		log.Printf("[GetAnamolousSIDs] JSON parse failed key=%s: %v", fileName, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse JSON data", "details": err.Error()})
		return
	}

	// Flatten the nested structure to extract all SIDs
	allData := make([]map[string]interface{}, 0)
	// Iterate through operator IDs (e.g., "WCD_RJ_UD_NS887326")
	for operatorID, operatorData := range rawData {
		if operatorMap, ok := operatorData.(map[string]interface{}); ok {
			// Iterate through anomaly categories (e.g., "Biometrics")
			for category, categoryData := range operatorMap {
				if categoryMap, ok := categoryData.(map[string]interface{}); ok {
					// Iterate through SIDs (e.g., "0862533020198020251030134051")
					for sid, sidData := range categoryMap {
						if sidMap, ok := sidData.(map[string]interface{}); ok {
							// Create a flattened record with SID as key
							record := map[string]interface{}{
								"sid":              sid,
								"operator_id":      operatorID,
								"anomaly_category": category,
							}
							// Add all SID data fields
							for key, value := range sidMap {
								record[key] = value
							}
							allData = append(allData, record)
						}
					}
				}
			}
		}
	}

	// Apply anomaly_category filter if provided
	filteredData := allData
	if anomalyCategoryFilter != "" {
		filteredData = make([]map[string]interface{}, 0)
		for _, record := range allData {
			if category, ok := record["anomaly_category"].(string); ok {
				// Case-insensitive comparison
				if strings.EqualFold(category, anomalyCategoryFilter) {
					filteredData = append(filteredData, record)
				}
			}
		}
	}

	// Calculate pagination
	totalRecords = len(filteredData)
	totalPages := (totalRecords + pageSize - 1) / pageSize

	if page > totalPages && totalPages > 0 {
		page = totalPages
	}

	startIndex := (page - 1) * pageSize
	endIndex := startIndex + pageSize

	if startIndex >= totalRecords {
		startIndex = 0
		endIndex = 0
	} else if endIndex > totalRecords {
		endIndex = totalRecords
	}
	paginatedData := []map[string]interface{}{}
	if startIndex < endIndex {
		paginatedData = filteredData[startIndex:endIndex]
	}

	log.Printf("[GetAnamolousSIDs] Returning %d/%d anomalous SIDs for opt_id=%s user=%s (page %d)",
		len(paginatedData), totalRecords, optID, user.ADID, page)
	c.JSON(http.StatusOK, gin.H{
		"regional_office":         user.RegionalOffice,
		"operator_id":             optID,
		"file":                    fileName,
		"anomaly_category_filter": anomalyCategoryFilter,
		"pagination": gin.H{
			"page":          page,
			"page_size":     pageSize,
			"total_records": totalRecords,
			"total_pages":   totalPages,
			"has_next":      page < totalPages,
			"has_previous":  page > 1,
		},
		"count":        len(paginatedData),
		"data":         paginatedData,
		"requested_by": user.ADID,
	})
}
