"""Postgres helpers for the job queue."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required for queue mode")
    return url


def connect() -> psycopg.Connection:
    return psycopg.connect(database_url(), row_factory=dict_row)


def ensure_schema(conn: psycopg.Connection) -> None:
    schema = (Path(__file__).resolve().parents[1] / "db" / "schema.sql").read_text()
    with conn.cursor() as cur:
        cur.execute(schema)
    conn.commit()


def claim_next_job(conn: psycopg.Connection) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH next_job AS (
              SELECT id
              FROM jobs
              WHERE status = 'queued'
              ORDER BY created_at
              FOR UPDATE SKIP LOCKED
              LIMIT 1
            )
            UPDATE jobs j
            SET status = 'running',
                started_at = NOW(),
                updated_at = NOW()
            FROM next_job
            WHERE j.id = next_job.id
            RETURNING j.*;
            """
        )
        row = cur.fetchone()
    conn.commit()
    return row


def bump_attempts(conn: psycopg.Connection, job_id: UUID) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE jobs
            SET attempts = attempts + 1, updated_at = NOW()
            WHERE id = %s
            """,
            (job_id,),
        )
    conn.commit()


def finish_job(
    conn: psycopg.Connection,
    job_id: UUID,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE jobs
            SET status = %s,
                result_json = %s,
                error = %s,
                finished_at = NOW(),
                updated_at = NOW()
            WHERE id = %s AND status = 'running'
            """,
            (status, Jsonb(result) if result is not None else None, error, job_id),
        )
    conn.commit()


def get_job(conn: psycopg.Connection, job_id: UUID) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
        return cur.fetchone()


def list_jobs(conn: psycopg.Connection, limit: int = 50) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, status, carrier, dep, arr, travel_date, dep_time,
                   target_seats, car, dry_run, attempts, error,
                   created_at, started_at, finished_at, result_json
            FROM jobs
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return list(cur.fetchall())


def insert_job(conn: psycopg.Connection, job: dict[str, Any]) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO jobs (
              id, status, carrier, dep, arr, travel_date, dep_time,
              target_seats, car, interval_sec, dry_run, max_attempts,
              credentials_enc
            ) VALUES (
              %(id)s, 'queued', %(carrier)s, %(dep)s, %(arr)s, %(travel_date)s, %(dep_time)s,
              %(target_seats)s, %(car)s, %(interval_sec)s, %(dry_run)s, %(max_attempts)s,
              %(credentials_enc)s
            )
            RETURNING *
            """,
            job,
        )
        row = cur.fetchone()
    conn.commit()
    return row


def cancel_job(conn: psycopg.Connection, job_id: UUID) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE jobs
            SET status = 'canceled',
                finished_at = NOW(),
                updated_at = NOW()
            WHERE id = %s AND status IN ('queued', 'running')
            RETURNING *
            """,
            (job_id,),
        )
        row = cur.fetchone()
    conn.commit()
    return row


def serialize_job(row: dict[str, Any]) -> dict[str, Any]:
    """JSON-safe job view (never includes credentials)."""
    out = dict(row)
    for key in ("id",):
        if key in out and out[key] is not None:
            out[key] = str(out[key])
    for key in ("created_at", "updated_at", "started_at", "finished_at"):
        if out.get(key) is not None:
            out[key] = out[key].isoformat()
    out.pop("credentials_enc", None)
    if out.get("result_json") is not None and not isinstance(out["result_json"], dict):
        out["result_json"] = json.loads(json.dumps(out["result_json"], default=str))
    return out
