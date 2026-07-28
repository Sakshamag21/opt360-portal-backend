package models

// AnomalyReportRequest represents the request body for reporting an anomaly
type AnomalyReportRequest struct {
	EID              string        `json:"eid"`
	AnomalyCategory  string        `json:"anomaly_category"`
	AnomalyType      []AnomalyType `json:"anomaly_type"`
	DateCreated      string        `json:"date_created"`
	EnrolmentType    string        `json:"enrolnment_type"`
	OperatorID       string        `json:"operator_id"`
	OptID            string        `json:"opt_id"`
	OptState         string        `json:"opt_state"`
	OptDistrict      string        `json:"opt_district"`
	PktSource        string        `json:"pkt_source"`
	PktUpdtType      []string      `json:"pkt_updt_type"`
	Remarks          []string      `json:"remarks"`
	SID              string        `json:"sid"`
	StationMachineCode string      `json:"station_machine_code"`
	StationNo        string        `json:"station_no"`
}

// AnomalyType represents an anomaly type in the request
type AnomalyType struct {
	AnomalyCategory string       `json:"anomaly_category"`
	AnomalyCode     string       `json:"anomaly_code"`
	AnomalyName     string       `json:"anomaly_name"`
	Reason          ReasonDetail `json:"reason"`
}

// ReasonDetail represents the reason details for an anomaly
type ReasonDetail struct {
	ErrorCategory string `json:"error_category"`
}

// MarkAnomaly represents a record in the mark_anomaly table
type MarkAnomaly struct {
	EID                string `db:"eid"`
	AnomalyCategory    string `db:"anomaly_category"`
	AnomalyCode        string `db:"anomaly_code"`
	AnomalyName        string `db:"anomaly_name"`
	ErrorCategory      string `db:"error_category"`
	DateCreated        string `db:"date_created"`
	EnrolmentType      string `db:"enrolnment_type"`
	OptDistrict        string `db:"opt_district"`
	OptState           string `db:"opt_state"`
	OptID              string `db:"opt_id"`
	PktSource          string `db:"pkt_source"`
	PktUpdtType        string `db:"pkt_updt_type"`
	Remarks            string `db:"remarks"`
	StationMachineCode string `db:"station_machine_code"`
	StationNo          string `db:"station_no"`
}
