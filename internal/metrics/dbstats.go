package metrics

import (
	"database/sql"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

// StatsGetter is satisfied by *database.DB. It's defined here rather than
// imported to avoid a dependency from metrics (a low-level package) onto
// database.
type StatsGetter interface {
	Stats() sql.DBStats
}

// RegisterDBStats registers gauges that report the MySQL connection pool
// state on every scrape, sourced live from db.Stats() rather than sampled on
// an interval.
func RegisterDBStats(db StatsGetter) {
	const namespace = "db_pool"

	gauge := func(name, help string, value func(sql.DBStats) float64) {
		promauto.NewGaugeFunc(prometheus.GaugeOpts{
			Namespace: namespace,
			Name:      name,
			Help:      help,
		}, func() float64 {
			return value(db.Stats())
		})
	}

	gauge("open_connections", "Number of established connections, both in use and idle.", func(s sql.DBStats) float64 {
		return float64(s.OpenConnections)
	})
	gauge("in_use_connections", "Number of connections currently in use.", func(s sql.DBStats) float64 {
		return float64(s.InUse)
	})
	gauge("idle_connections", "Number of idle connections.", func(s sql.DBStats) float64 {
		return float64(s.Idle)
	})
	gauge("max_open_connections", "Maximum number of open connections allowed.", func(s sql.DBStats) float64 {
		return float64(s.MaxOpenConnections)
	})
	gauge("wait_count_total", "Total number of connections waited for.", func(s sql.DBStats) float64 {
		return float64(s.WaitCount)
	})
	gauge("wait_duration_seconds_total", "Total time blocked waiting for a new connection.", func(s sql.DBStats) float64 {
		return s.WaitDuration.Seconds()
	})
}
