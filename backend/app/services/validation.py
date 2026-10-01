import csv
from datetime import date, datetime
from pathlib import Path

from app.services.profiling import NULL_LIKE_VALUES


VALIDATION_LEVELS = {"error", "warning", "info"}


def _is_null(value: str | None) -> bool:
    return value is None or value.strip().lower() in NULL_LIKE_VALUES


def _type_matches(value: str, expected_type: str) -> bool:
    value = value.strip()
    if _is_null(value):
        return True

    if expected_type == "string":
        return True
    if expected_type == "boolean":
        return value.lower() in {"true", "false"}
    if expected_type == "integer":
        try:
            int(value)
            return True
        except ValueError:
            return False
    if expected_type == "number":
        try:
            float(value)
            return True
        except ValueError:
            return False
    if expected_type == "date":
        try:
            date.fromisoformat(value)
            return True
        except ValueError:
            return False
    if expected_type == "datetime":
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return True
        except ValueError:
            return False

    return False


def _issue(level: str, code: str, message: str, column: str | None = None, row: int | None = None) -> dict:
    if level not in VALIDATION_LEVELS:
        raise ValueError(f"Unsupported validation level: {level}")
    result = {"level": level, "code": code, "message": message}
    if column is not None:
        result["column"] = column
    if row is not None:
        result["row"] = row
    return result


def validate_csv(
    file_path: str | Path,
    *,
    required_fields: set[str] | None = None,
    expected_types: dict[str, str] | None = None,
    key_fields: list[str] | None = None,
) -> dict:
    """Validate a CSV against an explicit target schema.

    The validator is deliberately schema-driven: callers decide which fields
    are required, which types are expected, and which fields form a key.
    This keeps validation reusable for different datasets.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")

    required_fields = required_fields or set()
    expected_types = expected_types or {}
    key_fields = key_fields or []
    issues: list[dict] = []

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            headers = next(reader)
        except StopIteration:
            return {
                "status": "error",
                "row_count": 0,
                "issues": [_issue("error", "empty_file", "CSV file is empty")],
            }

        if not headers or any(not header.strip() for header in headers):
            issues.append(_issue("error", "invalid_headers", "CSV contains an empty column name"))

        if len(set(headers)) != len(headers):
            issues.append(_issue("error", "duplicate_columns", "CSV contains duplicate column names"))

        header_set = set(headers)
        for field in sorted(required_fields - header_set):
            issues.append(_issue("error", "missing_required_field", f"Missing required field: {field}", column=field))

        for field, expected_type in expected_types.items():
            if field not in header_set:
                continue
            if expected_type not in {"string", "boolean", "integer", "number", "date", "datetime"}:
                issues.append(_issue("error", "unsupported_type", f"Unsupported expected type: {expected_type}", column=field))

        key_indexes = [headers.index(field) for field in key_fields if field in header_set]
        seen_keys: set[tuple[str, ...]] = set()
        null_counts = {field: 0 for field in headers}
        row_count = 0

        for row_number, row in enumerate(reader, start=2):
            if len(row) != len(headers):
                issues.append(
                    _issue(
                        "error",
                        "invalid_row_length",
                        f"Row has {len(row)} values; expected {len(headers)}",
                        row=row_number,
                    )
                )
                continue

            row_count += 1
            for index, field in enumerate(headers):
                value = row[index]
                if _is_null(value):
                    null_counts[field] += 1

                expected_type = expected_types.get(field)
                if expected_type and not _type_matches(value, expected_type):
                    issues.append(
                        _issue(
                            "error",
                            "type_mismatch",
                            f"Value does not match expected type '{expected_type}'",
                            column=field,
                            row=row_number,
                        )
                    )

            if key_indexes:
                key = tuple(row[index].strip() for index in key_indexes)
                if any(_is_null(value) for value in key):
                    issues.append(
                        _issue(
                            "error",
                            "null_key",
                            "Key field contains a null value",
                            column=",".join(key_fields),
                            row=row_number,
                        )
                    )
                elif key in seen_keys:
                    issues.append(
                        _issue(
                            "error",
                            "duplicate_key",
                            "Duplicate key value detected",
                            column=",".join(key_fields),
                            row=row_number,
                        )
                    )
                else:
                    seen_keys.add(key)

        for field, count in null_counts.items():
            if count:
                issues.append(
                    _issue(
                        "warning",
                        "null_values",
                        f"{count} rows contain null-like values",
                        column=field,
                    )
                )

    status = "error" if any(issue["level"] == "error" for issue in issues) else "warning" if issues else "passed"
    return {
        "status": status,
        "row_count": row_count,
        "issues": issues,
        "summary": {
            "errors": sum(issue["level"] == "error" for issue in issues),
            "warnings": sum(issue["level"] == "warning" for issue in issues),
            "info": sum(issue["level"] == "info" for issue in issues),
        },
    }
