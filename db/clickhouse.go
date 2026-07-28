package db

import (
	"context"
	"crypto/tls"
	"fmt"
	"log"
	"net"
	"strconv"
	"sync"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/ClickHouse/clickhouse-go/v2/lib/driver"
)

const (
	chPingMaxRetryCount = 3
	chPingRetrySleep    = 2 * time.Second
	chDialTimeout       = 5 * time.Second
)

var (
	chDB     driver.Conn
	chDBOnce sync.Once
)

type ClickHouseConfig struct {
	Host     string
	Port     int
	Database string
	Username string
	Password string
	Secure   bool
}

// InitClickHouseDB initialises the ClickHouse connection. Non-fatal: errors are
// logged but do not stop the server. Call GetClickHouseDB later to check if the
// client is available.
//
// Uses the HTTP protocol (Options.Protocol = clickhouse.HTTP), not the native
// TCP protocol — some managed/proxied ClickHouse deployments only expose the
// HTTP interface (default port 8123, or 8443 for https) rather than the
// native port (9000/9440), and the native protocol will fail the connection
// test even when the host is otherwise reachable.
//
// This uses clickhouse.Open (the native driver.Conn), not clickhouse.OpenDB
// (the database/sql wrapper). OpenDB refuses to run at all if MaxOpenConns/
// MaxIdleConns/ConnMaxLifetime are set on Options — every query fails with
// "cannot connect. invalid settings" — and in general has been the less
// reliable path for this cluster. clickhouse.Open + an explicit Ping retry
// loop is the pattern confirmed working against the same infra elsewhere, so
// this mirrors that rather than continuing to debug OpenDB blind.
func InitClickHouseDB(cfg ClickHouseConfig) {
	chDBOnce.Do(func() {
		if cfg.Host == "" {
			log.Printf("[ClickHouse] Skipping init: no host configured")
			return
		}

		addr := net.JoinHostPort(cfg.Host, strconv.Itoa(cfg.Port))

		// Pre-flight raw TCP reachability check, independent of the ClickHouse
		// wire protocol/TLS/auth handshake, purely to disambiguate failure causes
		// in the logs: a dial failure here means network/firewall; a dial success
		// followed by a Ping failure below means the network path is fine and the
		// problem is protocol, TLS, or credentials.
		if rawConn, dialErr := net.DialTimeout("tcp", addr, chDialTimeout); dialErr != nil {
			log.Printf("[ClickHouse] TCP dial to %s FAILED (network/firewall issue): %v", addr, dialErr)
		} else {
			rawConn.Close()
			log.Printf("[ClickHouse] TCP reachable at %s", addr)
		}

		opts := &clickhouse.Options{
			Addr: []string{addr},
			Auth: clickhouse.Auth{
				Database: cfg.Database,
				Username: cfg.Username,
				Password: cfg.Password,
			},
			TLS:         nil,
			Protocol:    clickhouse.HTTP,
			DialTimeout: chDialTimeout,
		}
		if cfg.Secure {
			opts.TLS = &tls.Config{}
		}

		conn, err := clickhouse.Open(opts)
		if err != nil {
			log.Printf("[ClickHouse] Open FAILED (%s, secure=%v): %v", addr, cfg.Secure, err)
			return
		}

		for attempt := 0; attempt < chPingMaxRetryCount; attempt++ {
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			err = conn.Ping(ctx)
			cancel()
			if err == nil {
				break
			}
			log.Printf("[ClickHouse] Ping attempt %d/%d failed: %v", attempt+1, chPingMaxRetryCount, err)
			if attempt+1 == chPingMaxRetryCount {
				log.Printf("[ClickHouse] Connection test FAILED (%s, secure=%v) after %d attempts: %v", addr, cfg.Secure, chPingMaxRetryCount, err)
				if !cfg.Secure {
					log.Printf("[ClickHouse] Hint: if the TCP dial above succeeded but every ping still failed, the cluster may require TLS on the HTTP port (https, typically 8443) — set clickhouse.secure=true in config.json")
				}
				return
			}
			time.Sleep(chPingRetrySleep)
		}

		chDB = conn
		log.Printf("[ClickHouse] Connection established (%s/%s, secure=%v)", addr, cfg.Database, cfg.Secure)
	})
}

// GetClickHouseDB returns the ClickHouse client, or an error if it was never
// successfully initialised.
func GetClickHouseDB() (driver.Conn, error) {
	if chDB == nil {
		return nil, fmt.Errorf("ClickHouse client not available (connection failed or not initialised)")
	}
	return chDB, nil
}

// CloseClickHouseDB closes the ClickHouse connection.
func CloseClickHouseDB() {
	if chDB != nil {
		chDB.Close()
	}
}
