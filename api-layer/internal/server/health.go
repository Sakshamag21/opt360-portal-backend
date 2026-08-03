package server

import "net/http"

// HealthCheck handles GET /api/ - basic health check.
func (s *Server) HealthCheck(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"status":        "healthy",
		"service":       "operator360-api",
		"database_host": orNotConfigured(s.Config.DBHost()),
	})
}

func orNotConfigured(v string) string {
	if v == "" {
		return "Not configured"
	}
	return v
}

// DetailedHealth handles GET /api/health - health check with a live DB ping.
func (s *Server) DetailedHealth(w http.ResponseWriter, r *http.Request) {
	dbStatus := "disconnected"
	overall := "degraded"
	if s.DB.TestConnection() {
		dbStatus = "connected"
		overall = "healthy"
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"status":   overall,
		"service":  "operator360-api",
		"database": dbStatus,
	})
}

// EndpointsInfo handles GET /api/endpoints - a static, self-describing
// catalogue of the API's routes, ported from routes.py's get_endpoints_info.
func (s *Server) EndpointsInfo(w http.ResponseWriter, r *http.Request) {
	endpoints := []map[string]any{
		{
			"path": "/api/", "method": "GET", "tag": "Health",
			"summary":     "Health check endpoint",
			"description": "Basic health check to verify service is running",
			"parameters":  []any{}, "request_body": nil,
		},
		{
			"path": "/api/health", "method": "GET", "tag": "Health",
			"summary":     "Detailed health check",
			"description": "Detailed health check with database connection test",
			"parameters":  []any{}, "request_body": nil,
		},
		{
			"path": "/api/endpoints", "method": "GET", "tag": "Health",
			"summary":     "API endpoints information",
			"description": "Get information about all available API endpoints",
			"parameters":  []any{}, "request_body": nil,
		},
		{
			"path": "/api/signal/create", "method": "POST", "tag": "Signals",
			"summary":     "Create a new signal",
			"description": "Create a new signal with specified parameters",
			"parameters":  []any{},
			"request_body": map[string]any{
				"required_fields": []string{
					"id", "name", "description", "feature_id",
					"feature_version", "threshold", "severity_level", "user",
				},
				"example": map[string]any{
					"id": "SIG001", "name": "Sample Signal", "description": "Signal description",
					"feature_id": "FEAT001", "feature_version": "1.0", "threshold": 0.85,
					"severity_level": "high", "user": "admin",
				},
			},
		},
		{
			"path": "/api/signal/info/id/{signal_id}", "method": "GET", "tag": "Signals",
			"summary":     "Get signals by signal ID",
			"description": "Get all active signals correcsponding to a signal id",
			"parameters": []map[string]any{
				{"name": "signal_id", "in": "path", "required": true, "type": "string", "description": "The identifier of the signal"},
			},
			"request_body": nil,
		},
		{
			"path": "/api/signal/info/{feature_id}", "method": "GET", "tag": "Signals",
			"summary":     "Get signals by feature ID",
			"description": "Get all active signals for a specific feature",
			"parameters": []map[string]any{
				{"name": "feature_id", "in": "path", "required": true, "type": "string", "description": "The unique identifier of the feature"},
			},
			"request_body": nil,
		},
		{
			"path": "/api/feature/info/", "method": "POST", "tag": "Features",
			"summary":     "Get feature information",
			"description": "Get feature information with optional filters",
			"parameters":  []any{},
			"request_body": map[string]any{
				"required_fields": []string{},
				"optional_fields": []string{"feature_id", "version", "active", "is_risk", "status"},
				"examples": []map[string]any{
					{"description": "Get all features", "value": map[string]any{}},
					{"description": "Get specific feature", "value": map[string]any{"feature_id": "FEAT001"}},
					{"description": "Get specific version", "value": map[string]any{"feature_id": "FEAT001", "version": "1.0"}},
					{"description": "Get active features", "value": map[string]any{"active": true}},
					{"description": "Get risky features", "value": map[string]any{"is_risk": true}},
				},
			},
		},
		{
			"path": "/api/opt_details/info", "method": "POST", "tag": "Operator Details",
			"summary":     "Get Operator Information",
			"description": "Get metadata related to the corresponding Operator Id",
			"parameters":  []any{},
			"request_body": map[string]any{
				"required_fields": []string{"operator_id"},
				"example":         map[string]any{"operator_id": "OPT12345"},
			},
		},
		{
			"path": "/api/opt_details/sid/{sid}", "method": "GET", "tag": "Operator Details for SID",
			"summary":     "Get Operator information corresponding to the particular SID",
			"description": "Get metadata of the Operator related to the corresponding SID",
			"parameters": []map[string]any{
				{"name": "sid", "in": "path", "required": true, "type": "string", "description": "The unique identifier of the packet"},
			},
			"request_body": nil,
		},
		{
			"path": "/api/sid_details/sids/all", "method": "POST", "tag": "SID Details",
			"summary":     "List SIDs for an operator/date",
			"description": "Get a paginated list of SIDs (with enrichment details) for a given operator and date",
			"parameters":  []any{},
			"request_body": map[string]any{
				"required_fields": []string{"opt_id", "date"},
				"optional_fields": []string{"limit", "page"},
				"example":         map[string]any{"opt_id": "OPT12345", "date": "2026-07-01", "page": 1},
			},
		},
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"service":         "operator360-api",
		"version":         "1.0.0",
		"base_url":        "/api",
		"total_endpoints": len(endpoints),
		"endpoints":       endpoints,
		"documentation":   "documentation.txt",
	})
}
