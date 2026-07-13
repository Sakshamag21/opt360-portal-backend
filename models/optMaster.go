package models

import "time"

// OptMaster represents a row from data_platform.opt_master table
type OptMaster struct {
	ID                string     `json:"id"`
	UID               string     `json:"uid"`
	Name              string     `json:"name"`
	Phone             string     `json:"phone"`
	Email             string     `json:"email"`
	Reg               *string    `json:"reg"`
	RegCode           *string    `json:"reg_code"`
	EA                *string    `json:"ea"`
	EACode            *string    `json:"ea_code"`
	RO                *string    `json:"ro"`
	RiskScore         *float64   `json:"risk_score"`
	RiskBucket        *string    `json:"risk_bucket"`
	CenterName        *string    `json:"center_name"`
	CenterID          *string    `json:"center_id"`
	CenterAddress     *string    `json:"center_address"`
	Pincode           *string    `json:"pincode"`
	VTC               *string    `json:"vtc"`
	SubDistrict       *string    `json:"sub_district"`
	District          *string    `json:"district"`
	State             *string    `json:"state"`
	Latitude          *string    `json:"latitude"`
	Longitude         *string    `json:"longitude"`
	Altitude          *string    `json:"altitude"`
	MachineCode       *string    `json:"machine_code"`
	ClientVersion     *string    `json:"client_version"`
	ClientType        *string    `json:"client_type"`
	LastSyncTimestamp *time.Time `json:"last_sync_timestamp"`
	DataPath          *string    `json:"data_path"`
	UpdatedAt         *time.Time `json:"updated_at"`
}

// OptMasterListResponse wraps a paginated list of OptMaster records
type OptMasterListResponse struct {
	Data       []OptMaster `json:"data"`
	Total      int         `json:"total"`
	Page       int         `json:"page"`
	PageSize   int         `json:"page_size"`
	TotalPages int         `json:"total_pages"`
	RiskBucket string      `json:"risk_bucket"`
}

// OperatorSearchRequest is the POST body for /api/operator_search.
// It replaces the old operator_list / active_operator_list / inactive_operator_list /
// high_risk_operator / med_risk_operator / low_risk_operator / operator_list_with_risk /
// filter_operator_list endpoints with one unified, filter-parameterized search.
//
// RO is not access-restricted: it defaults to the caller's own regional office when
// omitted, but any value may be supplied to view another RO's operators (viewing is
// not scoped by role/group — only feedback submission is RO-restricted).
//
// Sourced entirely from operator360.opt_master — no cross-cluster UID-DB join
// (see docs/VIEW_OPERATORS_REDESIGN_PLAN.md). RegCode/EACode are exact-match
// filters on opt_master.reg_code/ea_code (the View Operators UI's typeahead
// shows the name but searches by code); Reg/EA remain available as name-based
// filters for any other consumer that wants substring-free name matching.
type OperatorSearchRequest struct {
	RO         string `json:"ro"`
	State      string `json:"state"`
	District   string `json:"district"`
	ID         string `json:"id"`
	EA         string `json:"ea"`
	EACode     string `json:"ea_code"`
	Reg        string `json:"reg"`
	RegCode    string `json:"reg_code"`
	RiskBucket string `json:"risk_bucket"`
	Status     string `json:"status"` // "active" | "inactive", from opt_master.is_active directly
	SortBy     string `json:"sort_by"`
	SortDir    string `json:"sort_dir"`
	Page       int    `json:"page"`
	PageSize   int    `json:"page_size"`
}

// SearchOperator is the projection returned by /api/operator_search.
type SearchOperator struct {
	ID                string     `json:"id"`
	UID               string     `json:"uid"`
	Name              string     `json:"name"`
	Phone             string     `json:"phone"`
	Email             string     `json:"email"`
	RiskScore         *float64   `json:"risk_score"`
	RiskBucket        *string    `json:"risk_bucket"`
	Reg               *string    `json:"reg"`
	RegCode           *string    `json:"reg_code"`
	EA                *string    `json:"ea"`
	EACode            *string    `json:"ea_code"`
	RO                *string    `json:"ro"`
	District          *string    `json:"district"`
	State             *string    `json:"state"`
	LastSyncTimestamp *time.Time `json:"last_sync_timestamp"`
	DataPath          *string    `json:"data_path"`
	Status            *string    `json:"status"`
}

// OperatorSearchAppliedFilters records which filters were active in the request,
// including the resolved RO (explicit override or the caller's default).
type OperatorSearchAppliedFilters struct {
	RO         string `json:"ro"`
	State      string `json:"state,omitempty"`
	District   string `json:"district,omitempty"`
	ID         string `json:"id,omitempty"`
	EA         string `json:"ea,omitempty"`
	EACode     string `json:"ea_code,omitempty"`
	Reg        string `json:"reg,omitempty"`
	RegCode    string `json:"reg_code,omitempty"`
	RiskBucket string `json:"risk_bucket,omitempty"`
	Status     string `json:"status,omitempty"`
	SortBy     string `json:"sort_by,omitempty"`
	SortDir    string `json:"sort_dir,omitempty"`
}

// OperatorSearchResponse is the top-level response for /api/operator_search.
type OperatorSearchResponse struct {
	Data           []SearchOperator             `json:"data"`
	Total          int                          `json:"total"`
	Page           int                          `json:"page"`
	PageSize       int                          `json:"page_size"`
	TotalPages     int                          `json:"total_pages"`
	AppliedFilters OperatorSearchAppliedFilters `json:"applied_filters"`
}

// NameCode is a (display name, search code) pair — used for the Registrar/EA
// typeahead filters in View Operators.
type NameCode struct {
	Name string `json:"name"`
	Code string `json:"code"`
}

// OperatorFiltersRequest is the POST body for /api/operator_filters.
// RO is optional; when set, the registrar/ea/risk_bucket lists are scoped to
// that RO instead of being global.
type OperatorFiltersRequest struct {
	RO string `json:"ro"`
}

// OperatorFiltersResponse is the response for /api/operator_filters — everything
// needed to populate the View Operators filter UI, sourced live from opt_master.
type OperatorFiltersResponse struct {
	RegionalOffices []string   `json:"regional_offices"`
	Registrars      []NameCode `json:"registrars"`
	EAs             []NameCode `json:"eas"`
	RiskBuckets     []string   `json:"risk_buckets"`
}
