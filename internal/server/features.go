package server

import (
	"net/http"
	"strings"

	"operator360-api/internal/messages"
	"operator360-api/internal/response"
)

// GetFeatureInfo handles POST /api/feature/info/. All body fields are
// optional; an empty body returns every feature row. Ported from
// src/feature/get_feature.py.
func (s *Server) GetFeatureInfo(w http.ResponseWriter, r *http.Request) {
	request, err := decodeJSONObject(r)
	if err != nil {
		writeJSON(w, http.StatusOK, response.Error("Invalid JSON request body", nil))
		return
	}
	writeJSON(w, http.StatusOK, s.getFeatureInfo(request))
}

func (s *Server) getFeatureInfo(request map[string]any) response.Response {
	query := s.FeatureQ.GetFeatureMetadataGlobal()
	var filters []string
	var params []any

	if v, ok := request["feature_id"]; ok {
		filters = append(filters, "feature_name = ?")
		params = append(params, v)
	}
	if v, ok := request["version"]; ok {
		filters = append(filters, "version = ?")
		params = append(params, v)
	}
	if v, ok := request["active"]; ok && v == true {
		filters = append(filters, "is_active = true")
	}
	if v, ok := request["is_risk"]; ok && v == true {
		filters = append(filters, "is_risk = true")
	}
	if v, ok := request["status"]; ok {
		filters = append(filters, "status = ?")
		params = append(params, v)
	}

	if len(filters) > 0 {
		query += strings.Join(filters, " AND ")
	} else {
		query = strings.TrimSuffix(query, "WHERE ")
	}

	rows, err := s.DB.ExecuteQuery(query, params...)
	if err != nil {
		return response.Error("Failed to retrieve features from database", nil)
	}

	featureID := requestOrDefault(request, "feature_id", "N/A")
	version := requestOrDefault(request, "version", "N/A")

	if len(rows) == 0 {
		return response.Error(messages.FeatureNotFound(featureID, version), nil)
	}

	return response.Success(
		messages.FeatureRetrieved(requestOrDefault(request, "feature_id", "All"), version),
		map[string]any{"feature": rows, "count": len(rows)},
	)
}

func requestOrDefault(request map[string]any, key string, def string) any {
	if v, ok := request[key]; ok {
		return v
	}
	return def
}
