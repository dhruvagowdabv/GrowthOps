# GrowthOps frontend

A React + Vite JavaScript interface for the GrowthOps CSV analytics API.

## Requirements
- Node.js 20 or newer
- The GrowthOps backend running locally (default API URL: `http://localhost:8000`)

## Run locally

From this directory:

```bash
npm install
cp .env.example .env
npm run dev
```

On Windows PowerShell, copy the environment template with:

```powershell
Copy-Item .env.example .env
```

Update `VITE_API_BASE_URL` in `.env` if the backend runs elsewhere. Restart Vite after changing environment variables.

## Build

```bash
npm run build
```

## Current API integration
- `POST /api/uploads`
- `GET /api/uploads/{upload_id}/profile`
- `GET /api/uploads/{upload_id}/mapping`
- `GET /api/uploads/{upload_id}/validation`
- `POST /api/uploads/{upload_id}/ingest`
- `GET /api/uploads/{upload_id}/analytics`
- `GET /api/analytics/overview`
- `GET /api/analytics/relationships`

The UI renders returned analytics and provides empty states when the API has no results. It does not add or modify backend functionality.