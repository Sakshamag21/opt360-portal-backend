package OperatorDetailView

import (
	"database/sql"
	"encoding/json"
	"errors"
	"io"
	"log"
	"net/http"
	"regexp"
	"strings"
	"time"

	"opt360-portal-backend/config"
	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/s3"
	"github.com/gin-gonic/gin"
)

var optIDRe = regexp.MustCompile(`^[A-Za-z0-9_]+$`)

// --- Response Structs for ClickHouse ---

type anomalyDistribution struct {
	HighRisk   int `json:"high_risk"`
	MediumRisk int `json:"medium_risk"`
	LowRisk    int `json:"low_risk"`
	NoRisk     int `json:"no_risk"`
}

type anomalyMetric struct {
	AnomalyCode         string              `json:"anomaly_code"`
	AnomalyName         string              `json:"anomaly_name"`
	AnomalyScore        float64             `json:"anomaly_score"`
	AnomalyDistribution anomalyDistribution `json:"anomaly_distribution"`
}

type categoryScore struct {
	CategoryCode    string          `json:"category_code"`
	CategoryName    string          `json:"category_name"`
	CategoryScore   float64         `json:"category_score"`
	CategoryMetrics []anomalyMetric `json:"category_metrics"`
}

type riskMetrics struct {
	OptRiskScore         float64         `json:"opt_risk_score"`
	AnomalyCategoryScore []categoryScore `json:"anomaly_category_score"`
}

type riskDetailResponse struct {
	OptID       string      `json:"opt_id"`
	OptRo       string      `json:"opt_ro"`
	UpdatedAt   time.Time   `json:"updated_at"`
	RiskMetrics riskMetrics `json:"risk_metrics"`
	RequestedBy string      `json:"requested_by"`
	Source      string      `json:"source"` // "clickhouse" or "s3"
}

// getEmptyMetrics scaffolds the expected sub-metrics with zeroed values
func getEmptyMetrics(categoryCode string) []anomalyMetric {
	dist := anomalyDistribution{}
	switch categoryCode {
	case "hardware":
		return []anomalyMetric{
			{AnomalyCode: "hardware_multiple_biodev", AnomalyName: "Multiple Bio Devices", AnomalyScore: 0.0, AnomalyDistribution: dist},
			{AnomalyCode: "hardware_machine_signature_change", AnomalyName: "Machine Signature Change", AnomalyScore: 0.0, AnomalyDistribution: dist},
		}
	case "biometrics":
		return []anomalyMetric{
			{AnomalyCode: "bio_mfc_fraud", AnomalyName: "Biometric Manual Fraud", AnomalyScore: 0.0, AnomalyDistribution: dist},
		}
	case "work":
		return []anomalyMetric{
			{AnomalyCode: "work_multiple_optname", AnomalyName: "Operator Using Multiple Names", AnomalyScore: 0.0, AnomalyDistribution: dist},
			{AnomalyCode: "work_opt_machinesync", AnomalyName: "Operator Not Syncing Machines", AnomalyScore: 0.0, AnomalyDistribution: dist},
		}
	case "suspicious":
		return []anomalyMetric{
			{AnomalyCode: "sustxn_res_namechange", AnomalyName: "Operator Changing User Names", AnomalyScore: 0.0, AnomalyDistribution: dist},
			{AnomalyCode: "sustxn_oddhour_pkts", AnomalyName: "Operator Making Packet out of Working Hour", AnomalyScore: 0.0, AnomalyDistribution: dist},
			{AnomalyCode: "sustxn_outstate_pkts", AnomalyName: "Operator Making Out of State Packet", AnomalyScore: 0.0, AnomalyDistribution: dist},
		}
	case "authentication":
		return []anomalyMetric{
			{AnomalyCode: "auth_failure_ratio", AnomalyName: "Authentication Failure Ratio", AnomalyScore: 0.0, AnomalyDistribution: dist},
			{AnomalyCode: "auth_oddhour_txn", AnomalyName: "Odd Hour Authentication Transaction", AnomalyScore: 0.0, AnomalyDistribution: dist},
		}
	default:
		return []anomalyMetric{}
	}
}

// --- Handler ---

