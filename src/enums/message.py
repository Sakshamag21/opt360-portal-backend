

class SignalMessage:
    SIGNAL_CREATED = "Signal created successfully! ID: {id} FEATURE: {feature_id} VERSION: {feature_version} THRESHOLD: {threshold} SEVERITY: {severity_level}"
    SIGNAL_VALUE_MISSING = "Signal value is missing for {field}"
class FeatureMessage:
    FEATURE_RETRIEVED = "Feature retrieved successfully! {feature_id} version {version}"
    FEATTURE_NOT_FOUND = "Feature not found with ID: {feature_id} and version: {version}"
class ErrorMessage:
    FIELD_NOT_FOUND = "Field not found in request body: {field}"
    SIGNAL_NOT_FOUND = "Signal not found with ID: {signal_id} for Feature ID: {feature_id}"