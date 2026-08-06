"""
Feedback -> Kafka backfill.

POST /api/feedback (backend/handlers/Feedback/feedback.go) durably writes
every submission to S3 as <prefix>/<opt_id>/<ad_id>/<date>/<event_id>/feedback.json
(plus any evidence_* files alongside it), and separately makes a best-effort
attempt to publish the same submission as a "feedback_submitted" event to
Kafka (backend/kafka/producer.go) -- best-effort because a Kafka failure must
never block the S3 write, which is the durable record.

This script walks the S3 records and (re)publishes each one to Kafka, for
submissions that predate Kafka being wired up, or that hit a Kafka outage at
submission time.

There is no publish-once ledger anywhere -- every run re-publishes every
feedback.json matching the given filters, regardless of whether it was
already published (at submission time or by a previous run of this script).
Scope with --opt-id/--since/--until/--limit, and use --execute only once
you've checked the --dry-run output.

Usage:
    pip install -r requirements.txt
    cp .env.example .env   # then fill in real values
    python feedback_to_kafka.py                                # dry-run: list + parse only
    python feedback_to_kafka.py --since 2026_01_01 --execute   # actually publish
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import timezone

import boto3
import pymysql
from botocore.config import Config as BotoConfig
from dotenv import load_dotenv
from kafka import KafkaProducer

load_dotenv()


@dataclass
class Filters:
    opt_id: str | None = None
    since: str | None = None  # inclusive, "YYYY_MM_DD"
    until: str | None = None  # inclusive, "YYYY_MM_DD"
    limit: int = 0            # 0 = no limit


@dataclass
class Counts:
    found: int = 0
    published: int = 0
    skipped: int = 0
    failed: int = 0


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def make_s3_client():
    kwargs = {
        "region_name": env("S3_REGION") or None,
        "aws_access_key_id": env("S3_ACCESS_KEY") or None,
        "aws_secret_access_key": env("S3_SECRET_KEY") or None,
    }
    endpoint = env("S3_ENDPOINT")
    if endpoint:
        kwargs["endpoint_url"] = endpoint
        # Mirrors the backend's S3ForcePathStyle=true (config.NewS3Client) --
        # needed for any non-AWS S3-compatible endpoint.
        kwargs["config"] = BotoConfig(s3={"addressing_style": "path"})
    return boto3.client("s3", **kwargs)


def feedback_bucket() -> str:
    return env("FEEDBACK_BUCKET_NAME") or env("S3_BUCKET_NAME")


def make_kafka_producer() -> KafkaProducer:
    brokers = [b.strip() for b in env("KAFKA_BROKERS").split(",") if b.strip()]
    if not brokers or not env("KAFKA_TOPIC"):
        raise RuntimeError("KAFKA_BROKERS/KAFKA_TOPIC not configured")

    kwargs = {
        "bootstrap_servers": brokers,
        "value_serializer": lambda v: json.dumps(v).encode("utf-8"),
        "key_serializer": lambda k: k.encode("utf-8") if k is not None else None,
    }

    mechanism = env("KAFKA_SASL_MECHANISM").lower()
    if mechanism:
        mechanism_map = {
            "plain": "PLAIN",
            "scram-sha-256": "SCRAM-SHA-256",
            "scram-sha-512": "SCRAM-SHA-512",
        }
        if mechanism not in mechanism_map:
            raise RuntimeError(
                f"unsupported KAFKA_SASL_MECHANISM {mechanism!r} "
                "(want plain | scram-sha-256 | scram-sha-512)"
            )
        kwargs.update(
            security_protocol="SASL_SSL",
            sasl_mechanism=mechanism_map[mechanism],
            sasl_plain_username=env("KAFKA_SASL_USERNAME"),
            sasl_plain_password=env("KAFKA_SASL_PASSWORD"),
        )

    return KafkaProducer(**kwargs)


def lookup_submitter(ad_id: str) -> dict:
    """Best-effort ad_id -> {name, email, regional_office} via portal_users.
    Returns {} (never raises past its own try/except) if MySQL isn't
    configured or the lookup fails -- feedback.json itself never stored the
    submitter's name/email, only ad_id (via the S3 path), so this is the only
    way to recover them, and its absence shouldn't block a publish."""
    if not env("MYSQL_HOST"):
        return {}
    try:
        conn = pymysql.connect(
            host=env("MYSQL_HOST"),
            port=int(env("MYSQL_PORT", "3306")),
            user=env("MYSQL_USER"),
            password=env("MYSQL_PASSWORD"),
            database=env("MYSQL_DATABASE"),
            connect_timeout=10,
        )
        try:
            table = env("MYSQL_PORTAL_USERS_TABLE", "opt360_portal_users")
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT user_name, `group`, email FROM {table} WHERE user_id = %s",
                    (ad_id,),
                )
                row = cur.fetchone()
                if not row:
                    return {}
                name, regional_office, email = row
                return {
                    "name": name or "",
                    "regional_office": regional_office or "",
                    "email": email or "",
                }
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 -- best-effort, never fatal
        print(f"[feedback_to_kafka] submitter lookup failed ad_id={ad_id}: {exc}", file=sys.stderr)
        return {}


