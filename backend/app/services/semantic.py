"""Generic semantic inference for arbitrary tabular datasets.

The module deliberately returns confidence-scored hints instead of pretending
that business meaning can always be inferred with certainty.
"""

from __future__ import annotations

import re
from collections.abc import Iterable


_ID_PATTERNS = (
    r"(^|_)(id|uuid|key)$",
    r"(^|_)(id|uuid|key)(_.*|$)",
    r"(^|_)(code|number|no)$",
)
_DATE_HINTS = ("date", "time", "timestamp", "created", "updated", "signup", "joined")
_CURRENCY_HINTS = ("amount", "price", "cost", "revenue", "sales", "spend", "salary", "profit", "margin")
_PERCENT_HINTS = ("percent", "percentage", "rate", "ratio", "share")


def _name_score(name: str, hints: Iterable[str]) -> float:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    tokens = set(normalized.split("_"))
    score = 0.0
    for hint in hints:
        if hint in tokens or normalized == hint:
            score = max(score, 0.9)
        elif hint in normalized:
            score = max(score, 0.7)
    return score


def infer_column_semantics(column: dict, row_count: int) -> dict:
    """Infer a conservative semantic role for one profiler column."""
    name = str(column["name"])
    inferred_type = column.get("inferred_type", "unknown")
    unique_count = int(column.get("unique_count", 0) or 0)
    null_count = int(column.get("null_count", 0) or 0)
    unique_ratio = (unique_count / row_count) if row_count else 0.0

    role = "attribute"
    confidence = 0.55
    subtype = None

    if inferred_type in {"date", "datetime"} or _name_score(name, _DATE_HINTS) >= 0.7:
        role = "datetime"
        confidence = max(0.8, _name_score(name, _DATE_HINTS))
    elif inferred_type in {"integer", "number"}:
        currency_score = _name_score(name, _CURRENCY_HINTS)
        percent_score = _name_score(name, _PERCENT_HINTS)
        if percent_score > currency_score and percent_score >= 0.7:
            role = "measure"
            subtype = "percentage_or_rate"
            confidence = percent_score
        elif currency_score >= 0.7:
            role = "measure"
            subtype = "currency_like"
            confidence = currency_score
        else:
            role = "measure"
            subtype = "numeric"
            confidence = 0.7
    elif inferred_type == "boolean":
        role = "flag"
        confidence = 0.95
    elif inferred_type == "string":
        id_score = max((_name_score(name, (pattern,)) for pattern in ("id", "uuid", "key", "code")), default=0.0)
        looks_like_id = any(re.search(pattern, name.lower()) for pattern in _ID_PATTERNS)
        if looks_like_id and unique_ratio >= 0.8:
            role = "identifier"
            confidence = min(0.99, max(0.8, id_score + 0.1))
        elif unique_ratio <= 0.05 or unique_count <= 50:
            role = "category"
            confidence = 0.9
        elif unique_ratio >= 0.98:
            role = "identifier_candidate"
            confidence = 0.65
        else:
            role = "text"
            confidence = 0.75

    if unique_count == 1 and row_count > 1:
        confidence = min(confidence, 0.9)

    return {
        "role": role,
        "confidence": round(confidence, 4),
        "subtype": subtype,
        "unique_ratio": round(unique_ratio, 6),
        "null_count": null_count,
    }


def infer_schema(profile: dict) -> dict:
    row_count = int(profile.get("row_count", 0) or 0)
    columns = []
    for column in profile.get("columns", []):
        semantic = infer_column_semantics(column, row_count)
        columns.append({**column, "semantic": semantic})

    return {
        "row_count": row_count,
        "column_count": len(columns),
        "columns": columns,
    }
