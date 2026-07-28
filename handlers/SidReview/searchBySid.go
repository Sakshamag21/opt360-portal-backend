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


// PacketResponse defines the exact structure the UI expects
type PacketResponse struct {
    Eid                string        `json:"eid"`
    EnrollmentType     string        `json:"enrollment_type"`
    OptID              string        `json:"opt_id"`
    DateCreated        string        `json:"date_created"`
    StationNo          string        `json:"station_no"`
    StationMachineCode string        `json:"station_machine_code"`
    PktSource          string        `json:"pkt_source"`
    AnomalyType        interface{}   `json:"anomaly_type"`
}

type SIDRequestPayload struct {
    OptID string `json:"opt_id"`
    Date  string `json:"date"`
    Limit int    `json:"limit"`
    Page  int    `json:"page"`
}

type SIDResponse struct {
    Success bool            `json:"success"`
    Message string          `json:"message"`
    Data    SIDResponseData `json:"data"`
}

type SIDResponseData struct {
    SIDs        []SIDDetail `json:"sids"`
    TotalSIDs   int         `json:"total_sids"`
    TotalPages  int         `json:"total_pages"`
    CurrentPage int         `json:"current_page"`
    PageSize    int         `json:"page_size"`
}

type SIDDetail struct {
    SID         string  `json:"sid"`
    OptID       *string `json:"opt_id"`
    PktType     *string `json:"pkt_type"`
    StationID   *string `json:"station_id"`
    MachineCode *string `json:"machine_code"`
    CreatedAt   *string `json:"created_at"`
}



