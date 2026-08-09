package Maps

import (
	"log"
	"net/http"
	"strings"

	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/gin-gonic/gin"
)

// StateWiseCountRow represents a single row in the state-wise count response
type StateWiseCountRow struct {
	State    string `json:"state"`
	Critical int    `json:"c"`
	High     int    `json:"h"`
	Med      int    `json:"m"`
	Low      int    `json:"l"`
	Total    int    `json:"total"`
}

// StateWiseCountResponse is the top-level response for the state-wise count endpoint
type StateWiseCountResponse struct {
	Data          []StateWiseCountRow `json:"data"`
	RequestedBy   string              `json:"requested_by"`
	TotalStates   int                 `json:"total_states"`
	TotalCritical int                 `json:"total_critical"`
	TotalHigh     int                 `json:"total_high"`
	TotalMedium   int                 `json:"total_medium"`
	TotalLow      int                 `json:"total_low"`
	TotalOverall  int                 `json:"total_overall"`
}

// GetStateWiseCount returns the state-wise risk bucket counts from data_platform.opt_master
func GetStateWiseCount(c *gin.Context) {
	// Get user from context (set by auth middleware)
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}

	user, ok := userInterface.(*models.User)
	if !ok {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse user from context"})
		return
	}

	// Unlike operator_search's default-to-caller's-own-RO behavior (right for
	// a worklist), the map's "All Regional Offices" option is meant to mean
	// literally all ROs for every user, not just global (TechCentre/
	// HeadQuarters) users — so this reads the raw param directly instead of
	// going through models.ResolveRO. An explicit RO is still honored the
	// same as any other RO-scoped handler; only the no-selection default
	// differs.
	filterRO := strings.TrimSpace(c.Query("ro"))
	filterRiskBucket := strings.TrimSpace(c.Query("risk_bucket"))
	filterRegCode := strings.TrimSpace(c.Query("reg_code"))
	filterEACode := strings.TrimSpace(c.Query("ea_code"))
	filterStatus := strings.ToLower(strings.TrimSpace(c.Query("status")))

	// Get DB connection
	database, err := db.GetDB()
	if err != nil {
		log.Printf("[GetStateWiseCount] DB connection error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Database connection unavailable",
			"details": err.Error(),
		})
		return
	}

	// Base query for state-wise risk bucket counts
	query := `
		SELECT
			state,
			SUM(CASE WHEN risk_bucket = 'Critical' THEN 1 ELSE 0 END) AS c,
			SUM(CASE WHEN risk_bucket = 'High' THEN 1 ELSE 0 END) AS h,
			SUM(CASE WHEN risk_bucket = 'Medium' THEN 1 ELSE 0 END) AS m,
			SUM(CASE WHEN risk_bucket = 'Low' THEN 1 ELSE 0 END) AS l,
			COUNT(*) AS total
		FROM
			operator360.opt_master
		WHERE
			state IS NOT NULL
			AND state != ''
	`

	// Arguments for the query
	var args []interface{}

	if filterRO != "" {
		query += " AND ro = ?"
		args = append(args, filterRO)
	}
	if filterRiskBucket != "" {
		query += " AND risk_bucket = ?"
		args = append(args, filterRiskBucket)
	}
	if filterRegCode != "" {
		query += " AND reg_code = ?"
		args = append(args, filterRegCode)
	}
	if filterEACode != "" {
		query += " AND ea_code = ?"
		args = append(args, filterEACode)
	}
	if filterStatus == "active" {
		// is_active is numeric — 1 means active, anything else (including
		// NULL) means inactive. Same rule as SearchOperators.
		query += " AND is_active = 1"
	} else if filterStatus == "inactive" {
		query += " AND (is_active IS NULL OR is_active <> 1)"
	}

	query += `
		GROUP BY 
			state
		ORDER BY 
			total DESC
	`

	// Execute the query
	rows, err := database.Query(query, args...)
	if err != nil {
		log.Printf("[GetStateWiseCount] Query error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to fetch state-wise counts",
			"details": err.Error(),
		})
		return
	}
	defer rows.Close()

	// Prepare response data
	var data []StateWiseCountRow
	var totalCritical, totalHigh, totalMedium, totalLow, totalOverall int

	for rows.Next() {
		var row StateWiseCountRow
		if err := rows.Scan(&row.State, &row.Critical, &row.High, &row.Med, &row.Low, &row.Total); err != nil {
			log.Printf("[GetStateWiseCount] Row scan error: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error":   "Failed to process state-wise count record",
				"details": err.Error(),
			})
			return
		}

		data = append(data, row)
		totalCritical += row.Critical
		totalHigh += row.High
		totalMedium += row.Med
		totalLow += row.Low
		totalOverall += row.Total
	}

	// Check for row-iteration errors
	if err := rows.Err(); err != nil {
		log.Printf("[GetStateWiseCount] Row iteration error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Error while reading state-wise count records",
			"details": err.Error(),
		})
		return
	}

	// If no data found, return an empty array instead of null
	if data == nil {
		data = []StateWiseCountRow{}
	}

	// Build the final response
	response := StateWiseCountResponse{
		Data:          data,
		RequestedBy:   user.ADID,
		TotalStates:   len(data),
		TotalCritical: totalCritical,
		TotalHigh:     totalHigh,
		TotalMedium:   totalMedium,
		TotalLow:      totalLow,
		TotalOverall:  totalOverall,
	}

	log.Printf("[GetStateWiseCount] Returning %d states (Total: %d, Critical: %d, High: %d, Med: %d, Low: %d) for user %s (RO: %q risk_bucket: %q reg_code: %q ea_code: %q status: %q)",
		len(data), totalOverall, totalCritical, totalHigh, totalMedium, totalLow, user.ADID, filterRO, filterRiskBucket, filterRegCode, filterEACode, filterStatus)

	// Return the JSON response
	c.JSON(http.StatusOK, response)
}
