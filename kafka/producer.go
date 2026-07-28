// Package kafka publishes portal domain events (currently just feedback
// submissions) to a Kafka topic. It's intentionally best-effort: if no
// broker/topic is configured (config.KafkaConfig.Enabled() == false), or a
// publish fails, callers should log and continue — a missing/unreachable
// Kafka cluster must never block the feedback S3 write it accompanies, since
// that write is the durable record and the event is a downstream notification.
package kafka

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"opt360-portal-backend/config"

	kafkago "github.com/segmentio/kafka-go"
	"github.com/segmentio/kafka-go/sasl"
	"github.com/segmentio/kafka-go/sasl/plain"
	"github.com/segmentio/kafka-go/sasl/scram"
)

var (
	writerOnce sync.Once
	writer     *kafkago.Writer
	writerErr  error
)

// FeedbackEvent is published to config.KafkaConfig.Topic whenever feedback
// (with or without evidence) is submitted via POST /api/feedback.
type FeedbackEvent struct {
	// EventID matches the last path segment of every S3 object this
	// submission wrote (feedback.json + any evidence files) — see
	// handlers/Feedback's feedbackBasePath — so the event and its S3
	// artifacts can be correlated.
	EventID   string    `json:"event_id"`
	EventType string    `json:"event_type"`
	Timestamp time.Time `json:"timestamp"`

	User struct {
		ADID           string `json:"ad_id"`
		Name           string `json:"name"`
		Email          string `json:"email,omitempty"`
		RegionalOffice string `json:"regional_office"`
	} `json:"user"`

	Operator struct {
		OptID          string `json:"opt_id"`
		Name           string `json:"name,omitempty"`
		RegionalOffice string `json:"regional_office,omitempty"`
		State          string `json:"state,omitempty"`
		District       string `json:"district,omitempty"`
	} `json:"operator"`

	Feedback interface{} `json:"feedback"`

	// EvidenceFiles maps each evidence category (e.g. "fraudulent",
	// "cloned_machine") to the S3 key it was uploaded to. Empty when no
	// evidence was attached.
	EvidenceFiles map[string]string `json:"evidence_files,omitempty"`

	// FeedbackFilePath is the S3 key of the feedback JSON record itself
	// (the existing /api/feedback S3 write, unrelated to evidence files).
	FeedbackFilePath string `json:"feedback_file_path"`
}

func getWriter() (*kafkago.Writer, error) {
	writerOnce.Do(func() {
		cfg := config.GetDefaultKafkaConfig()
		if !cfg.Enabled() {
			writerErr = fmt.Errorf("kafka not configured (OPT360_KAFKA_BROKERS/OPT360_KAFKA_TOPIC unset)")
			return
		}

		transport := &kafkago.Transport{}
		if cfg.SASLMechanism != "" {
			mechanism, err := saslMechanism(cfg)
			if err != nil {
				writerErr = err
				return
			}
			transport.SASL = mechanism
			transport.TLS = &tls.Config{}
		}

		writer = &kafkago.Writer{
			Addr:                   kafkago.TCP(cfg.BrokerList()...),
			Topic:                  cfg.Topic,
			Balancer:               &kafkago.LeastBytes{},
			Transport:              transport,
			AllowAutoTopicCreation: true,
			WriteTimeout:           5 * time.Second,
		}
	})
	return writer, writerErr
}

func saslMechanism(cfg config.KafkaConfig) (sasl.Mechanism, error) {
	switch cfg.SASLMechanism {
	case "plain":
		return plain.Mechanism{Username: cfg.SASLUsername, Password: cfg.SASLPassword}, nil
	case "scram-sha-256":
		return scram.Mechanism(scram.SHA256, cfg.SASLUsername, cfg.SASLPassword)
	case "scram-sha-512":
		return scram.Mechanism(scram.SHA512, cfg.SASLUsername, cfg.SASLPassword)
	default:
		return nil, fmt.Errorf("unsupported OPT360_KAFKA_SASL_MECHANISM %q (want plain | scram-sha-256 | scram-sha-512)", cfg.SASLMechanism)
	}
}

// PublishFeedbackEvent publishes event to the configured topic. Returns an
// error (never panics) when Kafka is unconfigured or the write fails —
// callers should log this and continue, not fail the request it accompanies.
func PublishFeedbackEvent(ctx context.Context, event FeedbackEvent) error {
	w, err := getWriter()
	if err != nil {
		return err
	}

	payload, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("marshal feedback event: %w", err)
	}

	writeCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	if err := w.WriteMessages(writeCtx, kafkago.Message{
		Key:   []byte(event.Operator.OptID),
		Value: payload,
	}); err != nil {
		return fmt.Errorf("publish feedback event: %w", err)
	}

	log.Printf("[kafka] published feedback event event_id=%s opt_id=%s user=%s", event.EventID, event.Operator.OptID, event.User.ADID)
	return nil
}
