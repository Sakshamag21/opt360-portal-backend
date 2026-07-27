package server

import (
	"log"
	"net/http"

	"operator360-api/internal/messages"
	"operator360-api/internal/response"
)

var signalRequiredFields = []string{
	"id", "name", "description", "feature_id",
	"feature_version", "threshold", "severity_level", "user",
}

// CreateSignal handles POST /api/signal/create.
func (s *Server) CreateSignal(w http.ResponseWriter, r *http.Request) {
	request, err := decodeJSONObject(r)
	if err != nil {
		writeJSON(w, http.StatusOK, response.Error("Invalid JSON request body", nil))
		return
	}
	writeJSON(w, http.StatusOK, s.createSignal(request))
}

func (s *Server) createSignal(request map[string]any) response.Response {
	for _, field := range signalRequiredFields {
		if _, ok := request[field]; !ok {
			return response.Error(messages.SignalValueMissing(field), nil)
		}
	}

	id := request["id"]
	featureID := request["feature_id"]

	maxVersion, err := s.checkSignalExists(id, featureID)
	if err != nil {
		return response.Error("Failed to create signal in database", nil)
	}
	newVersion := maxVersion + 1

	log.Printf("Creating signal %v with version %d", id, newVersion)

	_, err = s.DB.ExecuteWrite(
		s.SignalQ.CreateSignal(),
		id,
		request["name"],
		newVersion,
		request["description"],
		featureID,
		request["feature_version"],
		request["threshold"],
		request["severity_level"],
		request["user"],
	)
	if err != nil {
		return response.Error("Failed to create signal in database", nil)
	}

	return response.Success(messages.SignalCreated(
		id, featureID, request["feature_version"], request["threshold"], request["severity_level"],
	), nil)
}

// checkSignalExists returns the current max version for (signalID, featureID),
// or 0 if no rows exist yet.
func (s *Server) checkSignalExists(signalID, featureID any) (int64, error) {
	row, err := s.DB.ExecuteQueryOne(s.SignalQ.RetrieveSignalVersion(), signalID, featureID)
	if err != nil {
		return 0, err
	}
	if row == nil || row["max_version"] == nil {
		return 0, nil
	}
	return toInt64(row["max_version"]), nil
}

// GetSignalInfoByFeature handles GET /api/signal/info/{feature_id}.
func (s *Server) GetSignalInfoByFeature(w http.ResponseWriter, r *http.Request) {
	featureID := r.PathValue("feature_id")
	writeJSON(w, http.StatusOK, s.getSignals(s.SignalQ.RetrieveSignalActive(), featureID))
}

// GetSignalInfoByID handles GET /api/signal/info/id/{signal_id}.
func (s *Server) GetSignalInfoByID(w http.ResponseWriter, r *http.Request) {
	signalID := r.PathValue("signal_id")
	writeJSON(w, http.StatusOK, s.getSignals(s.SignalQ.RetrieveSignalByID(), signalID))
}

func (s *Server) getSignals(query, param string) response.Response {
	rows, err := s.DB.ExecuteQuery(query, param)
	if err != nil {
		return response.Error("Failed to retrieve signals from database", nil)
	}

	if len(rows) == 0 {
		return response.Success("No active signals found", map[string]any{
			"signals": []map[string]any{}, "count": 0,
		})
	}

	return response.Success("Signals retrieved successfully", map[string]any{
		"signals": rows, "count": len(rows),
	})
}
