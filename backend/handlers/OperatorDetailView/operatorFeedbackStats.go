package OperatorDetailView

import (
	"context"
	"log"
	"net/http"
	"time"

	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/gin-gonic/gin"
)

const operatorFeedbackQueryTimeout = 10 * time.Second

// feedbackEventsTable is the ClickHouse table a Kafka Engine + materialized
// view flattens backend/kafka's FeedbackEvent ("feedback_submitted", see
// kafka/producer.go) into, one row per feedback submission. Column names
// mirror the event's JSON one-for-one, nested objects joined with "_"
// (event.user.ad_id -> user_ad_id, event.feedback.verified_fraud_operator
// .verdict -> verified_fraud_operator_verdict, etc.) and "timestamp" -> ts.
// Adjust this file's query if the real materialized view names things
// differently.
const feedbackEventsTable = "default.feedback_events"

// feedbackCategories lists the five yes/no/not-set verdicts one feedback
// submission carries (see handlers/Feedback/feedback.go and
// OperatorFeedback.jsx), in submission-form order.
var feedbackCategories = []string{
	"verified_fraud_operator",
	"verified_legitimate_operator",
	"worked_with_cloned_machine",
	"unsystematic_biometric_capture",
	"packet_anomaly_identified",
}

// FeedbackRecord mirrors one row of feedbackEventsTable.
type FeedbackRecord struct {
	EventID          string            `json:"event_id"`
	Timestamp        time.Time         `json:"timestamp"`
	SubmittedByADID  string            `json:"submitted_by_ad_id"`
	SubmittedByName  string            `json:"submitted_by_name"`
	Verdicts         map[string]*bool  `json:"verdicts"`
	Remarks          map[string]string `json:"remarks"`
	FeedbackFilePath string            `json:"feedback_file_path"`
}

// CategoryStats counts, across every feedback submission for one operator,
// how many times a given verdict came back Yes / No / was left unset (null).
type CategoryStats struct {
	Yes   int `json:"yes"`
	No    int `json:"no"`
	Unset int `json:"unset"`
}

// GetOperatorFeedbackStatsFromClickHouse fetches every feedbackEventsTable
// row for optID, most recent submission first.
func GetOperatorFeedbackStatsFromClickHouse(optID string) ([]FeedbackRecord, error) {
	start := time.Now()
	defer func() {
		log.Printf("[ClickHouse][OperatorFeedbackStats] Completed in %s", time.Since(start))
	}()

	conn, err := db.GetClickHouseDB()
	if err != nil {
		log.Printf("[ClickHouse][OperatorFeedbackStats] ClickHouse unavailable: %v", err)
		return nil, err
	}

	query := `
SELECT
	event_id,
	ts,
	user_ad_id,
	user_name,
	verified_fraud_operator_verdict, verified_fraud_operator_remarks,
	verified_legitimate_operator_verdict, verified_legitimate_operator_remarks,
	worked_with_cloned_machine_verdict, worked_with_cloned_machine_remarks,
	unsystematic_biometric_capture_verdict, unsystematic_biometric_capture_remarks,
	packet_anomaly_identified_verdict, packet_anomaly_identified_remarks,
	feedback_file_path
FROM ` + feedbackEventsTable + `
WHERE opt_id = ?
ORDER BY ts DESC
`

	ctx, cancel := context.WithTimeout(context.Background(), operatorFeedbackQueryTimeout)
	defer cancel()

	log.Printf("[ClickHouse][OperatorFeedbackStats] -> querying %s for opt_id=%s at %s", feedbackEventsTable, optID, start.Format(time.RFC3339))

	rows, err := conn.Query(ctx, query, optID)
	if err != nil {
		log.Printf("[ClickHouse][OperatorFeedbackStats] Query failed: %v", err)
		return nil, err
	}
	defer rows.Close()

	records := make([]FeedbackRecord, 0)
	for rows.Next() {
		var (
			eventID, adID, name, feedbackFilePath string
			ts                                    time.Time
			fraudVerdict, legitVerdict            *bool
			clonedVerdict, biometricVerdict       *bool
			anomalyVerdict                        *bool
			fraudRemarks, legitRemarks            string
			clonedRemarks, biometricRemarks       string
			anomalyRemarks                        string
		)
		if err := rows.Scan(
			&eventID, &ts, &adID, &name,
			&fraudVerdict, &fraudRemarks,
			&legitVerdict, &legitRemarks,
			&clonedVerdict, &clonedRemarks,
			&biometricVerdict, &biometricRemarks,
			&anomalyVerdict, &anomalyRemarks,
			&feedbackFilePath,
		); err != nil {
			log.Printf("[ClickHouse][OperatorFeedbackStats] Scan failed: %v", err)
			return nil, err
		}

		records = append(records, FeedbackRecord{
			EventID:         eventID,
			Timestamp:       ts,
			SubmittedByADID: adID,
			SubmittedByName: name,
			Verdicts: map[string]*bool{
				"verified_fraud_operator":        fraudVerdict,
				"verified_legitimate_operator":   legitVerdict,
				"worked_with_cloned_machine":     clonedVerdict,
				"unsystematic_biometric_capture": biometricVerdict,
				"packet_anomaly_identified":      anomalyVerdict,
			},
			Remarks: map[string]string{
				"verified_fraud_operator":        fraudRemarks,
				"verified_legitimate_operator":   legitRemarks,
				"worked_with_cloned_machine":     clonedRemarks,
				"unsystematic_biometric_capture": biometricRemarks,
				"packet_anomaly_identified":      anomalyRemarks,
			},
			FeedbackFilePath: feedbackFilePath,
		})
	}
	if err := rows.Err(); err != nil {
		log.Printf("[ClickHouse][OperatorFeedbackStats] Row iteration failed: %v", err)
		return nil, err
	}

	log.Printf("[ClickHouse][OperatorFeedbackStats] <- %d rows for opt_id=%s (took %s)", len(records), optID, time.Since(start))
	return records, nil
}

// GetOperatorFeedbackStats handles GET /api/operator_feedback_stats,
// aggregating every ClickHouse feedback_events row for one operator into
// per-category yes/no/unset counts (for the profile page's feedback stats
// card) plus the full submission history (replacing the localStorage-only
// history OperatorDetailView.jsx currently keeps).
func GetOperatorFeedbackStats(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)

	optID := c.Query("opt_id")
	if optID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "opt_id query parameter is required"})
		return
	}

	records, err := GetOperatorFeedbackStatsFromClickHouse(optID)
	if err != nil {
		log.Printf("[GetOperatorFeedbackStats] ClickHouse query failed opt_id=%s user=%s: %v", optID, user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to fetch feedback stats", "details": err.Error()})
		return
	}

	categories := make(map[string]CategoryStats, len(feedbackCategories))
	for _, cat := range feedbackCategories {
		categories[cat] = CategoryStats{}
	}
	for _, rec := range records {
		for _, cat := range feedbackCategories {
			stat := categories[cat]
			switch v := rec.Verdicts[cat]; {
			case v == nil:
				stat.Unset++
			case *v:
				stat.Yes++
			default:
				stat.No++
			}
			categories[cat] = stat
		}
	}

	var latest *FeedbackRecord
	if len(records) > 0 {
		latest = &records[0] // ORDER BY ts DESC -- records[0] is most recent
	}

	log.Printf("[GetOperatorFeedbackStats] Serving opt_id=%s user=%s submissions=%d", optID, user.ADID, len(records))
	c.JSON(http.StatusOK, gin.H{
		"opt_id":               optID,
		"total_feedback_count": len(records),
		"categories":           categories,
		"latest":               latest,
		"history":              records,
	})
}
