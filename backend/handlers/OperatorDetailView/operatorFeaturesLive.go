package OperatorDetailView

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

type operatorFeaturesLiveRequest struct {
	OptID string `json:"opt_id"`
}

// GetOperatorFeaturesLive handles POST /api/operator_features/live. It reads
// opt_id from the JSON body and returns the operator's features fetched live
// from ClickHouse, shaped like operator_features_v1.json's "kpis" array:
// a single object keyed by feature_group, each holding that group's features.
//
// feature_type, remarks, and feature_graph aren't present in the ClickHouse
// table, so they're returned empty ("" / {} / {}) rather than omitted, to
// keep the response shape identical to the JSON file.
func GetOperatorFeaturesLive(c *gin.Context) {
	requestStart := time.Now()

	body, err := io.ReadAll(c.Request.Body)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "failed to read request body"})
		return
	}

	var req operatorFeaturesLiveRequest
	if err := json.Unmarshal(body, &req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid request body", "details": err.Error()})
		return
	}

	if req.OptID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "opt_id is required"})
		return
	}

	log.Printf("[GetOperatorFeaturesLive] Request received opt_id=%s at %s", req.OptID, requestStart.Format(time.RFC3339))

	rows, ro, err := GetOperatorFeaturesFromClickHouse(req.OptID)
	if err != nil {
		log.Printf("[GetOperatorFeaturesLive] ClickHouse lookup failed for opt_id=%s: %v (took %s)", req.OptID, err, time.Since(requestStart))
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to fetch operator features", "details": err.Error()})
		return
	}

	if len(rows) == 0 {
		log.Printf("[GetOperatorFeaturesLive] No features found for opt_id=%s (took %s)", req.OptID, time.Since(requestStart))
		c.JSON(http.StatusNotFound, gin.H{"error": "no features found for opt_id", "opt_id": req.OptID})
		return
	}

	kpisObj := gin.H{}
	for _, row := range rows {
		item := gin.H{
			"feature_id":          row.FeatureID,
			"feature_name":        row.FeatureName,
			"feature_type":        "",
			"feature_description": row.Description,
			"feature_value":       row.FeatureValue,
			"remarks":             gin.H{},
			"feature_graph":       gin.H{},
		}
		existing, _ := kpisObj[row.FeatureGroup].([]gin.H)
		kpisObj[row.FeatureGroup] = append(existing, item)
	}

	log.Printf("[GetOperatorFeaturesLive] Serving %d features across %d groups for opt_id=%s (took %s)", len(rows), len(kpisObj), req.OptID, time.Since(requestStart))

	c.JSON(http.StatusOK, gin.H{
		"opt_id": req.OptID,
		"ro":     ro,
		"kpis":   []gin.H{kpisObj},
	})
}
