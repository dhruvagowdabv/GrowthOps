"""Safe, auditable CSV cleaning, file-backed version history and schema drift checks.

Raw uploads are never modified. Each applied cleaning operation writes a new
version and a manifest that records the source, operations and profile snapshot.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from typing import Any

from app.services.profiling import NULL_LIKE_VALUES, profile_csv


SAFE_OPERATIONS = {"trim_whitespace", "normalize_nulls"}
EXPLICIT_OPERATIONS = {"drop_duplicate_rows"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def preview_cleaning(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    profile = profile_csv(source)
    rows = 0
    duplicate_rows = 0
    seen: set[tuple[str, ...]] = set()
    whitespace_cells = 0
    null_tokens = 0
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        headers = next(reader, [])
        for row in reader:
            rows += 1
            key = tuple(row)
            if key in seen:
                duplicate_rows += 1
            else:
                seen.add(key)
            for value in row:
                if value != value.strip():
                    whitespace_cells += 1
                if value.strip().lower() in NULL_LIKE_VALUES - {""}:
                    null_tokens += 1
    suggestions = []
    if whitespace_cells:
        suggestions.append({"operation": "trim_whitespace", "count": whitespace_cells, "risk": "low", "automatic": True})
    if null_tokens:
        suggestions.append({"operation": "normalize_nulls", "count": null_tokens, "risk": "low", "automatic": True})
    if duplicate_rows:
        suggestions.append({"operation": "drop_duplicate_rows", "count": duplicate_rows, "risk": "review", "automatic": False,
                            "reason": "Duplicate-looking rows may represent legitimate repeated events."})
    return {"row_count": rows, "profile": profile, "suggestions": suggestions,
            "raw_file_sha256": _sha256(source), "raw_file_unchanged": True}


def apply_cleaning(source_path: str | Path, operations: list[str], versions_root: str | Path,
                   upload_id: str) -> dict[str, Any]:
    source = Path(source_path)
    requested = list(dict.fromkeys(operations))
    unsupported = set(requested) - SAFE_OPERATIONS - EXPLICIT_OPERATIONS
    if unsupported:
        raise ValueError(f"Unsupported cleaning operations: {', '.join(sorted(unsupported))}")
    if not requested:
        raise ValueError("Select at least one cleaning operation")

    version_id = str(uuid4())
    folder = Path(versions_root) / upload_id
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / f"{version_id}.csv"
    before = profile_csv(source)
    rows_written = 0
    rows_removed = 0

    with source.open("r", encoding="utf-8-sig", newline="") as inp, output.open("w", encoding="utf-8", newline="") as out:
        reader = csv.reader(inp)
        writer = csv.writer(out)
        headers = next(reader, None)
        if headers is None:
            raise ValueError("CSV file is empty")
        writer.writerow(headers)
        seen: set[tuple[str, ...]] = set()
        for row in reader:
            cleaned = list(row)
            if "trim_whitespace" in requested:
                cleaned = [value.strip() for value in cleaned]
            if "normalize_nulls" in requested:
                cleaned = ["" if value.strip().lower() in NULL_LIKE_VALUES else value for value in cleaned]
            key = tuple(cleaned)
            if "drop_duplicate_rows" in requested and key in seen:
                rows_removed += 1
                continue
            seen.add(key)
            writer.writerow(cleaned)
            rows_written += 1

    after = profile_csv(output)
    manifest = {
        "version_id": version_id, "upload_id": upload_id, "source_file": str(source),
        "source_sha256": _sha256(source), "version_file": str(output),
        "operations": requested, "rows_written": rows_written, "rows_removed": rows_removed,
        "before_profile": before, "after_profile": after,
    }
    manifest_path = folder / f"{version_id}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def list_versions(versions_root: str | Path, upload_id: str) -> list[dict[str, Any]]:
    folder = Path(versions_root) / upload_id
    if not folder.exists():
        return []
    items = []
    for path in sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        data = json.loads(path.read_text(encoding="utf-8"))
        items.append({k: data[k] for k in ("version_id", "operations", "rows_written", "rows_removed", "source_sha256")})
    return items


def compare_drift(baseline: dict[str, Any], current: dict[str, Any], null_delta_threshold: float = 10.0,
                  uniqueness_delta_threshold: float = 0.2) -> dict[str, Any]:
    base_cols = {c["name"]: c for c in baseline.get("columns", [])}
    current_cols = {c["name"]: c for c in current.get("columns", [])}
    changes = []
    for name in sorted(current_cols.keys() - base_cols.keys()):
        changes.append({"type": "column_added", "column": name, "severity": "warning"})
    for name in sorted(base_cols.keys() - current_cols.keys()):
        changes.append({"type": "column_removed", "column": name, "severity": "error"})
    for name in sorted(base_cols.keys() & current_cols.keys()):
        old, new = base_cols[name], current_cols[name]
        if old.get("inferred_type") != new.get("inferred_type"):
            changes.append({"type": "type_changed", "column": name, "from": old.get("inferred_type"), "to": new.get("inferred_type"), "severity": "error"})
        null_delta = float(new.get("null_percent", 0)) - float(old.get("null_percent", 0))
        if abs(null_delta) >= null_delta_threshold:
            changes.append({"type": "null_rate_changed", "column": name, "change_percentage_points": round(null_delta, 2), "severity": "warning"})
        old_count = max(int(baseline.get("row_count", 0)) - int(old.get("null_count", 0)), 0)
        new_count = max(int(current.get("row_count", 0)) - int(new.get("null_count", 0)), 0)
        old_ratio = int(old.get("unique_count", 0)) / old_count if old_count else 0
        new_ratio = int(new.get("unique_count", 0)) / new_count if new_count else 0
        if abs(new_ratio - old_ratio) >= uniqueness_delta_threshold:
            changes.append({"type": "uniqueness_changed", "column": name, "from": round(old_ratio, 4), "to": round(new_ratio, 4), "severity": "warning"})
    return {"drift_detected": bool(changes), "change_count": len(changes), "changes": changes,
            "baseline_rows": baseline.get("row_count", 0), "current_rows": current.get("row_count", 0)}
