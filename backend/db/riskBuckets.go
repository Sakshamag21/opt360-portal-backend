package db

import (
	"log"
	"sort"
	"strings"
	"sync"
)

var (
	riskBucketsCache []string
	riskBucketsOnce  sync.Once
)

// riskBucketSeverityOrder ranks known bucket names so the cached list stays
// in a sensible order; anything not listed here sorts after these, in
// whatever order the DISTINCT query returned it.
var riskBucketSeverityOrder = map[string]int{
	"critical": 0,
	"high":     1,
	"medium":   2,
	"low":      3,
}

// InitRiskBucketCache runs once at startup: SELECT DISTINCT risk_bucket FROM
// opt_master, cached in memory for the life of the process. Handlers that
// need to enumerate risk buckets should call GetRiskBuckets instead of
// hardcoding a fixed High/Medium/Low list — this is what lets a bucket like
// "Critical" (or any future bucket) get picked up everywhere it's used
// without a code change, as long as it exists in opt_master.
//
// Non-fatal: if the query fails (e.g. called before the DB is ready), the
// cache is left empty and callers fall back to whatever they do for an empty
// list. Call again (or restart) once the DB is reachable.
func InitRiskBucketCache() {
	riskBucketsOnce.Do(func() {
		refreshRiskBucketCache()
	})
}

func refreshRiskBucketCache() {
	database, err := GetDB()
	if err != nil {
		log.Printf("[RiskBuckets] DB unavailable, cache empty: %v", err)
		return
	}

	rows, err := database.Query("SELECT DISTINCT risk_bucket FROM operator360.opt_master WHERE risk_bucket IS NOT NULL")
	if err != nil {
		log.Printf("[RiskBuckets] Query failed, cache empty: %v", err)
		return
	}
	defer rows.Close()

	var buckets []string
	for rows.Next() {
		var b string
		if err := rows.Scan(&b); err != nil {
			log.Printf("[RiskBuckets] Row scan error: %v", err)
			continue
		}
		buckets = append(buckets, b)
	}
	if err := rows.Err(); err != nil {
		log.Printf("[RiskBuckets] Row iteration error: %v", err)
		return
	}

	sort.SliceStable(buckets, func(i, j int) bool {
		oi, oki := riskBucketSeverityOrder[strings.ToLower(buckets[i])]
		oj, okj := riskBucketSeverityOrder[strings.ToLower(buckets[j])]
		if !oki {
			oi = 100
		}
		if !okj {
			oj = 100
		}
		return oi < oj
	})

	riskBucketsCache = buckets
	log.Printf("[RiskBuckets] Cached %d risk buckets: %v", len(buckets), buckets)
}

// GetRiskBuckets returns the cached list of distinct non-null risk_bucket
// values from opt_master, ordered by known severity (Critical > High >
// Medium > Low), with any unrecognized values appended last.
func GetRiskBuckets() []string {
	return riskBucketsCache
}
