// Command operator360-api is the entrypoint for the Operator360 API service.
// It loads configuration, opens the MySQL connection pool, registers HTTP
// routes under /api, and starts the server.
package main

import (
	"log"
	"net/http"
	"os"

	"operator360-api/internal/config"
	"operator360-api/internal/database"
	"operator360-api/internal/metrics"
	"operator360-api/internal/server"
)

func main() {
	configPath := os.Getenv("CONFIG_PATH")
	if configPath == "" {
		configPath = "/app/resources/config.yaml"
	}

	cfg, err := config.Load(configPath)
	if err != nil {
		log.Fatalf("failed to load configuration: %v", err)
	}

	db, err := database.Open(cfg.DSN())
	if err != nil {
		log.Fatalf("failed to open database connection pool: %v", err)
	}

	srv := server.New(cfg, db)
	metrics.RegisterDBStats(db)

	mux := http.NewServeMux()
	srv.RegisterRoutes(mux)
	mux.Handle("GET /metrics", metrics.Handler())

	port := os.Getenv("PORT")
	if port == "" {
		port = "8000"
	}

	addr := "0.0.0.0:" + port
	log.Printf("Operator360 API listening on %s", addr)
	if err := http.ListenAndServe(addr, metrics.Middleware(mux)); err != nil {
		log.Fatalf("server error: %v", err)
	}
}
