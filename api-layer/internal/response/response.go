// Package response defines the standard {success, message, data} JSON envelope
// returned by every handler.
package response

// Response is the standard API response envelope.
type Response struct {
	Success bool           `json:"success"`
	Message string         `json:"message"`
	Data    map[string]any `json:"data"`
}

// Success builds a successful response. A nil data map is normalized to an
// empty object so the JSON shape is always consistent.
func Success(message string, data map[string]any) Response {
	if data == nil {
		data = map[string]any{}
	}
	return Response{Success: true, Message: message, Data: data}
}

// Error builds a failed response.
func Error(message string, data map[string]any) Response {
	if data == nil {
		data = map[string]any{}
	}
	return Response{Success: false, Message: message, Data: data}
}
