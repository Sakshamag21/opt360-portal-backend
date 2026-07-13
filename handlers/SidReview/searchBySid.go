package SidReview

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"opt360-portal-backend/config"
	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/s3"
	"github.com/gin-gonic/gin"
	"github.com/xitongsys/parquet-go-source/local"
	"github.com/xitongsys/parquet-go/reader"
)


func SearchOperatorPacketsBySID(c *gin.Context) {
	// Get user from context
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}

	user := userInterface.(*models.User)

	// Get pagination parameters
	page := 1
	pageSize := 10
	
	if pageParam := c.Query("page"); pageParam != "" {
		if p, err := fmt.Sscanf(pageParam, "%d", &page); err == nil && p == 1 && page > 0 {
			// page is valid
		} else {
			page = 1
		}
	}
	
	if pageSizeParam := c.Query("page_size"); pageSizeParam != "" {
		if ps, err := fmt.Sscanf(pageSizeParam, "%d", &pageSize); err == nil && ps == 1 && pageSize > 0 && pageSize <= 1000 {
			// pageSize is valid
		} else {
			pageSize = 10
		}
	}

	optID := c.Query("opt_id") // e.g., "GJ_DOP_VDR_NS764416"

	// Get optional filter parameters
	searchSID := c.Query("sid")            // e.g., "123456789012" (optional)
	anomalyFilter := c.Query("anomaly_filter") // "anomalous" or "non-anomalous" (optional)
	enrollmentTypeFilter := c.Query("enrollment_type") // "new_enrollment" or "update" (optional)
	dateFilter := c.Query("date")          // e.g., "2025-12-25" or "2025_12_25" (optional)

	if optID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "opt_id query parameter is required",
		})
		return
	}

	dataPath, err := db.GetDataPathByOptID(optID)
	if err != nil {
		log.Printf("[SearchOperatorPacketsBySID] DataPath lookup failed opt_id=%s user=%s: %v", optID, user.ADID, err)
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
		log.Printf("[SearchOperatorPacketsBySID] S3 client error opt_id=%s user=%s: %v", optID, user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create S3 client", "details": err.Error()})
		return
	}

	filePath := strings.TrimSuffix(dataPath, "/") + "/sid.parquet"

	result, err := s3Client.GetObject(&s3.GetObjectInput{
		Bucket: aws.String(s3Cfg.BucketName),
		Key:    aws.String(filePath),
	})
	if err != nil {
		log.Printf("[SearchOperatorPacketsBySID] S3 fetch failed key=%s user=%s: %v", filePath, user.ADID, err)
		c.JSON(http.StatusNotFound, gin.H{
			"error":           "Failed to fetch sid.parquet file",
			"regional_office": user.RegionalOffice,
			"operator_id":     optID,
			"file_path":       filePath,
			"details":         err.Error(),
		})
		return
	}
	defer result.Body.Close()

	parquetBytes, err := io.ReadAll(result.Body)
	if err != nil {
		log.Printf("[SearchOperatorPacketsBySID] Read body failed key=%s: %v", filePath, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read parquet data from S3", "details": err.Error()})
		return
	}

	tempFile, err := os.CreateTemp("", "sid_*.parquet")
	if err != nil {
		log.Printf("[SearchOperatorPacketsBySID] CreateTemp error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create temporary file", "details": err.Error()})
		return
	}
	defer os.Remove(tempFile.Name())

	if _, err = tempFile.Write(parquetBytes); err != nil {
		tempFile.Close()
		log.Printf("[SearchOperatorPacketsBySID] Write temp error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to write parquet data to temporary file", "details": err.Error()})
		return
	}
	tempFile.Close()

	fr, err := local.NewLocalFileReader(tempFile.Name())
	if err != nil {
		log.Printf("[SearchOperatorPacketsBySID] Open parquet error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to open parquet file", "details": err.Error()})
		return
	}
	defer fr.Close()

	pr, err := reader.NewParquetReader(fr, nil, 4)
	if err != nil {
		log.Printf("[SearchOperatorPacketsBySID] Parquet reader error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create parquet reader", "details": err.Error()})
		return
	}
	defer pr.ReadStop()

	numRows := int(pr.GetNumRows())
	log.Printf("[SearchOperatorPacketsBySID] Loaded %d rows from key=%s user=%s", numRows, filePath, user.ADID)
	strs, err := pr.ReadByNumber(numRows)
	if err != nil {
		log.Printf("[SearchOperatorPacketsBySID] Read parquet data error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read parquet data", "details": err.Error()})
		return
	}

	// Convert parquet data to JSON format
	allData := make([]map[string]interface{}, 0)
	for _, str := range strs {
		// Marshal to JSON and unmarshal back to get map
		jsonBytes, err := json.Marshal(str)
		if err != nil {
			continue
		}

		var rowMap map[string]interface{}
		if err := json.Unmarshal(jsonBytes, &rowMap); err != nil {
			continue
		}

		// Skip empty rows
		if len(rowMap) == 0 {
			continue
		}

		// Convert date fields to normal format (YYYY-MM-DD HH:MM:SS)
		for key, val := range rowMap {
			lowerKey := strings.ToLower(key)
			if strings.Contains(lowerKey, "date") || strings.Contains(lowerKey, "time") {
				var timestamp float64
				
				// Handle different numeric types
				switch v := val.(type) {
				case float64:
					timestamp = v
				case float32:
					timestamp = float64(v)
				case int64:
					timestamp = float64(v)
				case int:
					timestamp = float64(v)
				case string:
					// Try parsing string as number
					valStr := strings.TrimSpace(v)
					// Check if it's a date string format
					if strings.Contains(valStr, "-") || strings.Contains(valStr, "_") {
						// Already in string date format, normalize it
						normalizedDate := strings.ReplaceAll(valStr, "_", "-")
						rowMap[key] = normalizedDate
						continue
					}
					// Try parsing as number
					fmt.Sscanf(valStr, "%f", &timestamp)
				}
				
				// If we have a timestamp value, convert it
				if timestamp > 0 {
					// Detect timestamp precision:
					// Nanoseconds: > 1e15 (typically 19 digits like 1761396321000000000)
					// Microseconds: > 1e12 and < 1e15
					// Milliseconds: > 1e9 and < 1e12
					// Seconds: < 1e9
					
					if timestamp > 1e15 {
						// Nanoseconds - convert to seconds
						timestamp = timestamp / 1e9
					} else if timestamp > 1e12 {
						// Milliseconds - convert to seconds
						timestamp = timestamp / 1000.0
					}
					
					// Validate timestamp is in reasonable range (between 2000 and 2100)
					// Unix timestamp for 2000-01-01: 946684800
					// Unix timestamp for 2100-01-01: 4102444800
					if timestamp >= 946684800 && timestamp <= 4102444800 {
						t := time.Unix(int64(timestamp), 0)
						formattedDate := t.Format("2006-01-02 15:04:05")
						rowMap[key] = formattedDate
					}
				}
			}
		}

		allData = append(allData, rowMap)
	}

	// Apply filters if provided
	filteredData := make([]map[string]interface{}, 0)
	for _, rowMap := range allData {
		// Filter by SID search (check "eid" field)
		if searchSID != "" {
			matchFound := false
			for key, val := range rowMap {
				if strings.EqualFold(key, "eid") {
					valStr := fmt.Sprintf("%v", val)
					if strings.Contains(strings.ToLower(valStr), strings.ToLower(searchSID)) {
						matchFound = true
						break
					}
				}
			}
			if !matchFound {
				continue
			}
		}

		// Filter by anomaly status
		if anomalyFilter != "" {
			isAnomalous := false
			
			// Check Anomaly_type field
			for key, val := range rowMap {
				if strings.EqualFold(key, "anomaly_type") {
					// Check if the value is a non-empty array
					switch v := val.(type) {
					case []interface{}:
						isAnomalous = len(v) > 0
					case []string:
						isAnomalous = len(v) > 0
					case string:
						// Handle string representation of arrays
						v = strings.TrimSpace(v)
						isAnomalous = v != "[]" && v != "" && v != "null"
					default:
						// If it's some other type, check if it's not nil/empty
						isAnomalous = val != nil
					}
					break
				}
			}
			
			// Apply filter based on anomaly status
			if strings.EqualFold(anomalyFilter, "anomalous") && !isAnomalous {
				continue
			}
			if strings.EqualFold(anomalyFilter, "non-anomalous") && isAnomalous {
				continue
			}
		}

		// Filter by enrollment type
		if enrollmentTypeFilter != "" {
			enrollmentType := ""
			
			// Check Enrolnment_type field
			for key, val := range rowMap {
				if strings.EqualFold(key, "enrolnment_type") {
					valStr := fmt.Sprintf("%v", val)
					enrollmentType = strings.TrimSpace(valStr)
					break
				}
			}
			
			// Map the enrollment type: "U" = update, "N" = new_enrollment
			if strings.EqualFold(enrollmentTypeFilter, "update") && !strings.EqualFold(enrollmentType, "U") {
				continue
			}
			if strings.EqualFold(enrollmentTypeFilter, "new_enrollment") && !strings.EqualFold(enrollmentType, "N") {
				continue
			}
		}

		// Filter by date
		if dateFilter != "" {
			matchFound := false
			// Normalize date filter (support both - and _ separators)
			normalizedDateFilter := strings.ReplaceAll(dateFilter, "-", "_")
			
			// Check common date fields: date, Date, packet_date, Date_packet, etc.
			for key, val := range rowMap {
				lowerKey := strings.ToLower(key)
				if strings.Contains(lowerKey, "date") {
					valStr := fmt.Sprintf("%v", val)
					// Normalize value (replace - with _)
					normalizedVal := strings.ReplaceAll(valStr, "-", "_")
					if strings.Contains(normalizedVal, normalizedDateFilter) {
						matchFound = true
						break
					}
				}
			}
			if !matchFound {
				continue
			}
		}

		filteredData = append(filteredData, rowMap)
	}

	// Calculate pagination
	totalRecords := len(filteredData)
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

	log.Printf("[SearchOperatorPacketsBySID] Returning %d/%d rows for opt_id=%s user=%s (page %d)",
		len(paginatedData), totalRecords, optID, user.ADID, page)
	c.JSON(http.StatusOK, gin.H{
		"regional_office":        user.RegionalOffice,
		"operator_id":            optID,
		"file_path":              filePath,
		"search_sid":             searchSID,
		"anomaly_filter":         anomalyFilter,
		"enrollment_type_filter": enrollmentTypeFilter,
		"date_filter":            dateFilter,
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