// Package queries builds parameterized SQL query strings using table names
// resolved from configuration, mirroring src/enums/queries.py from the
// original Python service.
package queries

import "fmt"

// SignalQueries holds SQL templates for the signal registry table.
type SignalQueries struct {
	Table string
}

// NewSignalQueries builds signal query templates for the given table name.
func NewSignalQueries(table string) SignalQueries {
	return SignalQueries{Table: table}
}

func (q SignalQueries) CreateSignal() string {
	return fmt.Sprintf(`INSERT INTO %s
	(id,
	name,
	version,
	description,
	feature_id,
	feature_version,
	threshold,
	severity_level,
	created_by)
	VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`, q.Table)
}

func (q SignalQueries) RetrieveSignalVersion() string {
	return fmt.Sprintf("SELECT MAX(version) as max_version FROM %s WHERE id = ? AND feature_id = ?", q.Table)
}

func (q SignalQueries) RetrieveSignalActive() string {
	return fmt.Sprintf("SELECT * FROM %s WHERE feature_id = ? AND active = true", q.Table)
}

func (q SignalQueries) RetrieveSignalByID() string {
	return fmt.Sprintf("SELECT * FROM %s where id= ? and active=true", q.Table)
}

// FeatureQueries holds SQL templates for the feature registry table.
type FeatureQueries struct {
	Table string
}

// NewFeatureQueries builds feature query templates for the given table name.
func NewFeatureQueries(table string) FeatureQueries {
	return FeatureQueries{Table: table}
}

func (q FeatureQueries) CreateFeature() string {
	return fmt.Sprintf(`INSERT INTO %s
	(feature_id,
	feature_name,
	data_type,
	description,
	status,
	destination_table,
	update_window,
	version,
	dependent_features,
	is_risk,
	is_active,
	source_table,
	created_by)
	VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`, q.Table)
}

func (q FeatureQueries) RetrieveFeatureVersion() string {
	return fmt.Sprintf("SELECT MAX(version) as max_version FROM %s WHERE feature_id = ?", q.Table)
}

// GetFeatureMetadataGlobal returns the base SELECT ending in "WHERE " so
// callers can append dynamic filters (see server.GetFeatureInfo).
func (q FeatureQueries) GetFeatureMetadataGlobal() string {
	return fmt.Sprintf(
		"SELECT feature_id as unique_id, feature_name as id, version, data_type, description, "+
			"status, created_at, created_by, destination_table, update_window, dependent_features, "+
			"is_risk, source_table FROM %s WHERE ", q.Table,
	)
}

// OperatorDetailQueries holds SQL templates for the operator registry table.
type OperatorDetailQueries struct {
	Table string
}

// NewOperatorDetailQueries builds operator query templates for the given table name.
func NewOperatorDetailQueries(table string) OperatorDetailQueries {
	return OperatorDetailQueries{Table: table}
}

func (q OperatorDetailQueries) GetOperatorMetadata() string {
	return fmt.Sprintf(`
	SELECT
		id as optId,
		name,
		email,
		reg,
		reg_code as regCode,
		ea,
		ea_code as eaCode,
		pincode,
		district,
		state,
		ro,
		'' as machineCode,
		risk_score as riskScore
	FROM %s
	where id= ?
	`, q.Table)
}
