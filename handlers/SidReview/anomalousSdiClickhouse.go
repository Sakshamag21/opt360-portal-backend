package SidReview

import (
	"context"
	"fmt"
	"log"
	"strings"
	"time"

	"opt360-portal-backend/db"
)

const clickHouseQueryTimeout = 10 * time.Second

// GetAnomalousSIDsFromClickHouse fetches anomalous packets from ClickHouse.
//
// Returns:
//   - []map[string]interface{} : Same structure as the S3 flattening logic
//   - totalRecords             : Total matching records (before pagination)
//   - error
func GetAnomalousSIDsFromClickHouse(
	optID string,
	anomalyCategory string,
	page int,
	pageSize int,
) ([]map[string]interface{}, int, error) {

	log.Printf("[ClickHouse][AnomalousPackets] Request received opt_id=%s page=%d page_size=%d category=%q",
		optID,
		page,
		pageSize,
		anomalyCategory,
	)

	conn, err := db.GetClickHouseDB()
	if err != nil {
		log.Printf("[ClickHouse][AnomalousPackets] Connection unavailable: %v", err)
		return nil, 0, err
	}

	offset := (page - 1) * pageSize

	//-------------------------------------------------------
	// Build WHERE clause
	//-------------------------------------------------------

	whereClause := "WHERE opt_id = ?"
	countArgs := []interface{}{optID}

	if anomalyCategory != "" {
		whereClause += " AND lower(anomaly_type) = lower(?)"
		countArgs = append(countArgs, anomalyCategory)
	}

	//-------------------------------------------------------
	// Count Query
	//-------------------------------------------------------

	countSQL := fmt.Sprintf(`
		SELECT count()
		FROM operator360.anomalous_packets
		%s
	`, whereClause)

	log.Printf("[ClickHouse][AnomalousPackets] Count SQL: %s", strings.TrimSpace(countSQL))

	ctx, cancel := context.WithTimeout(context.Background(), clickHouseQueryTimeout)
	defer cancel()

	var totalRecords uint64

	if err := conn.QueryRow(ctx, countSQL, countArgs...).Scan(&totalRecords); err != nil {
		log.Printf("[ClickHouse][AnomalousPackets] Count query failed: %v", err)
		return nil, 0, err
	}

	log.Printf("[ClickHouse][AnomalousPackets] Total matching records=%d", totalRecords)

	if totalRecords == 0 {
		return []map[string]interface{}{}, 0, nil
	}

	//-------------------------------------------------------
	// Data Query
	//-------------------------------------------------------

	dataSQL := fmt.Sprintf(`
		SELECT
			packet_eid,
			opt_id,
			anomaly_type,
			enrolment_type,
			created_date,
			station_id,
			machine_code,
			pkt_source,
			feature_group,
			comments
		FROM operator360.anomalous_packets
		%s
		ORDER BY created_date DESC
		LIMIT ? OFFSET ?
	`, whereClause)

	queryArgs := append(countArgs, pageSize, offset)

	log.Printf(
		"[ClickHouse][AnomalousPackets] Executing query (limit=%d offset=%d)",
		pageSize,
		offset,
	)

	rows, err := conn.Query(ctx, dataSQL, queryArgs...)
	if err != nil {
		log.Printf("[ClickHouse][AnomalousPackets] Query failed: %v", err)
		return nil, 0, err
	}
	defer rows.Close()

	results := make([]map[string]interface{}, 0)

	for rows.Next() {

		var (
			packetEID     string
			operatorID    string
			anomalyType   string
			enrolmentType string
			createdDate   time.Time
			stationID     string
			machineCode   string
			packetSource  string
			featureGroup  string
			comments      string
		)

		if err := rows.Scan(
			&packetEID,
			&operatorID,
			&anomalyType,
			&enrolmentType,
			&createdDate,
			&stationID,
			&machineCode,
			&packetSource,
			&featureGroup,
			&comments,
		); err != nil {

			log.Printf("[ClickHouse][AnomalousPackets] Scan failed: %v", err)
			return nil, 0, err
		}

		record := map[string]interface{}{
			// Keep SAME response as existing API
			"sid":              packetEID,
			"operator_id":      operatorID,
			"anomaly_category": anomalyType,

			// Existing fields
			"enrolment_type": enrolmentType,
			"created_date":   createdDate,
			"station_id":     stationID,
			"machine_code":   machineCode,
			"pkt_source":     packetSource,
			"feature_group":  featureGroup,
			"comments":       comments,
		}

		results = append(results, record)
	}

	if err := rows.Err(); err != nil {
		log.Printf("[ClickHouse][AnomalousPackets] Row iteration failed: %v", err)
		return nil, 0, err
	}

	log.Printf(
		"[ClickHouse][AnomalousPackets] Returning %d/%d records for opt_id=%s",
		len(results),
		totalRecords,
		optID,
	)

	return results, int(totalRecords), nil
}
