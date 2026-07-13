package main

import (
	"fmt"
	"log"
	"net"
	"net/http"
	"net/url"
	"opt360-portal-backend/config"
	"opt360-portal-backend/db"
	"opt360-portal-backend/routes"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

// toDBConfig maps a config.DatabaseConfig (JSON/env-sourced) onto db.DBConfig
// (what the db package's Init* functions accept), including per-database pool
// tuning.
func toDBConfig(c config.DatabaseConfig) db.DBConfig {
	return db.DBConfig{
		User:            c.User,
		Password:        c.Password,
		Host:            c.Host,
		Port:            c.Port,
		Database:        c.Database,
		MaxOpenConns:    c.MaxOpenConns,
		MaxIdleConns:    c.MaxIdleConns,
		ConnMaxLifetime: c.ConnMaxLifetime(),
	}
}

func checkSIDStoreConnectivity(baseURL string, timeoutSeconds int) {
	timeout := time.Duration(timeoutSeconds) * time.Second

	// 1. Is the server reachable? (TCP dial)
	parsed, err := url.Parse(baseURL)
	if err != nil {
		log.Printf("[SID Store] Invalid base URL %q: %v", baseURL, err)
		return
	}
	host := parsed.Host
	conn, err := net.DialTimeout("tcp", host, timeout)
	if err != nil {
		log.Printf("[SID Store] Server UNREACHABLE at %s: %v", host, err)
	} else {
		conn.Close()
		log.Printf("[SID Store] Server reachable at %s", host)
	}

	// 2. Is the API working? (probe the actual SID endpoint with a dummy value)
	apiURL := strings.TrimRight(baseURL, "/") + "/api/opt_details/sid/__probe__"
	client := &http.Client{Timeout: timeout}
	resp, err := client.Get(apiURL)
	if err != nil {
		log.Printf("[SID Store] API endpoint UNREACHABLE at %s: %v", apiURL, err)
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusNotFound {
		log.Printf("[SID Store] API endpoint reachable but SID not found (HTTP 404) — endpoint is live at %s", apiURL)
	} else {
		log.Printf("[SID Store] API responding at %s (HTTP %d)", apiURL, resp.StatusCode)
	}
}

func main() {
	// Load configuration
	cfg, err := config.LoadConfig()
	if err != nil {
		log.Fatal("Failed to load config.json: ", err)
	}

	// Initialize database connection (operator360).
	//
	// Hardcoded per explicit instruction rather than sourced from
	// cfg.Databases.Opt360: the opt_master table lives on a different host
	// than what config was resolving, so its connection is pinned directly
	// here instead of going through config.json/OPT360_DB_OPT360_*. This
	// means rotating these credentials requires a code change + rebuild,
	// unlike every other connection in this app.
	if err := db.InitDB(db.DBConfig{
		Host:     "10.10.108.224",
		Port:     3306,
		User:     "Data_platform_W",
		Password: "Dataplat_7634",
		Database: "operator360",
	}); err != nil {
		log.Fatal("Failed to initialize database: ", err)
	}
	defer db.Close()

	fmt.Println("Database connection established")

	// Cache the distinct risk_bucket values opt_master actually has, once, so
	// handlers enumerate buckets dynamically instead of hardcoding a fixed
	// High/Medium/Low list — see db/riskBuckets.go.
	db.InitRiskBucketCache()

	// Initialize UID database connection
	if err := db.InitUIDDB(toDBConfig(cfg.Databases.UID)); err != nil {
		log.Fatal("Failed to initialize UID database: ", err)
	}

	fmt.Println("UID Database connection established")

	// Initialize portal database connection (strot_services — user auth)
	if err := db.InitPortalDB(toDBConfig(cfg.Databases.Portal)); err != nil {
		log.Fatal("Failed to initialize portal database: ", err)
	}

	fmt.Println("Portal Database connection established")

	// Non-fatal connectivity check for SID Store
	checkSIDStoreConnectivity(cfg.SIDStore.BaseURL, cfg.SIDStore.TimeoutSeconds)

	// Non-fatal ClickHouse connection (logs result; server starts regardless)
	db.InitClickHouseDB(db.ClickHouseConfig{
		Host:     cfg.ClickHouse.Host,
		Port:     cfg.ClickHouse.Port,
		Database: cfg.ClickHouse.Database,
		Username: cfg.ClickHouse.Username,
		Password: cfg.ClickHouse.Password,
		Secure:   cfg.ClickHouse.Secure,
	})
	defer db.CloseClickHouseDB()

	// Non-fatal Trino connection (logs result; server starts regardless)
	db.InitTrinoDB(db.TrinoConfig{
		Host:     cfg.Trino.Host,
		Port:     cfg.Trino.Port,
		Catalog:  cfg.Trino.Catalog,
		Schema:   cfg.Trino.Schema,
		Username: cfg.Trino.Username,
	})
	defer db.CloseTrinoDB()

	// Initialize Gin router
	router := gin.Default()

	// Setup all routes
	routes.SetupRoutes(router)

	// Start server - always bind to 0.0.0.0 in container environments
	port := cfg.Server.Port
	if port == 0 {
		port = 8080
	}
	serverAddr := fmt.Sprintf("0.0.0.0:%d", port)
	fmt.Printf("Server starting on http://%s\n", serverAddr)
	router.Run(serverAddr)
}
