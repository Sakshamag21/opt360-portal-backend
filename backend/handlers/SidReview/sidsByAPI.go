package SidReview

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "log"
    "math/rand"
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
    apiURL := fmt.Sprintf("%s/api/sid_details/sids/all", baseURL)
    client := &http.Client{Timeout: time.Duration(cfg.SIDStore.TimeoutSeconds) * time.Second}

    reqPayload := struct {
        OptID    *string `json:"opt_id"`
        Date     *string `json:"date"`
        PageSize int     `json:"page_size"`
        Page     int     `json:"page"`
    }{
        OptID:    &optID,
        PageSize: limit,
        Page:     page,
    }
    if dateStr != "" {
        d := dateStr // copy to avoid aliasing surprises
        reqPayload.Date = &d
    }

    jsonData, err := json.Marshal(reqPayload)
    if err != nil {
        return nil, 0, fmt.Errorf("failed to marshal request body: %w", err)
    }

    callStart := time.Now()
    log.Printf("[fetchSIDsFromAPI] -> POST %s opt_id=%s date=%s limit=%d page=%d at %s",
        apiURL, optID, dateStr, limit, page, callStart.Format(time.RFC3339))

    const maxRetries = 10
    var lastErr error
    var sidResp SIDResponse // declared here…

    for attempt := 1; attempt <= maxRetries; attempt++ {
        attemptStart := time.Now()
        log.Printf("[fetchSIDsFromAPI] Attempt %d/%d for opt_id=%s", attempt, maxRetries, optID)

        // ✅ RESET on every attempt so partial decodes can't leak across retries
        sidResp = SIDResponse{}

        req, err := http.NewRequest(http.MethodPost, apiURL, bytes.NewBuffer(jsonData))
        if err != nil {
            lastErr = err
            log.Printf("[fetchSIDsFromAPI] attempt %d create-req failed: %v", attempt, err)
            sleepBackoff(attempt)
            continue
        }
        req.Header.Set("Content-Type", "application/json")

        resp, err := client.Do(req)
        if err != nil {
            lastErr = err
            log.Printf("[fetchSIDsFromAPI] attempt %d do failed: %v", attempt, err)
            sleepBackoff(attempt)
            continue
        }

        // ✅ Capture body for debugging
        bodyBytes, readErr := io.ReadAll(io.LimitReader(resp.Body, 10<<20)) // 10MB cap
        resp.Body.Close()
        if readErr != nil {
            lastErr = readErr
            log.Printf("[fetchSIDsFromAPI] attempt %d body read failed: %v", attempt, readErr)
            sleepBackoff(attempt)
            continue
        }

        if resp.StatusCode != http.StatusOK {
            lastErr = fmt.Errorf("SID API returned status %d", resp.StatusCode)
            log.Printf("[fetchSIDsFromAPI] attempt %d non-200 status=%d body=%s",
                attempt, resp.StatusCode, truncate(string(bodyBytes), 500))
            if resp.StatusCode >= 400 && resp.StatusCode < 500 {
                break // client error — retrying won't help
            }
            sleepBackoff(attempt)
            continue
        }

        if err := json.Unmarshal(bodyBytes, &sidResp); err != nil {
            lastErr = err
            log.Printf("[fetchSIDsFromAPI] attempt %d decode failed: %v body=%s",
                attempt, err, truncate(string(bodyBytes), 500))
            sleepBackoff(attempt)
            continue
        }

        log.Printf("[fetchSIDsFromAPI] attempt %d ok in %s success=%t total=%d got=%d",
            attempt, time.Since(attemptStart), sidResp.Success,
            sidResp.Data.TotalSIDs, len(sidResp.Data.SIDs))

        if !sidResp.Success {
            lastErr = fmt.Errorf("api returned success=false: %s",
                truncate(string(bodyBytes), 500))
            break // explicit failure — don't retry
        }

        // ✅ Retry on empty result — this is the key fix for intermittent empties
        if len(sidResp.Data.SIDs) == 0 && sidResp.Data.TotalSIDs > 0 {
            lastErr = fmt.Errorf("api returned 0 SIDs but total=%d (likely replica lag)",
                sidResp.Data.TotalSIDs)
            log.Printf("[fetchSIDsFromAPI] attempt %d empty-result retry: %v", attempt, lastErr)
            if attempt < maxRetries {
                sleepBackoff(attempt)
                continue
            }
            break
        }

        lastErr = nil
        break
    }

    log.Printf("[fetchSIDsFromAPI] <- opt_id=%s finished in %s success=%t got=%d",
        optID, time.Since(callStart), lastErr == nil, len(sidResp.Data.SIDs))

    if lastErr != nil {
        return nil, 0, fmt.Errorf("failed to fetch SIDs after %d attempts: %w", maxRetries, lastErr)
    }

    mappedData := make([]PacketResponse, 0, len(sidResp.Data.SIDs))
    for _, item := range sidResp.Data.SIDs {
        pkt := PacketResponse{
            Eid:                item.SID,
            OptID:              optID,
            AnomalyType:        []interface{}{},
        }
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
        if item.PktSource != nil {
            pkt.PktSource = *item.PktSource
        }
        mappedData = append(mappedData, pkt)
    }

    return mappedData, sidResp.Data.TotalSIDs, nil
}

func sleepBackoff(attempt int) {
    // real exponential backoff with jitter
    base := time.Duration(1<<uint(attempt-1)) * time.Second
    if base > 30*time.Second {
        base = 30 * time.Second
    }
    jitter := time.Duration(rand.Intn(250)) * time.Millisecond
    time.Sleep(base + jitter)
}

func truncate(s string, n int) string {
    if len(s) <= n {
        return s
    }
    return s[:n] + "…(truncated)"
}