from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.upload import Upload
from app.services.mapping import map_profile
from app.services.profiling import profile_csv

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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


@router.get("/{upload_id}/profile")
def get_upload_profile(upload_id: UUID, db: Session = Depends(get_db)) -> dict:
    record = db.get(Upload, upload_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    profile = _load_profile(record)
    return {
        "upload_id": str(record.upload_id),
        "filename": record.filename,
        "status": record.status,
        "profile": profile,
    }


@router.get("/{upload_id}/mapping")
def get_upload_mapping(upload_id: UUID, db: Session = Depends(get_db)) -> dict:
    record = db.get(Upload, upload_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Upload not found")

    profile = _load_profile(record)
    mapping = map_profile(profile)
    return {
        "upload_id": str(record.upload_id),
        "filename": record.filename,
        "status": record.status,
        "mapping": mapping,
    }
