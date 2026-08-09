package LandingPage

import (
	"context"
	"log"
	"net/http"
	"strings"
	"time"

	"opt360-portal-backend/cache"
	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/gin-gonic/gin"
)

// featureAnalysisCacheTTL is how long a cached feature analysis response is considered fresh.
const featureAnalysisCacheTTL = 10 * time.Minute

// operatorFeaturesTable is the same ClickHouse table
// OperatorDetailView.GetOperatorFeaturesFromClickHouse reads from
// (opt_id, ro, feature_group, feature_id, feature_name, description,
// feature_value, last_updated_at). feature_group doubles as this page's
// "category".
const operatorFeaturesTable = "default.operator_features"

const featureAnalysisClickHouseTimeout = 20 * time.Second

// featureStat is one of {max, min, average} for a feature.
type featureStat struct {
	Value      float64 `json:"value"`
	OperatorID *string `json:"operatorId"`
}

// featureAnalysisItem mirrors one entry of the old S3 featureAnalysis.json
// file's shape — kept identical so the frontend (FeatureAnalysisPage.jsx)
// needs no changes.
type featureAnalysisItem struct {
	FeatureID   string      `json:"featureId"`
	FeatureName string      `json:"featureName"`
	Description string      `json:"description"`
	Category    string      `json:"category"`
	Count       uint64      `json:"count"`
	Max         featureStat `json:"max"`
	Min         featureStat `json:"min"`
	Average     featureStat `json:"average"`
}

