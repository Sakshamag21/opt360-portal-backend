package Anomaly

import (
	"log"
	"net/http"
	"opt360-portal-backend/db"
	"opt360-portal-backend/models"
	"strings"

	"github.com/gin-gonic/gin"
)

// ReportAnomaly handles POST requests to report an anomaly
func ReportAnomaly(c *gin.Context) {
	// Parse request body
	var reqData models.AnomalyReportRequest
	if err := c.ShouldBindJSON(&reqData); err != nil {
		log.Printf("Invalid JSON in request body: %v", err)
		c.JSON(http.StatusBadRequest, gin.H{
			"error":   "Invalid JSON in request body",
			"details": err.Error(),
		})
		return
	}

	// Validate required fields
	if reqData.EID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "eid is required",
		})
		return
	}

	if reqData.OptID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "opt_id is required",
		})
		return
	}

	// Build MarkAnomaly record
	// opt_state and opt_district will be NULL if not provided in request
	markAnomaly := &models.MarkAnomaly{
		EID:                reqData.EID,
		AnomalyCategory:    reqData.AnomalyCategory,
		DateCreated:        reqData.DateCreated,
		EnrolmentType:      reqData.EnrolmentType,
		OptDistrict:        reqData.OptDistrict,
		OptState:           reqData.OptState,
		OptID:              reqData.OptID,
		PktSource:          reqData.PktSource,
		StationMachineCode: reqData.StationMachineCode,
		StationNo:          reqData.StationNo,
	}

	// Extract anomaly details from first anomaly_type if available
	if len(reqData.AnomalyType) > 0 {
		markAnomaly.AnomalyCode = reqData.AnomalyType[0].AnomalyCode
		markAnomaly.AnomalyName = reqData.AnomalyType[0].AnomalyName
		markAnomaly.ErrorCategory = reqData.AnomalyType[0].Reason.ErrorCategory
	}

	// Join pkt_updt_type array into comma-separated string
	if len(reqData.PktUpdtType) > 0 {
		markAnomaly.PktUpdtType = strings.Join(reqData.PktUpdtType, ", ")
	}

	// Join remarks array into comma-separated string
	if len(reqData.Remarks) > 0 {
		markAnomaly.Remarks = strings.Join(reqData.Remarks, ", ")
	}

	// Insert into database
	if err := db.InsertMarkAnomaly(markAnomaly); err != nil {
		log.Printf("Failed to insert anomaly: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to insert anomaly record",
			"details": err.Error(),
		})
		return
	}

	// Return success response
	c.JSON(http.StatusOK, gin.H{
		"message": "Anomaly reported successfully",
		"eid":     reqData.EID,
	})
}