func SearchOperatorPacketsBySID(c *gin.Context) {
    requestStart := time.Now()
    log.Printf("[SearchOperatorPacketsBySID] Request received at %s", requestStart.Format(time.RFC3339))

    // Get user from context
    // userInterface, exists := c.Get("user")
    // if !exists {
    //     c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
    //     return
    // }

    // user := userInterface.(*models.User)

    userInterface, exists := c.Get("user")
    var user *models.User

    if !exists {
        log.Println("[WARN] No user in context. Using hardcoded test user.")
        user = &models.User{
            ADID:           "TEST_USER_123",
            RegionalOffice: "TestRegion",
        }
    } else {
        user = userInterface.(*models.User)
    }

    // Get pagination parameters
    page := 1
    pageSize := 10
    
    // Using strconv is cleaner, but keeping your existing logic to minimize changes
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

    optID := c.Query("opt_id")
    searchSID := c.Query("sid")
    anomalyFilter := c.Query("anomaly_filter")
    enrollmentTypeFilter := c.Query("enrollment_type")
    dateFilter := c.Query("date")

    if optID == "" {
        c.JSON(http.StatusBadRequest, gin.H{"error": "opt_id query parameter is required"})
        return
    }

	useAPI := searchSID == "" && anomalyFilter == "" && enrollmentTypeFilter == "" && dateFilter != ""

	if useAPI {
        log.Printf("[SearchOperatorPacketsBySID] Routing opt_id=%s to SID API (date=%s, page=%d, page_size=%d)", optID, dateFilter, page, pageSize)
        apiCallStart := time.Now()
        apiData, totalRecords, err := fetchSIDsFromAPI(optID, dateFilter, pageSize, page)
        log.Printf("[SearchOperatorPacketsBySID] SID API call for opt_id=%s took %s", optID, time.Since(apiCallStart))

        if err == nil && len(apiData) > 0 {
            log.Printf("[SearchOperatorPacketsBySID] Successfully fetched %d records from API for opt_id=%s (total request time %s)", len(apiData), optID, time.Since(requestStart))

            totalPages := (totalRecords + pageSize - 1) / pageSize
            c.JSON(http.StatusOK, gin.H{
                "regional_office":        user.RegionalOffice,
                "operator_id":            optID,
                "data_source":            "api", // Frontend knows it came from API
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
                "count":        len(apiData),
                "data":         apiData,
                "requested_by": user.ADID,
            })
            return // Exit early since API succeeded
        }

        if err != nil {
            log.Printf("[SearchOperatorPacketsBySID] API call failed for opt_id=%s: %v. Falling back to Parquet...", optID, err)
        }
    }


    dataPath, err := db.GetDataPathByOptID(optID)
	// dataPath:= "opt360Store/Lucknow/UttarPradesh/Gorakhpur/UPEDU_GKP_NS860961"
	// fmt.Sprintf(dataPath)
    if err != nil {
        log.Printf("[SearchOperatorPacketsBySID] DataPath lookup failed opt_id=%s user=%s: %v", optID, user.ADID, err)
        c.JSON(http.StatusNotFound, gin.H{"error": "Operator data path not found", "details": err.Error()})
        return
    }

    s3Cfg := config.GetDefaultS3Config()
    s3Client, err := config.NewS3Client(s3Cfg)
    if err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create S3 client", "details": err.Error()})
        return
    }

    filePath := strings.TrimSuffix(dataPath, "/") + "/sid.parquet"

    s3CallStart := time.Now()
    log.Printf("[SearchOperatorPacketsBySID] -> S3 GetObject bucket=%s key=%s at %s", s3Cfg.BucketName, filePath, s3CallStart.Format(time.RFC3339))

    result, err := s3Client.GetObject(&s3.GetObjectInput{
        Bucket: aws.String(s3Cfg.BucketName),
        Key:    aws.String(filePath),
    })
    if err != nil {
        log.Printf("[SearchOperatorPacketsBySID] <- S3 GetObject bucket=%s key=%s failed: %v (took %s)", s3Cfg.BucketName, filePath, err, time.Since(s3CallStart))
        c.JSON(http.StatusNotFound, gin.H{"error": "Failed to fetch sid.parquet file", "details": err.Error()})
        return
    }
    defer result.Body.Close()
    log.Printf("[SearchOperatorPacketsBySID] <- S3 GetObject bucket=%s key=%s succeeded (took %s)", s3Cfg.BucketName, filePath, time.Since(s3CallStart))

    // Optimization: Stream directly to file instead of loading all into RAM
    tempFile, err := os.CreateTemp("", "sid_*.parquet")
    if err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create temporary file", "details": err.Error()})
        return
    }
    defer os.Remove(tempFile.Name())

    if _, err = io.Copy(tempFile, result.Body); err != nil {
        tempFile.Close()
        c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to write parquet data to temporary file", "details": err.Error()})
        return
    }
    tempFile.Close()

    fr, err := local.NewLocalFileReader(tempFile.Name())
    if err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to open parquet file", "details": err.Error()})
        return
    }
    defer fr.Close()

    pr, err := reader.NewParquetReader(fr, nil, 4)
    if err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create parquet reader", "details": err.Error()})
        return
    }
    defer pr.ReadStop()

    numRows := int(pr.GetNumRows())
    rawRows, err := pr.ReadByNumber(numRows)
    if err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read parquet data", "details": err.Error()})
        return
    }

    // --- INTERNAL MAPPING LOGIC ---
    mappedData := make([]PacketResponse, 0, numRows)

    for _, rawRow := range rawRows {
        jsonBytes, err := json.Marshal(rawRow)
        if err != nil {
            continue
        }

        var rowMap map[string]interface{}
        if err := json.Unmarshal(jsonBytes, &rowMap); err != nil {
            continue
        }

        if len(rowMap) == 0 {
            continue
        }

        // Map to our strict struct
        var pkt PacketResponse
        for key, val := range rowMap {
            lowerKey := strings.ToLower(key)
            switch lowerKey {
            case "eid":
                pkt.Eid = fmt.Sprintf("%v", val)
            case "enrolnment_type": // keeping the typo as it exists in your parquet
                pkt.EnrollmentType = fmt.Sprintf("%v", val)
            case "opt_id":
                pkt.OptID = fmt.Sprintf("%v", val)
            case "station_no":
                pkt.StationNo = fmt.Sprintf("%v", val)
            case "station_machine_code":
                pkt.StationMachineCode = fmt.Sprintf("%v", val)
            case "pkt_source":
                pkt.PktSource = fmt.Sprintf("%v", val)
            case "anomaly_type":
                pkt.AnomalyType = val
            case "date_created":
                // Re-using your timestamp logic specifically for this field
                if timestamp, ok := getTimestamp(val); ok {
                    if timestamp > 1e15 {
                        timestamp = timestamp / 1e9
                    } else if timestamp > 1e12 {
                        timestamp = timestamp / 1000.0
                    }
                    if timestamp >= 946684800 && timestamp <= 4102444800 {
                        t := time.Unix(int64(timestamp), 0)
                        pkt.DateCreated = t.Format("2006-01-02 15:04:05")
                    }
                } else if strVal, isStr := val.(string); isStr {
                    // If it's already a string, just normalize underscores to dashes
                    pkt.DateCreated = strings.ReplaceAll(strVal, "_", "-")
                }
            }
        }
        mappedData = append(mappedData, pkt)
    }

    // --- FILTERING LOGIC (Now much cleaner using the struct) ---
    filteredData := make([]PacketResponse, 0)
    for _, pkt := range mappedData {
        
        // Filter by SID
        if searchSID != "" && !strings.Contains(strings.ToLower(pkt.Eid), strings.ToLower(searchSID)) {
            continue
        }

        // Filter by anomaly status
        if anomalyFilter != "" {
            isAnomalous := false
            switch v := pkt.AnomalyType.(type) {
            case []interface{}:
                isAnomalous = len(v) > 0
            case []string:
                isAnomalous = len(v) > 0
            case string:
                strVal := strings.TrimSpace(v)
                isAnomalous = strVal != "[]" && strVal != "" && strVal != "null"
            default:
                isAnomalous = pkt.AnomalyType != nil
            }

            if strings.EqualFold(anomalyFilter, "anomalous") && !isAnomalous {
                continue
            }
            if strings.EqualFold(anomalyFilter, "non-anomalous") && isAnomalous {
                continue
            }
        }

        // Filter by enrollment type
        if enrollmentTypeFilter != "" {
            if strings.EqualFold(enrollmentTypeFilter, "update") && !strings.EqualFold(pkt.EnrollmentType, "U") {
                continue
            }
            if strings.EqualFold(enrollmentTypeFilter, "new_enrollment") && !strings.EqualFold(pkt.EnrollmentType, "N") {
                continue
            }
        }

        // Filter by date
        if dateFilter != "" {
            normalizedDateFilter := strings.ReplaceAll(dateFilter, "-", "_")
            normalizedVal := strings.ReplaceAll(pkt.DateCreated, "-", "_")
            if !strings.Contains(normalizedVal, normalizedDateFilter) {
                continue
            }
        }

        filteredData = append(filteredData, pkt)
    }

    // --- PAGINATION LOGIC ---
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
    
    var paginatedData []PacketResponse
    if startIndex < endIndex {
        paginatedData = filteredData[startIndex:endIndex]
    } else {
        paginatedData = []PacketResponse{}
    }

    log.Printf("[SearchOperatorPacketsBySID] Served %d records for opt_id=%s from Parquet (total request time %s)", len(paginatedData), optID, time.Since(requestStart))

    c.JSON(http.StatusOK, gin.H{
        "regional_office":        user.RegionalOffice,
        "operator_id":            optID,
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

// Helper function to extract timestamp from various numeric types
func getTimestamp(val interface{}) (float64, bool) {
    switch v := val.(type) {
    case float64:
        return v, true
    case float32:
        return float64(v), true
    case int64:
        return float64(v), true
    case int:
        return float64(v), true
    case string:
        var ts float64
        _, err := fmt.Sscanf(strings.TrimSpace(v), "%f", &ts)
        return ts, err == nil
    }
    return 0, false
}