
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

    RETRIEVE_SIGNAL = "SELECT MAX(version) as max_version FROM opt360_signals WHERE id = %s AND feature_id = %s"