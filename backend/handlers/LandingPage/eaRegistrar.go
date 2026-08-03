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

// eaRegistrarCacheTTL is how long a cached EA registrar response is considered fresh.
const eaRegistrarCacheTTL = 10 * time.Minute

// GetEARegistrar handles GET /api/get_ea_registrar.
// Returns EAs grouped by registrar for the resolved RO (optional ?ro=
// override; defaults to the caller's own RO, or global — all ROs — for
// TechCentre/HeadQuarters, see models.ResolveRO).
func GetEARegistrar(c *gin.Context) {

	// ── 1. Auth guard ──────────────────────────────────────────────────────────
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)
	ro := models.ResolveRO(strings.TrimSpace(c.Query("ro")), user)

	// ── 2. Cache lookup ────────────────────────────────────────────────────────
	cacheKey := cache.GenerateKey("ea_registrar", ro)
	var cached struct {
		Data  map[string][]string `json:"data"`
		Total int                 `json:"total"`
	}
	if hit, err := landingCache.Get("ea_registrar", cacheKey, eaRegistrarCacheTTL, &cached); err != nil {
		log.Printf("[GetEARegistrar] Cache read error for ro=%s: %v", ro, err)
	} else if hit {
		log.Printf("[GetEARegistrar] Cache hit for ro=%s", ro)
		c.JSON(http.StatusOK, gin.H{
			"data":            cached.Data,
			"total":           cached.Total,
			"regional_office": ro,
		})
		return
	}

	// ── 3. DB connection ───────────────────────────────────────────────────────
	database, err := db.GetDB()
	if err != nil {
		log.Printf("[GetEARegistrar] DB connection error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Database connection unavailable",
			"details": err.Error(),
		})
		return
	}

	// ── 4. Query distinct reg/ea pairs for the resolved RO ────────────────────
	query := "SELECT DISTINCT reg, ea FROM operator360.opt_master"
	var queryArgs []interface{}
	if ro != "" {
		query += " WHERE ro = ?"
		queryArgs = append(queryArgs, ro)
	}
	query += " ORDER BY reg, ea"
	rows, err := database.Query(query, queryArgs...)
	if err != nil {
		log.Printf("[GetEARegistrar] Query error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to fetch EA registrar data",
			"details": err.Error(),
		})
		return
	}
	defer rows.Close()

	// ── 5. Scan and group EAs by registrar ─────────────────────────────────────
	data := make(map[string][]string)
	totalPairs := 0
	for rows.Next() {
		var reg, ea string
		if err := rows.Scan(&reg, &ea); err != nil {
			log.Printf("[GetEARegistrar] Row scan error: %v", err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error":   "Failed to process EA registrar record",
				"details": err.Error(),
			})
			return
		}
		data[reg] = append(data[reg], ea)
		totalPairs++
	}
	if err := rows.Err(); err != nil {
		log.Printf("[GetEARegistrar] Row iteration error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Error while reading EA registrar records",
			"details": err.Error(),
		})
		return
	}

	// ── 6. Cache write ─────────────────────────────────────────────────────────
	cachedData := struct {
		Data  map[string][]string `json:"data"`
		Total int                 `json:"total"`
	}{
		Data:  data,
		Total: totalPairs,
	}
	if err := landingCache.Set("ea_registrar", cacheKey, cachedData); err != nil {
		log.Printf("[GetEARegistrar] Cache write failed for ro=%s: %v", ro, err)
	}

	// ── 7. Respond ─────────────────────────────────────────────────────────────
	log.Printf("[GetEARegistrar] Returning %d reg/ea pairs across %d registrars for ro=%q",
		totalPairs, len(data), ro)

	c.JSON(http.StatusOK, gin.H{
		"data":            data,
		"total":           totalPairs,
		"regional_office": ro,
	})
}
