package LandingPage

import (
	"database/sql"
	"log"
	"net/http"
	"sort"
	"strings"
	"time"

	"opt360-portal-backend/cache"
	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/gin-gonic/gin"
)

// auditCacheTTL is how long a cached audit response is considered fresh.
const auditCacheTTL = 10 * time.Minute

// Request structure for selected EAs
type SelectedEAsRequest struct {
	SelectedEAs []string `json:"selected_eas" binding:"required"`
	RO          string   `json:"ro"`
}

// resolveROOrRespond resolves the RO to use for an S3-file-per-RO lookup
// (audit.json/kpi.json-style endpoints, which have no global/aggregate
// file). If the resolved RO is empty (a TechCentre/HeadQuarters user with no
// override), it writes a 400 and returns ok=false so the caller can bail out
// immediately instead of building a bogus opt360Store//... path.
//
// NOTE: Still used by selectedRegistrars.go (S3-backed). The EA handlers in
// this file now query opt_master directly and use models.ResolveRO instead,
// which allows a global (empty-RO) query for TechCentre/HeadQuarters users.
func resolveROOrRespond(c *gin.Context, explicitRO string, user *models.User) (ro string, ok bool) {
	ro = models.ResolveRO(explicitRO, user)
	if ro == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "Select a Regional Office — there is no global/aggregate file for this data.",
		})
		return "", false
	}
	return ro, true
}

// EA distribution structure
type EADistribution struct {
	HighRisk int `json:"high_risk"`
	MedRisk  int `json:"med_risk"`
	LowRisk  int `json:"low_risk"`
	NoRisk   int `json:"no_risk"`
}

// AuditData structure
type AuditData struct {
	EADistribution map[string]EADistribution `json:"ea_distribution"`
}

// fetchEADistribution fetches EA risk-bucket counts from operator360.opt_master
// for a given RO, using the cache when possible. An empty ro means "all ROs"
// (used by TechCentre/HeadQuarters users).
func fetchEADistribution(ro string) (*AuditData, error) {
	cacheKey := cache.GenerateKey("audit", ro)
	var cached AuditData
	if hit, err := landingCache.Get("audit", cacheKey, auditCacheTTL, &cached); err != nil {
		log.Printf("[fetchEADistribution] Cache read error for ro=%s: %v", ro, err)
	} else if hit {
		log.Printf("[fetchEADistribution] Cache hit for ro=%s", ro)
		return &cached, nil
	}

	database, err := db.GetDB()
	if err != nil {
		return nil, err
	}

	query := "SELECT ea, risk_bucket, COUNT(*) FROM operator360.opt_master WHERE ea IS NOT NULL AND risk_bucket IS NOT NULL"
	var args []interface{}
	if ro != "" {
		query += " AND ro = ?"
		args = append(args, ro)
	}
	query += " GROUP BY ea, risk_bucket"

	rows, err := database.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	eaDistribution := make(map[string]EADistribution)
	for rows.Next() {
		var ea, riskBucket sql.NullString
		var count int
		if err := rows.Scan(&ea, &riskBucket, &count); err != nil {
			return nil, err
		}
		if !ea.Valid || !riskBucket.Valid {
			continue
		}
		dist := eaDistribution[ea.String]
		switch strings.ToLower(riskBucket.String) {
		case "high":
			dist.HighRisk = count
		case "medium":
			dist.MedRisk = count
		case "low":
			dist.LowRisk = count
		case "no":
			dist.NoRisk = count
		}
		eaDistribution[ea.String] = dist
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	auditData := &AuditData{EADistribution: eaDistribution}

	if err := landingCache.Set("audit", cacheKey, auditData); err != nil {
		log.Printf("[fetchEADistribution] Cache write failed for ro=%s: %v", ro, err)
	}

	return auditData, nil
}

func GetSelectedEAs(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)

	var req SelectedEAsRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		log.Printf("[GetSelectedEAs] Invalid request body user=%s: %v", user.ADID, err)
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body", "details": err.Error()})
		return
	}
	if len(req.SelectedEAs) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "selected_eas array cannot be empty"})
		return
	}
	ro := models.ResolveRO(strings.TrimSpace(req.RO), user)

	auditData, err := fetchEADistribution(ro)
	if err != nil {
		log.Printf("[GetSelectedEAs] Failed to fetch EA distribution for ro=%s user=%s: %v", ro, user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to fetch EA distribution", "regional_office": ro,
			"details": err.Error(),
		})
		return
	}

	filteredDistribution := make(map[string]EADistribution)
	for _, eaName := range req.SelectedEAs {
		if distribution, ok := auditData.EADistribution[eaName]; ok {
			filteredDistribution[eaName] = distribution
		}
	}

	log.Printf("[GetSelectedEAs] Returning %d EAs for user=%s", len(filteredDistribution), user.ADID)
	c.JSON(http.StatusOK, gin.H{"ea_distribution": filteredDistribution})
}

func GetAllEAs(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)
	ro := models.ResolveRO(strings.TrimSpace(c.Query("ro")), user)

	auditData, err := fetchEADistribution(ro)
	if err != nil {
		log.Printf("[GetAllEAs] Failed to fetch EA distribution for ro=%s user=%s: %v", ro, user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to fetch EA distribution", "regional_office": ro,
			"details": err.Error(),
		})
		return
	}

	eaNames := make([]string, 0, len(auditData.EADistribution))
	for eaName := range auditData.EADistribution {
		eaNames = append(eaNames, eaName)
	}
	sort.Strings(eaNames)

	log.Printf("[GetAllEAs] Returning %d EAs for user=%s", len(eaNames), user.ADID)
	c.JSON(http.StatusOK, gin.H{"eas": eaNames, "count": len(eaNames)})
}
