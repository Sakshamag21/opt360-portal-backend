package Feedback

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"path/filepath"
	"strings"
	"time"

	"opt360-portal-backend/config"
	"opt360-portal-backend/db"
	kafkaproducer "opt360-portal-backend/kafka"
	"opt360-portal-backend/models"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/service/s3"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

// evidenceMaxBytes caps a single evidence file — generous enough for a
// scanned PDF/photo, small enough to not let one request exhaust memory
// (files are read into memory before the S3 PutObject call).
const evidenceMaxBytes = 25 << 20 // 25 MiB

// SubmitFeedback handles POST /api/feedback. Accepts either:
//   - application/json — the original shape, no evidence (kept for
//     backward compatibility with any caller not yet sending files).
//   - multipart/form-data — a "feedback" field holding the same JSON
//     payload as a string, plus zero or more evidence files under field
//     names prefixed "evidence_" (e.g. "evidence_fraudulent"). Each
//     evidence file is uploaded to S3 alongside the existing feedback JSON
//     record, and a Kafka event carrying user/operator/feedback details
//     plus every evidence S3 path is published (best-effort — see
//     kafka.PublishFeedbackEvent).
func SubmitFeedback(c *gin.Context) {
	userInterface, exists := c.Get("user")
	if !exists {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "User not found in context"})
		return
	}
	user := userInterface.(*models.User)

	feedbackData, evidenceFiles, err := parseFeedbackRequest(c)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request", "details": err.Error()})
		return
	}

	optID, optIDExists := feedbackData["opt_id"].(string)
	if !optIDExists || optID == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "opt_id is required in request body"})
		return
	}

	// Operator-existence check only — the returned data_path is no longer
	// used for the feedback S3 location (see basePath below), which has its
	// own dedicated bucket/prefix convention independent of where the
	// operator's other files live.
	if _, err := db.GetDataPathByOptID(optID); err != nil {
		log.Printf("[SubmitFeedback] Operator lookup failed opt_id=%s user=%s: %v", optID, user.ADID, err)
		c.JSON(http.StatusNotFound, gin.H{
			"error":       "Operator not found",
			"operator_id": optID,
			"details":     err.Error(),
		})
		return
	}

	fbCfg := config.GetDefaultFeedbackConfig()
	s3Cfg := config.GetDefaultS3Config()
	s3Client, err := config.NewS3Client(s3Cfg)
	if err != nil {
		log.Printf("[SubmitFeedback] S3 client error user=%s: %v", user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to create S3 client", "details": err.Error()})
		return
	}

	// eventID uniquely identifies this submission — it's the last path
	// segment for every S3 object this request writes, and is republished
	// verbatim as the Kafka event's event_id so the two can be correlated.
	eventID := uuid.NewString()
	currentDate := time.Now().Format("2006_01_02")
	basePath := feedbackBasePath(fbCfg.Prefix, optID, user.ADID, currentDate, eventID)

	// ── Upload evidence files (if any) first, so their S3 paths can be
	// recorded both in the feedback JSON and the Kafka event. ──
	evidencePaths := map[string]string{}
	for category, file := range evidenceFiles {
		key := basePath + "evidence_" + category + "_" + sanitizeFilename(file.Filename)

		log.Printf("[SubmitFeedback] Uploading evidence key=%s bucket=%s category=%s user=%s", key, fbCfg.BucketName, category, user.ADID)
		if _, err := s3Client.PutObject(&s3.PutObjectInput{
			Bucket:      aws.String(fbCfg.BucketName),
			Key:         aws.String(key),
			Body:        bytes.NewReader(file.Bytes),
			ContentType: aws.String(file.ContentType),
		}); err != nil {
			log.Printf("[SubmitFeedback] Evidence upload failed key=%s user=%s: %v", key, user.ADID, err)
			c.JSON(http.StatusInternalServerError, gin.H{
				"error":    "Failed to upload evidence file to S3",
				"category": category,
				"details":  err.Error(),
			})
			return
		}
		evidencePaths[category] = key
	}
	if len(evidencePaths) > 0 {
		feedbackData["evidence_files"] = evidencePaths
	}
	feedbackData["event_id"] = eventID

	fileName := basePath + "feedback.json"

	jsonData, err := json.MarshalIndent(feedbackData, "", "  ")
	if err != nil {
		log.Printf("[SubmitFeedback] JSON marshal error user=%s: %v", user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to marshal feedback data to JSON", "details": err.Error()})
		return
	}

	log.Printf("[SubmitFeedback] Uploading feedback key=%s bucket=%s user=%s", fileName, fbCfg.BucketName, user.ADID)
	if _, err = s3Client.PutObject(&s3.PutObjectInput{
		Bucket:      aws.String(fbCfg.BucketName),
		Key:         aws.String(fileName),
		Body:        bytes.NewReader(jsonData),
		ContentType: aws.String("application/json"),
	}); err != nil {
		log.Printf("[SubmitFeedback] S3 upload failed key=%s user=%s: %v", fileName, user.ADID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to upload feedback file to S3", "details": err.Error()})
		return
	}

	log.Printf("[SubmitFeedback] Feedback stored key=%s user=%s", fileName, user.ADID)

	publishFeedbackEvent(c, user, optID, eventID, feedbackData, evidencePaths, fileName)

	c.JSON(http.StatusOK, gin.H{
		"message":         "Feedback submitted successfully",
		"regional_office": user.RegionalOffice,
		"operator_id":     optID,
		"event_id":        eventID,
		"bucket":          fbCfg.BucketName,
		"file_path":       fileName,
		"evidence_files":  evidencePaths,
		"date":            currentDate,
		"submitted_by":    user.ADID,
	})
}

// feedbackBasePath builds the per-submission S3 key prefix:
// <prefix>/<optID>/<adID>/<date>/<eventID>/ — prefix (from config, optional)
// leads, then a strict opt_id/ad_id/date/event_id hierarchy so every
// submission's files (feedback.json + any evidence) land together under one
// unique folder.
func feedbackBasePath(prefix, optID, adID, date, eventID string) string {
	segments := []string{}
	if p := strings.Trim(prefix, "/"); p != "" {
		segments = append(segments, p)
	}
	segments = append(segments, optID, adID, date, eventID)
	return strings.Join(segments, "/") + "/"
}

// evidenceFile holds one parsed multipart evidence upload, read fully into
// memory (bounded by evidenceMaxBytes) so it can be sent to S3 with a known
// Content-Length via bytes.NewReader.
type evidenceFile struct {
	Filename    string
	ContentType string
	Bytes       []byte
}

// parseFeedbackRequest supports both a plain JSON body (no evidence) and a
// multipart/form-data body (a "feedback" field with the same JSON payload as
// a string, plus optional "evidence_<category>" file fields).
func parseFeedbackRequest(c *gin.Context) (map[string]interface{}, map[string]evidenceFile, error) {
	contentType := c.ContentType()

	if !strings.HasPrefix(contentType, "multipart/form-data") {
		var feedbackData map[string]interface{}
		if err := c.ShouldBindJSON(&feedbackData); err != nil {
			return nil, nil, fmt.Errorf("invalid JSON in request body: %w", err)
		}
		return feedbackData, nil, nil
	}

	form, err := c.MultipartForm()
	if err != nil {
		return nil, nil, fmt.Errorf("invalid multipart form: %w", err)
	}

	feedbackJSON := ""
	if values := form.Value["feedback"]; len(values) > 0 {
		feedbackJSON = values[0]
	}
	if feedbackJSON == "" {
		return nil, nil, fmt.Errorf("multipart request must include a 'feedback' field")
	}

	var feedbackData map[string]interface{}
	if err := json.Unmarshal([]byte(feedbackJSON), &feedbackData); err != nil {
		return nil, nil, fmt.Errorf("invalid JSON in 'feedback' field: %w", err)
	}

	evidenceFiles := map[string]evidenceFile{}
	for fieldName, headers := range form.File {
		category := strings.TrimPrefix(fieldName, "evidence_")
		if category == fieldName || len(headers) == 0 {
			continue // not an evidence_* field
		}

		header := headers[0]
		if header.Size > evidenceMaxBytes {
			return nil, nil, fmt.Errorf("evidence file %q exceeds the %d MB limit", header.Filename, evidenceMaxBytes>>20)
		}

		file, err := header.Open()
		if err != nil {
			return nil, nil, fmt.Errorf("opening evidence file %q: %w", header.Filename, err)
		}
		buf, err := io.ReadAll(file)
		file.Close()
		if err != nil {
			return nil, nil, fmt.Errorf("reading evidence file %q: %w", header.Filename, err)
		}

		contentType := header.Header.Get("Content-Type")
		if contentType == "" {
			contentType = "application/octet-stream"
		}

		evidenceFiles[category] = evidenceFile{
			Filename:    header.Filename,
			ContentType: contentType,
			Bytes:       buf,
		}
	}

	return feedbackData, evidenceFiles, nil
}

// sanitizeFilename strips any path components and keeps the S3 key
// predictable — the client-supplied filename is untrusted.
func sanitizeFilename(name string) string {
	name = filepath.Base(name)
	if name == "" || name == "." || name == string(filepath.Separator) {
		return "evidence"
	}
	return name
}

// publishFeedbackEvent builds and publishes the Kafka event for this
// submission. Best-effort: a Kafka failure is logged, never surfaced to the
// caller — the feedback S3 write above is already durable.
func publishFeedbackEvent(c *gin.Context, user *models.User, optID, eventID string, feedbackData map[string]interface{}, evidencePaths map[string]string, feedbackFilePath string) {
	event := kafkaproducer.FeedbackEvent{
		EventID:          eventID,
		EventType:        "feedback_submitted",
		Timestamp:        time.Now().UTC(),
		Feedback:         feedbackData["feedback"],
		EvidenceFiles:    evidencePaths,
		FeedbackFilePath: feedbackFilePath,
	}
	event.User.ADID = user.ADID
	event.User.Name = user.Name
	event.User.RegionalOffice = user.RegionalOffice
	if user.Email != nil {
		event.User.Email = *user.Email
	}

	event.Operator.OptID = optID
	if name, ok := feedbackData["operator_name"].(string); ok {
		event.Operator.Name = name
	}
	if ro, ok := feedbackData["regional_office"].(string); ok {
		event.Operator.RegionalOffice = ro
	}
	if state, ok := feedbackData["opt_state"].(string); ok {
		event.Operator.State = state
	}
	if district, ok := feedbackData["opt_district"].(string); ok {
		event.Operator.District = district
	}

	if err := kafkaproducer.PublishFeedbackEvent(c.Request.Context(), event); err != nil {
		log.Printf("[SubmitFeedback] Kafka publish skipped/failed opt_id=%s user=%s: %v", optID, user.ADID, err)
	}
}
