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

// GetTop10regV1 handles GET /api/top10regv1.
// Returns the top 10 registrars by total operator count across all risk
// buckets, for the logged-in user's regional office. Bucket names are
// whatever db.GetRiskBuckets() has cached from opt_master — not a fixed
// High/Medium/Low list — so a bucket like "Critical" is included
// automatically.
func GetTop10regV1(c *gin.Context) {

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
		log.Printf("[GetTop10regV1] DB connection error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Database connection unavailable",
			"details": err.Error(),
		})
		return
	}

	// ── 3. Query raw (reg, risk_bucket) counts for the user's RO ──────────────
	query := `
		SELECT reg, risk_bucket, COUNT(*)
		FROM operator360.opt_master
		WHERE ro = ? AND reg IS NOT NULL AND risk_bucket IS NOT NULL
		GROUP BY reg, risk_bucket
	`

	rows, err := database.Query(query, user.RegionalOffice)
	if err != nil {
		log.Printf("[GetTop10regV1] Query error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to fetch top 10 registrar data",
			"details": err.Error(),
		})
		return
	}
	defer rows.Close()

	// ── 4. Aggregate reg -> bucket -> count, and reg -> total ──────────────────
	regMap := make(map[string]map[string]int)
	totals := make(map[string]int)
	for rows.Next() {
		var reg, riskBucket sql.NullString
		var count int
		if err := rows.Scan(&reg, &riskBucket, &count); err != nil {
			log.Printf("[GetTop10regV1] Row scan error: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error":   "Failed to process registrar record",
				"details": err.Error(),
			})
			return
		}
		if !reg.Valid || !riskBucket.Valid {
			continue
		}
		if regMap[reg.String] == nil {
			regMap[reg.String] = make(map[string]int)
		}
		regMap[reg.String][riskBucket.String] += count
		totals[reg.String] += count
	}
	if err := rows.Err(); err != nil {
		log.Printf("[GetTop10regV1] Row iteration error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Error while reading registrar records",
			"details": err.Error(),
		})
		return
	}

	// ── 5. Top 10 by total descending ──────────────────────────────────────────
	regNames := make([]string, 0, len(regMap))
	for reg := range regMap {
		regNames = append(regNames, reg)
	}
	sort.Slice(regNames, func(i, j int) bool { return totals[regNames[i]] > totals[regNames[j]] })
	if len(regNames) > 10 {
		regNames = regNames[:10]
	}
	top10 := make(map[string]map[string]int, len(regNames))
	for _, reg := range regNames {
		top10[reg] = regMap[reg]
	}

	// ── 6. Respond ─────────────────────────────────────────────────────────────
	log.Printf("[GetTop10regV1] Returning top %d registrars for ro=%s", len(top10), user.RegionalOffice)
	c.JSON(http.StatusOK, gin.H{
		"data": gin.H{
			"registrars": top10,
		},
		"regional_office": user.RegionalOffice,
	})
}
