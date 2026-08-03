package server

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"strings"
	"time"

	"operator360-api/internal/response"
)

const sidsCacheTTL = 300 * time.Second

// GetAllSidsDate lists all SIDs for an operator on a given date (fetched from
// the RocksDB operator store and cached in-process for 5 minutes), paginates
// the list, and enriches the current page via GetSidDetails. Ported from
// src/sid_details/all_sids.py.
func (s *Server) GetAllSidsDate(optID, dateStr string, limit, page int) response.Response {
	start := time.Now()

	endpoint := s.Config.RocksDBOperatorStore
	if endpoint.Host == "" {
		log.Println("Fallback triggered: RocksDB configuration missing")
		return response.Error("RocksDB configuration missing", nil)
	}
	endpointURL := endpoint.URL()

	dateClean := strings.ReplaceAll(dateStr, "-", "")
	cacheKey := "sids:" + optID + ":" + dateClean

	log.Printf("--- Starting execution for opt_id=%s, date=%s, page=%d ---", optID, dateClean, page)
	logCacheState(s.sidCache)
	s.sidCache.cleanup()

	allSids, hit := s.sidCache.get(cacheKey)
	if !hit {
		lock := s.sidCache.fetchLock(cacheKey)
		var errResp *response.Response

		func() {
			lock.Lock()
			defer lock.Unlock()

			if cached, ok := s.sidCache.get(cacheKey); ok {
				log.Println("Data fetched by another goroutine while waiting. Using cache.")
				allSids = cached
				return
			}

			log.Printf("Cache miss for %s. Fetching from RocksDB.", cacheKey)
			fetched, fe := s.fetchAllSidsFromRocksDB(endpointURL, optID, dateClean)
			if fe != nil {
				errResp = fe
				return
			}

			sizeBytes := 0
			if b, err := json.Marshal(fetched); err == nil {
				sizeBytes = len(b)
			}
			s.sidCache.set(cacheKey, fetched, sizeBytes, sidsCacheTTL)
			s.sidCache.cleanup()
			allSids = fetched
		}()

		if errResp != nil {
			return *errResp
		}
	}

	if len(allSids) == 0 {
		log.Printf("No SIDs found for opt_id=%s, date=%s.", optID, dateClean)
		log.Printf("Total execution time: %s", time.Since(start))
		return response.Success(
			fmt.Sprintf("No SIDs found for the operator id: %s, date=%s", optID, dateClean),
			map[string]any{
				"sids": []map[string]any{}, "total_sids": 0, "total_pages": 0,
				"current_page": page, "has_more": false,
			},
		)
	}

	totalSids := len(allSids)
	totalPages := (totalSids + limit - 1) / limit
	startIndex := (page - 1) * limit
	endIndex := startIndex + limit

	// Go panics on out-of-range slice indices; Python silently clamps them.
	// Clamp explicitly so an out-of-range page behaves the same as the
	// original (an empty page rather than a crash).
	if startIndex < 0 {
		startIndex = 0
	}
	if startIndex > totalSids {
		startIndex = totalSids
	}
	if endIndex > totalSids {
		endIndex = totalSids
	}
	if endIndex < startIndex {
		endIndex = startIndex
	}

	pageSids := allSids[startIndex:endIndex]

	if len(pageSids) == 0 {
		log.Printf("Total execution time: %s", time.Since(start))
		return response.Success("No more SIDs to fetch", map[string]any{
			"sids": []map[string]any{}, "total_sids": totalSids, "total_pages": totalPages,
			"current_page": page, "has_more": false,
		})
	}

	log.Printf("Successfully fetched %d SIDs for page %d. Proceeding to enrichment.", len(pageSids), page)

	sidDetailsResp := s.GetSidDetails(pageSids)
	sidsInfo, _ := sidDetailsResp.Data["sids_info"].([]map[string]any)

	detailsMap := make(map[string]map[string]any, len(sidsInfo))
	for _, info := range sidsInfo {
		if sidVal, ok := info["sid"].(string); ok {
			detailsMap[sidVal] = info
		}
	}

	sidDet := make([]map[string]any, 0, len(pageSids))
	for _, sid := range pageSids {
		if details, ok := detailsMap[sid]; ok {
			merged := make(map[string]any, len(details)+1)
			merged["sid"] = sid
			for k, v := range details {
				if k == "sid" {
					continue
				}
				merged[k] = v
			}
			sidDet = append(sidDet, merged)
		} else {
			sidDet = append(sidDet, map[string]any{"sid": sid})
		}
	}

	logCacheState(s.sidCache)
	log.Printf("Total execution time: %s", time.Since(start))

	return response.Success(
		fmt.Sprintf("SIDs and details retrieved successfully for operator id: %s, date=%s", optID, dateClean),
		map[string]any{
			"sids": sidDet, "total_sids": totalSids, "total_pages": totalPages,
			"current_page": page, "page_size": len(pageSids),
		},
	)
}

// fetchAllSidsFromRocksDB fetches the full SID list for opt_id+date from the
// RocksDB operator store. A non-nil *response.Response return means the
// caller should short-circuit and return it directly to the client.
func (s *Server) fetchAllSidsFromRocksDB(endpointURL, optID, dateClean string) ([]string, *response.Response) {
	resp, err := postJSON(s.HTTPClient, endpointURL, 15*time.Second, map[string]any{"opt_id": optID, "date": dateClean})
	if err != nil {
		if isTimeoutErr(err) {
			r := response.Error("Request to Operator store timed out", nil)
			return nil, &r
		}
		r := response.Error("Failed to connect to Operator store: "+err.Error(), nil)
		return nil, &r
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		r := response.Error(fmt.Sprintf("Operator store request failed with status %d", resp.StatusCode), nil)
		return nil, &r
	}

	var payload struct {
		Results []any `json:"results"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		r := response.Error("Invalid JSON response from Operator store", nil)
		return nil, &r
	}

	fetched := make([]string, 0, len(payload.Results))
	for _, record := range payload.Results {
		switch v := record.(type) {
		case string:
			fetched = append(fetched, v)
		case map[string]any:
			if sidVal, ok := v["sid"].(string); ok && sidVal != "" {
				fetched = append(fetched, sidVal)
			}
		}
	}
	return fetched, nil
}

func logCacheState(c *sidCache) {
	items, totalBytes := c.stats()
	log.Printf("Cache State: %d items | Size: %.4f MB", items, float64(totalBytes)/(1024*1024))
}

type timeoutError interface{ Timeout() bool }

func isTimeoutErr(err error) bool {
	var t timeoutError
	if errors.As(err, &t) {
		return t.Timeout()
	}
	return false
}
