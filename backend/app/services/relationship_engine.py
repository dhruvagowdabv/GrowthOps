"""Conservative relationship discovery for arbitrary uploaded datasets."""

from __future__ import annotations

import csv
from itertools import combinations
from pathlib import Path
from typing import Any

MAX_VALUES_PER_KEY = 50000
MIN_OVERLAP = 0.2


def _values(path: Path, column: str) -> set[str]:
    values: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            value = row.get(column)
            if value is None or not value.strip():
                continue
            values.add(value.strip())
            if len(values) >= MAX_VALUES_PER_KEY:
                break
    return values


def _relationship_confidence(parent: dict, child: dict, overlap_ratio: float) -> float:
    role_score = 1.0 if parent["role"] == "identifier" and child["role"] == "reference" else 0.75
    overlap_score = min(1.0, overlap_ratio)
    return round(min(parent["confidence"], child["confidence"]) * role_score * overlap_score, 4)


def discover_relationships(datasets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Discover likely primary/reference links using schema evidence and overlap.

    Each candidate key is read at most once. This keeps discovery practical as
    the number of uploaded datasets grows while retaining deterministic,
    explainable matching rather than guessing relationships from table names.
    """
    candidates = []
    for dataset in datasets:
        analytics = dataset.get("analytics", {})
        for key in analytics.get("candidate_keys", []):
            candidates.append({
                "upload_id": dataset["upload_id"],
                "filename": dataset["filename"],
                "path": dataset["path"],
                "column": key["column"],
                "role": key["role"],
                "confidence": key["confidence"],
                "unique_ratio": key.get("unique_ratio", 0.0),
            })

    values_cache: dict[tuple[str, str], set[str]] = {}
    for candidate in candidates:
        cache_key = (candidate["upload_id"], candidate["column"])
        try:
            values_cache[cache_key] = _values(Path(candidate["path"]), candidate["column"])
        except (FileNotFoundError, OSError):
            values_cache[cache_key] = set()

    relationships = []
    for left, right in combinations(candidates, 2):
        if left["upload_id"] == right["upload_id"]:
            continue
        if left["role"] == right["role"] == "reference":
            continue

        left_values = values_cache[(left["upload_id"], left["column"])]
        right_values = values_cache[(right["upload_id"], right["column"])]
        if not left_values or not right_values:
            continue

        overlap = len(left_values & right_values)
        ratio = overlap / min(len(left_values), len(right_values))
        if ratio < MIN_OVERLAP:
            continue

        if left["role"] == "identifier" and right["role"] == "reference":
            parent, child = left, right
        elif right["role"] == "identifier" and left["role"] == "reference":
            parent, child = right, left
        elif left["unique_ratio"] >= right["unique_ratio"]:
            parent, child = left, right
        else:
            parent, child = right, left

        relationships.append({
            "parent": {
                "upload_id": parent["upload_id"],
                "filename": parent["filename"],
                "column": parent["column"],
            },
            "child": {
                "upload_id": child["upload_id"],
                "filename": child["filename"],
                "column": child["column"],
            },
            "overlap_count": overlap,
            "overlap_ratio": round(ratio, 6),
            "confidence": _relationship_confidence(parent, child, ratio),
        })

    return sorted(relationships, key=lambda item: item["confidence"], reverse=True)
