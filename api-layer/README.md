# Operator360 API

Operator360 API is a Go service for managing signals and features used by the
Operator360 system. It exposes REST endpoints for creating and retrieving
features and signals, plus operator/SID lookups, backed by MySQL and two
internal RocksDB-based microservices.

**Contents**
- `main.go` - application entrypoint and route registration
- `internal/config/` - resources/config.yaml loader
- `internal/database/` - MySQL connection pool + query helpers
- `internal/response/` - standard `{success, message, data}` response envelope
- `internal/messages/` - user-facing message templates
- `internal/queries/` - SQL query templates (built from configured table names)
- `internal/server/` - HTTP handlers (health, signals, features, operator
  details, SID details) and the in-process SID-list cache
- `internal/metrics/` - Prometheus instrumentation (HTTP + DB pool metrics)
  exposed at `/metrics`
- `resources/config.yaml` - runtime configuration
- `go.mod` / `go.sum` - Go module dependencies

## Requirements

- Go 1.25+

## Installation

Dependencies are declared in `go.mod`; fetch them with:

```bash
go mod download
```

## Running the app

```bash
go run .
```

By default the server listens on port 8000. Override it with the `PORT`
environment variable. The config file path defaults to
`resources/config.yaml` (relative to the working directory); override it with
the `CONFIG_PATH` environment variable.

To build a binary:

```bash
go build -o operator360-api .
./operator360-api
```

## API

All endpoints are mounted under `/api` and, unless noted otherwise, return the
standard envelope defined in `internal/response/response.go`:

```json
{
  "success": true,
  "message": "human-readable summary",
  "data": {}
}
```

`success` is `false` and `data` is typically `{}` on failure. A handful of
endpoints that validate their request body (missing/invalid required fields)
instead return a FastAPI-style `422 Unprocessable Entity` body:

```json
{
  "detail": [
    { "loc": ["body", "<field>"], "msg": "field required", "type": "value_error" }
  ]
}
```

Every response below is `200 OK` unless a status code is called out explicitly.

---

### `GET /api/`
Basic health check. — [health.go](internal/server/health.go)

**Response**
```json
{
  "status": "healthy",
  "service": "operator360-api",
  "database_host": "10.10.106.159"
}
```
(`database_host` is `"Not configured"` if unset in `resources/config.yaml`.)

---

### `GET /api/health`
Detailed health check that pings the database. — [health.go](internal/server/health.go)

**Response**
```json
{
  "status": "healthy",
  "service": "operator360-api",
  "database": "connected"
}
```
`status`/`database` are `"degraded"`/`"disconnected"` if the DB ping fails.

---

### `GET /api/endpoints`
Self-describing catalogue of every route (used by API consumers/tooling, not
by humans reading this README). Returns `{ service, version, base_url,
total_endpoints, endpoints: [...], documentation }`.

---

### `POST /api/signal/create`
Create a new signal. Auto-increments the version for a given `(id,
feature_id)` pair. — [signals.go](internal/server/signals.go)

**Request body** (all fields required)
```json
{
  "id": "SIG001",
  "name": "Sample Signal",
  "description": "Signal description",
  "feature_id": "FEAT001",
  "feature_version": "1.0",
  "threshold": 0.85,
  "severity_level": "high",
  "user": "admin"
}
```
Missing a required field returns `success: false` with message `"Signal value
is missing for <field>"` (200, not 422).

**Response**
```json
{
  "success": true,
  "message": "Signal created successfully! ID: SIG001 FEATURE: FEAT001 VERSION: 1.0 THRESHOLD: 0.85 SEVERITY: high",
  "data": {}
}
```

---

### `GET /api/signal/info/id/{signal_id}`
Get all active signals for a signal ID. — [signals.go](internal/server/signals.go)

**Response**
```json
{
  "success": true,
  "message": "Signals retrieved successfully",
  "data": { "signals": [ { "...": "row columns as returned by MySQL" } ], "count": 1 }
}
```
If none are found: `message: "No active signals found"`, `data.signals: []`, `data.count: 0`.

---

### `GET /api/signal/info/{feature_id}`
Get all active signals for a feature ID. Same response shape as above.

---

### `POST /api/feature/info/`
Get feature metadata, optionally filtered. All body fields are optional — an
empty body (`{}`) returns every feature row. — [features.go](internal/server/features.go)

**Request body** (all fields optional)
```json
{
  "feature_id": "FEAT001",
  "version": "1.0",
  "active": true,
  "is_risk": true,
  "status": "approved"
}
```

**Response**
```json
{
  "success": true,
  "message": "Feature retrieved successfully! FEAT001 version 1.0",
  "data": { "feature": [ { "...": "row columns" } ], "count": 1 }
}
```
No matching rows: `success: false`, `message: "Feature not found with ID: <id> and version: <version>"`.

---

### `POST /api/opt_details/info`
Look up operator metadata by operator ID. — [optdetails.go](internal/server/optdetails.go)

