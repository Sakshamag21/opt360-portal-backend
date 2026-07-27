// Package config loads runtime configuration from resources/config.yaml.
package config

import (
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

// RocksDBEndpoint describes a RocksDB-backed HTTP microservice.
type RocksDBEndpoint struct {
	Host     string `yaml:"host"`
	Port     int    `yaml:"port"`
	Endpoint string `yaml:"endpoint"`
}

// URL builds the full HTTP URL for this endpoint.
func (e RocksDBEndpoint) URL() string {
	return fmt.Sprintf("http://%s:%d%s", e.Host, e.Port, e.Endpoint)
}

type tables struct {
	FeatureRegistry string `yaml:"feature_registry"`
	SignalRegistry  string `yaml:"signal_registry"`
	OptRegistry     string `yaml:"opt_registry"`
}

type database struct {
	Host     string `yaml:"host"`
	Port     int    `yaml:"port"`
	Username string `yaml:"username"`
	Password string `yaml:"password"`
	Name     string `yaml:"name"`
	Tables   tables `yaml:"tables"`
}

// Config is the top-level configuration structure, mirroring resources/config.yaml.
type Config struct {
	Database             database        `yaml:"database"`
	RocksDB              RocksDBEndpoint `yaml:"rocksdb"`
	RocksDBSIDStore      RocksDBEndpoint `yaml:"rocksdb_sid_store"`
	RocksDBOperatorStore RocksDBEndpoint `yaml:"rocksdb_operator_store"`
}

// DBHost returns the configured database host (used by the health check).
func (c *Config) DBHost() string {
	return c.Database.Host
}

// DSN builds a go-sql-driver/mysql compatible data source name.
func (c *Config) DSN() string {
	return fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?parseTime=true",
		c.Database.Username, c.Database.Password,
		c.Database.Host, c.Database.Port, c.Database.Name)
}

// FeatureTable, SignalTable, OptTable expose the configured table names.
func (c *Config) FeatureTable() string {
	return orDefault(c.Database.Tables.FeatureRegistry, "features")
}
func (c *Config) SignalTable() string { return orDefault(c.Database.Tables.SignalRegistry, "signals") }
func (c *Config) OptTable() string    { return orDefault(c.Database.Tables.OptRegistry, "opt_master") }

func orDefault(v, def string) string {
	if v == "" {
		return def
	}
	return v
}

// Load reads and parses the YAML config file at path.
func Load(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("config file not found at %q: %w", path, err)
	}

	var cfg Config
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("failed to parse config file %q: %w", path, err)
	}

	return &cfg, nil
}
