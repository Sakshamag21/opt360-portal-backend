package SidReview

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"strings"
	"sync"
	"time"

	"opt360-portal-backend/config"

	"github.com/gin-gonic/gin"
)

type sidBatchGetRequest struct {
	SIDs []string `json:"sids"`
}

type sidLookupResult struct {
	SID        string `json:"sid"`
	Success    bool   `json:"success"`
	StatusCode int    `json:"status_code"`
	Response   any    `json:"response,omitempty"`
	Error      string `json:"error,omitempty"`
}

func GetSIDBatchValues(c *gin.Context) {
	body, err := io.ReadAll(c.Request.Body)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "failed to read request body"})
		return
	}

	var sids []string
	if err := json.Unmarshal(body, &sids); err != nil {
		var req sidBatchGetRequest
		if err := json.Unmarshal(body, &req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request body", "details": err.Error()})
			return
		}
		sids = req.SIDs
	}

	if len(sids) == 0 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "sids are required"})
		return
	}

	batchStart := time.Now()
	log.Printf("[GetSIDBatchValues] Processing %d SID lookups at %s", len(sids), batchStart.Format(time.RFC3339))

	cfg, err := config.LoadConfig()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to load configuration", "details": err.Error()})
		return
	}

	baseURL := strings.TrimRight(cfg.SIDStore.BaseURL, "/")
	client := &http.Client{Timeout: time.Duration(cfg.SIDStore.TimeoutSeconds) * time.Second}
	results := make([]sidLookupResult, len(sids))

	var wg sync.WaitGroup
	for i, sid := range sids {
		i, sid := i, strings.TrimSpace(sid)
		if sid == "" {
			results[i] = sidLookupResult{SID: sid, Success: false, StatusCode: http.StatusBadRequest, Error: "sid is required"}
			continue
		}

		wg.Add(1)
		go func() {
			defer wg.Done()

			endpoint := fmt.Sprintf("%s/api/opt_details/sid/%s", baseURL, url.PathEscape(sid))
			reqStart := time.Now()
			log.Printf("[GetSIDBatchValues] -> GET %s (sid=%s) at %s", endpoint, sid, reqStart.Format(time.RFC3339))

			upstreamReq, err := http.NewRequestWithContext(c.Request.Context(), http.MethodGet, endpoint, nil)
			if err != nil {
				log.Printf("[GetSIDBatchValues] <- %s (sid=%s) failed to build request: %v (took %s)", endpoint, sid, err, time.Since(reqStart))
				results[i] = sidLookupResult{SID: sid, Success: false, StatusCode: http.StatusInternalServerError, Error: "failed to create upstream request"}
				return
			}

			upstreamResp, err := client.Do(upstreamReq)
			if err != nil {
				log.Printf("[GetSIDBatchValues] <- %s (sid=%s) request failed: %v (took %s)", endpoint, sid, err, time.Since(reqStart))
				results[i] = sidLookupResult{SID: sid, Success: false, StatusCode: http.StatusBadGateway, Error: err.Error()}
				return
			}
			defer upstreamResp.Body.Close()

			respBytes, err := io.ReadAll(upstreamResp.Body)
			if err != nil {
				log.Printf("[GetSIDBatchValues] <- %s (sid=%s) failed to read response: %v (took %s)", endpoint, sid, err, time.Since(reqStart))
				results[i] = sidLookupResult{SID: sid, Success: false, StatusCode: http.StatusBadGateway, Error: "failed to read upstream response"}
				return
			}

			var parsed any
			if len(respBytes) > 0 {
				if err := json.Unmarshal(respBytes, &parsed); err != nil {
					parsed = gin.H{"raw": string(respBytes)}
				}
			}

			// The upstream opt_details/sid endpoint always responds 200, even
			// when the SID isn't found — the real outcome is in the body's
			// "success"/"message" fields, so HTTP status alone isn't enough.
			success := upstreamResp.StatusCode >= 200 && upstreamResp.StatusCode < 300
			errMsg := ""
			if body, ok := parsed.(map[string]interface{}); ok {
				if bodySuccess, ok := body["success"].(bool); ok {
					success = success && bodySuccess
				}
				if !success {
					if msg, ok := body["message"].(string); ok {
						errMsg = msg
					}
				}
			}

			log.Printf("[GetSIDBatchValues] <- %s (sid=%s) status=%d success=%t (took %s)", endpoint, sid, upstreamResp.StatusCode, success, time.Since(reqStart))

			results[i] = sidLookupResult{
				SID:        sid,
				Success:    success,
				StatusCode: upstreamResp.StatusCode,
				Response:   parsed,
				Error:      errMsg,
			}
		}()
	}
	wg.Wait()

	successCount := 0
	for _, r := range results {
		if r.Success {
			successCount++
		}
	}

	log.Printf("[GetSIDBatchValues] Completed: %d/%d successful, total time %s", successCount, len(sids), time.Since(batchStart))
	c.JSON(http.StatusOK, gin.H{
		"success":    successCount == len(sids),
		"message":    "SID lookups completed",
		"requested":  len(sids),
		"successful": successCount,
		"results":    results,
	})
}
