# train.chasehuh web

Closed Next.js console for the Railway job queue.

```bash
cp .env.example .env.local   # fill RAILWAY_API_KEY
pnpm install
pnpm dev
```

Booking flow: search bar → results → select seat → Confirm → `POST /api/jobs`.
Search proxies `POST /v1/trains/search` (mock fallback when undeployed).

See the root [README](../README.md) for env vars and architecture.
