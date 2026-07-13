package config

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/credentials"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/s3"
)

// S3Config holds S3 connection configuration
type S3Config struct {
	BucketName string `json:"bucket_name"`
	AccessKey  string `json:"access_key"`
	SecretKey  string `json:"secret_key"`
	Endpoint   string `json:"endpoint"`
	Region     string `json:"region"`
}

// DatabaseConfig holds one database's connection configuration, including its
// own connection-pool tuning. Pool settings are per-database deliberately —
// this app's three MySQL databases see very different traffic shapes (the
// portal DB is light auth lookups; the opt360 DB carries the heavy
// operator-search/listing traffic), so one shared pool size wouldn't fit all
// three well. All fields (including pool settings) are individually
// overridable via env vars — see applyEnvOverrides.
type DatabaseConfig struct {
	Host     string `json:"host"`
	Port     int    `json:"port"`
	User     string `json:"user"`
	Password string `json:"password"`
	Database string `json:"database"`

	// Connection pool tuning. Zero values fall back to sane defaults in Load()
	// (25 / 5 / 5 minutes) rather than Go's database/sql default of "unlimited
	// open connections", which is rarely what you actually want in production.
	MaxOpenConns           int `json:"max_open_conns"`
	MaxIdleConns           int `json:"max_idle_conns"`
	ConnMaxLifetimeSeconds int `json:"conn_max_lifetime_seconds"`
}

// ConnMaxLifetime returns ConnMaxLifetimeSeconds as a time.Duration.
func (d DatabaseConfig) ConnMaxLifetime() time.Duration {
	return time.Duration(d.ConnMaxLifetimeSeconds) * time.Second
}

// DatabasesConfig groups this app's MySQL connections. Grouped (rather than
// top-level Config fields, one of them ambiguously named "database") so the
// shape reads clearly and maps cleanly onto separate ConfigMap/Secret pairs
// when this moves to stage/prod.
//
// The opt360 (operator360/opt_master) connection is deliberately NOT here —
// it's hardcoded in main.go instead, since it lives on a different host than
// config was resolving it to and needed to be pinned directly. See main.go's
// db.InitDB call.
type DatabasesConfig struct {
	Portal DatabaseConfig `json:"portal"` // strot_services — auth users + anomaly reports
	UID    DatabaseConfig `json:"uid"`    // uidmasterv1_1 — UID/user identity data
}

type SIDStoreConfig struct {
	BaseURL        string `json:"base_url"`
	TimeoutSeconds int    `json:"timeout_seconds"`
}

type ClickHouseConfig struct {
	Host     string `json:"host"`
	Port     int    `json:"port"`
	Database string `json:"database"`
	Username string `json:"username"`
	Password string `json:"password"`
	// Secure enables TLS for the HTTP protocol connection (i.e. https, typically
	// port 8443 on managed/prod clusters instead of the default 8123); leaving
	// it false against a TLS-only cluster will fail the connection test even
	// though the host is network-reachable.
	Secure bool `json:"secure"`
}

type TrinoConfig struct {
	Host     string `json:"host"`
	Port     int    `json:"port"`
	Catalog  string `json:"catalog"`
	Schema   string `json:"schema"`
	Username string `json:"username"`
}

type ServerConfig struct {
	Host string `json:"host"`
	Port int    `json:"port"`
}

// TableRef identifies one table's location: the schema/database it lives in
// and its table name, both supplied independently via config since staging
// and prod can each use different values for either. Deliberately not
// derived from DatabasesConfig — the database a table lives in is a property
// of that table, not necessarily the same as any one connection's own
// "default" database.
type TableRef struct {
	Database string `json:"database"`
	Table    string `json:"table"`
}

// String returns the schema-qualified reference (e.g. "operator360.opt_master")
// to drop directly into a FROM/JOIN clause. If Database is unset, returns the
// bare table name and relies on the query's connection default database.
func (t TableRef) String() string {
	if t.Database == "" {
		return t.Table
	}
	return t.Database + "." + t.Table
}

