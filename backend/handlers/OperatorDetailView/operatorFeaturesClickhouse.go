package OperatorDetailView

import (
	"context"
	"log"
	"time"

	"opt360-portal-backend/db"
)

const operatorFeaturesQueryTimeout = 10 * time.Second

// operatorFeaturesTable is a guess based on this codebase's "operator360.<table>"
// naming convention (see ro_state_metrics, anomalous_packets_v2_rmt, opt_master).
// Confirm the real database/table name and update this constant if it differs.
const operatorFeaturesTable = "default.operator_features"

// OperatorFeatureRow mirrors one row of operatorFeaturesTable.
type OperatorFeatureRow struct {
	FeatureGroup string
	FeatureID    string
	FeatureName  string
	Description  string
	FeatureValue string
}

// GetOperatorFeaturesFromClickHouse fetches every feature row for optID from
// ClickHouse, along with the operator's regional office (ro).
//
// FeatureValue is scanned as a string, assuming the feature_value column is
// ClickHouse type String (needed since sample values mix free text like
// "1.2 hr" with plain numbers). If the column is actually numeric, this Scan
// will fail — switch the field/Scan target to the matching numeric type.
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