func GetOperatorRiskDetails(c *gin.Context) {
	userIface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}

	user, ok := userIface.(*models.User)
	if !ok {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Invalid user type in context"})
		return
	}

	optID := c.Query("opt_id")
	if optID == "" || !optIDRe.MatchString(optID) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid or missing opt_id"})
		return
	}

	// 1. Attempt to fetch from ClickHouse first
	// Using errors.Is for standard DB no-rows, but logging actual error if it's a connection issue.
	conn, err := db.GetClickHouseDB()
	if err == nil {
		query := `
            SELECT 
                ro_name, opt_id, 
                document_category_score, work_category_score, 
                authentication_category_score, suspicious_category_score, 
                biometrics_category_score, hardware_category_score, 
                updated_at
            FROM risk_analysis
            WHERE opt_id = ?
            ORDER BY updated_at DESC
            LIMIT 1
        `

		var (
			roName              string
			optIDDb             string
			documentScore       float64
			workScore           float64
			authenticationScore float64
			suspiciousScore     float64
			biometricsScore     float64
			hardwareScore       float64
			updatedAt           time.Time
		)

		err = conn.QueryRow(c.Request.Context(), query, optID).Scan(
			&roName, &optIDDb, &documentScore, &workScore, &authenticationScore,
			&suspiciousScore, &biometricsScore, &hardwareScore, &updatedAt,
		)

		if err == nil {
			// Success in ClickHouse! Build and return response.
			metrics := riskMetrics{
				OptRiskScore: 0.0,
				AnomalyCategoryScore: []categoryScore{
					{CategoryCode: "document", CategoryName: "Document", CategoryScore: documentScore, CategoryMetrics: getEmptyMetrics("document")},
					{CategoryCode: "hardware", CategoryName: "Hardware", CategoryScore: hardwareScore, CategoryMetrics: getEmptyMetrics("hardware")},
					{CategoryCode: "biometrics", CategoryName: "Biometrics", CategoryScore: biometricsScore, CategoryMetrics: getEmptyMetrics("biometrics")},
					{CategoryCode: "work", CategoryName: "Work", CategoryScore: workScore, CategoryMetrics: getEmptyMetrics("work")},
					{CategoryCode: "suspicious", CategoryName: "Suspicious", CategoryScore: suspiciousScore, CategoryMetrics: getEmptyMetrics("suspicious")},
					{CategoryCode: "authentication", CategoryName: "Authentication", CategoryScore: authenticationScore, CategoryMetrics: getEmptyMetrics("authentication")},
				},
			}

			response := riskDetailResponse{
				OptID:       optIDDb,
				OptRo:       roName,
				UpdatedAt:   updatedAt,
				RiskMetrics: metrics,
				RequestedBy: user.ADID,
				Source:      "clickhouse",
			}

			log.Printf("[GetOperatorRiskDetails] Served from ClickHouse opt_id=%s user=%s", optID, user.ADID)
			c.JSON(http.StatusOK, response)
			return
		}

		// If it's just "no rows", we silently fall back to S3.
		// If it's another error, we log it and fall back to S3.
		if !errors.Is(err, sql.ErrNoRows) {
			log.Printf("[GetOperatorRiskDetails] ClickHouse query failed, falling back to S3. opt_id=%s: %v", optID, err)
		} else {
			log.Printf("[GetOperatorRiskDetails] Not found in ClickHouse, falling back to S3. opt_id=%s", optID)
		}
	} else {
		log.Printf("[GetOperatorRiskDetails] ClickHouse unavailable, falling back to S3: %v", err)
	}

	// 2. Fallback to S3 File
	dataPath, err := db.GetDataPathByOptID(optID)
	if err != nil {
		log.Printf("[GetOperatorRiskDetails] DataPath lookup failed opt_id=%s user=%s: %v", optID, user.ADID, err)
		c.JSON(http.StatusNotFound, gin.H{"error": "Operator data path not found"})
		return
	}

	s3Cfg := config.GetDefaultS3Config()
	fileName := strings.TrimSuffix(dataPath, "/") + "/risk_details.json"

	s3Client, err := config.NewS3Client(s3Cfg)
	if err != nil {
		log.Printf("[GetOperatorRiskDetails] S3 client error opt_id=%s user=%s: %v", optID, user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create S3 client"})
		return
	}

	result, err := s3Client.GetObject(&s3.GetObjectInput{
		Bucket: aws.String(s3Cfg.BucketName),
		Key:    aws.String(fileName),
	})
	if err != nil {
		log.Printf("[GetOperatorRiskDetails] S3 fetch failed key=%s user=%s: %v", fileName, user.ADID, err)
		c.JSON(http.StatusNotFound, gin.H{"error": "Operator risk details file not found"})
		return
	}
	defer result.Body.Close()

	body, err := io.ReadAll(io.LimitReader(result.Body, 10<<20)) // 10MB limit
	if err != nil {
		log.Printf("[GetOperatorRiskDetails] Read body failed key=%s: %v", fileName, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read S3 data"})
		return
	}

	// Unmarshal S3 JSON into a map so we can inject our custom fields
	var s3Data map[string]interface{}
	if err := json.Unmarshal(body, &s3Data); err != nil {
		log.Printf("[GetOperatorRiskDetails] JSON parse failed key=%s: %v", fileName, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse JSON data"})
		return
	}

	// Inject source and file_location into the JSON response
	s3Data["source"] = "s3"
	s3Data["file_location"] = fileName
	s3Data["requested_by"] = user.ADID

	log.Printf("[GetOperatorRiskDetails] Served from S3 key=%s user=%s", fileName, user.ADID)
	c.JSON(http.StatusOK, s3Data)
}
