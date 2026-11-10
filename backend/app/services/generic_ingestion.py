"""Generic CSV-to-JSON-record ingestion for datasets without fixed business models."""
from __future__ import annotations

import csv
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.generic_dataset import GenericDatasetRecord


def ingest_generic_csv(db: Session, path: str | Path, upload_id: UUID, batch_size: int = 1000) -> dict:
    source = Path(path)
    rows_read = 0
    rows_inserted = 0
    batch = []
    try:
        with source.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames:
                raise ValueError("CSV must contain a header row")
            if len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise ValueError("CSV contains duplicate column names")
            for row_number, row in enumerate(reader, start=2):
                rows_read += 1
                if None in row:
                    raise ValueError(f"Row {row_number} contains more values than the header")
                batch.append(GenericDatasetRecord(upload_id=upload_id, row_number=row_number, payload=dict(row)))
                if len(batch) >= batch_size:
                    db.add_all(batch)
                    db.flush()
                    rows_inserted += len(batch)
                    batch.clear()
            if batch:
                db.add_all(batch)
                db.flush()
                rows_inserted += len(batch)
        db.commit()
        return {"status": "completed", "rows_read": rows_read, "rows_inserted": rows_inserted, "rows_failed": 0}
    except Exception:
        db.rollback()
        raise
