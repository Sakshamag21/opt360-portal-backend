package LandingPage

import (
	"log"
	"net/http"
	"strings"
	"time"

	"opt360-portal-backend/cache"
	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/gin-gonic/gin"
)

// highestRiskOptCacheTTL is how long a cached highest risk operator response is considered fresh.
const highestRiskOptCacheTTL = 10 * time.Minute

// GetHighestRiskOperator handles GET /api/highest_risk_opt.
// Returns the single operator with the highest risk_score for the resolved
// RO. Optional ?ro= query param overrides the default; for a normal user the
// default is their own RO, for a TechCentre/HeadQuarters user the default is
// global (all ROs) — see models.ResolveRO.
func GetHighestRiskOperator(c *gin.Context) {

	// ── 1. Auth guard ──────────────────────────────────────────────────────────
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)
	ro := models.ResolveRO(strings.TrimSpace(c.Query("ro")), user)

	// ── 2. Cache lookup ────────────────────────────────────────────────────────
	cacheKey := cache.GenerateKey("highest_risk_opt", ro)
	var cached gin.H
	if hit, err := landingCache.Get("highest_risk_opt", cacheKey, highestRiskOptCacheTTL, &cached); err != nil {
		log.Printf("[GetHighestRiskOperator] Cache read error for ro=%s: %v", ro, err)
	} else if hit {
		log.Printf("[GetHighestRiskOperator] Cache hit for ro=%s", ro)
		c.JSON(http.StatusOK, cached)
		return
	}

	// ── 3. DB connection ───────────────────────────────────────────────────────
	database, err := db.GetDB()
	if err != nil {
		log.Printf("[GetHighestRiskOperator] DB connection error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Database connection unavailable",
			"details": err.Error(),
		})
		return
	}

	// ── 4. Query ───────────────────────────────────────────────────────────────
	query := "SELECT id, NAME, risk_score FROM operator360.opt_master where is_active=1 "
	countQuery := "SELECT COUNT(*) FROM operator360.opt_master WHERE risk_bucket = 'Critical' AND is_active = 1"
	var queryArgs, countArgs []interface{}
	if ro != "" {
		query += " AND ro = ?"
		queryArgs = append(queryArgs, ro)
		countQuery += " AND ro = ?"
		countArgs = append(countArgs, ro)
	}
	query += " ORDER BY risk_score DESC LIMIT 1"

	row := database.QueryRow(query, queryArgs...)

	var id, name string
	var riskScore float64

	if err := row.Scan(&id, &name, &riskScore); err != nil {
		log.Printf("[GetHighestRiskOperator] Scan error for ro=%q: %v", ro, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to retrieve highest risk operator",
			"details": err.Error(),
		})
		return
	}

	// ── 5. Urgent Feedback Required count: critical + active operators only ────
	// (was risk_bucket = 'High' with no status filter — narrowed per explicit
	// instruction, see docs/OVERVIEW_RISK_CRITICAL_BUCKET_PLAN.md item 2.)
	var highOptCount int
	if err := database.QueryRow(countQuery, countArgs...).Scan(&highOptCount); err != nil {
		log.Printf("[GetHighestRiskOperator] Count scan error for ro=%q: %v", ro, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to retrieve critical+active operator count",
			"details": err.Error(),
		})
		return
	}

	// ── 6. Cache write ─────────────────────────────────────────────────────────
	responseData := gin.H{
		"regional_office": ro,
		"data": gin.H{
			"id":             id,
			"name":           name,
			"risk_score":     riskScore,
			"high_opt_count": highOptCount,
		},
	}
	if err := landingCache.Set("highest_risk_opt", cacheKey, responseData); err != nil {
		log.Printf("[GetHighestRiskOperator] Cache write failed for ro=%s: %v", ro, err)
	}

	// ── 7. Response ────────────────────────────────────────────────────────────
	c.JSON(http.StatusOK, responseData)
}
