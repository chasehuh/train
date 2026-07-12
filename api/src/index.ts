import { createCipheriv, createHash, randomBytes, randomUUID, timingSafeEqual } from "node:crypto";
import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { HTTPException } from "hono/http-exception";
import pg from "pg";
import { z } from "zod";

const { Pool } = pg;

const PORT = Number(process.env.PORT || 3000);
const API_KEY = process.env.API_KEY || "";
const APP_SECRET = process.env.APP_SECRET || "";
const DATABASE_URL = process.env.DATABASE_URL || "";

if (!DATABASE_URL) {
  console.error("DATABASE_URL is required");
  process.exit(1);
}
if (!API_KEY) {
  console.error("API_KEY is required (closed access)");
  process.exit(1);
}
if (!APP_SECRET) {
  console.error("APP_SECRET is required");
  process.exit(1);
}

const pool = new Pool({ connectionString: DATABASE_URL });

async function ensureSchema() {
  await pool.query(`
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
`);
}

function aesKey(): Buffer {
  return createHash("sha256").update(APP_SECRET, "utf8").digest();
}

/** Match Python cryptography AESGCM: nonce || ciphertext || tag, base64url. */
function encryptCredentialsPyCompat(payload: { id: string; pw: string }): string {
  const key = aesKey();
  const nonce = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key, nonce);
  const plaintext = Buffer.from(JSON.stringify(payload), "utf8");
  const encrypted = Buffer.concat([cipher.update(plaintext), cipher.final()]);
  const tag = cipher.getAuthTag();
  return Buffer.concat([nonce, encrypted, tag]).toString("base64url");
}

const CreateJobSchema = z.object({
  carrier: z.enum(["srt", "korail"]),
  dep: z.string().min(1),
  arr: z.string().min(1),
  date: z.string().regex(/^\d{8}$/),
  time: z.string().regex(/^\d{6}$/),
  target: z.number().int().min(1).max(8).default(1),
  car: z.number().int().positive().nullable().optional(),
  interval_sec: z.number().positive().max(60).default(3),
  dry_run: z.boolean().default(true),
  max_attempts: z.number().int().positive().nullable().optional(),
  credentials: z
    .object({
      id: z.string().min(1),
      pw: z.string().min(1),
    })
    .optional(),
});

function requireApiKey(authHeader: string | undefined) {
  if (!authHeader?.startsWith("Bearer ")) {
    throw new HTTPException(401, { message: "missing bearer token" });
  }
  const token = authHeader.slice("Bearer ".length).trim();
  const a = Buffer.from(token);
  const b = Buffer.from(API_KEY);
  if (a.length !== b.length || !timingSafeEqual(a, b)) {
    throw new HTTPException(401, { message: "invalid api key" });
  }
}

function publicJob(row: Record<string, unknown>) {
  const { credentials_enc: _c, ...rest } = row;
  return rest;
}

const app = new Hono();

app.get("/health", (c) => c.json({ ok: true }));

app.use("/v1/*", async (c, next) => {
  requireApiKey(c.req.header("authorization"));
  await next();
});

app.post("/v1/jobs", async (c) => {
  const body = CreateJobSchema.parse(await c.req.json());
  const id = randomUUID();
  const credentialsEnc = body.credentials
    ? encryptCredentialsPyCompat(body.credentials)
    : null;

  const result = await pool.query(
    `INSERT INTO jobs (
      id, carrier, dep, arr, travel_date, dep_time,
      target_seats, car, interval_sec, dry_run, max_attempts, credentials_enc
    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
    RETURNING id, status, carrier, dep, arr, travel_date, dep_time,
              target_seats, car, interval_sec, dry_run, max_attempts,
              attempts, created_at, started_at, finished_at, result_json, error`,
    [
      id,
      body.carrier,
      body.dep,
      body.arr,
      body.date,
      body.time,
      body.target,
      body.car ?? null,
      body.interval_sec,
      body.dry_run,
      body.max_attempts ?? (body.dry_run ? 5 : null),
      credentialsEnc,
    ],
  );

  return c.json({ job: publicJob(result.rows[0]) }, 201);
});

app.get("/v1/jobs", async (c) => {
  const limit = Math.min(Number(c.req.query("limit") || 50), 100);
  const result = await pool.query(
    `SELECT id, status, carrier, dep, arr, travel_date, dep_time,
            target_seats, car, interval_sec, dry_run, max_attempts,
            attempts, created_at, started_at, finished_at, result_json, error
     FROM jobs
     ORDER BY created_at DESC
     LIMIT $1`,
    [limit],
  );
  return c.json({ jobs: result.rows.map(publicJob) });
});

app.get("/v1/jobs/:id", async (c) => {
  const result = await pool.query(
    `SELECT id, status, carrier, dep, arr, travel_date, dep_time,
            target_seats, car, interval_sec, dry_run, max_attempts,
            attempts, created_at, started_at, finished_at, result_json, error
     FROM jobs WHERE id = $1`,
    [c.req.param("id")],
  );
  if (!result.rows[0]) throw new HTTPException(404, { message: "not found" });
  return c.json({ job: publicJob(result.rows[0]) });
});

app.post("/v1/jobs/:id/cancel", async (c) => {
  const result = await pool.query(
    `UPDATE jobs
     SET status = 'canceled', finished_at = NOW(), updated_at = NOW()
     WHERE id = $1 AND status IN ('queued', 'running')
     RETURNING id, status, carrier, dep, arr, travel_date, dep_time,
               target_seats, car, dry_run, attempts, created_at, started_at, finished_at, error`,
    [c.req.param("id")],
  );
  if (!result.rows[0]) throw new HTTPException(404, { message: "not cancelable" });
  return c.json({ job: publicJob(result.rows[0]) });
});

app.onError((err, c) => {
  if (err instanceof HTTPException) return err.getResponse();
  if (err instanceof z.ZodError) {
    return c.json({ error: "validation_failed", details: err.flatten() }, 400);
  }
  console.error(err);
  return c.json({ error: "internal_error" }, 500);
});

await ensureSchema();
console.log(`train api listening on :${PORT}`);
serve({ fetch: app.fetch, port: PORT });
