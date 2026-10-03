"""Generic analytics engine for arbitrary CSV datasets."""

from __future__ import annotations

import csv
import math
from collections import Counter
from pathlib import Path
from typing import Any

from app.services.profiling import profile_csv
from app.services.semantic_engine import infer_schema

MAX_CATEGORY_VALUES = 20
MAX_TREND_POINTS = 5000
CORRELATION_SAMPLE_SIZE = 5000


def _to_number(value: str) -> float | None:
    try:
        return float(value.strip())
    except (TypeError, ValueError):
        return None


def _to_date(value: str):
    from datetime import date, datetime
    value = value.strip()
    try:
        return date.fromisoformat(value)
    except ValueError:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = min(len(xs), len(ys))
    if n < 2:
        return None
    xs, ys = xs[:n], ys[:n]
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    denominator_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if denominator_x == 0 or denominator_y == 0:
        return None
    return round(numerator / (denominator_x * denominator_y), 6)


def analyze_csv(file_path: str | Path) -> dict[str, Any]:
    """Analyze any CSV using structural inference, not table-specific rules."""
    path = Path(file_path)
    profile = profile_csv(path)
    schema = infer_schema(profile)
    columns = schema["columns"]

    numeric_names = {
        c["name"] for c in columns
        if c["inferred_type"] in {"integer", "number"}
        and c["semantic"]["role"] == "measure"
    }
    category_names = {
        c["name"] for c in columns if c["semantic"]["role"] in {"category", "flag"}
    }
    date_names = {c["name"] for c in columns if c["semantic"]["role"] == "datetime"}

    category_counts = {name: Counter() for name in category_names}
    date_counts = {name: Counter() for name in date_names}
    numeric_stats = {
        name: {"count": 0, "sum": 0.0, "min": None, "max": None, "mean": None, "m2": 0.0}
        for name in numeric_names
    }
    numeric_rows: list[dict[str, float]] = []
    row_count = 0

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row_count += 1
            row_numeric: dict[str, float] = {}

            for name in category_names:
                value = row.get(name, "")
                if value is not None and value.strip():
                    category_counts[name][value.strip()] += 1

            for name in date_names:
                value = row.get(name, "")
                if value is not None and value.strip():
                    parsed = _to_date(value)
                    if parsed is not None:
                        date_counts[name][parsed.isoformat()[:10]] += 1

            for name in numeric_names:
                value = row.get(name, "")
                number = _to_number(value) if value is not None else None
                if number is None or math.isnan(number):
                    continue
                row_numeric[name] = number
                stats = numeric_stats[name]
                count = int(stats["count"]) + 1
                old_mean = float(stats["mean"] or 0.0)
                delta = number - old_mean
                new_mean = old_mean + delta / count
                stats["count"] = count
                stats["sum"] = float(stats["sum"] or 0.0) + number
                stats["mean"] = new_mean
                stats["m2"] = float(stats["m2"] or 0.0) + delta * (number - new_mean)
                stats["min"] = number if stats["min"] is None else min(float(stats["min"]), number)
                stats["max"] = number if stats["max"] is None else max(float(stats["max"]), number)

            if row_numeric and len(numeric_rows) < CORRELATION_SAMPLE_SIZE:
                numeric_rows.append(row_numeric)

    numeric_output = {}
    for name, stats in numeric_stats.items():
        count = int(stats["count"])
        variance = float(stats["m2"] or 0.0) / (count - 1) if count > 1 else 0.0
        numeric_output[name] = {
            "count": count,
            "sum": round(float(stats["sum"] or 0.0), 6),
            "mean": round(float(stats["mean"] or 0.0), 6) if count else None,
            "min": stats["min"],
            "max": stats["max"],
            "stddev": round(math.sqrt(max(variance, 0.0)), 6) if count > 1 else 0.0,
        }

    distributions = {
        name: [{"value": value, "count": count} for value, count in counts.most_common(MAX_CATEGORY_VALUES)]
        for name, counts in category_counts.items()
    }
    trends = {
        name: [{"date": value, "count": count} for value, count in sorted(counts.items())[:MAX_TREND_POINTS]]
        for name, counts in date_counts.items()
    }

    correlations = []
    numeric_list = list(numeric_names)
    for index, left in enumerate(numeric_list):
        for right in numeric_list[index + 1:]:
            pairs = [(row[left], row[right]) for row in numeric_rows if left in row and right in row]
            if len(pairs) >= 2:
                coefficient = _pearson([p[0] for p in pairs], [p[1] for p in pairs])
                if coefficient is not None:
                    correlations.append({"left": left, "right": right, "coefficient": coefficient})

    candidate_keys = [
        {
            "column": c["name"],
            "role": c["semantic"]["role"],
            "confidence": c["semantic"]["confidence"],
            "unique_ratio": c["semantic"]["unique_ratio"],
        }
        for c in columns if c["semantic"]["role"] in {"identifier", "reference"}
    ]

    return {
        "schema": schema,
        "summary": {
            "row_count": row_count,
            "column_count": len(columns),
            "numeric_columns": len(numeric_names),
            "categorical_columns": len(category_names),
            "datetime_columns": len(date_names),
            "candidate_key_count": len(candidate_keys),
        },
        "quality": {
            "null_cells": sum(c["null_count"] for c in columns),
            "columns_with_nulls": sum(1 for c in columns if c["null_count"] > 0),
            "duplicate_column_names": False,
        },
        "numeric": numeric_output,
        "distributions": distributions,
        "trends": trends,
        "correlations": correlations,
        "candidate_keys": candidate_keys,
    }
