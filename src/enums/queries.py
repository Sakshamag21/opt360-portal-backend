from config.config import config

class SignalQueries:
    # Get table name from config
    signal_table = config.get('database.tables.signal_registry', 'signals')
    
    # Format queries with actual table name
    CREATE_SIGNAL = f"""INSERT INTO {signal_table} 
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

    RETRIEVE_SIGNAL_VERSION = f"SELECT MAX(version) as max_version FROM {signal_table} WHERE id = %s AND feature_id = %s"
    RETRIEVE_SIGNAL_ACTIVE = f"SELECT * FROM {signal_table} WHERE feature_id = %s AND active = true"

    RETRIEVE_SIGNAL_BY_ID= f"SELECT * FROM {signal_table} where id= %s and active=true"
    
    
    

class FeatureQueries:
    # Get table name from config
    feature_table = config.get('database.tables.feature_registry', 'features')
    
    # Format queries with actual table name
    CREATE_FEATURE = f"""INSERT INTO {feature_table} 
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

    RETRIEVE_FEATURE_VERSION = f"SELECT MAX(version) as max_version FROM {feature_table} WHERE feature_id = %s"

    GET_FEATURE_METADATA_GLOBAL = f"SELECT feature_id as unique_id, feature_name as id, version, data_type, description, status, created_at, created_by, destination_table, update_window, dependent_features, is_risk, source_table FROM {feature_table} WHERE "
    
    
class OperatorDetailQueries:
    
    metadata_table= config.get('database.tables.opt_registry','opt_master')
    
    GET_OPERATOR_METADATA=f"""
    SELECT 
        id as opt_id,
        name,
        email,
        reg,
        reg_code,
        ea,
        ea_code,
        pincode,
        district,
        state,
        ro,
        machine_code,
        risk_score,
        last_sync_timestamp
    FROM {metadata_table}
    where id= %s
    """
    




