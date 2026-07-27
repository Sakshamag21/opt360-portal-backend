// Package server implements the HTTP handlers for the Operator360 API,
// mirroring the Python handlers under src/signals, src/feature,
// src/opt_details and src/sid_details.
package server

import (
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"operator360-api/internal/config"
	"operator360-api/internal/database"
	"operator360-api/internal/queries"
)

// Server holds shared dependencies for all HTTP handlers.
type Server struct {
	Config     *config.Config
	DB         *database.DB
	SignalQ    queries.SignalQueries
	FeatureQ   queries.FeatureQueries
	OperatorQ  queries.OperatorDetailQueries
	HTTPClient *http.Client
	sidCache   *sidCache
}

// New builds a Server with query templates derived from cfg and an HTTP
// client shared across outbound RocksDB calls.
func New(cfg *config.Config, db *database.DB) *Server {
	return &Server{
		Config:    cfg,
		DB:        db,
		SignalQ:   queries.NewSignalQueries(cfg.SignalTable()),
		FeatureQ:  queries.NewFeatureQueries(cfg.FeatureTable()),
		OperatorQ: queries.NewOperatorDetailQueries(cfg.OptTable()),
		HTTPClient: &http.Client{
			Timeout: 15 * time.Second,
		},
		sidCache: newSidCache(5 * 1024 * 1024), // 5 MB, matches MAX_CACHE_BYTES in all_sids.py
	}
}

// writeJSON marshals v as JSON with the given status code.
func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

// writeValidationError approximates FastAPI's automatic 422 response for a
// request body that fails model validation.
func writeValidationError(w http.ResponseWriter, field, message string) {
	writeJSON(w, http.StatusUnprocessableEntity, map[string]any{
		"detail": []map[string]any{
			{"loc": []string{"body", field}, "msg": message, "type": "value_error"},
		},
	})
}

// decodeJSONObject decodes the request body into a generic map, used for the
// loosely-typed endpoints that accept an arbitrary JSON object (create
// signal, feature info filters, etc.) just like the Python `request: dict`
// handlers.
func decodeJSONObject(r *http.Request) (map[string]any, error) {
	var body map[string]any
	if r.Body == nil {
		return map[string]any{}, nil
	}
	dec := json.NewDecoder(r.Body)
	if err := dec.Decode(&body); err != nil {
		return nil, err
	}
	if body == nil {
		body = map[string]any{}
	}
	return body, nil
}

// toInt64 converts values returned by the MySQL driver (int64, float64,
// []byte/string) into an int64, used for reading MAX(version) results.
func toInt64(v any) int64 {
	switch t := v.(type) {
	case int64:
		return t
	case int:
		return int64(t)
	case float64:
		return int64(t)
	case string:
		n, _ := strconv.ParseInt(t, 10, 64)
		return n
	case []byte:
		n, _ := strconv.ParseInt(string(t), 10, 64)
		return n
	default:
		return 0
	}
}
