
class SignalQueries:
    CREATE_SIGNAL = """INSERT INTO opt360_signals 
    (id,
    name,
    version,
    description,
    feature_id,
    feature_version,
    threshold,
    severity_level,
    created_by) 
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""

    RETRIEVE_SIGNAL_VERSION = "SELECT MAX(version) as max_version FROM opt360_signals WHERE id = %s AND feature_id = %s"
    RETRIEVE_SIGNAL_ACTIVE = "SELECT * FROM opt360_signals WHERE feature_id = %s and active = true"  


class FeatureQueries:
    CREATE_FEATURE = """INSERT INTO opt360_features 
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
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""

    RETRIEVE_FEATURE_VERSION = "SELECT MAX(version) as max_version FROM opt360_features WHERE feature_id = %s"

    GET_FEATURE_METADATA_GLOBAL = "SELECT feature_id as unique_id, feature_name as id, version, data_type, description, status, created_at, created_by, destination_table,update_window, dependent_features,is_risk,source_table FROM opt360_features WHERE "