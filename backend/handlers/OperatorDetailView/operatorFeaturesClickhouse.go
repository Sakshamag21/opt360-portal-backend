package OperatorDetailView

import (
	"context"
	"log"
	"net/http"
	"time"

	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/gin-gonic/gin"
)

const operatorFeaturesQueryTimeout = 10 * time.Second
const operatorFeaturesTable = "default.operator_features"

// OperatorFeatureRow mirrors one row of operatorFeaturesTable.
type OperatorFeatureRow struct {
	FeatureGroup string
	FeatureID    string
	FeatureName  string
	Description  string
	FeatureValue string
}

func GetOperatorFeaturesFromClickHouse(optID string) ([]OperatorFeatureRow, string, error) {
	start := time.Now()
	defer func() {
		log.Printf("[ClickHouse][OperatorFeatures] Completed in %s", time.Since(start))
	}()

	conn, err := db.GetClickHouseDB()
	if err != nil {
		log.Printf("[ClickHouse][OperatorFeatures] ClickHouse unavailable: %v", err)
		return nil, "", err
	}

	query := `
SELECT
	ro,
	feature_group,
	feature_id,
	feature_name,
	description,
	feature_value
FROM ` + operatorFeaturesTable + `
WHERE opt_id = ?
`

	ctx, cancel := context.WithTimeout(context.Background(), operatorFeaturesQueryTimeout)
	defer cancel()

	log.Printf("[ClickHouse][OperatorFeatures] -> querying %s for opt_id=%s at %s", operatorFeaturesTable, optID, start.Format(time.RFC3339))

	rows, err := conn.Query(ctx, query, optID)
	if err != nil {
		log.Printf("[ClickHouse][OperatorFeatures] Query failed: %v", err)
		return nil, "", err
	}
	defer rows.Close()

	var ro string
	features := make([]OperatorFeatureRow, 0)

	for rows.Next() {
		var row OperatorFeatureRow
		var rowRO string
		if err := rows.Scan(&rowRO, &row.FeatureGroup, &row.FeatureID, &row.FeatureName, &row.Description, &row.FeatureValue); err != nil {
			log.Printf("[ClickHouse][OperatorFeatures] Scan failed: %v", err)
			return nil, "", err
		}
		ro = rowRO
		features = append(features, row)
	}
	if err := rows.Err(); err != nil {
		log.Printf("[ClickHouse][OperatorFeatures] Row iteration failed: %v", err)
		return nil, "", err
	}

	log.Printf("[ClickHouse][OperatorFeatures] <- %d rows for opt_id=%s (took %s)", len(features), optID, time.Since(start))

	return features, ro, nil
}

// GetOperatorFeaturesClickHouse handles GET /api/operator_features, sourcing
// data from ClickHouse instead of the S3 operator_features.json file used by
// GetOperatorFeatures. Request and response shape are kept identical to that
// handler (see operator_features_v1.json for a sample body): {opt_id, kpis},
// where kpis is an array of objects each keyed by one feature_group, holding
// that group's features.
//
// feature_type, remarks, and feature_graph aren't present in ClickHouse, so
// they're returned empty ("" / {} / {}) rather than omitted, to keep each
// feature item's shape identical to the JSON file's.
func GetOperatorFeaturesClickHouse(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}

	user := userInterface.(*models.User)

	optID := c.Query("opt_id")

	if optID == "" {
		c.JSON(http.StatusBadRequest, gin.H{
			"error": "opt_id query parameter is required",
		})
		return
	}

	rows, _, err := GetOperatorFeaturesFromClickHouse(optID)
	if err != nil {
		log.Printf("[GetOperatorFeaturesClickHouse] ClickHouse query failed opt_id=%s user=%s: %v", optID, user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to fetch operator features", "details": err.Error()})
		return
	}

	if len(rows) == 0 {
		log.Printf("[GetOperatorFeaturesClickHouse] No features found opt_id=%s user=%s", optID, user.ADID)
		c.JSON(http.StatusNotFound, gin.H{
			"error":       "Operator features not found",
			"operator_id": optID,
		})
		return
	}

	groupedFeatures := make(map[string][]map[string]interface{})
	var groupOrder []string
	for _, row := range rows {
		if _, seen := groupedFeatures[row.FeatureGroup]; !seen {
			groupOrder = append(groupOrder, row.FeatureGroup)
		}
		groupedFeatures[row.FeatureGroup] = append(groupedFeatures[row.FeatureGroup], map[string]interface{}{
			"feature_id":          row.FeatureID,
			"feature_name":        row.FeatureName,
			"feature_type":        "",
			"feature_description": row.Description,
			"feature_value":       row.FeatureValue,
			"remarks":             map[string]interface{}{},
			"feature_graph":       map[string]interface{}{},
		})
	}

	kpisArray := make([]map[string]interface{}, 0, len(groupOrder))
	for _, groupName := range groupOrder {
		kpisArray = append(kpisArray, map[string]interface{}{
			groupName: groupedFeatures[groupName],
		})
	}

	log.Printf("[GetOperatorFeaturesClickHouse] Serving opt_id=%s user=%s groups=%d rows=%d", optID, user.ADID, len(kpisArray), len(rows))
	c.JSON(http.StatusOK, gin.H{
		"opt_id": optID,
		"kpis":   kpisArray,
	})
}
