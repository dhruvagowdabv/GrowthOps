# Generic Analytics Architecture

GrowthOps analytics is intentionally dataset-agnostic. The analytics layer does not contain separate customer, session, order, or product analytics implementations.

## Pipeline

```text
CSV upload
  -> profiling
  -> semantic inference
  -> generic analytics
  -> candidate key/reference detection
  -> cross-dataset relationship discovery
  -> API
  -> frontend
```

## Components

- `profiling.py` reads the CSV and infers primitive types, null counts, unique counts, and examples.
- `semantic_engine.py` converts primitive schema information into confidence-scored structural roles such as identifier, reference, measure, category, flag, text, and datetime.
- `analytics_engine.py` produces generic summaries, numeric statistics, categorical distributions, date trends, correlations, data-quality indicators, and candidate keys.
- `relationship_engine.py` compares identifier/reference candidates across uploaded datasets and reports likely parent/child relationships using value overlap.
- `api/analytics.py` exposes dataset analytics and relationship discovery without business-table-specific branching.

## Why this scales

A new CSV does not require a new analytics service. If a dataset has IDs, dates, categories, measures, or other recognizable structural patterns, the same engine can analyze it.

Business-specific interpretation is intentionally separated from structural analytics. Semantic results include confidence and evidence so the system can surface uncertainty instead of pretending every inference is certain.

## API

- `GET /api/uploads/{upload_id}/analytics` — generic analytics for one uploaded CSV.
- `GET /api/analytics/overview` — overview for one dataset or all uploaded datasets.
- `GET /api/analytics/relationships` — likely relationships between uploaded datasets.
