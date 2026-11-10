# CryptoPilot AI Dashboard

The Phase 12 dashboard is a Vite + React + TypeScript frontend backed by the FastAPI service.

## Run locally

```bash
npm install
npm run dev
```

Start the API on `http://127.0.0.1:8000` first. Vite proxies `/api` requests to that service during development. For another API host, set `VITE_API_BASE_URL`.

The account selector keeps the `$30` Small-Account ledger and `$10,000` Research ledger visibly separate. Empty API collections are shown as empty states and request failures are displayed as an error banner.
