package LandingPage

import (
	"database/sql"
	"log"
	"net/http"
	"sort"
	"strings"

	"opt360-portal-backend/cache"
	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/gin-gonic/gin"
)

// Request structure for selected Registrars
type SelectedRegistrarsRequest struct {
	SelectedRegistrars []string `json:"selected_registrars" binding:"required"`
	RO                 string   `json:"ro"`
}

// Registrar distribution structure
type RegistrarDistribution struct {
	HighRisk int `json:"high_risk"`
	MedRisk  int `json:"med_risk"`
	LowRisk  int `json:"low_risk"`
	NoRisk   int `json:"no_risk"`
}

// Audit data structure for registrars
type AuditDataRegistrar struct {
	RegDistribution map[string]RegistrarDistribution `json:"reg_distribution"`
}

// fetchRegDistribution fetches registrar risk-bucket counts from
// operator360.opt_master for a given RO, using the cache when possible. An
// empty ro means "all ROs" (used by TechCentre/HeadQuarters users).
func fetchRegDistribution(ro string) (*AuditDataRegistrar, error) {
	cacheKey := cache.GenerateKey("audit_registrar", ro)
	var cached AuditDataRegistrar
	if hit, err := landingCache.Get("audit_registrar", cacheKey, auditCacheTTL, &cached); err != nil {
		log.Printf("[fetchRegDistribution] Cache read error for ro=%s: %v", ro, err)
	} else if hit {
		log.Printf("[fetchRegDistribution] Cache hit for ro=%s", ro)
		return &cached, nil
	}

	database, err := db.GetDB()
	if err != nil {
		return nil, err
	}

	query := "SELECT reg, risk_bucket, COUNT(*) FROM operator360.opt_master WHERE reg IS NOT NULL AND risk_bucket IS NOT NULL"
	var args []interface{}
	if ro != "" {
		query += " AND ro = ?"
		args = append(args, ro)
	}
	query += " GROUP BY reg, risk_bucket"

	rows, err := database.Query(query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	regDistribution := make(map[string]RegistrarDistribution)
	for rows.Next() {
		var reg, riskBucket sql.NullString
		var count int
		if err := rows.Scan(&reg, &riskBucket, &count); err != nil {
			return nil, err
		}
		if !reg.Valid || !riskBucket.Valid {
			continue
		}
		dist := regDistribution[reg.String]
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
		regDistribution[reg.String] = dist
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	auditData := &AuditDataRegistrar{RegDistribution: regDistribution}

	if err := landingCache.Set("audit_registrar", cacheKey, auditData); err != nil {
		log.Printf("[fetchRegDistribution] Cache write failed for ro=%s: %v", ro, err)
	}

	return auditData, nil
}

func GetSelectedRegistrars(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)

	var req SelectedRegistrarsRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		log.Printf("[GetSelectedRegistrars] Invalid request body user=%s: %v", user.ADID, err)
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body", "details": err.Error()})
		return
	}
	if len(req.SelectedRegistrars) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "selected_registrars array cannot be empty"})
		return
	}
	ro := models.ResolveRO(strings.TrimSpace(req.RO), user)

	auditData, err := fetchRegDistribution(ro)
	if err != nil {
		log.Printf("[GetSelectedRegistrars] Failed to fetch registrar distribution for ro=%s user=%s: %v", ro, user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to fetch registrar distribution", "regional_office": ro,
			"details": err.Error(),
		})
		return
	}

	filteredDistribution := make(map[string]RegistrarDistribution)
	for _, registrarName := range req.SelectedRegistrars {
		if distribution, ok := auditData.RegDistribution[registrarName]; ok {
			filteredDistribution[registrarName] = distribution
		}
	}

	log.Printf("[GetSelectedRegistrars] Returning %d registrars for user=%s", len(filteredDistribution), user.ADID)
	c.JSON(http.StatusOK, gin.H{"reg_distribution": filteredDistribution})
}

func GetAllRegistrars(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)
	ro := models.ResolveRO(strings.TrimSpace(c.Query("ro")), user)

	auditData, err := fetchRegDistribution(ro)
	if err != nil {
		log.Printf("[GetAllRegistrars] Failed to fetch registrar distribution for ro=%s user=%s: %v", ro, user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to fetch registrar distribution", "regional_office": ro,
			"details": err.Error(),
		})
		return
	}

	registrarNames := make([]string, 0, len(auditData.RegDistribution))
	for registrarName := range auditData.RegDistribution {
		registrarNames = append(registrarNames, registrarName)
	}
	sort.Strings(registrarNames)

	log.Printf("[GetAllRegistrars] Returning %d registrars for user=%s", len(registrarNames), user.ADID)
	c.JSON(http.StatusOK, gin.H{"registrars": registrarNames, "count": len(registrarNames)})
}
