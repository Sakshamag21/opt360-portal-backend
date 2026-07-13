package LandingPage

import (
	"database/sql"
	"log"
	"net/http"
	"sort"

	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/gin-gonic/gin"
)

// GetTop10EAsV1 handles GET /api/top10eav1.
// Returns the top 10 EAs by total operator count across all risk buckets,
// for the logged-in user's regional office. Bucket names are whatever
// db.GetRiskBuckets() has cached from opt_master — not a fixed High/Medium/
// Low list — so a bucket like "Critical" is included automatically.
func GetTop10EAsV1(c *gin.Context) {

	// ── 1. Auth guard ──────────────────────────────────────────────────────────
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)

	// ── 2. DB connection ───────────────────────────────────────────────────────
	database, err := db.GetDB()
	if err != nil {
		log.Printf("[GetTop10EAsV1] DB connection error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Database connection unavailable",
			"details": err.Error(),
		})
		return
	}

	// ── 3. Query raw (ea, risk_bucket) counts for the user's RO ───────────────
	query := `
		SELECT ea, risk_bucket, COUNT(*)
		FROM operator360.opt_master
		WHERE ro = ? AND ea IS NOT NULL AND risk_bucket IS NOT NULL
		GROUP BY ea, risk_bucket
	`

	rows, err := database.Query(query, user.RegionalOffice)
	if err != nil {
		log.Printf("[GetTop10EAsV1] Query error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to fetch top 10 EA data",
			"details": err.Error(),
		})
		return
	}
	defer rows.Close()

	// ── 4. Aggregate ea -> bucket -> count, and ea -> total ────────────────────
	eaMap := make(map[string]map[string]int)
	totals := make(map[string]int)
	for rows.Next() {
		var ea, riskBucket sql.NullString
		var count int
		if err := rows.Scan(&ea, &riskBucket, &count); err != nil {
			log.Printf("[GetTop10EAsV1] Row scan error: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error":   "Failed to process EA record",
				"details": err.Error(),
			})
			return
		}
		if !ea.Valid || !riskBucket.Valid {
			continue
		}
		if eaMap[ea.String] == nil {
			eaMap[ea.String] = make(map[string]int)
		}
		eaMap[ea.String][riskBucket.String] += count
		totals[ea.String] += count
	}
	if err := rows.Err(); err != nil {
		log.Printf("[GetTop10EAsV1] Row iteration error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Error while reading EA records",
			"details": err.Error(),
		})
		return
	}

	// ── 5. Top 10 by total descending ──────────────────────────────────────────
	eaNames := make([]string, 0, len(eaMap))
	for ea := range eaMap {
		eaNames = append(eaNames, ea)
	}
	sort.Slice(eaNames, func(i, j int) bool { return totals[eaNames[i]] > totals[eaNames[j]] })
	if len(eaNames) > 10 {
		eaNames = eaNames[:10]
	}
	top10 := make(map[string]map[string]int, len(eaNames))
	for _, ea := range eaNames {
		top10[ea] = eaMap[ea]
	}

	// ── 6. Respond ─────────────────────────────────────────────────────────────
	log.Printf("[GetTop10EAsV1] Returning top %d EAs for ro=%s", len(top10), user.RegionalOffice)
	c.JSON(http.StatusOK, gin.H{
		"data": gin.H{
			"ea": top10,
		},
		"regional_office": user.RegionalOffice,
	})
}
