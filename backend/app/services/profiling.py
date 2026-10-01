import csv
from datetime import date, datetime
from pathlib import Path
from typing import TextIO


NULL_LIKE_VALUES = {"", "null", "none", "nan", "na", "n/a"}


def _is_null(value: str | None) -> bool:
    return value is None or value.strip().lower() in NULL_LIKE_VALUES


def _infer_type(values: list[str]) -> str:
    non_null = [value.strip() for value in values if not _is_null(value)]
    if not non_null:
        return "unknown"

    if all(value.lower() in {"true", "false"} for value in non_null):
        return "boolean"

    try:
        for value in non_null:
            int(value)
        return "integer"
    except ValueError:
        pass

    try:
        for value in non_null:
            float(value)
        return "number"
    except ValueError:
        pass

    # Check date-only values before datetimes. datetime.fromisoformat()
    # also accepts date-only strings and would otherwise classify them as
    # datetimes.
    try:
        for value in non_null:
            date.fromisoformat(value)
        return "date"
    except ValueError:
        pass

    try:
        for value in non_null:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        return "datetime"
    except ValueError:
        pass

    return "string"


def profile_csv(file_path: str | Path, sample_size: int = 5) -> dict:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Uploaded file not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return _profile_reader(handle, sample_size=sample_size)


def _profile_reader(handle: TextIO, sample_size: int = 5) -> dict:
    reader = csv.reader(handle)
    try:
        headers = next(reader)
    except StopIteration:
        raise ValueError("CSV file is empty") from None

    if not headers or any(not header.strip() for header in headers):
        raise ValueError("CSV contains an empty column name")

    if len(set(headers)) != len(headers):
        raise ValueError("CSV contains duplicate column names")

    values_by_column: list[list[str]] = [[] for _ in headers]
    null_counts = [0] * len(headers)
    unique_values = [set() for _ in headers]
    row_count = 0

    for row in reader:
        if len(row) != len(headers):
            raise ValueError(
                f"CSV row {row_count + 2} has {len(row)} values; expected {len(headers)}"
            )

        row_count += 1
        for index, value in enumerate(row):
            values_by_column[index].append(value)
            if _is_null(value):
                null_counts[index] += 1
            else:
                unique_values[index].add(value)

    columns = []
    for index, name in enumerate(headers):
        values = values_by_column[index]
        non_null_examples = [value for value in values if not _is_null(value)]
        columns.append(
            {
                "name": name,
                "inferred_type": _infer_type(values),
                "null_count": null_counts[index],
                "null_percent": round((null_counts[index] / row_count) * 100, 4)
                if row_count
                else 0.0,
                "unique_count": len(unique_values[index]),
                "examples": non_null_examples[:sample_size],
            }
        )

    return {
        "row_count": row_count,
        "column_count": len(headers),
        "columns": columns,
    }
