"""Conservative relationship discovery between uploaded CSV datasets."""

from __future__ import annotations

import csv
from itertools import combinations
from pathlib import Path
from typing import Any


MAX_VALUES_PER_KEY = 50000
MIN_OVERLAP = 0.2


def _identifier_values(path: Path, column: str) -> set[str]:
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
    """Find high-overlap identifier candidates without assuming table names."""
    candidates = []
    for dataset in datasets:
        for key in dataset.get("analytics", {}).get("candidate_keys", []):
            candidates.append({
                "upload_id": dataset["upload_id"],
                "filename": dataset["filename"],
                "column": key["column"],
                "confidence": key["confidence"],
            })

    relationships = []
    for left, right in combinations(candidates, 2):
        if left["upload_id"] == right["upload_id"]:
            continue
        # Relationship discovery is intentionally conservative: both sides
        # must look like identifiers and share a meaningful fraction of the
        # smaller candidate's observed values.
        left_values = _identifier_values(Path(left["path"]), left["column"])
        right_values = _identifier_values(Path(right["path"]), right["column"])
        if not left_values or not right_values:
            continue
        overlap = len(left_values & right_values)
        ratio = overlap / min(len(left_values), len(right_values))
        if ratio < MIN_OVERLAP:
            continue
        relationships.append({
            "left": {
                "upload_id": left["upload_id"],
                "filename": left["filename"],
                "column": left["column"],
            },
            "right": {
                "upload_id": right["upload_id"],
                "filename": right["filename"],
                "column": right["column"],
            },
            "overlap_count": overlap,
            "overlap_ratio": round(ratio, 6),
        })

    return relationships