def parse_feedback_key(prefix: str, key: str) -> tuple[str, str, str, str] | None:
    """Recovers (opt_id, ad_id, date, event_id) from a key written by
    feedbackBasePath (backend/handlers/Feedback/feedback.go):
    <prefix>/<opt_id>/<ad_id>/<date>/<event_id>/feedback.json"""
    rest = key
    if prefix:
        rest = rest[len(prefix) + 1:] if rest.startswith(prefix + "/") else rest
    if not rest.endswith("/feedback.json"):
        return None
    rest = rest[: -len("/feedback.json")]
    parts = rest.split("/")
    if len(parts) != 4:
        return None
    return parts[0], parts[1], parts[2], parts[3]


def build_event(feedback_data: dict, opt_id: str, ad_id: str, event_id: str,
                 key: str, submitted_at) -> dict:
    submitter = lookup_submitter(ad_id)

    event_id = feedback_data.get("event_id") or event_id
    evidence_files = feedback_data.get("evidence_files") or {}

    return {
        "event_id": event_id,
        "event_type": "feedback_submitted",
        "timestamp": submitted_at.astimezone(timezone.utc).isoformat(),
        "user": {
            "ad_id": ad_id,
            "name": submitter.get("name", ""),
            "email": submitter.get("email", ""),
            "regional_office": submitter.get("regional_office", ""),
        },
        "operator": {
            "opt_id": opt_id,
            "name": feedback_data.get("operator_name", ""),
            "regional_office": feedback_data.get("regional_office", ""),
            "state": feedback_data.get("opt_state", ""),
            "district": feedback_data.get("opt_district", ""),
        },
        "feedback": feedback_data.get("feedback"),
        "evidence_files": evidence_files,
        "feedback_file_path": key,
    }


def iter_feedback_keys(s3_client, bucket: str, prefix: str):
    paginator = s3_client.get_paginator("list_objects_v2")
    list_prefix = f"{prefix}/" if prefix else ""
    for page in paginator.paginate(Bucket=bucket, Prefix=list_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/feedback.json"):
                yield key, obj["LastModified"]


def run(filters: Filters, execute: bool) -> Counts:
    bucket = feedback_bucket()
    if not bucket:
        raise RuntimeError("FEEDBACK_BUCKET_NAME/S3_BUCKET_NAME not configured")
    prefix = env("FEEDBACK_PREFIX").strip("/")

    s3_client = make_s3_client()
    producer = make_kafka_producer() if execute else None

    counts = Counts()
    try:
        for key, last_modified in iter_feedback_keys(s3_client, bucket, prefix):
            if filters.limit and counts.found >= filters.limit:
                break

            parsed = parse_feedback_key(prefix, key)
            if parsed is None:
                print(f"[feedback_to_kafka] skipping key with unexpected shape: {key}", file=sys.stderr)
                counts.skipped += 1
                continue
            opt_id, ad_id, date, event_id = parsed

            if filters.opt_id and opt_id != filters.opt_id:
                continue
            if filters.since and date < filters.since:
                continue
            if filters.until and date > filters.until:
                continue

            counts.found += 1

            try:
                obj = s3_client.get_object(Bucket=bucket, Key=key)
                feedback_data = json.loads(obj["Body"].read())
                event = build_event(feedback_data, opt_id, ad_id, event_id, key, last_modified)

                if not execute:
                    print(f"[dry-run] would publish event_id={event['event_id']} opt_id={opt_id} ad_id={ad_id}")
                else:
                    producer.send(env("KAFKA_TOPIC"), key=opt_id, value=event)
                    producer.flush(timeout=10)
                    print(f"published event_id={event['event_id']} opt_id={opt_id} ad_id={ad_id}")
                counts.published += 1
            except Exception as exc:  # noqa: BLE001
                print(f"[feedback_to_kafka] FAILED key={key}: {exc}", file=sys.stderr)
                counts.failed += 1
    finally:
        if producer is not None:
            producer.close()

    return counts


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--opt-id", help="only process feedback for this opt_id")
    p.add_argument("--since", help="only process feedback submitted on/after this date (YYYY_MM_DD)")
    p.add_argument("--until", help="only process feedback submitted on/before this date (YYYY_MM_DD)")
    p.add_argument("--limit", type=int, default=0, help="stop after this many matching records (0 = no limit)")
    p.add_argument("--execute", action="store_true",
                    help="actually publish to Kafka (default is dry-run: list + parse only)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    filters = Filters(opt_id=args.opt_id, since=args.since, until=args.until, limit=args.limit)

    counts = run(filters, execute=args.execute)

    action = "published" if args.execute else "would publish (dry-run; pass --execute to actually publish)"
    print(
        f"\ndone: {counts.found} matched, {counts.published} {action}, "
        f"{counts.skipped} skipped, {counts.failed} failed"
    )


if __name__ == "__main__":
    main()
