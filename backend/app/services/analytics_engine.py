"""Generic analytics engine for arbitrary CSV datasets.

The engine derives analytics from inferred column semantics and never relies
on business-table names such as customers, sessions, orders, or products.
"""

from __future__ import annotations

import csv
import math
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.services.profiling import profile_csv
from app.services.semantic_engine import infer_schema

MAX_CATEGORY_VALUES = 20
MAX_TREND_POINTS = 5000
CORRELATION_SAMPLE_SIZE = 5000
OUTLIER_SAMPLE_SIZE = 10000


def _to_number(value: str) -> float | None:
    try:
        number = float(value.strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _to_date(value: str) -> date | datetime | None:
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


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _quality_score(columns: list[dict], duplicate_rows: int, row_count: int) -> float:
    if not row_count or not columns:
        return 0.0
    null_cells = sum(int(column.get("null_count", 0) or 0) for column in columns)
    total_cells = row_count * len(columns)
    completeness = 1 - (null_cells / total_cells if total_cells else 0)
    duplicate_rate = duplicate_rows / row_count
    return round(max(0.0, min(1.0, completeness * (1 - duplicate_rate))), 4)


def _build_insights(
    schema: dict,
    numeric: dict,
    distributions: dict,
    trends: dict,
    correlations: list[dict],
    quality: dict,
) -> list[dict[str, Any]]:
    """Create explainable, domain-neutral observations from computed metrics."""
    insights: list[dict[str, Any]] = []

    if quality["completeness_percent"] < 95:
        insights.append({
            "type": "quality",
            "severity": "warning",
            "message": f"Dataset completeness is {quality['completeness_percent']}%.",
            "evidence": {"columns_with_nulls": quality["columns_with_nulls"]},
        })

    for name, stats in numeric.items():
        if stats["count"] and stats["min"] == stats["max"]:
            insights.append({
                "type": "quality",
                "severity": "info",
                "message": f"Numeric column '{name}' has no variation.",
                "evidence": {"value": stats["min"]},
            })
        outlier_count = stats.get("outlier_count", 0)
        if outlier_count:
            insights.append({
                "type": "anomaly",
                "severity": "info",
                "message": f"Numeric column '{name}' contains {outlier_count} IQR outliers in the analyzed sample.",
                "evidence": {"outlier_count": outlier_count, "sample_size": stats["sample_size"]},
            })

    for name, values in distributions.items():
        if len(values) >= 2 and values[0]["count"] > sum(item["count"] for item in values[1:]):
            insights.append({
                "type": "distribution",
                "severity": "info",
                "message": f"'{name}' is concentrated in its most common observed value.",
                "evidence": {"top_value": values[0]["value"], "top_count": values[0]["count"]},
            })

    for name, points in trends.items():
        if len(points) >= 2:
            first, last = points[0]["count"], points[-1]["count"]
            direction = "increased" if last > first else "decreased" if last < first else "remained stable"
            insights.append({
                "type": "trend",
                "severity": "info",
                "message": f"Observed record frequency for '{name}' {direction} from the first to last observed date.",
                "evidence": {"first_count": first, "last_count": last},
            })

    for correlation in correlations:
        if abs(correlation["coefficient"]) >= 0.8:
            insights.append({
                "type": "relationship",
                "severity": "info",
                "message": f"'{correlation['left']}' and '{correlation['right']}' show a strong linear correlation.",
                "evidence": {"coefficient": correlation["coefficient"]},
            })

    return insights


def analyze_csv(file_path: str | Path) -> dict[str, Any]:
    """Analyze any CSV using structural inference, not table-specific rules."""
    path = Path(file_path)
    profile = profile_csv(path)
    schema = infer_schema(profile)
    columns = schema["columns"]

    numeric_names = {
        column["name"] for column in columns
        if column["inferred_type"] in {"integer", "number"}
        and column["semantic"]["role"] == "measure"
    }
    category_names = {
        column["name"] for column in columns
        if column["semantic"]["role"] in {"category", "flag"}
    }
    date_names = {
        column["name"] for column in columns
        if column["semantic"]["role"] == "datetime"
    }

    category_counts = {name: Counter() for name in category_names}
    date_counts = {name: Counter() for name in date_names}
    numeric_stats = {
        name: {
            "count": 0, "sum": 0.0, "min": None, "max": None,
            "mean": None, "m2": 0.0, "sample": [],
        }
        for name in numeric_names
    }
    numeric_rows: list[dict[str, float]] = []
    row_count = 0
    duplicate_rows = 0
    seen_rows: set[tuple[str, ...]] = set()

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row_count += 1
            row_tuple = tuple(row.get(column["name"], "") or "" for column in columns)
            if row_tuple in seen_rows:
                duplicate_rows += 1
            elif len(seen_rows) < OUTLIER_SAMPLE_SIZE:
                seen_rows.add(row_tuple)

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
                if number is None:
                    continue
                row_numeric[name] = number
                stats = numeric_stats[name]
                count = int(stats["count"]) + 1
                old_mean = float(stats["mean"] or 0.0)
                delta = number - old_mean
                new_mean = old_mean + delta / count
                stats["count"] = count
                stats["sum"] = float(stats["sum"]) + number
                stats["mean"] = new_mean
                stats["m2"] = float(stats["m2"]) + delta * (number - new_mean)
                stats["min"] = number if stats["min"] is None else min(float(stats["min"]), number)
                stats["max"] = number if stats["max"] is None else max(float(stats["max"]), number)
                if len(stats["sample"]) < OUTLIER_SAMPLE_SIZE:
                    stats["sample"].append(number)

            if row_numeric and len(numeric_rows) < CORRELATION_SAMPLE_SIZE:
                numeric_rows.append(row_numeric)

    numeric_output: dict[str, dict[str, Any]] = {}
    for name, stats in numeric_stats.items():
        count = int(stats["count"])
        sample = list(stats["sample"])
        variance = float(stats["m2"]) / (count - 1) if count > 1 else 0.0
        q1 = _percentile(sample, 0.25)
        median = _percentile(sample, 0.5)
        q3 = _percentile(sample, 0.75)
        outlier_count = 0
        if q1 is not None and q3 is not None:
            iqr = q3 - q1
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outlier_count = sum(value < lower or value > upper for value in sample)

        numeric_output[name] = {
            "count": count,
            "sum": round(float(stats["sum"]), 6),
            "mean": round(float(stats["mean"]), 6) if count else None,
            "min": stats["min"],
            "max": stats["max"],
            "stddev": round(math.sqrt(max(variance, 0.0)), 6) if count > 1 else 0.0,
            "q1": round(q1, 6) if q1 is not None else None,
            "median": round(median, 6) if median is not None else None,
            "q3": round(q3, 6) if q3 is not None else None,
            "outlier_count": outlier_count,
            "sample_size": len(sample),
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
                coefficient = _pearson([pair[0] for pair in pairs], [pair[1] for pair in pairs])
                if coefficient is not None:
                    correlations.append({"left": left, "right": right, "coefficient": coefficient})

    candidate_keys = []
    for column in columns:
        semantic = column["semantic"]
        role = semantic["role"]
        unique_ratio = float(semantic["unique_ratio"])
        null_count = int(column.get("null_count", 0) or 0)
        non_null_count = row_count - null_count
        is_structurally_unique = (
            non_null_count > 0
            and null_count == 0
            and unique_ratio >= 0.95
        )
        if role in {"identifier", "reference"} or is_structurally_unique:
            candidate_keys.append({
                "name": column["name"],
                "column": column["name"],
                "role": role,
                "confidence": semantic["confidence"],
                "unique_ratio": unique_ratio,
                "reason": "semantic_identifier" if role in {"identifier", "reference"} else "high_cardinality_unique",
            })

    null_cells = sum(int(column["null_count"]) for column in columns)
    total_cells = row_count * len(columns)
    completeness_percent = round((1 - null_cells / total_cells) * 100, 4) if total_cells else 0.0
    quality = {
        "null_cells": null_cells,
        "columns_with_nulls": sum(1 for column in columns if column["null_count"] > 0),
        "duplicate_rows": duplicate_rows,
        "duplicate_row_percent": round((duplicate_rows / row_count) * 100, 4) if row_count else 0.0,
        "completeness_percent": completeness_percent,
        "score": _quality_score(columns, duplicate_rows, row_count),
    }

    insights = _build_insights(schema, numeric_output, distributions, trends, correlations, quality)

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
        "quality": quality,
        "numeric": numeric_output,
        "distributions": distributions,
        "trends": trends,
        "correlations": correlations,
        "candidate_keys": candidate_keys,
        "insights": insights,
    }
