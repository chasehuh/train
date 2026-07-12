const DEFAULT_API_URL = "https://api-production-85f7.up.railway.app";

export type JobCredentials = {
  id: string;
  pw: string;
};

export type CreateJobBody = {
  carrier: "srt" | "korail";
  dep: string;
  arr: string;
  date: string;
  time: string;
  target: number;
  car?: number | null;
  interval_sec?: number;
  dry_run?: boolean;
  max_attempts?: number | null;
  credentials?: JobCredentials;
};

export type PublicJob = {
  id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "canceled";
  carrier: "srt" | "korail";
  dep: string;
  arr: string;
  travel_date: string;
  dep_time: string;
  target_seats: number;
  car: number | null;
  interval_sec: number;
  dry_run: boolean;
  max_attempts: number | null;
  attempts: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  result_json: unknown;
  error: string | null;
};

function apiConfig() {
  const baseUrl = (process.env.RAILWAY_API_URL || DEFAULT_API_URL).replace(
    /\/$/,
    "",
  );
  const apiKey = process.env.RAILWAY_API_KEY;
  if (!apiKey) {
    throw new Error("RAILWAY_API_KEY is not configured on the server");
  }
  return { baseUrl, apiKey };
}

async function railwayFetch(path: string, init?: RequestInit) {
  const { baseUrl, apiKey } = apiConfig();
  const res = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text };
    }
  }

  if (!res.ok) {
    const message =
      typeof data === "object" &&
      data &&
      "message" in data &&
      typeof (data as { message: unknown }).message === "string"
        ? (data as { message: string }).message
        : typeof data === "object" &&
            data &&
            "error" in data &&
            typeof (data as { error: unknown }).error === "string"
          ? (data as { error: string }).error
          : `Railway API ${res.status}`;
    const err = new Error(message) as Error & { status: number; data: unknown };
    err.status = res.status;
    err.data = data;
    throw err;
  }

  return data;
}

export async function createJob(body: CreateJobBody) {
  return railwayFetch("/v1/jobs", {
    method: "POST",
    body: JSON.stringify(body),
  }) as Promise<{ job: PublicJob }>;
}

export async function listJobs(limit = 50) {
  return railwayFetch(`/v1/jobs?limit=${limit}`) as Promise<{
    jobs: PublicJob[];
  }>;
}

export async function getJob(id: string) {
  return railwayFetch(`/v1/jobs/${id}`) as Promise<{ job: PublicJob }>;
}

export async function cancelJob(id: string) {
  return railwayFetch(`/v1/jobs/${id}/cancel`, {
    method: "POST",
  }) as Promise<{ job: PublicJob }>;
}

export type RailLoginBody = {
  carrier: "srt" | "korail";
  id: string;
  pw: string;
};

export type RailLoginResponse = {
  ok: boolean;
  carrier?: "srt" | "korail";
  id_normalized?: string;
  id_masked?: string;
  verified_at?: string;
  error?: string;
  message?: string;
};

export async function verifyRailLogin(body: RailLoginBody) {
  const { baseUrl, apiKey } = apiConfig();
  const res = await fetch(`${baseUrl}/v1/rail/login`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
    cache: "no-store",
  });

  const text = await res.text();
  let data: RailLoginResponse = { ok: false };
  if (text) {
    try {
      data = JSON.parse(text) as RailLoginResponse;
    } catch {
      data = { ok: false, error: text, message: text };
    }
  }

  // Auth / validation failures are structured responses for the login UI.
  if (res.status === 401 || res.status === 400) {
    return {
      ok: false,
      error: data.error || "login_failed",
      message: data.message || "login failed",
      carrier: data.carrier,
      id_masked: data.id_masked,
      id_normalized: data.id_normalized,
    };
  }

  if (!res.ok) {
    const message = data.message || data.error || `Railway API ${res.status}`;
    const err = new Error(message) as Error & { status: number; data: unknown };
    err.status = res.status;
    err.data = data;
    throw err;
  }

  return data;
}

export type TrainSearchBody = {
  carrier: "srt" | "korail";
  dep: string;
  arr: string;
  date: string;
  time?: string;
  available_only?: boolean;
  credentials: JobCredentials;
};

export async function searchTrains(body: TrainSearchBody) {
  return railwayFetch("/v1/trains/search", {
    method: "POST",
    body: JSON.stringify(body),
  }) as Promise<{
    ok: boolean;
    carrier: "srt" | "korail";
    dep: string;
    arr: string;
    date: string;
    time: string;
    trains: unknown[];
    source?: string;
    error?: string;
    message?: string;
  }>;
}
