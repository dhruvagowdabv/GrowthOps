import csv
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.business import Customer
from app.models.ingestion import IngestionError, IngestionRun

SOURCE_TO_CANONICAL = {
    "customer_id": "customer_id",
    "signup_date": "signup_date",
    "country": "country",
    "region": "region",
    "preferred_device": "preferred_device",
    "acquisition_channel": "acquisition_channel",
    "customer_type": "customer_type",
}

REQUIRED_COLUMNS = tuple(SOURCE_TO_CANONICAL)


def ingest_customers_csv(db: Session, csv_path: Path, upload_id: UUID, batch_size: int = 1000) -> IngestionRun:
    run = IngestionRun(upload_id=upload_id, status="started")
    db.add(run)
    db.flush()

    try:
        with csv_path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None:
                raise ValueError("CSV has no header row")

            missing = [column for column in REQUIRED_COLUMNS if column not in reader.fieldnames]
            if missing:
                raise ValueError(f"Missing required columns: {', '.join(missing)}")

            batch: list[Customer] = []
            seen_ids: set[str] = set()

            for row_number, row in enumerate(reader, start=2):
                run.rows_read += 1
                customer_id = (row.get("customer_id") or "").strip()

                if not customer_id:
                    raise ValueError(f"Row {row_number}: customer_id is required")
                if customer_id in seen_ids:
                    raise ValueError(f"Row {row_number}: duplicate customer_id '{customer_id}'")
                seen_ids.add(customer_id)

                customer = Customer(
                    customer_id=customer_id,
                    signup_date=datetime.strptime(row["signup_date"].strip(), "%Y-%m-%d").date(),
                    country=row["country"].strip(),
                    region=row["region"].strip(),
                    preferred_device=row["preferred_device"].strip(),
                    acquisition_channel=row["acquisition_channel"].strip(),
                    customer_type=row["customer_type"].strip(),
                )
                batch.append(customer)

                if len(batch) >= batch_size:
                    db.add_all(batch)
                    db.flush()
                    run.rows_inserted += len(batch)
                    batch.clear()

            if batch:
                db.add_all(batch)
                db.flush()
                run.rows_inserted += len(batch)

        run.status = "completed"
        run.completed_at = datetime.utcnow()
        db.commit()
        return run

    except Exception as exc:
        db.rollback()
        failed_run = db.get(IngestionRun, run.run_id)
        if failed_run is None:
            raise
        failed_run.status = "failed"
        failed_run.completed_at = datetime.utcnow()
        failed_run.rows_failed = max(failed_run.rows_read - failed_run.rows_inserted, 1)
        db.add(IngestionError(
            run_id=failed_run.run_id,
            row_number=failed_run.rows_read + 2,
            error_type=type(exc).__name__,
            message=str(exc),
        ))
        db.commit()
        return failed_run
