package Profile

import (
	"context"
	"log"
	"net/http"
	"time"

	"opt360-portal-backend/db"
	"opt360-portal-backend/models"

	"github.com/gin-gonic/gin"
)

const submitterFeedbackQueryTimeout = 10 * time.Second

// feedbackEventsTable must match operatorFeedbackStats.go's table of the same
// name (handlers/OperatorDetailView) -- both read the same ClickHouse table,
// just filtered on a different column (user_ad_id here vs. opt_id there).
const feedbackEventsTable = "default.feedback_events"

// recentFeedbackLimit caps how many of the caller's own past submissions are
// returned for the profile page's "recent activity" list -- the count itself
// (TotalFeedbackCount) is always computed over every submission, unbounded.
const recentFeedbackLimit = 5

// RecentFeedbackItem is one row of the caller's own feedback submission
// history, for the profile page's recent-activity list.
type RecentFeedbackItem struct {
	EventID      string    `json:"event_id"`
	Timestamp    time.Time `json:"timestamp"`
	OptID        string    `json:"opt_id"`
	OperatorName string    `json:"operator_name"`
}

// GetMyFeedbackStats handles POST /api/profile/feedback_stats -- how many
// /feedback submissions (see handlers/Feedback/feedback.go) the calling user
// has made, read back out of ClickHouse the same way
// OperatorDetailView.GetOperatorFeedbackStats does, just filtered by the
// caller's own ad_id instead of one opt_id.
func GetMyFeedbackStats(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)

	start := time.Now()
	conn, err := db.GetClickHouseDB()
	if err != nil {
		log.Printf("[GetMyFeedbackStats] ClickHouse unavailable user=%s: %v", user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to fetch feedback stats", "details": err.Error()})
		return
	}

	query := `
SELECT event_id, ts, opt_id, operator_name
FROM ` + feedbackEventsTable + `
WHERE user_ad_id = ?
ORDER BY ts DESC
`

	ctx, cancel := context.WithTimeout(context.Background(), submitterFeedbackQueryTimeout)
	defer cancel()

	rows, err := conn.Query(ctx, query, user.ADID)
	if err != nil {
		log.Printf("[GetMyFeedbackStats] Query failed user=%s: %v", user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to fetch feedback stats", "details": err.Error()})
		return
	}
	defer rows.Close()

	distinctOperators := make(map[string]struct{})
	recent := make([]RecentFeedbackItem, 0, recentFeedbackLimit)
	total := 0

	for rows.Next() {
		var (
			eventID, optID, operatorName string
			ts                           time.Time
		)
		if err := rows.Scan(&eventID, &ts, &optID, &operatorName); err != nil {
			log.Printf("[GetMyFeedbackStats] Scan failed user=%s: %v", user.ADID, err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read feedback stats", "details": err.Error()})
			return
		}

		total++
		distinctOperators[optID] = struct{}{}
		if len(recent) < recentFeedbackLimit {
			// ORDER BY ts DESC -- the first recentFeedbackLimit rows are the
			// most recent submissions.
			recent = append(recent, RecentFeedbackItem{
				EventID:      eventID,
				Timestamp:    ts,
				OptID:        optID,
				OperatorName: operatorName,
			})
		}
	}
	if err := rows.Err(); err != nil {
		log.Printf("[GetMyFeedbackStats] Row iteration failed user=%s: %v", user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to read feedback stats", "details": err.Error()})
		return
	}

	log.Printf("[GetMyFeedbackStats] Served user=%s total=%d operators=%d (took %s)", user.ADID, total, len(distinctOperators), time.Since(start))
	c.JSON(http.StatusOK, gin.H{
		"total_feedback_count":     total,
		"distinct_operators_count": len(distinctOperators),
		"recent":                   recent,
	})
}