// TablesConfig holds the location of tables used across the app's SQL
// queries. Staging and prod have different database and table names for the
// same logical data, so these must never be hardcoded string literals in
// handler/db code — every query should build its FROM/JOIN clause from these
// fields instead.
//
// opt_master is deliberately NOT here — its table reference is hardcoded to
// "operator360.opt_master" directly at each query call site, alongside its
// hardcoded connection in main.go. See main.go's db.InitDB call.
type TablesConfig struct {
	PortalUsers TableRef `json:"portal_users"` // opt360-portal-ui user accounts
	MarkAnomaly TableRef `json:"mark_anomaly"` // reported anomaly records
}

// Config holds the entire configuration structure.
type Config struct {
	Server     ServerConfig     `json:"server"`
	S3         S3Config         `json:"s3"`
	Databases  DatabasesConfig  `json:"databases"`
	Tables     TablesConfig     `json:"tables"`
	SIDStore   SIDStoreConfig   `json:"sid_store"`
	ClickHouse ClickHouseConfig `json:"clickhouse"`
	Trino      TrinoConfig      `json:"trino"`
}

var (
	config     *Config
	configOnce sync.Once
	configErr  error
)

// Load reads configuration from the given file path (if present), then layers
// OPT360_* environment variable overrides on top, then validates and applies
// defaults.
//
// The file is optional: in local dev it's normally config.json; in
// stage/prod, where this moves to a Kubernetes ConfigMap (non-secret fields)
// + Secret (credentials) injected as env vars, no file needs to exist at all
// — a missing file just means every field comes from the environment
// instead. This lets the same binary and the same Config struct serve both
// deployment styles without code changes.
func Load(path string) (*Config, error) {
	var cfg Config

	file, err := os.Open(path)
	switch {
	case err == nil:
		defer file.Close()
		if decodeErr := json.NewDecoder(file).Decode(&cfg); decodeErr != nil {
			return nil, fmt.Errorf("failed to decode config file '%s': %w", path, decodeErr)
		}
	case os.IsNotExist(err):
		log.Printf("[config] %s not found — relying entirely on OPT360_* environment variables", path)
	default:
		return nil, fmt.Errorf("failed to open config file '%s': %w", path, err)
	}

	applyEnvOverrides(&cfg)

	// ── Defaults ────────────────────────────────────────────────────────────
	if cfg.Server.Port == 0 {
		cfg.Server.Port = 8080
	}
	if cfg.SIDStore.BaseURL == "" {
		cfg.SIDStore.BaseURL = "http://localhost:9001"
	}
	if cfg.SIDStore.TimeoutSeconds <= 0 {
		cfg.SIDStore.TimeoutSeconds = 15
	}
	if cfg.ClickHouse.Port == 0 {
		cfg.ClickHouse.Port = 8123
	}
	if cfg.Trino.Port == 0 {
		cfg.Trino.Port = 8080
	}
	applyDatabaseDefaults(&cfg.Databases.Portal)
	applyDatabaseDefaults(&cfg.Databases.UID)
	applyTableRefDefaults(&cfg.Tables.PortalUsers, "strot_services", "opt360_portal_users")
	applyTableRefDefaults(&cfg.Tables.MarkAnomaly, "strot_services", "mark_anomaly")

	// ── Validation ──────────────────────────────────────────────────────────
	if cfg.S3.AccessKey == "" || cfg.S3.SecretKey == "" || cfg.S3.Endpoint == "" {
		return nil, fmt.Errorf("s3 access_key, secret_key, and endpoint must be set (config.json 's3' section or OPT360_S3_* env vars)")
	}
	if cfg.S3.BucketName == "" {
		return nil, fmt.Errorf("s3 bucket_name must be set (config.json 's3' section or OPT360_S3_BUCKET_NAME)")
	}
	if err := validateDatabase("portal", cfg.Databases.Portal); err != nil {
		return nil, err
	}
	if err := validateDatabase("uid", cfg.Databases.UID); err != nil {
		return nil, err
	}

	return &cfg, nil
}

func applyTableRefDefaults(ref *TableRef, defaultDatabase, defaultTable string) {
	if ref.Database == "" {
		ref.Database = defaultDatabase
	}
	if ref.Table == "" {
		ref.Table = defaultTable
	}
}