// GetFeatureAnalysis handles GET /api/featureAnalysis?RO=.
//
// Sourced from ClickHouse (operatorFeaturesTable) instead of the S3
// featureAnalysis.json file this used to read — RO membership isn't on that
// table's own `ro` column here on purpose (per explicit instruction): the
// operator IDs for the requested RO are resolved from
// operator360.opt_master (MySQL) first, then used to scope the ClickHouse
// query, so opt_master stays the single source of truth for RO membership
// app-wide.
//
// A feature can have more than one historical row per operator
// (last_updated_at) — argMax(..., last_updated_at) picks the latest value
// per (opt_id, feature_id) before aggregating across operators, the same
// "latest wins" pattern used for the risk map's lat/lon lookup.
// feature_value's ClickHouse column type isn't guaranteed numeric, so it's
// parsed with toFloat64OrNull rather than assumed — non-numeric values are
// dropped instead of failing the whole query.
//
// Response shape is unchanged from the old handler:
// {regional_office, requested_by, data: [...]}, still cached for
// featureAnalysisCacheTTL per RO.
func GetFeatureAnalysis(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)

	ro := strings.TrimSpace(c.Query("RO"))
	if ro == "" {
		ro = user.RegionalOffice
	}

	// ── Cache lookup ──────────────────────────────────────────────────────────
	cacheKey := cache.GenerateKey("feature_analysis", ro)
	var cached interface{}
	if hit, err := landingCache.Get("feature_analysis", cacheKey, featureAnalysisCacheTTL, &cached); err != nil {
		log.Printf("[GetFeatureAnalysis] Cache read error for ro=%s: %v", ro, err)
	} else if hit {
		log.Printf("[GetFeatureAnalysis] Cache hit for ro=%s", ro)
		c.JSON(http.StatusOK, gin.H{
			"regional_office": ro,
			"requested_by":    user.ADID,
			"data":            cached,
		})
		return
	}

	// ── Resolve operator IDs for this RO from MySQL ───────────────────────────
	mysqlDB, err := db.GetDB()
	if err != nil {
		log.Printf("[GetFeatureAnalysis] MySQL connection error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Database connection unavailable",
			"details": err.Error(),
		})
		return
	}

	idRows, err := mysqlDB.Query("SELECT id FROM operator360.opt_master WHERE ro = ?", ro)
	if err != nil {
		log.Printf("[GetFeatureAnalysis] opt_master query error ro=%s: %v", ro, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to resolve operators for regional office",
			"details": err.Error(),
		})
		return
	}
	var operatorIDs []string
	for idRows.Next() {
		var id string
		if err := idRows.Scan(&id); err != nil {
			idRows.Close()
			log.Printf("[GetFeatureAnalysis] opt_master row scan error ro=%s: %v", ro, err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read operator record", "details": err.Error()})
			return
		}
		operatorIDs = append(operatorIDs, id)
	}
	idRows.Close()
	if err := idRows.Err(); err != nil {
		log.Printf("[GetFeatureAnalysis] opt_master row iteration error ro=%s: %v", ro, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Error while reading operator records", "details": err.Error()})
		return
	}

	if len(operatorIDs) == 0 {
		log.Printf("[GetFeatureAnalysis] No operators found for ro=%s user=%s", ro, user.ADID)
		data := []featureAnalysisItem{}
		if err := landingCache.Set("feature_analysis", cacheKey, data); err != nil {
			log.Printf("[GetFeatureAnalysis] Cache write failed for ro=%s: %v", ro, err)
		}
		c.JSON(http.StatusOK, gin.H{
			"regional_office": ro,
			"requested_by":    user.ADID,
			"data":            data,
		})
		return
	}

	// ── Aggregate features across those operators from ClickHouse ────────────
	chConn, err := db.GetClickHouseDB()
	if err != nil {
		log.Printf("[GetFeatureAnalysis] ClickHouse connection error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "ClickHouse connection unavailable",
			"details": err.Error(),
		})
		return
	}

	query := `
		SELECT
			feature_id,
			any(feature_group) AS feature_group,
			any(feature_name)  AS feature_name,
			any(description)   AS description,
			count()            AS cnt,
			max(latest_value)  AS max_value,
			argMax(opt_id, latest_value) AS max_opt_id,
			min(latest_value)  AS min_value,
			argMin(opt_id, latest_value) AS min_opt_id,
			avg(latest_value)  AS avg_value
		FROM (
			SELECT
				opt_id,
				feature_id,
				argMax(feature_group, last_updated_at) AS feature_group,
				argMax(feature_name, last_updated_at)  AS feature_name,
				argMax(description, last_updated_at)   AS description,
				toFloat64OrNull(argMax(feature_value, last_updated_at)) AS latest_value
			FROM ` + operatorFeaturesTable + `
			WHERE opt_id IN (?)
			GROUP BY opt_id, feature_id
		)
		WHERE latest_value IS NOT NULL
		GROUP BY feature_id
		ORDER BY feature_id
	`

	ctx, cancel := context.WithTimeout(context.Background(), featureAnalysisClickHouseTimeout)
	defer cancel()

	rows, err := chConn.Query(ctx, query, operatorIDs)
	if err != nil {
		log.Printf("[GetFeatureAnalysis] ClickHouse query error ro=%s operators=%d: %v", ro, len(operatorIDs), err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to fetch feature analysis from ClickHouse",
			"details": err.Error(),
		})
		return
	}
	defer rows.Close()

	data := make([]featureAnalysisItem, 0)
	for rows.Next() {
		var item featureAnalysisItem
		var maxOptID, minOptID string
		if err := rows.Scan(
			&item.FeatureID,
			&item.Category,
			&item.FeatureName,
			&item.Description,
			&item.Count,
			&item.Max.Value,
			&maxOptID,
			&item.Min.Value,
			&minOptID,
			&item.Average.Value,
		); err != nil {
			log.Printf("[GetFeatureAnalysis] ClickHouse row scan error ro=%s: %v", ro, err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to process feature analysis record", "details": err.Error()})
			return
		}
		item.Max.OperatorID = &maxOptID
		item.Min.OperatorID = &minOptID
		// average has no single owning operator
		data = append(data, item)
	}
	if err := rows.Err(); err != nil {
		log.Printf("[GetFeatureAnalysis] ClickHouse row iteration error ro=%s: %v", ro, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Error while reading feature analysis records", "details": err.Error()})
		return
	}

	// ── Cache write ────────────────────────────────────────────────────────────
	if err := landingCache.Set("feature_analysis", cacheKey, data); err != nil {
		log.Printf("[GetFeatureAnalysis] Cache write failed for ro=%s: %v", ro, err)
	}

	log.Printf("[GetFeatureAnalysis] Serving ro=%s user=%s operators=%d features=%d", ro, user.ADID, len(operatorIDs), len(data))
	c.JSON(http.StatusOK, gin.H{
		"regional_office": ro,
		"requested_by":    user.ADID,
		"data":            data,
	})
}