**Request body**
```json
{ "operator_id": "OPT12345" }
```
Missing `operator_id` → `422` with the validation-error shape above.

**Response**
```json
{
  "success": true,
  "message": "Operator retrieved successfully",
  "data": {
    "operator": [
      {
        "optId": "OPT12345",
        "name": "John Doe",
        "email": "johndoe@example.com",
        "reg": "RegName",
        "regCode": "RC001",
        "ea": "EAName",
        "eaCode": "EA002",
        "pincode": "560001",
        "district": "Bengaluru",
        "state": "Karnataka",
        "ro": "RO_South",
        "machineCode": "MCH-9981",
        "riskScore": 14.5
      }
    ]
  }
}
```
No matching operator: `success: true`, `message: "No operator found for the Id"`, `data.operator: []`.

---

### `GET /api/opt_details/sid/{sid}`
Resolve a SID to an operator via the RocksDB `sid` microservice, then return
operator metadata enriched with the SID's packet type. — [optdetails.go](internal/server/optdetails.go)

**Response**
```json
{
  "success": true,
  "message": "Operator details retrieved successfully",
  "data": {
    "operator": [
      {
        "optId": "WCDKOJ_NS776624",
        "name": "Sahanaj Parvina Mondal",
        "email": "",
        "reg": "WCD Assam",
        "regCode": "991.0",
        "ea": "WCD Assam",
        "eaCode": "991",
        "pincode": "783337.0",
        "district": "Kokrajhar",
        "state": "Assam",
        "ro": "Guwahati",
        "machineCode": "LENOVOB053F1E5-F10A-21BD-6B6F-F2D672CCA9A",
        "riskScore": 0.04,
        "pktType": "U",
        "id": "S132222983161020260418055209",
        "idType": "sid"
      }
    ]
  }
}
```
SID not found in RocksDB, RocksDB unreachable, or operator lookup failure all
return `success: false` with a descriptive `message`.

---

### `POST /api/sid_details/sids/all`
Paginated, enriched list of SIDs for an operator on a given date. The full
SID list per `(opt_id, date)` is cached in-process for 5 minutes; the page
size is hardcoded to 50 regardless of any `limit` sent. — [allsids.go](internal/server/allsids.go), [sidrequest.go](internal/server/sidrequest.go)

**Request body**
```json
{ "opt_id": "OPT12345", "date": "2026-07-01", "page": 1 }
```
- `opt_id`, `date` are required (`date` must be `YYYY-MM-DD`); missing/invalid
  values return `422`.
- `limit` is accepted but ignored (always 50 per page).
- `page` defaults to `1` if omitted or `<= 0`.

**Response**
```json
{
  "success": true,
  "message": "SIDs and details retrieved successfully for operator id: OPT12345, date=20260701",
  "data": {
    "sids": [ { "sid": "S132222...", "...": "enrichment columns" } ],
    "total_sids": 120,
    "total_pages": 3,
    "current_page": 1,
    "page_size": 50
  }
}
```
No SIDs for the operator/date: `data.sids: []`, `total_sids: 0`, `total_pages: 0`, `has_more: false`.
Page past the end: `message: "No more SIDs to fetch"`, `data.sids: []`, `has_more: false`.

---

### `GET /metrics`
Prometheus scrape endpoint (plain text exposition format, not the `{success,
message, data}` envelope). Exposes, per HTTP route/method/status:
`http_requests_total`, `http_request_duration_seconds`,
`http_requests_in_flight`, `http_response_size_bytes`; plus MySQL pool gauges
(`db_pool_open_connections`, `db_pool_in_use_connections`,
`db_pool_idle_connections`, `db_pool_max_open_connections`,
`db_pool_wait_count_total`, `db_pool_wait_duration_seconds_total`) and the
default Go/process collectors. See [internal/metrics/](internal/metrics/).

---

See `documentation.txt` for architecture notes and known gaps.

## Configuration

Application configuration is read from `resources/config.yaml`. Review
`internal/config/config.go` for details on how configuration values are
loaded.

## Development

- Run with `go run .` for local development (no hot-reload; re-run after
  changes, or use a tool like `air` if you want one).
- Add tests and run them (`go test ./...`) before committing changes.

## Project Structure

```
Dockerfile
README.md
documentation.txt
go.mod
go.sum
main.go
resources/
	config.yaml
internal/
	config/
		config.go
	database/
		database.go
	response/
		response.go
	messages/
		messages.go
	queries/
		queries.go
	metrics/
		metrics.go
		dbstats.go
	server/
		server.go
		routes.go
		health.go
		signals.go
		features.go
		optdetails.go
		siddetails.go
		allsids.go
		sidrequest.go
		cache.go
		httpclient.go
```

## Notes & Next Steps

- This README provides quick start instructions; extend it with
  authentication details and deployment notes as the project evolves.

## Current Deployed IP:-
10.10.118.48:8000