func applyDatabaseDefaults(db *DatabaseConfig) {
	if db.Port == 0 {
		db.Port = 3306
	}
	if db.MaxOpenConns <= 0 {
		db.MaxOpenConns = 25
	}
	if db.MaxIdleConns <= 0 {
		db.MaxIdleConns = 5
	}
	if db.ConnMaxLifetimeSeconds <= 0 {
		db.ConnMaxLifetimeSeconds = 300
	}
}

func validateDatabase(name string, db DatabaseConfig) error {
	if db.User == "" || db.Password == "" || db.Host == "" {
		return fmt.Errorf(
			"databases.%s: user, password, and host must be set (config.json or OPT360_DB_%s_* env vars)",
			name, strings.ToUpper(name),
		)
	}
	return nil
}

// applyEnvOverrides layers OPT360_* environment variables over whatever was
// loaded from the config file. Any field left unset in the environment keeps
// its file-loaded (or zero) value. This is what lets a Kubernetes ConfigMap
// (mounted as env vars) and Secret (credentials, also as env vars) fully
// replace config.json in stage/prod without touching this struct or its
// callers.
func applyEnvOverrides(cfg *Config) {
	cfg.Server.Host = envString("OPT360_SERVER_HOST", cfg.Server.Host)
	cfg.Server.Port = envInt("OPT360_SERVER_PORT", cfg.Server.Port)

	cfg.S3.Endpoint = envString("OPT360_S3_ENDPOINT", cfg.S3.Endpoint)
	cfg.S3.BucketName = envString("OPT360_S3_BUCKET_NAME", cfg.S3.BucketName)
	cfg.S3.Region = envString("OPT360_S3_REGION", cfg.S3.Region)
	cfg.S3.AccessKey = envString("OPT360_S3_ACCESS_KEY", cfg.S3.AccessKey)
	cfg.S3.SecretKey = envString("OPT360_S3_SECRET_KEY", cfg.S3.SecretKey)

	applyDatabaseEnvOverrides(&cfg.Databases.Portal, "OPT360_DB_PORTAL")
	applyDatabaseEnvOverrides(&cfg.Databases.UID, "OPT360_DB_UID")

	applyTableRefEnvOverrides(&cfg.Tables.PortalUsers, "OPT360_TABLE_PORTAL_USERS")
	applyTableRefEnvOverrides(&cfg.Tables.MarkAnomaly, "OPT360_TABLE_MARK_ANOMALY")

	cfg.SIDStore.BaseURL = envString("OPT360_SID_STORE_BASE_URL", cfg.SIDStore.BaseURL)
	cfg.SIDStore.TimeoutSeconds = envInt("OPT360_SID_STORE_TIMEOUT_SECONDS", cfg.SIDStore.TimeoutSeconds)

	cfg.ClickHouse.Host = envString("OPT360_CLICKHOUSE_HOST", cfg.ClickHouse.Host)
	cfg.ClickHouse.Port = envInt("OPT360_CLICKHOUSE_PORT", cfg.ClickHouse.Port)
	cfg.ClickHouse.Database = envString("OPT360_CLICKHOUSE_DATABASE", cfg.ClickHouse.Database)
	cfg.ClickHouse.Username = envString("OPT360_CLICKHOUSE_USERNAME", cfg.ClickHouse.Username)
	cfg.ClickHouse.Password = envString("OPT360_CLICKHOUSE_PASSWORD", cfg.ClickHouse.Password)
	cfg.ClickHouse.Secure = envBool("OPT360_CLICKHOUSE_SECURE", cfg.ClickHouse.Secure)

	cfg.Trino.Host = envString("OPT360_TRINO_HOST", cfg.Trino.Host)
	cfg.Trino.Port = envInt("OPT360_TRINO_PORT", cfg.Trino.Port)
	cfg.Trino.Catalog = envString("OPT360_TRINO_CATALOG", cfg.Trino.Catalog)
	cfg.Trino.Schema = envString("OPT360_TRINO_SCHEMA", cfg.Trino.Schema)
	cfg.Trino.Username = envString("OPT360_TRINO_USERNAME", cfg.Trino.Username)
}

