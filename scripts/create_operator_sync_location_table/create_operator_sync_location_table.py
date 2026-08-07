"""
Creates operator360.operator_sync_location — the spatially-indexed lat/lng
table the risk map's operator-pin endpoint (GetOperatorMapData in
backend/handlers/Maps/operatorMapData.go) joins against via
opt_id = opt_master.id, using MBRContains(loc, ...) for the map's
viewport bounding-box queries.

Schema:
    opt_id      VARCHAR, primary key, matches opt_master.id
    loc         POINT NOT NULL SRID 4326 — read back via
                ST_Latitude(loc)/ST_Longitude(loc), which sidesteps SRID
                4326's lat/lng axis-order ambiguity on the way out.
    updated_at  TIMESTAMP, last sync time for this operator's location
    SPATIAL INDEX on loc — required for MBRContains to use the index
                rather than a full table scan on every map pan/zoom.

Creates the operator360 database itself first if it doesn't already exist,
so this can bootstrap a brand new MySQL instance end to end. Both statements
are idempotent (CREATE DATABASE/TABLE IF NOT EXISTS) — safe to re-run.
Production already has this table; this script is for provisioning a new
dev/staging database, or as a version-controlled record of the schema.

NOTE: opt_id's VARCHAR length below (64) is a guess based on sample IDs seen
in map data (e.g. "DOC_RJ_BI_NC037541") — it hasn't been checked against
opt_master.id's actual column definition (length/charset/collation). A
mismatch there won't break the join itself, but is worth confirming before
relying on this in a real environment.

Requires MySQL 8.0.3+ (SRID-typed spatial columns) with InnoDB (SPATIAL
INDEX on InnoDB requires 5.7.5+, but SRID typing needs 8.0.3+).

Usage:
    pip install -r requirements.txt
    cp .env.example .env   # then fill in real values
    python create_operator_sync_location_table.py
"""

from __future__ import annotations

import os
import sys

import pymysql
from dotenv import load_dotenv

CREATE_DATABASE_SQL = "CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS operator_sync_location (
    opt_id     VARCHAR(64) NOT NULL,
    loc        POINT NOT NULL SRID 4326,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (opt_id),
    SPATIAL INDEX idx_operator_sync_location_loc (loc)
) ENGINE=InnoDB
"""


def main() -> int:
    load_dotenv()

    host = os.environ.get("MYSQL_HOST")
    port = int(os.environ.get("MYSQL_PORT", "3306"))
    user = os.environ.get("MYSQL_USER")
    password = os.environ.get("MYSQL_PASSWORD")
    database = os.environ.get("MYSQL_DATABASE", "operator360")

    if not host or not user or not password:
        print(
            "Missing MYSQL_HOST / MYSQL_USER / MYSQL_PASSWORD — "
            "copy .env.example to .env and fill it in.",
            file=sys.stderr,
        )
        return 1

    # No `database=` here — the database itself may not exist yet.
    conn = pymysql.connect(host=host, port=port, user=user, password=password)
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_DATABASE_SQL.format(database=database))
            cur.execute(f"USE `{database}`")
            cur.execute(CREATE_TABLE_SQL)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(f"SHOW INDEX FROM `{database}`.operator_sync_location WHERE Key_name != 'PRIMARY'")
            spatial_indexes = cur.fetchall()

        print(f"operator_sync_location ready in `{database}` on {host}.")
        if spatial_indexes:
            print(f"Spatial index confirmed: {spatial_indexes[0][2]} on column loc.")
        else:
            print(
                "WARNING: no spatial index found on operator_sync_location.loc — "
                "MBRContains queries will full-scan instead of using the index.",
                file=sys.stderr,
            )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
