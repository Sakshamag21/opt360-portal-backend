package OperatorDetailView

import (
	"database/sql"
	"log"
	"net/http"

	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/gin-gonic/gin"
)

// OperatorDetailsData is the opt_master-sourced payload for GET /api/operator_details.
// Previously this endpoint fetched a static opt_details.json blob from S3, including
// pkt_per_day and 5 per-category anomaly scores that have no opt_master column
// equivalent — those fields are gone now, not renamed. KPI (operator_features) and
// risk breakdown (operator_risk_details) are unaffected and remain S3-backed.
type OperatorDetailsData struct {
	ID                string   `json:"id"`
	UID               string   `json:"uid"`
	Name              string   `json:"name"`
	Phone             string   `json:"phone"`
	Email             string   `json:"email"`
	RiskScore         *float64 `json:"risk_score"`
	RiskBucket        *string  `json:"risk_bucket"`
	Reg               *string  `json:"reg"`
	RegCode           *string  `json:"reg_code"`
	EA                *string  `json:"ea"`
	EACode            *string  `json:"ea_code"`
	RO                *string  `json:"ro"`
	District          *string  `json:"district"`
	State             *string  `json:"state"`
	LastSyncTimestamp *string  `json:"last_sync_timestamp"`
	Status            string   `json:"status"`
	MachineCode       *string  `json:"machine_code"`
}

// GetOperatorDetails handles GET /api/operator_details.
// Sourced entirely from operator360.opt_master — no S3 fetch.
func GetOperatorDetails(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)

	optID := c.Query("opt_id")
	if optID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "opt_id query parameter is required"})
		return
	}

	database, err := db.GetDB()
	if err != nil {
		log.Printf("[GetOperatorDetails] DB connection error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Database connection unavailable",
			"details": err.Error(),
		})
		return
	}

	query := `
		SELECT id, uid, name, phone, email, risk_score, risk_bucket,
		       reg, reg_code, ea, ea_code, ro, district, state,
		       last_sync_timestamp, is_active, machine_code
		FROM operator360.opt_master
		WHERE id = ?`

	var (
		d                 OperatorDetailsData
		riskScore         sql.NullFloat64
		riskBucket        sql.NullString
		reg, regCode      sql.NullString
		ea, eaCode        sql.NullString
		ro                sql.NullString
		district, state   sql.NullString
		lastSyncTimestamp sql.NullTime
		isActive          sql.NullInt64
		machineCode       sql.NullString
	)

	row := database.QueryRow(query, optID)
	if err := row.Scan(
		&d.ID, &d.UID, &d.Name, &d.Phone, &d.Email, &riskScore, &riskBucket,
		&reg, &regCode, &ea, &eaCode, &ro, &district, &state,
		&lastSyncTimestamp, &isActive, &machineCode,
	); err != nil {
		if err == sql.ErrNoRows {
			log.Printf("[GetOperatorDetails] Not found opt_id=%s user=%s", optID, user.ADID)
			c.JSON(http.StatusNotFound, gin.H{
				"error":       "Operator not found",
				"operator_id": optID,
			})
			return
		}
		log.Printf("[GetOperatorDetails] Query error opt_id=%s user=%s: %v", optID, user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to retrieve operator details",
			"details": err.Error(),
		})
		return
	}

	if riskScore.Valid {
		d.RiskScore = &riskScore.Float64
	}
	if riskBucket.Valid {
		d.RiskBucket = &riskBucket.String
	}
	if reg.Valid {
		d.Reg = &reg.String
	}
	if regCode.Valid {
		d.RegCode = &regCode.String
	}
	if ea.Valid {
		d.EA = &ea.String
	}
	if eaCode.Valid {
		d.EACode = &eaCode.String
	}
	if ro.Valid {
		d.RO = &ro.String
	}
	if district.Valid {
		d.District = &district.String
	}
	if state.Valid {
		d.State = &state.String
	}
	if lastSyncTimestamp.Valid {
		formatted := lastSyncTimestamp.Time.Format("2006-01-02T15:04:05Z07:00")
		d.LastSyncTimestamp = &formatted
	}
	if machineCode.Valid {
		d.MachineCode = &machineCode.String
	}

	// opt_master.is_active is a numeric column where 1 means active and every
	// other value (including NULL) means inactive — same rule as operatorSearch.go.
	d.Status = "inactive"
	if isActive.Valid && isActive.Int64 == 1 {
		d.Status = "active"
	}

	log.Printf("[GetOperatorDetails] Serving opt_id=%s user=%s", optID, user.ADID)
	c.JSON(http.StatusOK, gin.H{
		"regional_office": user.RegionalOffice,
		"operator_id":     optID,
		"data":            d,
		"requested_by":    user.ADID,
	})
}
