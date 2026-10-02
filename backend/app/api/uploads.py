import csv
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.upload import Upload
from app.services.ingestion import (
    SESSION_REQUIRED_COLUMNS,
    REQUIRED_COLUMNS,
    ingest_customers_csv,
    ingest_sessions_csv,
)
from app.services.mapping import build_source_to_canonical, map_profile
from app.services.profiling import profile_csv
from app.services.validation import validate_csv

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_upload(upload_id: UUID, db: Session) -> Upload:
    record = db.get(Upload, upload_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    return record


@router.post("", status_code=status.HTTP_201_CREATED)
def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    settings = get_settings()
    upload_id = uuid4()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / f"{upload_id}.csv"

    total_bytes = 0
    try:
        with destination.open("wb") as output:
            while chunk := file.file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > settings.max_upload_size_bytes:
                    raise HTTPException(status_code=413, detail="CSV file exceeds the maximum upload size")
                output.write(chunk)
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise

    if total_bytes == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Empty CSV files are not accepted")

    record = Upload(
        upload_id=upload_id,
        filename=Path(file.filename).name,
        storage_path=str(destination),
        file_size_bytes=total_bytes,
        status="uploaded",
    )
    db.add(record)
    db.commit()

    return {
        "upload_id": str(upload_id),
        "filename": record.filename,
        "status": record.status,
    }


def _load_profile(record: Upload) -> dict:
    try:
        return profile_csv(record.storage_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded file is missing from storage") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _get_source_columns(record: Upload) -> set[str]:
    try:
        with Path(record.storage_path).open("r", encoding="utf-8", newline="") as file:
            fieldnames = csv.DictReader(file).fieldnames
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded file is missing from storage") from None
    if fieldnames is None:
        raise HTTPException(status_code=422, detail="CSV has no header row")
    return set(fieldnames)


def _get_mapping(record: Upload) -> dict:
    return map_profile(_load_profile(record))


def _is_session_upload(record: Upload, mapping: dict) -> bool:
    source_to_canonical = build_source_to_canonical(mapping, set(SESSION_REQUIRED_COLUMNS))
    return {"session_id", "customer_id"}.issubset(source_to_canonical.values())


def _get_ingestion_mapping(mapping: dict, is_session: bool) -> dict[str, str]:
    canonical_fields = set(SESSION_REQUIRED_COLUMNS if is_session else REQUIRED_COLUMNS)
    return build_source_to_canonical(mapping, canonical_fields)


@router.get("/{upload_id}/profile")
def get_upload_profile(upload_id: UUID, db: Session = Depends(get_db)) -> dict:
    record = _get_upload(upload_id, db)
    profile = _load_profile(record)
    return {
        "upload_id": str(record.upload_id),
        "filename": record.filename,
        "status": record.status,
        "profile": profile,
    }


@router.get("/{upload_id}/mapping")
def get_upload_mapping(upload_id: UUID, db: Session = Depends(get_db)) -> dict:
    record = _get_upload(upload_id, db)
    mapping = _get_mapping(record)
    return {
        "upload_id": str(record.upload_id),
        "filename": record.filename,
        "status": record.status,
        "mapping": mapping,
    }


@router.get("/{upload_id}/validation")
def get_upload_validation(upload_id: UUID, db: Session = Depends(get_db)) -> dict:
    record = _get_upload(upload_id, db)
    profile = _load_profile(record)
    mapping = map_profile(profile)

    expected_types = {
        item["source_column"]: item["inferred_type"]
        for item in mapping["mappings"]
        if item["suggested_field"] and item["inferred_type"] != "unknown"
    }
    required_fields = {
        item["source_column"]
        for item in mapping["mappings"]
        if item["suggested_field"] and item["confidence"] == 1.0
    }
    key_fields = [
        item["source_column"]
        for item in mapping["mappings"]
        if item["suggested_field"] in {"customer_id", "session_id"} and item["confidence"] == 1.0
    ]

    validation = validate_csv(
        record.storage_path,
        required_fields=required_fields,
        expected_types=expected_types,
        key_fields=key_fields,
    )

    return {
        "upload_id": str(record.upload_id),
        "filename": record.filename,
        "status": record.status,
        "validation": validation,
    }


@router.post("/{upload_id}/ingest")
def ingest_upload(upload_id: UUID, db: Session = Depends(get_db)) -> dict:
    record = _get_upload(upload_id, db)
    validation = get_upload_validation(upload_id, db)["validation"]

    # Warnings are non-blocking; only validation errors prevent ingestion.
    if validation["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Upload failed validation", "validation": validation},
        )

    mapping = _get_mapping(record)
    is_session = _is_session_upload(record, mapping)
    ingestion_mapping = _get_ingestion_mapping(mapping, is_session)

    if is_session:
        run = ingest_sessions_csv(
            db,
            Path(record.storage_path),
            record.upload_id,
            source_to_canonical=ingestion_mapping,
        )
    else:
        run = ingest_customers_csv(
            db,
            Path(record.storage_path),
            record.upload_id,
            source_to_canonical=ingestion_mapping,
        )

    return {
        "upload_id": str(record.upload_id),
        "filename": record.filename,
        "ingestion": {
            "run_id": str(run.run_id),
            "status": run.status,
            "rows_read": run.rows_read,
            "rows_inserted": run.rows_inserted,
            "rows_failed": run.rows_failed,
        },
    }
