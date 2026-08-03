package server

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"time"
)

// postJSON POSTs payload as JSON to url and returns the raw HTTP response
// (caller must close the body). A timeout of 0 means "no deadline", matching
// the handful of Python call sites that omit an explicit requests timeout.
func postJSON(client *http.Client, url string, timeout time.Duration, payload any) (*http.Response, error) {
	data, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	ctx := context.Background()
	if timeout > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, timeout)
		defer cancel()
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(data))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")

	return client.Do(req)
}
