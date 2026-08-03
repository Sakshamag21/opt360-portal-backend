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

func GetRegionEvaluationFromClickHouse(
	regionalOffice string,
	optState string,
	optDistrict string,
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
	var districtFilter string

	if strings.TrimSpace(optState) == "" {

		// RO level
		stateFilter = "ALL"
		districtFilter = "ALL"

		log.Printf(
			"[ClickHouse][RegionEvaluation] RO level lookup ro=%s state=%s district=%s",
			regionalOffice,
			stateFilter,
			districtFilter,
		)

	} else if strings.TrimSpace(optDistrict) == "" {

		// State level

		stateFilter = optState
		districtFilter = "ALL"

		log.Printf(
			"[ClickHouse][RegionEvaluation] State level lookup ro=%s state=%s district=%s",
			regionalOffice,
			stateFilter,
			districtFilter,
		)
	} else {
		stateFilter = optState
		districtFilter = optDistrict

		log.Printf(
			"[ClickHouse][RegionEvaluation] District level lookup ro=%s state=%s district=%s",
			regionalOffice,
			stateFilter,
			districtFilter,
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
AND district_name = ?
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
		districtFilter,
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

// bucketRow holds the summed active+inactive risk-bucket counts for one
// name (a state or a district), as returned by the GROUP BY queries below.
type bucketRow struct {
	name     string
	critical uint64
	high     uint64
	med      uint64
	low      uint64
	noRisk   uint64
}

func (b bucketRow) toDistributionEntry() map[string]interface{} {
	return map[string]interface{}{
		"critical_risk": b.critical,
		"high_risk":     b.high,
		"med_risk":      b.med,
		"low_risk":      b.low,
		"no_risk":       b.noRisk,
	}
}

// GetRegionStateDistributionFromClickHouse returns opt_distribution-shaped
// risk-bucket counts (critical_risk/high_risk/med_risk/low_risk/no_risk,
// active+inactive summed together) for every real state under regionalOffice,
// keyed by state name — matching what GeographicAnalysisTab.jsx expects at
// the state-list ('drillLevel === state') level.
func GetRegionStateDistributionFromClickHouse(
	regionalOffice string,
) (map[string]interface{}, bool, error) {

	start := time.Now()
	defer func() {
		log.Printf(
			"[ClickHouse][RegionEvaluation] State distribution completed in %v",
			time.Since(start),
		)
	}()

	conn, err := db.GetClickHouseDB()
	if err != nil {
		log.Printf("[ClickHouse][RegionEvaluation] ClickHouse unavailable: %v", err)
		return nil, false, err
	}

	query := `
SELECT
	state_name,
	SUM(critical_risk_count_active) + SUM(critical_risk_count_inactive) AS critical,
	SUM(high_risk_count_active) + SUM(high_risk_count_inactive) AS high,
	SUM(medium_risk_count_active) + SUM(medium_risk_count_inactive) AS med,
	SUM(low_risk_count_active) + SUM(low_risk_count_inactive) AS low,
	SUM(no_risk_count_active) + SUM(no_risk_count_inactive) AS no_risk
FROM operator360.ro_state_metrics
WHERE ro_name = ?
AND state_name != 'ALL'
AND district_name = 'ALL'
GROUP BY state_name
`

	ctx, cancel := context.WithTimeout(
		context.Background(),
		regionEvaluationQueryTimeout,
	)
	defer cancel()

	rows, err := conn.Query(ctx, query, regionalOffice)
	if err != nil {
		log.Printf("[ClickHouse][RegionEvaluation] State distribution query failed: %v", err)
		return nil, false, fmt.Errorf("clickhouse query failed: %w", err)
	}
	defer rows.Close()

	distribution := map[string]interface{}{}
	for rows.Next() {
		var b bucketRow
		if err := rows.Scan(&b.name, &b.critical, &b.high, &b.med, &b.low, &b.noRisk); err != nil {
			log.Printf("[ClickHouse][RegionEvaluation] State distribution scan failed: %v", err)
			return nil, false, fmt.Errorf("clickhouse scan failed: %w", err)
		}
		distribution[b.name] = b.toDistributionEntry()
	}
	if err := rows.Err(); err != nil {
		return nil, false, fmt.Errorf("clickhouse row iteration failed: %w", err)
	}

	if len(distribution) == 0 {
		log.Printf("[ClickHouse][RegionEvaluation] No state metrics found for ro=%s", regionalOffice)
		return nil, false, nil
	}

	return distribution, true, nil
}

// GetRegionDistrictDistributionFromClickHouse returns opt_distribution-shaped
// risk-bucket counts for every real district under regionalOffice/optState,
// keyed by district name — matching what GeographicAnalysisTab.jsx expects at
// the district-list ('drillLevel === district') level.
func GetRegionDistrictDistributionFromClickHouse(
	regionalOffice string,
	optState string,
) (map[string]interface{}, bool, error) {

	start := time.Now()
	defer func() {
		log.Printf(
			"[ClickHouse][RegionEvaluation] District distribution completed in %v",
			time.Since(start),
		)
	}()

	conn, err := db.GetClickHouseDB()
	if err != nil {
		log.Printf("[ClickHouse][RegionEvaluation] ClickHouse unavailable: %v", err)
		return nil, false, err
	}

	query := `
SELECT
	district_name,
	SUM(critical_risk_count_active) + SUM(critical_risk_count_inactive) AS critical,
	SUM(high_risk_count_active) + SUM(high_risk_count_inactive) AS high,
	SUM(medium_risk_count_active) + SUM(medium_risk_count_inactive) AS med,
	SUM(low_risk_count_active) + SUM(low_risk_count_inactive) AS low,
	SUM(no_risk_count_active) + SUM(no_risk_count_inactive) AS no_risk
FROM operator360.ro_state_metrics
WHERE ro_name = ?
AND state_name = ?
AND district_name != 'ALL'
GROUP BY district_name
`

	ctx, cancel := context.WithTimeout(
		context.Background(),
		regionEvaluationQueryTimeout,
	)
	defer cancel()

	rows, err := conn.Query(ctx, query, regionalOffice, optState)
	if err != nil {
		log.Printf("[ClickHouse][RegionEvaluation] District distribution query failed: %v", err)
		return nil, false, fmt.Errorf("clickhouse query failed: %w", err)
	}
	defer rows.Close()

	distribution := map[string]interface{}{}
	for rows.Next() {
		var b bucketRow
		if err := rows.Scan(&b.name, &b.critical, &b.high, &b.med, &b.low, &b.noRisk); err != nil {
			log.Printf("[ClickHouse][RegionEvaluation] District distribution scan failed: %v", err)
			return nil, false, fmt.Errorf("clickhouse scan failed: %w", err)
		}
		distribution[b.name] = b.toDistributionEntry()
	}
	if err := rows.Err(); err != nil {
		return nil, false, fmt.Errorf("clickhouse row iteration failed: %w", err)
	}

	if len(distribution) == 0 {
		log.Printf(
			"[ClickHouse][RegionEvaluation] No district metrics found for ro=%s state=%s",
			regionalOffice,
			optState,
		)
		return nil, false, nil
	}

	return distribution, true, nil
}
