package db

import (
	"database/sql"
	"fmt"
	"log"
	"sync"

	_ "github.com/trinodb/trino-go-client/trino"
)

var (
	trinoDB     *sql.DB
	trinoDBOnce sync.Once
)

type TrinoConfig struct {
	Host     string
	Port     int
	Catalog  string
	Schema   string
	Username string
}

func InitTrinoDB(cfg TrinoConfig) {
	trinoDBOnce.Do(func() {
		dsn := fmt.Sprintf(
			"http://%s@%s:%d?catalog=%s&schema=%s",
			cfg.Username, cfg.Host, cfg.Port, cfg.Catalog, cfg.Schema,
		)

		db, err := sql.Open("trino", dsn)
		if err != nil {
			log.Printf("[Trino] Failed to open connection: %v", err)
			return
		}

		if err := db.Ping(); err != nil {
			log.Printf("[Trino] Connection test FAILED (%s:%d): %v", cfg.Host, cfg.Port, err)
			db.Close()
			return
		}

		trinoDB = db
		log.Printf("[Trino] Connection established (%s:%d catalog=%s schema=%s)", cfg.Host, cfg.Port, cfg.Catalog, cfg.Schema)
	})
}

func GetTrinoDB() (*sql.DB, error) {
	if trinoDB == nil {
		return nil, fmt.Errorf("Trino client not available (connection failed or not initialised)")
	}
	return trinoDB, nil
}

func CloseTrinoDB() {
	if trinoDB != nil {
		trinoDB.Close()
	}
}
