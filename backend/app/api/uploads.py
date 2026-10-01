from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.upload import Upload

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
    upload_id = UUID(str(__import__("uuid").uuid4()))
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
