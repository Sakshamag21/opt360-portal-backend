package LandingPage

import (
	"database/sql"
	"log"
	"net/http"
	"strings"

	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/gin-gonic/gin"
)

// GetEaAndReg handles GET /api/geteaandreg
// Query param: value=ea  → returns distinct ea values for the resolved RO
// Query param: value=reg → returns distinct reg values for the resolved RO
// Query param: ro (optional) → override the default RO (own RO for a normal
// user, global — all ROs — for TechCentre/HeadQuarters; see models.ResolveRO)
func GetEaAndReg(c *gin.Context) {

	// ── 1. Auth guard ──────────────────────────────────────────────────────────
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)
	ro := models.ResolveRO(strings.TrimSpace(c.Query("ro")), user)

	// ── 2. Validate query param ────────────────────────────────────────────────
	value := c.Query("value")
	if value != "ea" && value != "reg" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error":           "query parameter 'value' is required",
			"accepted_values": []string{"ea", "reg"},
		})
		return
	}

	// ── 3. DB connection ───────────────────────────────────────────────────────
	database, err := db.GetDB()
	if err != nil {
		log.Printf("[GetEaAndReg] DB connection error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Database connection unavailable",
			"details": err.Error(),
		})
		return
	}

	// ── 4. Build and execute query ─────────────────────────────────────────────
	// Column name is validated above (only "ea" or "reg"), safe to interpolate.
	query := "SELECT DISTINCT " + value + " FROM operator360.opt_master WHERE " + value + " IS NOT NULL"
	var queryArgs []interface{}
	if ro != "" {
		query += " AND ro = ?"
		queryArgs = append(queryArgs, ro)
	}
	query += " ORDER BY " + value

	rows, err := database.Query(query, queryArgs...)
	if err != nil {
		log.Printf("[GetEaAndReg] Query error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to fetch data",
			"details": err.Error(),
		})
		return
	}
	defer rows.Close()

	// ── 5. Scan rows ───────────────────────────────────────────────────────────
	results := make([]string, 0)
	for rows.Next() {
		var val sql.NullString
		if err := rows.Scan(&val); err != nil {
			log.Printf("[GetEaAndReg] Row scan error: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error":   "Failed to process record",
				"details": err.Error(),
			})
			return
		}
		if val.Valid {
			results = append(results, val.String)
		}
	}
	if err := rows.Err(); err != nil {
		log.Printf("[GetEaAndReg] Row iteration error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Error while reading records",
			"details": err.Error(),
		})
		return
	}

	// ── 6. Respond ─────────────────────────────────────────────────────────────
	log.Printf("[GetEaAndReg] Returning %d distinct %s values for ro=%q", len(results), value, ro)
	c.JSON(http.StatusOK, gin.H{
		"data":            results,
		"count":           len(results),
		"type":            value,
		"regional_office": ro,
	})
}
