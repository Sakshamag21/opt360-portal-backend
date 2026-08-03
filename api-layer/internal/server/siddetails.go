package server

import (
	"encoding/json"
	"log"
	"strconv"
	"time"

	"operator360-api/internal/response"
)

var sidDetailExpectedKeys = []string{"sid", "opt_id", "pkt_type", "station_id", "machine_code", "created_at"}

type rocksDBSidBatchResponse struct {
	Status string         `json:"status"`
	Items  []sidBatchItem `json:"items"`
}

type sidBatchItem struct {
	Sid    string           `json:"sid"`
	Values []map[string]any `json:"values"`
}

// GetSidDetails batch-fetches enrichment details (opt_id, pkt_type,
// station_id, machine_code, created_at) for a list of SIDs from the RocksDB
// SID store, ported from src/sid_details/info.py. Every requested SID is
// guaranteed a slot in the result, with nulls filled in for anything the
// store didn't return.
func (s *Server) GetSidDetails(sids []string) response.Response {
	start := time.Now()
	log.Printf("Fetching details for %d SIDs from RocksDB SID store...", len(sids))

	endpoint := s.Config.RocksDBSIDStore
	if endpoint.Host == "" {
		log.Println("Fallback triggered: RocksDB SID store configuration is missing.")
		return response.Error("RocksDB configuration missing", nil)
	}

	endpointURL := endpoint.URL()
	log.Printf("Connecting to RocksDB SID store endpoint: %s", endpointURL)

	resp, err := postJSON(s.HTTPClient, endpointURL, 10*time.Second, map[string]any{"sids": sids})
	if err != nil {
		log.Printf("Fallback triggered: network error fetching SID details: %v. Executed in %s", err, time.Since(start))
		return response.Error("Network error: "+err.Error(), nil)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		log.Printf("Fallback triggered: RocksDB SID store returned non-200 status code: %d. Executed in %s", resp.StatusCode, time.Since(start))
		return response.Error("RocksDB SID store request failed with status "+strconv.Itoa(resp.StatusCode), nil)
	}

	var payload rocksDBSidBatchResponse
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		log.Printf("Fallback triggered: failed to decode JSON response from RocksDB SID store: %v. Executed in %s", err, time.Since(start))
		return response.Error("Invalid JSON response from RocksDB SID store", nil)
	}

	formatItem := func(item map[string]any) map[string]any {
		out := make(map[string]any, len(sidDetailExpectedKeys))
		for _, k := range sidDetailExpectedKeys {
			out[k] = item[k]
		}
		return out
	}
	createNullItem := func(sid string) map[string]any {
		return map[string]any{
			"sid": sid, "opt_id": nil, "pkt_type": nil,
			"station_id": nil, "machine_code": nil, "created_at": nil,
		}
	}

	if payload.Status == "OK" {
		// Merge every value-map we receive for a given SID. Later writes
		// for the same key win, but only if they actually carry a value.
		merged := make(map[string]map[string]any, len(sids))
		for _, item := range payload.Items {
			if item.Sid == "" {
				continue
			}
			m, ok := merged[item.Sid]
			if !ok {
				m = make(map[string]any, len(sidDetailExpectedKeys))
				merged[item.Sid] = m
			}
			for _, v := range item.Values {   // <-- iterate ALL values, not just [0]
				for k, val := range v {
					if val == nil {
						continue // don't clobber an existing value with nil
					}
					m[k] = val
				}
			}
			m["sid"] = item.Sid
		}

		finalSidsInfo := make([]map[string]any, 0, len(sids))
		foundCount := 0
		for _, sid := range sids {
			m, ok := merged[sid]
			if ok {
				foundCount++
				finalSidsInfo = append(finalSidsInfo, formatItem(m))
			} else {
				finalSidsInfo = append(finalSidsInfo, createNullItem(sid))
			}
		}

		log.Printf("Successfully processed details. Requested: %d, Found: %d. Executed in %s",
			len(sids), foundCount, time.Since(start))
		return response.Success("SID details retrieved successfully",
			map[string]any{"sids_info": finalSidsInfo})
	}

	log.Printf("Fallback triggered: RocksDB status not OK. Status: %s. Returning null values for all %d requested sids. Executed in %s", payload.Status, len(sids), time.Since(start))
	finalSidsInfo := make([]map[string]any, 0, len(sids))
	for _, sid := range sids {
		finalSidsInfo = append(finalSidsInfo, createNullItem(sid))
	}
	return response.Success("No SID details found", map[string]any{"sids_info": finalSidsInfo})
}
