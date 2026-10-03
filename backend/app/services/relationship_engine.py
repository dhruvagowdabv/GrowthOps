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


def discover_relationships(datasets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Discover likely primary/reference links using schema evidence and overlap."""
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
            })

    relationships = []
    for left, right in combinations(candidates, 2):
        if left["upload_id"] == right["upload_id"]:
            continue
        if left["role"] == right["role"] == "reference":
            continue

        left_values = _values(Path(left["path"]), left["column"])
        right_values = _values(Path(right["path"]), right["column"])
        if not left_values or not right_values:
            continue

        overlap = len(left_values & right_values)
        ratio = overlap / min(len(left_values), len(right_values))
        if ratio < MIN_OVERLAP:
            continue

        # Prefer the side with the unique identifier as the referenced parent.
        if left["role"] == "identifier" and right["role"] == "reference":
            parent, child = left, right
        elif right["role"] == "identifier" and left["role"] == "reference":
            parent, child = right, left
        else:
            parent, child = left, right

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
            "confidence": round(min(parent["confidence"], child["confidence"]) * min(1.0, ratio), 4),
        })

    return sorted(relationships, key=lambda item: item["confidence"], reverse=True)
