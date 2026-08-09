package Maps

import (
	"fmt"
	"log"
	"net/http"
	"strconv"
	"strings"

	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/gin-gonic/gin"
)

// ─── Risk bucket mapping ──────────────────────────────────────────────────────

var riskBucketCode = map[string]string{
	"Low":      "l",
	"Medium":   "m",
	"High":     "h",
	"Critical": "c",
	"No":       "n",
}

const (
	defaultOperatorLimit = 1500
	maxOperatorLimit     = 5000
)

// GetOperatorMapData serves operator pins ([lat, lon, risk_code, operator_id]),
// joining operator360.opt_master (risk_bucket, ro, reg_code, ea_code) against
// operator360.operator_sync_location (opt_id, loc POINT SRID 4326) on
// opt_id = id.
//
// Two modes:
//
//   - id given: look up that single operator directly (like operator_search's
//     id filter, this ignores ro/risk_bucket/reg_code/ea_code and any RO
//     scoping — an exact operator ID is global, not RO-restricted) and return
//     it with no bounding box required. Used by the frontend's "locate
//     operator" flow to find coordinates to jump the map to.
//   - id omitted: the normal viewport query — min_lat/max_lat/min_lng/max_lng
//     are required, matched with MBRContains against the loc column's spatial
//     index rather than ST_Contains/ST_Within — MBRContains works off the raw
//     stored coordinate pairs and isn't sensitive to SRID 4326's lat/long
//     axis-order rules, so it can't silently mis-match the way ST_Contains
//     can, while still using the spatial index. ro/risk_bucket/reg_code/ea_code
//     narrow the result the same way they do on /api/operator_search and
//     /api/state_wise_count — except ro, which (unlike operator_search) is
//     read as the raw param with no default-to-caller's-own-RO fallback: an
//     empty ro means literally all ROs here, for every user, not just global
//     (TechCentre/HeadQuarters) ones.
//
// Lat/lon are read back with ST_Latitude/ST_Longitude, which sidesteps the
// same axis-order ambiguity on the way out.
//
// The caller (DynamicRiskMap.jsx) re-queries the viewport mode on every
// pan/zoom with the current map bounds, so only what's on screen is ever
// fetched instead of the full nationwide operator set.
//
// GET /operators?id=
// GET /operators?min_lat=&max_lat=&min_lng=&max_lng=&limit=&ro=&risk_bucket=&reg_code=&ea_code=&status=
// Response:
//
//	{
//	  "operators": [[lat, lon, "risk_code", "operator_id"], ...]
//	}
func GetOperatorMapData(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	if _, ok := userInterface.(*models.User); !ok {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to parse user from context"})
		return
	}

	database, err := db.GetDB()
	if err != nil {
		log.Printf("[GetOperatorMapData] DB connection error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Database connection unavailable",
			"details": err.Error(),
		})
		return
	}

	filterID := strings.TrimSpace(c.Query("id"))

	var query string
	var args []interface{}
	limit := defaultOperatorLimit

	if filterID != "" {
		query = `
			SELECT
				m.id,
				ST_Latitude(l.loc)  AS lat,
				ST_Longitude(l.loc) AS lon,
				m.risk_bucket
			FROM operator360.opt_master m
			JOIN operator360.operator_sync_location l ON l.opt_id = m.id
			WHERE m.risk_bucket IS NOT NULL AND m.id = ?
			LIMIT 1
		`
		args = []interface{}{filterID}
		limit = 1
	} else {
		minLat, err1 := strconv.ParseFloat(c.Query("min_lat"), 64)
		maxLat, err2 := strconv.ParseFloat(c.Query("max_lat"), 64)
		minLng, err3 := strconv.ParseFloat(c.Query("min_lng"), 64)
		maxLng, err4 := strconv.ParseFloat(c.Query("max_lng"), 64)
		if err1 != nil || err2 != nil || err3 != nil || err4 != nil {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "min_lat, max_lat, min_lng and max_lng query params are required and must be numeric (unless id is given)",
			})
			return
		}

		if l, err := strconv.Atoi(c.Query("limit")); err == nil && l > 0 {
			limit = l
		}
		if limit > maxOperatorLimit {
			limit = maxOperatorLimit
		}

		// SRID 4326's defined SRS orders axes as (latitude, longitude), so the
		// envelope ring is written "lat lng" per point, closing back on itself.
		envelopeWKT := fmt.Sprintf(
			"POLYGON((%f %f, %f %f, %f %f, %f %f, %f %f))",
			minLat, minLng,
			minLat, maxLng,
			maxLat, maxLng,
			maxLat, minLng,
			minLat, minLng,
		)

		query = `
			SELECT
				m.id,
				ST_Latitude(l.loc)  AS lat,
				ST_Longitude(l.loc) AS lon,
				m.risk_bucket
			FROM operator360.opt_master m
			JOIN operator360.operator_sync_location l ON l.opt_id = m.id
			WHERE m.risk_bucket IS NOT NULL
				AND MBRContains(ST_GeomFromText(?, 4326), l.loc)
		`
		args = []interface{}{envelopeWKT}

		// Raw param, not models.ResolveRO — the map's "All Regional Offices"
		// option means literally all ROs for every user, not just global
		// users (see the matching comment in GetStateWiseCount).
		filterRO := strings.TrimSpace(c.Query("ro"))
		if filterRO != "" {
			query += " AND m.ro = ?"
			args = append(args, filterRO)
		}
		if filterRiskBucket := strings.TrimSpace(c.Query("risk_bucket")); filterRiskBucket != "" {
			query += " AND m.risk_bucket = ?"
			args = append(args, filterRiskBucket)
		}
		if filterRegCode := strings.TrimSpace(c.Query("reg_code")); filterRegCode != "" {
			query += " AND m.reg_code = ?"
			args = append(args, filterRegCode)
		}
		if filterEACode := strings.TrimSpace(c.Query("ea_code")); filterEACode != "" {
			query += " AND m.ea_code = ?"
			args = append(args, filterEACode)
		}
		filterStatus := strings.ToLower(strings.TrimSpace(c.Query("status")))
		if filterStatus == "active" {
			// is_active is numeric — 1 means active, anything else
			// (including NULL) means inactive. Same rule as SearchOperators.
			query += " AND m.is_active = 1"
		} else if filterStatus == "inactive" {
			query += " AND (m.is_active IS NULL OR m.is_active <> 1)"
		}

		query += " LIMIT ?"
		args = append(args, limit)
	}

	rows, err := database.Query(query, args...)
	if err != nil {
		log.Printf("[GetOperatorMapData] Query error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Failed to fetch operator map data",
			"details": err.Error(),
		})
		return
	}
	defer rows.Close()

	operators := make([][4]interface{}, 0, limit)
	for rows.Next() {
		var id, riskBucket string
		var lat, lon float64
		if err := rows.Scan(&id, &lat, &lon, &riskBucket); err != nil {
			log.Printf("[GetOperatorMapData] Row scan error: %v", err)
			continue
		}

		code, ok := riskBucketCode[riskBucket]
		if !ok {
			continue
		}

		operators = append(operators, [4]interface{}{lat, lon, code, id})
	}
	if err := rows.Err(); err != nil {
		log.Printf("[GetOperatorMapData] Row iteration error: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error":   "Error while reading operator map records",
			"details": err.Error(),
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{"operators": operators})
}
