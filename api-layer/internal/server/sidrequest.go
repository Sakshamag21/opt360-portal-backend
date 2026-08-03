package server

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"operator360-api/internal/response"
)

const dateLayout = "2006-01-02"

// sidsAllRequestBody mirrors routes.py's SidRequest pydantic model: opt_id
// and date are required, limit/page have defaults.
type sidsAllRequestBody struct {
	OptID *string `json:"opt_id"`
	Date  *string `json:"date"`
	Limit int     `json:"limit"`
	Page  int     `json:"page"`
}

// GetSidsAll handles POST /api/sid_details/sids/all.
func (s *Server) GetSidsAll(w http.ResponseWriter, r *http.Request) {
	var body sidsAllRequestBody
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeValidationError(w, "body", "Invalid JSON body")
		return
	}

	if body.OptID == nil {
		writeValidationError(w, "opt_id", "field required")
		return
	}
	if body.Date == nil {
		writeValidationError(w, "date", "field required")
		return
	}

	parsedDate, err := time.Parse(dateLayout, *body.Date)
	if err != nil {
		writeValidationError(w, "date", fmt.Sprintf("Invalid date format: '%s'. Expected format: YYYY-MM-DD", *body.Date))
		return
	}
	normalizedDate := parsedDate.Format(dateLayout)

	page := body.Page
	if page <= 0 {
		page = 1
	}

	// The original route (routes.py: get_sids_details) parses request.limit
	// via the pydantic model but then hardcodes limit = 50 regardless of
	// what was sent, so we mirror that verbatim here.
	const limit = 50

	writeJSON(w, http.StatusOK, s.safeGetAllSidsDate(*body.OptID, normalizedDate, limit, page))
}

// safeGetAllSidsDate wraps GetAllSidsDate with a panic recovery, mirroring
// the blanket try/except Exception around sid_details.get_all_sids_date in
// the original route handler.
func (s *Server) safeGetAllSidsDate(optID, date string, limit, page int) (result response.Response) {
	defer func() {
		if rec := recover(); rec != nil {
			log.Printf("Panic in GetAllSidsDate: %v", rec)
			result = response.Error(fmt.Sprintf("An unexpected error occurred: %v", rec), nil)
		}
	}()
	return s.GetAllSidsDate(optID, date, limit, page)
}
