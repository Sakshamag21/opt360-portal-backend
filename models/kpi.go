package models

type KPIResponse struct {
	HighRiskCount          int                 `json:"high_risk_count"`
	HighestRiskOpt         HighestRiskOperator `json:"highest_risk_opt"`
	LowRiskCount           int                 `json:"low_risk_count"`
	MedRiskCount           int                 `json:"med_risk_count"`
	MostCommonAnomalyCode  string              `json:"most_common_anomaly_code"`
	MostCommonAnomalyGroup string              `json:"most_common_anomaly_group"`
	MostCommonAnomalyName  string              `json:"most_common_anomaly_name"`
	OptRO                  string              `json:"opt_ro"`
	Top10Operators         []TopOperator       `json:"top_10_opt"`
}

// RORiskDistResponse is the top-level response for /api/ro_risk_dist.
// Data maps RO -> risk_bucket -> count. Bucket names are whatever
// db.GetRiskBuckets() has cached from opt_master (not a fixed field list),
// so a new bucket (e.g. "Critical") appears automatically with no struct
// change.
type RORiskDistResponse struct {
	Data           map[string]map[string]int `json:"data"`
	RegionalOffice string                    `json:"regional_office"`
	RequestedBy    string                    `json:"requested_by"`
}

type HighestRiskOperator struct {
	OptID     string  `json:"opt_id"`
	OptName   string  `json:"opt_name"`
	RiskScore float64 `json:"opt_risk_score"`
}

type TopOperator struct {
	ActiveStatus   float64        `json:"active_status"`
	OptDistrict    string         `json:"opt_district"`
	OptEA          string         `json:"opt_ea"`
	OptID          string         `json:"opt_id"`
	OptName        string         `json:"opt_name"`
	OptReg         string         `json:"opt_reg"`
	OptRiskScore   float64        `json:"opt_risk_score"`
	OptRO          string         `json:"opt_ro"`
	OptState       string         `json:"opt_state"`
	PacketsPerDay  float64        `json:"pkts_per_day"`
	Rank           int            `json:"rn"`
	OptEmail       string         `json:"opt_email"`
	OptMobile      string         `json:"opt_mobile"`
	MachineDetails MachineDetails `json:"machine_details"`
}

type MachineDetails struct {
	LastSyncTime string `json:"last_sync_time"`
	MachineCode  string `json:"machine_code"`
	StationId    string `json:"station_id"`
}
