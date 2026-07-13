package RegionEvaluation

import (
	"context"
	"fmt"
	"log"
	"strings"
	"time"

	"opt360-portal-backend/db"
)

const regionEvaluationQueryTimeout = 10 * time.Second

// GetRegionEvaluationFromClickHouse returns:
//
//	data  -> JSON-compatible object (same shape expected by API)
//	found -> true if a row exists
//	err   -> query/connection error
//
// NOTE:
// RO Level  : state_name = "ro_<RegionalOffice>"
// State     : state_name = <StateName>
func GetRegionEvaluationFromClickHouse(
	regionalOffice string,
	optState string,
) (map[string]interface{}, bool, error) {

	start := time.Now()
	defer func() {
		log.Printf(
			"[ClickHouse][RegionEvaluation] Completed in %v",
			time.Since(start),
		)
	}()

	conn, err := db.GetClickHouseDB()
	if err != nil {
		log.Printf("[ClickHouse][RegionEvaluation] ClickHouse unavailable: %v", err)
		return nil, false, err
	}

	//---------------------------------------------------------
	// Determine state filter
	//---------------------------------------------------------

	var stateFilter string

	if strings.TrimSpace(optState) == "" {

		// RO level
		stateFilter = "ro_" + regionalOffice

		log.Printf(
			"[ClickHouse][RegionEvaluation] RO level lookup ro=%s state=%s",
			regionalOffice,
			stateFilter,
		)

	} else {

		// State level
		stateFilter = optState

		log.Printf(
			"[ClickHouse][RegionEvaluation] State level lookup ro=%s state=%s",
			regionalOffice,
			stateFilter,
		)
	}

	query := `
SELECT
	highest_risk_operator,

	critical_risk_count_active,
	high_risk_count_active,
	medium_risk_count_active,
	low_risk_count_active,
	no_risk_count_active,

	critical_risk_count_inactive,
	high_risk_count_inactive,
	medium_risk_count_inactive,
	low_risk_count_inactive,
	no_risk_count_inactive

FROM operator360.ro_state_metrics
WHERE ro_name = ?
AND state_name = ?
LIMIT 1
`

	ctx, cancel := context.WithTimeout(
		context.Background(),
		regionEvaluationQueryTimeout,
	)
	defer cancel()

	var (
		highestRiskOperator string

		criticalActive uint32
		highActive     uint32
		mediumActive   uint32
		lowActive      uint32
		noRiskActive   uint32

		criticalInactive uint32
		highInactive     uint32
		mediumInactive   uint32
		lowInactive      uint32
		noRiskInactive   uint32
	)

	err = conn.QueryRow(
		ctx,
		query,
		regionalOffice,
		stateFilter,
	).Scan(
		&highestRiskOperator,

		&criticalActive,
		&highActive,
		&mediumActive,
		&lowActive,
		&noRiskActive,

		&criticalInactive,
		&highInactive,
		&mediumInactive,
		&lowInactive,
		&noRiskInactive,
	)

	if err != nil {

		// ClickHouse returns an error if no row exists.
		// Treat that as "not found" so the caller can fall back to S3.
		if strings.Contains(strings.ToLower(err.Error()), "no rows") {

			log.Printf(
				"[ClickHouse][RegionEvaluation] No metrics found (ro=%s state=%s)",
				regionalOffice,
				stateFilter,
			)

			return nil, false, nil
		}

		log.Printf(
			"[ClickHouse][RegionEvaluation] Query failed: %v",
			err,
		)

		return nil, false, fmt.Errorf("clickhouse query failed: %w", err)
	}

	log.Printf(
		"[ClickHouse][RegionEvaluation] Metrics found for ro=%s state=%s",
		regionalOffice,
		stateFilter,
	)

	//---------------------------------------------------------
	// Build response object
	//---------------------------------------------------------

	response := map[string]interface{}{
		"highest_risk_operator": highestRiskOperator,

		"critical_risk_count_active": criticalActive,
		"high_risk_count_active":     highActive,
		"medium_risk_count_active":   mediumActive,
		"low_risk_count_active":      lowActive,
		"no_risk_count_active":       noRiskActive,

		"critical_risk_count_inactive": criticalInactive,
		"high_risk_count_inactive":     highInactive,
		"medium_risk_count_inactive":   mediumInactive,
		"low_risk_count_inactive":      lowInactive,
		"no_risk_count_inactive":       noRiskInactive,
	}

	return response, true, nil
}

