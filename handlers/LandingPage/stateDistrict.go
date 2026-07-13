package LandingPage

import (
	"log"
	"net/http"

	"opt360-portal-backend/db"

	"github.com/gin-gonic/gin"
)

// GetStateDistrict handles GET /api/get_state_district.
// Returns all distinct states and districts from data_platform.opt_master.
func GetStateDistrict(c *gin.Context) {

	// ── 1. Auth guard ──────────────────────────────────────────────────────────
	_, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}

	// ── 2. DB connection ───────────────────────────────────────────────────────
	database, err := db.GetDB()
	if err != nil {
		log.Printf("[GetStateDistrict] DB connection error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Database connection unavailable",
			"details": err.Error(),
		})
		return
	}

	// ── 3. Fetch distinct states ───────────────────────────────────────────────
	stateRows, err := database.Query("SELECT DISTINCT state FROM operator360.opt_master WHERE state IS NOT NULL ORDER BY state")
	if err != nil {
		log.Printf("[GetStateDistrict] State query error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to fetch states",
			"details": err.Error(),
		})
		return
	}
	defer stateRows.Close()

	states := make([]string, 0)
	for stateRows.Next() {
		var state string
		if err := stateRows.Scan(&state); err != nil {
			log.Printf("[GetStateDistrict] State scan error: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error":   "Failed to process state record",
				"details": err.Error(),
			})
			return
		}
		states = append(states, state)
	}
	if err := stateRows.Err(); err != nil {
		log.Printf("[GetStateDistrict] State iteration error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Error while reading state records",
			"details": err.Error(),
		})
		return
	}

	// ── 4. Fetch distinct districts ────────────────────────────────────────────
	districtRows, err := database.Query("SELECT DISTINCT district FROM operator360.opt_master WHERE district IS NOT NULL ORDER BY district")
	if err != nil {
		log.Printf("[GetStateDistrict] District query error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to fetch districts",
			"details": err.Error(),
		})
		return
	}
	defer districtRows.Close()

	districts := make([]string, 0)
	for districtRows.Next() {
		var district string
		if err := districtRows.Scan(&district); err != nil {
			log.Printf("[GetStateDistrict] District scan error: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error":   "Failed to process district record",
				"details": err.Error(),
			})
			return
		}
		districts = append(districts, district)
	}
	if err := districtRows.Err(); err != nil {
		log.Printf("[GetStateDistrict] District iteration error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Error while reading district records",
			"details": err.Error(),
		})
		return
	}

	// ── 5. Respond ─────────────────────────────────────────────────────────────
	log.Printf("[GetStateDistrict] Returning %d states and %d districts", len(states), len(districts))

	c.JSON(http.StatusOK, gin.H{
		"states":    states,
		"districts": districts,
	})
}
