package db

import (
	"database/sql"
	"log"
	"time"
)

// LoggedDB wraps *sql.DB so every Query/QueryRow/Exec issued through it gets
// logged (connection name, query text, args, duration, error if any) without
// touching any of the ~10 call sites across handlers — they already only use
// these three methods, so shadowing them here is enough for full coverage.
// Everything else (Close, Ping, SetMaxOpenConns, ...) passes through via the
// embedded *sql.DB unchanged.
type LoggedDB struct {
	*sql.DB
	name string
}

func newLoggedDB(name string, inner *sql.DB) *LoggedDB {
	return &LoggedDB{DB: inner, name: name}
}

func (d *LoggedDB) Query(query string, args ...interface{}) (*sql.Rows, error) {
	start := time.Now()
	rows, err := d.DB.Query(query, args...)
	logQuery(d.name, query, args, time.Since(start), err)
	return rows, err
}

func (d *LoggedDB) QueryRow(query string, args ...interface{}) *sql.Row {
	start := time.Now()
	row := d.DB.QueryRow(query, args...)
	logQuery(d.name, query, args, time.Since(start), nil)
	return row
}

func (d *LoggedDB) Exec(query string, args ...interface{}) (sql.Result, error) {
	start := time.Now()
	res, err := d.DB.Exec(query, args...)
	logQuery(d.name, query, args, time.Since(start), err)
	return res, err
}

func logQuery(connName, query string, args []interface{}, dur time.Duration, err error) {
	if err != nil {
		log.Printf("[SQL][%s] %s args=%v (%s) ERROR: %v", connName, query, args, dur, err)
		return
	}
	log.Printf("[SQL][%s] %s args=%v (%s)", connName, query, args, dur)
}
