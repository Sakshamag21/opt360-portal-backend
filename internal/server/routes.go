package server

import "net/http"

// RegisterRoutes wires every handler onto mux under the /api prefix,
// mirroring the `routers` list assembled in src/routes.py.
func (s *Server) RegisterRoutes(mux *http.ServeMux) {
	// Health
	// "{$}" restricts the pattern to an exact match; without it, a
	// trailing-slash pattern in Go's net/http ServeMux matches the entire
	// subtree (e.g. "/api/" would also swallow "/api/anything").
	mux.HandleFunc("GET /api/{$}", s.HealthCheck)
	mux.HandleFunc("GET /api/health", s.DetailedHealth)
	mux.HandleFunc("GET /api/endpoints", s.EndpointsInfo)

	// Signals
	mux.HandleFunc("POST /api/signal/create", s.CreateSignal)
	mux.HandleFunc("GET /api/signal/info/id/{signal_id}", s.GetSignalInfoByID)
	mux.HandleFunc("GET /api/signal/info/{feature_id}", s.GetSignalInfoByFeature)

	// Features
	mux.HandleFunc("POST /api/feature/info/{$}", s.GetFeatureInfo)

	// Operator details
	mux.HandleFunc("POST /api/opt_details/info", s.GetOperatorDetailsHTTP)
	mux.HandleFunc("GET /api/opt_details/sid/{sid}", s.GetOperatorBySID)

	// SID details
	mux.HandleFunc("POST /api/sid_details/sids/all", s.GetSidsAll)
}
