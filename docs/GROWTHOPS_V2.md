# GrowthOps V2 backend

V2 extends the V1 ingestion, profiling, validation and generic analytics services.
It is developed on `feature/growthops-v2`; V1 remains unchanged.

## New capabilities

- Generic CSV ingestion into JSON-backed dataset records, with paginated retrieval.
- Safe cleaning preview and versioned output. Raw uploaded files are never modified.
- Explicit opt-in duplicate-row removal; duplicate events may be legitimate.
- File-backed version manifests containing source hashes, operations and before/after profiles.
- Schema and profile drift comparison between raw and cleaned versions.
- E-commerce KPIs, period-over-period comparisons, event funnel, revenue segment decomposition,
  payment failure segmentation, channel ROAS and inventory snapshots.
- Daily revenue outlier signals using a period-wide z-score.
- Deterministic evidence-based explanations and recommended investigations.

## Configure the e-commerce sample data

The business analytics endpoint reads CSVs from `BUSINESS_DATA_DIR` (default: `data/business`,
relative to the backend working directory). Copy the sample files there:

- `customers.csv`
- `sessions.csv`
- `events.csv`
- `orders.csv`
- `products.csv`
- `payment_attempts.csv`
- `marketing_spend.csv`
- optionally `inventory_daily.csv`

Do not copy `GROUND_TRUTH.csv` or `ground_truth.csv` into the application data directory.
Those files are reserved for independent evaluation.

Set these values in `backend/.env` if needed:

```env
BUSINESS_DATA_DIR=data/business
UPLOAD_DIR=data/uploads
VERSION_DIR=data/versions
```

## API additions

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/uploads/{id}/ingest/generic` | Ingest any CSV into generic records |
| GET | `/api/uploads/{id}/records?limit=100&offset=0` | Page through generic records |
| GET | `/api/uploads/{id}/cleaning/preview` | Preview suggested cleaning operations |
| POST | `/api/uploads/{id}/cleaning/apply` | Create a cleaned version |
| GET | `/api/uploads/{id}/versions` | List versions for an upload |
| GET | `/api/uploads/{id}/versions/{version_id}/drift` | Compare raw and cleaned profiles |
| GET | `/api/analytics/drift?baseline_upload_id=...&current_upload_id=...` | Compare profiles across two uploaded snapshots |
| GET | `/api/business/analysis` | KPIs, funnel, comparisons, contributors and explanations |

Example cleaning request:

```json
{
  "operations": ["trim_whitespace", "normalize_nulls"]
}
```

Duplicate removal is intentionally opt-in:

```json
{
  "operations": ["trim_whitespace", "drop_duplicate_rows"]
}
```

Example analysis request:

```http
GET /api/business/analysis?start_date=2026-09-01&end_date=2026-09-30
```

The previous comparison period is automatically selected with the same number of days.

## Important analytical safeguards

- Revenue contribution and payment failure segments are descriptive, not causal proof.
- ROAS uses observed channel-labelled revenue and spend; it is not an incrementality experiment.
- Funnel stages are session counts by known event types. Unknown event types are appended alphabetically.
- Daily anomalies are exploratory signals and should be checked against promotions, calendar effects and data completeness.
- Deterministic explanations are available without an LLM provider. External generative-AI integration is not configured by this backend.

## Migration and tests

Apply migrations from the backend directory:

```bash
alembic upgrade head
pytest -q
```

Migration `0004_generic_dataset_records` adds the generic row store.
