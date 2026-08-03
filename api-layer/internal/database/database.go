// Package database provides a pooled MySQL client with generic
// map-of-any-column query helpers, mirroring src/utils/database.py from the
// original Python service.
package database

import (
	"database/sql"
	"log"
	"time"

	_ "github.com/go-sql-driver/mysql"
)

// PoolSize mirrors the Python service's mysql-connector pool_size of 5.
const PoolSize = 5

// DB wraps a pooled *sql.DB with dictionary-style query helpers.
type DB struct {
	pool *sql.DB
}

// Open creates a connection pool for the given DSN.
func Open(dsn string) (*DB, error) {
	pool, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, err
	}

	pool.SetMaxOpenConns(PoolSize)
	pool.SetMaxIdleConns(PoolSize)
	pool.SetConnMaxLifetime(5 * time.Minute)

	log.Println("Database connection pool created successfully")
	return &DB{pool: pool}, nil
}

// Stats returns the connection pool's current stats, used to feed the
// db_pool_* Prometheus gauges.
func (d *DB) Stats() sql.DBStats {
	return d.pool.Stats()
}

// TestConnection pings the database, used by the /api/health endpoint.
func (d *DB) TestConnection() bool {
	if err := d.pool.Ping(); err != nil {
		log.Printf("Database connection test failed: %v", err)
		return false
	}
	log.Println("Database connection test successful")
	return true
}

// ExecuteQuery runs a SELECT and returns all rows as a slice of
// column-name-to-value maps. Returns a nil slice and an error on failure,
// mirroring the Python helper's "return None on error" contract.
func (d *DB) ExecuteQuery(query string, params ...any) ([]map[string]any, error) {
	rows, err := d.pool.Query(query, params...)
	if err != nil {
		log.Printf("Error executing query: %v", err)
		log.Printf("Query: %s", query)
		return nil, err
	}
	defer rows.Close()

	results, err := scanRows(rows)
	if err != nil {
		log.Printf("Error scanning query results: %v", err)
		return nil, err
	}
	return results, nil
}

// ExecuteQueryOne runs a SELECT and returns only the first row, or nil if
// there are no matching rows.
func (d *DB) ExecuteQueryOne(query string, params ...any) (map[string]any, error) {
	results, err := d.ExecuteQuery(query, params...)
	if err != nil {
		return nil, err
	}
	if len(results) == 0 {
		return nil, nil
	}
	return results[0], nil
}

// ExecuteWrite runs an INSERT/UPDATE/DELETE. It returns the last inserted ID
// for INSERT statements, or the affected row count for UPDATE/DELETE,
// matching the Python helper's behavior.
func (d *DB) ExecuteWrite(query string, params ...any) (int64, error) {
	result, err := d.pool.Exec(query, params...)
	if err != nil {
		log.Printf("Error executing write operation: %v", err)
		log.Printf("Query: %s", query)
		return 0, err
	}

	lastID, _ := result.LastInsertId()
	if lastID > 0 {
		log.Printf("Write operation successful. Inserted ID: %d", lastID)
		return lastID, nil
	}

	affected, _ := result.RowsAffected()
	log.Printf("Write operation successful. Affected rows: %d", affected)
	return affected, nil
}

// scanRows converts *sql.Rows into a slice of maps, decoding []byte column
// values (MySQL's text-protocol representation of VARCHAR/DECIMAL/etc.) into
// strings so results marshal cleanly to JSON.
func scanRows(rows *sql.Rows) ([]map[string]any, error) {
	columns, err := rows.Columns()
	if err != nil {
		return nil, err
	}

	var results []map[string]any
	for rows.Next() {
		values := make([]any, len(columns))
		ptrs := make([]any, len(columns))
		for i := range values {
			ptrs[i] = &values[i]
		}

		if err := rows.Scan(ptrs...); err != nil {
			return nil, err
		}

		row := make(map[string]any, len(columns))
		for i, col := range columns {
			row[col] = normalizeValue(values[i])
		}
		results = append(results, row)
	}

	return results, rows.Err()
}

func normalizeValue(v any) any {
	if b, ok := v.([]byte); ok {
		return string(b)
	}
	return v
}
