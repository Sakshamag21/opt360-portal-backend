package server

import (
	"encoding/json"
	"log"
	"net/http"
	"strings"

	"operator360-api/internal/response"
)

// GetOperatorDetailsHTTP handles POST /api/opt_details/info.
// Body: {"operator_id": "<string>"}.
func (s *Server) GetOperatorDetailsHTTP(w http.ResponseWriter, r *http.Request) {
	request, err := decodeJSONObject(r)
	if err != nil {
		writeJSON(w, http.StatusOK, response.Error("Invalid JSON request body", nil))
		return
	}

	rawID, ok := request["operator_id"]
	if !ok {
		writeValidationError(w, "operator_id", "field required")
		return
	}
	operatorID, _ := rawID.(string)

	writeJSON(w, http.StatusOK, s.GetOperatorDetails(operatorID))
}

// GetOperatorDetails looks up operator metadata by operator_id, ported from
// src/opt_details/info.py. It is also called in-process by GetOperatorBySID.
func (s *Server) GetOperatorDetails(operatorID string) response.Response {
	rows, err := s.DB.ExecuteQuery(s.OperatorQ.GetOperatorMetadata(), strings.ToUpper(operatorID))
	if err != nil {
		log.Printf("Database query failed for Operator Id: %s", operatorID)
		return response.Error("Failed to retrieve Operator Details for operator_id:"+operatorID+" from database", nil)
	}

	if len(rows) == 0 {
		log.Printf("No operator found for Operator Id: %s", operatorID)
		return response.Success("No operator found for the Id", map[string]any{"operator": []map[string]any{}})
	}

	log.Printf("Retrieved Operator successfully for Operator Id: %s", operatorID)
	return response.Success("Operator retrieved successfully", map[string]any{"operator": rows})
}

// GetOperatorBySID handles GET /api/opt_details/sid/{sid}.
// It resolves a SID to an operator_id + pkt_type via the RocksDB `sid`
// endpoint, then fetches operator metadata in-process, ported from
// src/opt_details/get_sid.py.
func (s *Server) GetOperatorBySID(w http.ResponseWriter, r *http.Request) {
	sid := r.PathValue("sid")
	writeJSON(w, http.StatusOK, s.getOperatorBySID(sid))
}

func (s *Server) getOperatorBySID(sid string) response.Response {
	endpoint := s.Config.RocksDB
	if endpoint.Host == "" {
		return response.Error("RocksDB configuration missing", nil)
	}
	endpointURL := endpoint.URL()
	log.Printf("Connecting to RocksDB endpoint: %s", endpointURL)

	// No explicit timeout here, matching the original Python call site
	// (src/opt_details/get_sid.py), which also omitted one; the shared
	// HTTP client still applies its own default deadline.
	resp, err := postJSON(s.HTTPClient, endpointURL, 0, map[string]any{"sids": []string{sid}})
	if err != nil {
		log.Printf("Network error verification failed for SID %s: %v", sid, err)
		return response.Error("Network error: "+err.Error(), nil)
	}
	defer resp.Body.Close()

	var payload rocksDBBatchResponse
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return response.Error("Invalid JSON response from RocksDB", nil)
	}

	if payload.Status != "OK" || payload.Found != 1 || len(payload.Items) == 0 || len(payload.Items[0].Values) == 0 {
		return response.Error("SID "+sid+" not found in RocksDB", nil)
	}

	values := payload.Items[0].Values[0]
	optID, _ := values["opt_id"].(string)
	pktType := values["pkt_type"]

	operatorResp := s.GetOperatorDetails(optID)
	operators, _ := operatorResp.Data["operator"].([]map[string]any)
	if !operatorResp.Success || len(operators) == 0 {
		return response.Error("Failed to validate operator details for opt_id: "+optID, nil)
	}

	record := operators[0]
	record["pktType"] = pktType
	record["id"] = sid
	record["idType"] = "sid"

	return response.Success("Operator details retrieved successfully", map[string]any{"operator": operators})
}

// rocksDBBatchResponse mirrors the /sid/batch_get response shape.
type rocksDBBatchResponse struct {
	Status string `json:"status"`
	Found  int    `json:"found"`
	Items  []struct {
		Values []map[string]any `json:"values"`
	} `json:"items"`
}
