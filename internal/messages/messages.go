// Package messages centralizes user-facing message templates.
package messages

import "fmt"

// SignalCreated formats the success message for signal creation.
func SignalCreated(id, featureID, featureVersion, threshold, severityLevel any) string {
	return fmt.Sprintf(
		"Signal created successfully! ID: %v FEATURE: %v VERSION: %v THRESHOLD: %v SEVERITY: %v",
		id, featureID, featureVersion, threshold, severityLevel,
	)
}

// SignalValueMissing formats the message for a missing required signal field.
func SignalValueMissing(field string) string {
	return fmt.Sprintf("Signal value is missing for %s", field)
}

// FeatureRetrieved formats the success message for feature retrieval.
func FeatureRetrieved(featureID, version any) string {
	return fmt.Sprintf("Feature retrieved successfully! %v version %v", featureID, version)
}

// FeatureNotFound formats the message for a feature lookup miss.
func FeatureNotFound(featureID, version any) string {
	return fmt.Sprintf("Feature not found with ID: %v and version: %v", featureID, version)
}

// FieldNotFound formats a validation error message for a missing request field.
func FieldNotFound(field string) string {
	return fmt.Sprintf("Field not found in request body: %s", field)
}

// SignalNotFound formats the message for a signal lookup miss.
func SignalNotFound(signalID, featureID any) string {
	return fmt.Sprintf("Signal not found with ID: %v for Feature ID: %v", signalID, featureID)
}
