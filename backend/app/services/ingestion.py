import csv
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.business import Customer, Session as SessionModel
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

SESSION_REQUIRED_COLUMNS = (
    "session_id",
    "customer_id",
    "timestamp",
    "date",
    "region",
    "device",
    "channel",
    "campaign",
    "app_version",
    "landing_page",
)


def _start_run(db: Session, upload_id: UUID) -> IngestionRun:
    run = IngestionRun(upload_id=upload_id, status="started")
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _resolve_column_mapping(
    fieldnames: list[str],
    required_columns: tuple[str, ...],
    source_to_canonical: dict[str, str] | None,
) -> dict[str, str]:
    mapping = source_to_canonical or {column: column for column in fieldnames}
    mapped_targets = list(mapping.values())
    duplicate_targets = {
        target for target in mapped_targets if mapped_targets.count(target) > 1
    }
    if duplicate_targets:
        raise ValueError(
            f"Multiple source columns map to the same field: {', '.join(sorted(duplicate_targets))}"
        )

    missing = [column for column in required_columns if column not in mapping.values()]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    return mapping


def _canonical_row(row: dict, column_mapping: dict[str, str]) -> dict[str, str | None]:
    return {
        canonical: row.get(source)
        for source, canonical in column_mapping.items()
    }


def ingest_customers_csv(
    db: Session,
    csv_path: Path,
    upload_id: UUID,
    batch_size: int = 1000,
    source_to_canonical: dict[str, str] | None = None,
) -> IngestionRun:
    run = _start_run(db, upload_id)

    try:
        with csv_path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None:
                raise ValueError("CSV has no header row")

            column_mapping = _resolve_column_mapping(
                reader.fieldnames,
                REQUIRED_COLUMNS,
                source_to_canonical,
            )

            batch: list[Customer] = []
            seen_ids: set[str] = set()

            for row_number, row in enumerate(reader, start=2):
                run.rows_read += 1
                canonical_row = _canonical_row(row, column_mapping)
                customer_id = (canonical_row.get("customer_id") or "").strip()

                if not customer_id:
                    raise ValueError(f"Row {row_number}: customer_id is required")
                if customer_id in seen_ids:
                    raise ValueError(f"Row {row_number}: duplicate customer_id '{customer_id}'")
                seen_ids.add(customer_id)

                batch.append(Customer(
                    customer_id=customer_id,
                    signup_date=datetime.strptime((canonical_row["signup_date"] or "").strip(), "%Y-%m-%d").date(),
                    country=(canonical_row["country"] or "").strip(),
                    region=(canonical_row["region"] or "").strip(),
                    preferred_device=(canonical_row["preferred_device"] or "").strip(),
                    acquisition_channel=(canonical_row["acquisition_channel"] or "").strip(),
                    customer_type=(canonical_row["customer_type"] or "").strip(),
                ))

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
        run = db.get(IngestionRun, run.run_id)
        if run is None:
            raise RuntimeError("Ingestion run could not be recovered after rollback") from exc
        run.status = "failed"
        run.completed_at = datetime.utcnow()
        run.rows_failed = max(run.rows_read - run.rows_inserted, 1)
        db.add(IngestionError(
            run_id=run.run_id,
            row_number=run.rows_read + 2,
            error_type=type(exc).__name__,
            message=str(exc),
        ))
        db.commit()
        return run


def ingest_sessions_csv(
    db: Session,
    csv_path: Path,
    upload_id: UUID,
    batch_size: int = 1000,
    source_to_canonical: dict[str, str] | None = None,
) -> IngestionRun:
    run = _start_run(db, upload_id)

    try:
        with csv_path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None:
                raise ValueError("CSV has no header row")

            column_mapping = _resolve_column_mapping(
                reader.fieldnames,
                SESSION_REQUIRED_COLUMNS,
                source_to_canonical,
            )

            batch: list[SessionModel] = []
            seen_ids: set[str] = set()

            for row_number, row in enumerate(reader, start=2):
                run.rows_read += 1
                canonical_row = _canonical_row(row, column_mapping)
                session_id = (canonical_row.get("session_id") or "").strip()
                customer_id = (canonical_row.get("customer_id") or "").strip()

                if not session_id:
                    raise ValueError(f"Row {row_number}: session_id is required")
                if session_id in seen_ids:
                    raise ValueError(f"Row {row_number}: duplicate session_id '{session_id}'")
                if not customer_id:
                    raise ValueError(f"Row {row_number}: customer_id is required")
                seen_ids.add(session_id)

                batch.append(SessionModel(
                    session_id=session_id,
                    customer_id=customer_id,
                    timestamp=datetime.strptime((canonical_row["timestamp"] or "").strip(), "%Y-%m-%d %H:%M:%S"),
                    date=datetime.strptime((canonical_row["date"] or "").strip(), "%Y-%m-%d").date(),
                    region=(canonical_row["region"] or "").strip(),
                    device=(canonical_row["device"] or "").strip(),
                    channel=(canonical_row["channel"] or "").strip(),
                    campaign=(canonical_row["campaign"] or "").strip() or None,
                    app_version=(canonical_row["app_version"] or "").strip(),
                    landing_page=(canonical_row["landing_page"] or "").strip(),
                ))

                if len(batch) >= batch_size:
                    customer_ids = {item.customer_id for item in batch}
                    existing_ids = set(
                        db.scalars(select(Customer.customer_id).where(Customer.customer_id.in_(customer_ids)))
                    )
                    missing_customers = customer_ids - existing_ids
                    if missing_customers:
                        missing_customer = sorted(missing_customers)[0]
                        raise ValueError(
                            f"Row {row_number}: customer_id '{missing_customer}' does not exist"
                        )
                    db.add_all(batch)
                    db.flush()
                    run.rows_inserted += len(batch)
                    batch.clear()

            if batch:
                customer_ids = {item.customer_id for item in batch}
                existing_ids = set(
                    db.scalars(select(Customer.customer_id).where(Customer.customer_id.in_(customer_ids)))
                )
                missing_customers = customer_ids - existing_ids
                if missing_customers:
                    missing_customer = sorted(missing_customers)[0]
                    raise ValueError(f"customer_id '{missing_customer}' does not exist")
                db.add_all(batch)
                db.flush()
                run.rows_inserted += len(batch)

        run.status = "completed"
        run.completed_at = datetime.utcnow()
        db.commit()
        return run

    except Exception as exc:
        db.rollback()
        run = db.get(IngestionRun, run.run_id)
        if run is None:
            raise RuntimeError("Ingestion run could not be recovered after rollback") from exc
        run.status = "failed"
        run.completed_at = datetime.utcnow()
        run.rows_failed = max(run.rows_read - run.rows_inserted, 1)
        db.add(IngestionError(
            run_id=run.run_id,
            row_number=run.rows_read + 2,
            error_type=type(exc).__name__,
            message=str(exc),
        ))
        db.commit()
        return run
