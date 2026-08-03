package LandingPage

import (
	"database/sql"
	"log"
	"net/http"
	"time"

	"opt360-portal-backend/cache"
	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/gin-gonic/gin"
)

// roRiskDistCacheTTL is how long a cached RO risk distribution response is considered fresh.
const roRiskDistCacheTTL = 10 * time.Minute

// regionalOffices is the fixed list of ROs whose counts are always returned.
var regionalOffices = []string{
	"Bangalore", "Chandigarh", "Delhi", "Guwahati",
	"Hyderabad", "Lucknow", "Mumbai", "Ranchi",
}

// GetRORiskDist handles GET /api/ro_risk_dist.
// Returns per-risk-bucket counts for every regional office. Buckets are
// whatever db.GetRiskBuckets() has cached from opt_master (Critical/High/
// Medium/Low today, but not hardcoded — a new bucket picked up in the cache
// appears here with no code change).
func GetRORiskDist(c *gin.Context) {

	// ── 1. Auth guard ──────────────────────────────────────────────────────────
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)

	// ── 2. Cache lookup ────────────────────────────────────────────────────────
	// This endpoint returns data for all ROs in one query, so we use a single
	// fixed cache key rather than a per-RO key.
	cacheKey := cache.GenerateKey("ro_risk_dist", "all")
	var cached map[string]map[string]int
	if hit, err := landingCache.Get("ro_risk_dist", cacheKey, roRiskDistCacheTTL, &cached); err != nil {
		log.Printf("[GetRORiskDist] Cache read error: %v", err)
	} else if hit {
		log.Printf("[GetRORiskDist] Cache hit")
		c.JSON(http.StatusOK, models.RORiskDistResponse{
			Data:           cached,
			RegionalOffice: user.RegionalOffice,
			RequestedBy:    user.ADID,
		})
		return
	}

	// ── 3. DB connection ───────────────────────────────────────────────────────
	database, err := db.GetDB()
	if err != nil {
		log.Printf("[GetRORiskDist] DB connection error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Database connection unavailable",
			"details": err.Error(),
		})
		return
	}

	// ── 4. Query all ROs in one pass ───────────────────────────────────────────
	query := `
		SELECT
			ro,
			risk_bucket,
			COUNT(*)
		FROM operator360.opt_master
		WHERE risk_bucket IS NOT NULL
		GROUP BY ro, risk_bucket
		ORDER BY ro
	`

	rows, err := database.Query(query)
	if err != nil {
		log.Printf("[GetRORiskDist] Query error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to fetch RO risk distribution",
			"details": err.Error(),
		})
		return
	}
	defer rows.Close()

	// ── 5. Pre-populate every RO with a zeroed count for every known bucket ────
	knownBuckets := db.GetRiskBuckets()
	data := make(map[string]map[string]int, len(regionalOffices))
	for _, ro := range regionalOffices {
		counts := make(map[string]int, len(knownBuckets))
		for _, b := range knownBuckets {
			counts[b] = 0
		}
		data[ro] = counts
	}

	// ── 6. Scan rows — one row per (ro, risk_bucket) pair ─────────────────────
	for rows.Next() {
		var ro, riskBucket sql.NullString
		var count int
		if err := rows.Scan(&ro, &riskBucket, &count); err != nil {
			log.Printf("[GetRORiskDist] Row scan error: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error":   "Failed to process risk distribution record",
				"details": err.Error(),
			})
			return
		}
		if !ro.Valid || !riskBucket.Valid {
			continue
		}
		counts, ok := data[ro.String]
		if !ok {
			// RO not in the fixed regionalOffices list — track it anyway
			// rather than silently dropping the count.
			counts = make(map[string]int)
			data[ro.String] = counts
		}
		counts[riskBucket.String] += count
	}

	if err := rows.Err(); err != nil {
		log.Printf("[GetRORiskDist] Row iteration error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Error while reading risk distribution records",
			"details": err.Error(),
		})
		return
	}

	// ── 7. Cache write ─────────────────────────────────────────────────────────
	if err := landingCache.Set("ro_risk_dist", cacheKey, data); err != nil {
		log.Printf("[GetRORiskDist] Cache write failed: %v", err)
	}

	// ── 8. Respond ─────────────────────────────────────────────────────────────
	log.Printf("[GetRORiskDist] Returning risk distribution for %d ROs, requested by %s", len(data), user.ADID)

	c.JSON(http.StatusOK, models.RORiskDistResponse{
		Data:           data,
		RegionalOffice: user.RegionalOffice,
		RequestedBy:    user.ADID,
	})
}
