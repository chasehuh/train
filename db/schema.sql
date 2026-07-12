-- Job queue for concurrent multi-user SRT/Korail watch/reserve work.
CREATE TABLE IF NOT EXISTS jobs (
  id UUID PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'canceled')),
  carrier TEXT NOT NULL CHECK (carrier IN ('srt', 'korail')),
  dep TEXT NOT NULL,
  arr TEXT NOT NULL,
  travel_date TEXT NOT NULL,
  dep_time TEXT NOT NULL,
  target_seats INT NOT NULL DEFAULT 1,
  car INT NULL,
  interval_sec DOUBLE PRECISION NOT NULL DEFAULT 3,
  dry_run BOOLEAN NOT NULL DEFAULT TRUE,
  max_attempts INT NULL,
  -- AES-GCM ciphertext (base64) of {"id":"...","pw":"..."} ; null => use worker env creds
  credentials_enc TEXT NULL,
  result_json JSONB NULL,
  error TEXT NULL,
  attempts INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  started_at TIMESTAMPTZ NULL,
  finished_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS jobs_status_created_idx ON jobs (status, created_at);
