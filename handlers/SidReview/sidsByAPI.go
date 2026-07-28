package SidReview

import (
    "bytes"
    "encoding/json"
    "fmt"
    "log"
    "net/http"
    "time"

    "opt360-portal-backend/config"
)

func fetchSIDsFromAPI(optID, dateStr string, limit, page int) ([]PacketResponse, int, error) {
    cfg, err := config.LoadConfig()
    if err != nil {
        return nil, 0, fmt.Errorf("failed to load config: %w", err)
    }

    baseURL := cfg.SIDStore.BaseURL
    // Update the URL to the new endpoint
    apiURL := fmt.Sprintf("%s/api/sid_details/sids/all", baseURL)
    client := &http.Client{Timeout: time.Duration(cfg.SIDStore.TimeoutSeconds) * time.Second}

    // Prepare the JSON payload expected by GetSidsAll
    reqPayload := struct {
        OptID *string `json:"opt_id"`
        Date  *string `json:"date"`
        Limit int     `json:"limit"`
        Page  int     `json:"page"`
    }{
        OptID: &optID,
        Limit: limit,
        Page:  page,
    }
    // Only set Date if dateStr is not empty, otherwise let it be nil to trigger
    // the server's validation (or omit it if you prefer to handle it differently)
    if dateStr != "" {
        reqPayload.Date = &dateStr
    }

    jsonData, err := json.Marshal(reqPayload)
    if err != nil {
        return nil, 0, fmt.Errorf("failed to marshal request body: %w", err)
    }

    callStart := time.Now()
    log.Printf("[fetchSIDsFromAPI] -> POST %s opt_id=%s date=%s limit=%d page=%d at %s", apiURL, optID, dateStr, limit, page, callStart.Format(time.RFC3339))

    var lastErr error
    maxRetries := 10
    var sidResp SIDResponse

    for attempt := 1; attempt <= maxRetries; attempt++ {
        attemptStart := time.Now()
        log.Printf("[fetchSIDsFromAPI] Attempt %d/%d for opt_id=%s -> %s", attempt, maxRetries, optID, apiURL)

        // Create a new POST request with the JSON body
        req, err := http.NewRequest(http.MethodPost, apiURL, bytes.NewBuffer(jsonData))
        if err != nil {
            lastErr = err
            log.Printf("[fetchSIDsFromAPI] Attempt %d failed to create request for opt_id=%s: %v (took %s)", attempt, optID, err, time.Since(attemptStart))
            if attempt < maxRetries {
                time.Sleep(time.Duration(attempt) * time.Second) // Exponential backoff
            }
            continue
        }
        req.Header.Set("Content-Type", "application/json")

        resp, err := client.Do(req)
        if err != nil {
            lastErr = err
            log.Printf("[fetchSIDsFromAPI] Attempt %d failed for opt_id=%s: %v (took %s)", attempt, optID, err, time.Since(attemptStart))
            if attempt < maxRetries {
                time.Sleep(time.Duration(attempt) * time.Second) // Exponential backoff
            }
            continue
        }

        if resp.StatusCode != http.StatusOK {
            resp.Body.Close()
            lastErr = fmt.Errorf("SID API returned non-200 status: %d", resp.StatusCode)
            log.Printf("[fetchSIDsFromAPI] Attempt %d failed for opt_id=%s: %v (took %s)", attempt, optID, lastErr, time.Since(attemptStart))
            if resp.StatusCode >= 400 && resp.StatusCode < 500 {
                break // client error (e.g. validation) — retrying won't help
            }
            if attempt < maxRetries {
                time.Sleep(time.Duration(attempt) * time.Second)
            }
            continue
        }

        if err := json.NewDecoder(resp.Body).Decode(&sidResp); err != nil {
            resp.Body.Close()
            lastErr = err
            log.Printf("[fetchSIDsFromAPI] Attempt %d failed to decode response for opt_id=%s: %v (took %s)", attempt, optID, err, time.Since(attemptStart))
            if attempt < maxRetries {
                time.Sleep(time.Duration(attempt) * time.Second)
            }
            continue
        }
        resp.Body.Close()

        log.Printf("[fetchSIDsFromAPI] Attempt %d responded for opt_id=%s in %s (status=%d)", attempt, optID, time.Since(attemptStart), resp.StatusCode)

        if !sidResp.Success || len(sidResp.Data.SIDs) == 0 {
            lastErr = fmt.Errorf("no data returned from API")
            log.Printf("[fetchSIDsFromAPI] Attempt %d returned no data for opt_id=%s. Full response: %+v", attempt, optID, sidResp)
            break // Don't retry if the API successfully responds with no data
        }

        lastErr = nil
        break // Success, break out of retry loop
    }

    log.Printf("[fetchSIDsFromAPI] <- %s opt_id=%s finished in %s (success=%t)", apiURL, optID, time.Since(callStart), lastErr == nil)

    if lastErr != nil {
        return nil, 0, fmt.Errorf("failed to fetch SIDs from API after %d attempts: %w", maxRetries, lastErr)
    }

    // Map API response to our standard PacketResponse struct
    mappedData := make([]PacketResponse, 0, len(sidResp.Data.SIDs))
    for _, item := range sidResp.Data.SIDs {
        pkt := PacketResponse{
            Eid:                item.SID,
            OptID:              optID, // Default to requested opt_id
            EnrollmentType:     "",
            StationNo:          "",
            StationMachineCode: "",
            DateCreated:        "",
            PktSource:          "API",
            AnomalyType:        []interface{}{}, // API doesn't provide this
        }

        // Safely dereference pointers from API response
        if item.OptID != nil {
            pkt.OptID = *item.OptID
        }
        if item.PktType != nil {
            pkt.EnrollmentType = *item.PktType
        }
        if item.StationID != nil {
            pkt.StationNo = *item.StationID
        }
        if item.MachineCode != nil {
            pkt.StationMachineCode = *item.MachineCode
        }
        if item.CreatedAt != nil {
            pkt.DateCreated = *item.CreatedAt
        }

        mappedData = append(mappedData, pkt)
    }

    return mappedData, sidResp.Data.TotalSIDs, nil
}