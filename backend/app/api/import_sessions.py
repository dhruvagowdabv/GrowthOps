from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.import_session import ImportSession
from app.models.upload import Upload

router = APIRouter(prefix="/api/import-sessions", tags=["import-sessions"])

SUPPORTED_DATASET_TYPES = {
    "orders",
    "customers",
    "sessions",
    "events",
    "products",
    "payment_attempts",
    "marketing_spend",
    "inventory_daily",
    "other",
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_session(import_session_id: UUID, db: Session) -> ImportSession:
    record = db.get(ImportSession, import_session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Import session not found")
    return record


def _serialize_session(record: ImportSession, dataset_count: int) -> dict:
    return {
        "import_session_id": str(record.import_session_id),
        "name": record.name,
        "description": record.description,
        "status": record.status,
        "dataset_count": dataset_count,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_import_session(
    name: str = Form(..., min_length=1, max_length=255),
    description: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict:
    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(status_code=422, detail="Session name cannot be blank")
    record = ImportSession(name=clean_name, description=description)
    db.add(record)
    db.commit()
    db.refresh(record)
    return _serialize_session(record, 0)


@router.get("")
def list_import_sessions(db: Session = Depends(get_db)) -> dict:
    sessions = db.scalars(select(ImportSession).order_by(ImportSession.created_at.desc())).all()
    results = []
    for record in sessions:
        uploads = db.scalars(select(Upload.upload_id).where(
            Upload.import_session_id == record.import_session_id
        )).all()
        results.append(_serialize_session(record, len(uploads)))
    return {"import_sessions": results}


@router.get("/{import_session_id}")
def get_import_session(import_session_id: UUID, db: Session = Depends(get_db)) -> dict:
    record = _get_session(import_session_id, db)
    uploads = db.scalars(
        select(Upload).where(Upload.import_session_id == record.import_session_id)
        .order_by(Upload.created_at.desc())
    ).all()
    result = _serialize_session(record, len(uploads))
    result["datasets"] = [
        {
            "upload_id": str(item.upload_id),
            "filename": item.filename,
            "dataset_type": item.dataset_type,
            "status": item.status,
            "file_size_bytes": item.file_size_bytes,
            "created_at": item.created_at.isoformat(),
        }
        for item in uploads
    ]
    return result


@router.post("/{import_session_id}/uploads", status_code=status.HTTP_201_CREATED)
def upload_session_datasets(
    import_session_id: UUID,
    files: list[UploadFile] = File(...),
    dataset_types: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
) -> dict:
    record = _get_session(import_session_id, db)
    if not files:
        raise HTTPException(status_code=400, detail="At least one CSV file is required")
    if dataset_types and len(dataset_types) != len(files):
        raise HTTPException(
            status_code=422,
            detail="Provide one dataset_type for each uploaded file, in the same order",
        )

    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []
    created: list[Upload] = []

    try:
        for index, file in enumerate(files):
            if not file.filename or not file.filename.lower().endswith(".csv"):
                raise HTTPException(status_code=400, detail="Only CSV files are accepted")
            dataset_type = dataset_types[index].strip().lower() if dataset_types else "other"
            if dataset_type not in SUPPORTED_DATASET_TYPES:
                raise HTTPException(
                    status_code=422,
                    detail=f"Unsupported dataset_type '{dataset_type}'",
                )

            upload_id = uuid4()
            destination = upload_dir / f"{upload_id}.csv"
            saved_paths.append(destination)
            total_bytes = 0
            with destination.open("wb") as output:
                while chunk := file.file.read(1024 * 1024):
                    total_bytes += len(chunk)
                    if total_bytes > settings.max_upload_size_bytes:
                        raise HTTPException(
                            status_code=413,
                            detail=f"{Path(file.filename).name} exceeds the maximum upload size",
                        )
                    output.write(chunk)
            if total_bytes == 0:
                raise HTTPException(status_code=400, detail=f"{Path(file.filename).name} is empty")
            created.append(Upload(
                upload_id=upload_id,
                filename=Path(file.filename).name,
                storage_path=str(destination),
                file_size_bytes=total_bytes,
                status="uploaded",
                import_session_id=record.import_session_id,
                dataset_type=dataset_type,
            ))

        db.add_all(created)
        db.commit()
    except Exception:
        db.rollback()
        for path in saved_paths:
            path.unlink(missing_ok=True)
        raise

    return {
        "import_session_id": str(record.import_session_id),
        "uploaded_count": len(created),
        "datasets": [
            {
                "upload_id": str(item.upload_id),
                "filename": item.filename,
                "dataset_type": item.dataset_type,
                "status": item.status,
            }
            for item in created
        ],
    }