// applyTableRefEnvOverrides applies <prefix>_DATABASE and <prefix>_TABLE for
// one table. prefix is always one of the 3 literals passed below — never
// derived from user input.
func applyTableRefEnvOverrides(ref *TableRef, prefix string) {
	ref.Database = envString(prefix+"_DATABASE", ref.Database)
	ref.Table = envString(prefix+"_TABLE", ref.Table)
}

// applyDatabaseEnvOverrides applies OPT360_<prefix>_{HOST,PORT,USER,PASSWORD,
// DATABASE,MAX_OPEN_CONNS,MAX_IDLE_CONNS,CONN_MAX_LIFETIME_SECONDS} for one
// database. prefix is always one of the 3 literals passed below — never
// derived from user input.
func applyDatabaseEnvOverrides(db *DatabaseConfig, prefix string) {
	db.Host = envString(prefix+"_HOST", db.Host)
	db.Port = envInt(prefix+"_PORT", db.Port)
	db.User = envString(prefix+"_USER", db.User)
	db.Password = envString(prefix+"_PASSWORD", db.Password)
	db.Database = envString(prefix+"_DATABASE", db.Database)
	db.MaxOpenConns = envInt(prefix+"_MAX_OPEN_CONNS", db.MaxOpenConns)
	db.MaxIdleConns = envInt(prefix+"_MAX_IDLE_CONNS", db.MaxIdleConns)
	db.ConnMaxLifetimeSeconds = envInt(prefix+"_CONN_MAX_LIFETIME_SECONDS", db.ConnMaxLifetimeSeconds)
}

func envString(key, current string) string {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		return v
	}
	return current
}

func envInt(key string, current int) int {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
		log.Printf("[config] %s=%q is not a valid integer, ignoring", key, v)
	}
	return current
}

func envBool(key string, current bool) bool {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		if b, err := strconv.ParseBool(v); err == nil {
			return b
		}
		log.Printf("[config] %s=%q is not a valid boolean, ignoring", key, v)
	}
	return current
}

// LoadConfig loads configuration from config.json (if present) plus OPT360_*
// env var overrides, and caches the result for the life of the process.
func LoadConfig() (*Config, error) {
	configOnce.Do(func() {
		config, configErr = Load("config.json")
	})

	return config, configErr
}

// GetDefaultS3Config returns the S3 configuration from the loaded config.
func GetDefaultS3Config() S3Config {
	cfg, err := LoadConfig()
	if err != nil {
		fmt.Println("Error loading config:", err)
		return S3Config{}
	}

	return cfg.S3
}

// GetTablesConfig returns the table configuration from the loaded config.
func GetTablesConfig() TablesConfig {
	cfg, err := LoadConfig()
	if err != nil {
		fmt.Println("Error loading config:", err)
		return TablesConfig{
			PortalUsers: TableRef{Database: "strot_services", Table: "opt360_portal_users"},
			MarkAnomaly: TableRef{Database: "strot_services", Table: "mark_anomaly"},
		}
	}
	return cfg.Tables
}

// PortalUsersTableRef returns the schema-qualified opt360_portal_users table
// reference (e.g. "strot_services.opt360_portal_users"), built entirely from
// config.tables.portal_users.
func PortalUsersTableRef() string {
	return GetTablesConfig().PortalUsers.String()
}

// MarkAnomalyTableRef returns the schema-qualified mark_anomaly table
// reference (e.g. "strot_services.mark_anomaly"), built entirely from
// config.tables.mark_anomaly.
func MarkAnomalyTableRef() string {
	return GetTablesConfig().MarkAnomaly.String()
}

// NewS3Client creates a new S3 client with the given configuration
func NewS3Client(cfg S3Config) (*s3.S3, error) {
	sess, err := session.NewSession(&aws.Config{
		Region:           aws.String(cfg.Region),
		Endpoint:         aws.String(cfg.Endpoint),
		S3ForcePathStyle: aws.Bool(true),
		Credentials:      credentials.NewStaticCredentials(cfg.AccessKey, cfg.SecretKey, ""),
	})
	if err != nil {
		return nil, err
	}

	return s3.New(sess), nil
}
