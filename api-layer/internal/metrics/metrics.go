// Package metrics exposes Prometheus instrumentation for the Operator360
// API: HTTP request counters/latencies/in-flight gauges (via Middleware) and
// database connection pool stats (via RegisterDBStats), served over the
// standard /metrics scrape endpoint (via Handler).
package metrics

import (
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	requestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "http_requests_total",
			Help: "Total number of HTTP requests processed, labeled by method, route and status code.",
		},
		[]string{"method", "path", "status"},
	)

	requestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_request_duration_seconds",
			Help:    "HTTP request latency in seconds, labeled by method, route and status code.",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"method", "path", "status"},
	)

	requestsInFlight = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "http_requests_in_flight",
			Help: "Number of HTTP requests currently being served.",
		},
	)

	responseSize = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "http_response_size_bytes",
			Help:    "Size of HTTP responses in bytes, labeled by method, route and status code.",
			Buckets: prometheus.ExponentialBuckets(100, 10, 6),
		},
		[]string{"method", "path", "status"},
	)
)

// Handler returns the Prometheus scrape handler to mount at /metrics.
func Handler() http.Handler {
	return promhttp.Handler()
}

// Middleware instruments every request handled by next with request count,
// latency and response-size metrics. It must wrap the top-level
// *http.ServeMux so that r.Pattern (populated by ServeMux.ServeHTTP once it
// matches a route) is available when metrics are recorded, keeping label
// cardinality bounded to registered routes (e.g. "/api/signal/info/id/{signal_id}")
// rather than exploding per unique ID.
func Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestsInFlight.Inc()
		defer requestsInFlight.Dec()

		start := time.Now()
		sw := &statusWriter{ResponseWriter: w, status: http.StatusOK}

		next.ServeHTTP(sw, r)

		path := routeLabel(r)
		status := strconv.Itoa(sw.status)

		requestsTotal.WithLabelValues(r.Method, path, status).Inc()
		requestDuration.WithLabelValues(r.Method, path, status).Observe(time.Since(start).Seconds())
		responseSize.WithLabelValues(r.Method, path, status).Observe(float64(sw.bytes))
	})
}

// routeLabel returns the registered route pattern for r (e.g.
// "/api/signal/info/{feature_id}") rather than the raw URL path, so the
// "path" label stays low-cardinality even for parameterized routes.
// ServeMux.ServeHTTP sets r.Pattern to "METHOD /path"; the method prefix is
// stripped here since it's already carried by the "method" label.
func routeLabel(r *http.Request) string {
	pattern := r.Pattern
	if pattern == "" {
		return r.URL.Path
	}
	return strings.TrimPrefix(pattern, r.Method+" ")
}

// statusWriter wraps http.ResponseWriter to capture the status code and
// response size written by the underlying handler.
type statusWriter struct {
	http.ResponseWriter
	status      int
	bytes       int
	wroteHeader bool
}

func (sw *statusWriter) WriteHeader(status int) {
	if sw.wroteHeader {
		return
	}
	sw.wroteHeader = true
	sw.status = status
	sw.ResponseWriter.WriteHeader(status)
}

func (sw *statusWriter) Write(b []byte) (int, error) {
	if !sw.wroteHeader {
		sw.WriteHeader(http.StatusOK)
	}
	n, err := sw.ResponseWriter.Write(b)
	sw.bytes += n
	return n, err
}
