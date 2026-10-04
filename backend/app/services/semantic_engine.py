"""Confidence-scored semantic inference for arbitrary tabular data."""

from __future__ import annotations

import re
from collections.abc import Iterable

_ID_PATTERNS = (
    r"(^|_)(id|uuid|key)$",
    r"(^|_)(id|uuid|key)(_.*|$)",
    r"(^|_)(code|number|no)$",
)
_DATE_HINTS = ("date", "time", "timestamp", "created", "updated", "joined")
_CURRENCY_HINTS = ("amount", "price", "cost", "revenue", "sales", "spend", "salary", "profit", "margin")
_PERCENT_HINTS = ("percent", "percentage", "rate", "ratio", "share")


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _name_score(name: str, hints: Iterable[str]) -> float:
    normalized = _normalize(name)
    tokens = set(normalized.split("_"))
    score = 0.0
    for hint in hints:
        if hint in tokens or normalized == hint:
            score = max(score, 0.9)
        elif hint in normalized:
            score = max(score, 0.7)
    return score


def infer_column_semantics(column: dict, row_count: int) -> dict:
    name = str(column["name"])
    normalized_name = _normalize(name)
    inferred_type = column.get("inferred_type", "unknown")
    unique_count = int(column.get("unique_count", 0) or 0)
    null_count = int(column.get("null_count", 0) or 0)
    non_null_count = max(row_count - null_count, 0)
    unique_ratio = unique_count / non_null_count if non_null_count else 0.0
    id_score = _name_score(name, ("id", "uuid", "key", "code", "number", "no"))
    looks_like_id = any(re.search(pattern, normalized_name) for pattern in _ID_PATTERNS)

    role = "attribute"
    confidence = 0.55
    subtype = None

    # Explicit key naming is strongest evidence. Uniqueness provides a
    # second, domain-independent signal for datasets whose columns use
    # unfamiliar names.
    if looks_like_id and unique_ratio >= 0.8:
        role = "identifier"
        confidence = min(0.99, max(0.8, id_score + 0.1))
    elif looks_like_id and unique_count > 0:
        role = "reference"
        confidence = min(0.95, max(0.7, id_score))
    elif unique_ratio >= 0.995 and non_null_count >= 3 and inferred_type in {"string", "integer"}:
        role = "identifier"
        confidence = 0.82
    elif inferred_type in {"date", "datetime"} or _name_score(name, _DATE_HINTS) >= 0.7:
        role = "datetime"
        confidence = max(0.8, _name_score(name, _DATE_HINTS))
    elif inferred_type in {"integer", "number"}:
        currency_score = _name_score(name, _CURRENCY_HINTS)
        percent_score = _name_score(name, _PERCENT_HINTS)
        role = "measure"
        if percent_score > currency_score and percent_score >= 0.7:
            subtype, confidence = "percentage_or_rate", percent_score
        elif currency_score >= 0.7:
            subtype, confidence = "currency_like", currency_score
        else:
            subtype, confidence = "numeric", 0.7
    elif inferred_type == "boolean":
        role, confidence = "flag", 0.95
    elif inferred_type == "string":
        if unique_ratio <= 0.05 or unique_count <= 50:
            role, confidence = "category", 0.9
        elif unique_ratio >= 0.8:
            role, confidence = "text", 0.8
        else:
            role, confidence = "text", 0.75

    if unique_count == 1 and row_count > 1:
        confidence = min(confidence, 0.9)

    return {
        "role": role,
        "confidence": round(confidence, 4),
        "subtype": subtype,
        "unique_ratio": round(unique_ratio, 6),
        "null_count": null_count,
    }


def infer_dataset_semantics(columns: list[dict]) -> dict:
    roles = [column["semantic"]["role"] for column in columns]
    identifiers = roles.count("identifier")
    references = roles.count("reference")
    measures = roles.count("measure")
    datetimes = roles.count("datetime")
    categories = roles.count("category")

    if measures and (references or identifiers) and datetimes:
        dataset_type = "transactional_or_event_like"
    elif references >= 2 and datetimes:
        dataset_type = "relational_activity_like"
    elif identifiers == 1 and categories >= 1 and measures == 0:
        dataset_type = "entity_like"
    elif datetimes and categories:
        dataset_type = "time_series_or_activity_like"
    elif measures:
        dataset_type = "analytical_measure_like"
    else:
        dataset_type = "tabular"

    return {
        "type": dataset_type,
        "confidence": 0.65 if dataset_type != "tabular" else 0.5,
        "evidence": {
            "identifier_columns": identifiers,
            "reference_columns": references,
            "measure_columns": measures,
            "datetime_columns": datetimes,
            "category_columns": categories,
        },
    }


def infer_schema(profile: dict) -> dict:
    row_count = int(profile.get("row_count", 0) or 0)
    columns = []
    for column in profile.get("columns", []):
        columns.append({**column, "semantic": infer_column_semantics(column, row_count)})

    schema = {
        "row_count": row_count,
        "column_count": len(columns),
        "columns": columns,
    }
    schema["dataset"] = infer_dataset_semantics(columns)
    return schema
