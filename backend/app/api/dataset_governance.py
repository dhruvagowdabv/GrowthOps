from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.upload import Upload
from app.services.dataset_governance import apply_cleaning, compare_drift, list_versions, preview_cleaning

router = APIRouter(prefix="/api/uploads", tags=["dataset-governance"])


class CleaningRequest(BaseModel):
    operations: list[str] = Field(min_length=1)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _upload(upload_id: UUID, db: Session) -> Upload:
    record = db.get(Upload, upload_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    if not Path(record.storage_path).is_file():
        raise HTTPException(status_code=404, detail="Uploaded file is missing from storage")
    return record


@router.get("/{upload_id}/cleaning/preview")
def cleaning_preview(upload_id: UUID, db: Session = Depends(get_db)) -> dict:
    record = _upload(upload_id, db)
    try:
        return {"upload_id": str(upload_id), **preview_cleaning(record.storage_path)}
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{upload_id}/cleaning/apply")
def cleaning_apply(upload_id: UUID, request: CleaningRequest, db: Session = Depends(get_db)) -> dict:
    record = _upload(upload_id, db)
    settings = get_settings()
    versions_root = getattr(settings, "version_dir", "data/versions")
    try:
        return apply_cleaning(record.storage_path, request.operations, versions_root, str(upload_id))
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{upload_id}/versions")
def upload_versions(upload_id: UUID, db: Session = Depends(get_db)) -> dict:
    _upload(upload_id, db)
    settings = get_settings()
    versions = list_versions(getattr(settings, "version_dir", "data/versions"), str(upload_id))
    return {"upload_id": str(upload_id), "versions": versions}


@router.get("/{upload_id}/versions/{version_id}/drift")
def version_drift(upload_id: UUID, version_id: str, db: Session = Depends(get_db)) -> dict:
    _upload(upload_id, db)
    settings = get_settings()
    manifest_path = Path(getattr(settings, "version_dir", "data/versions")) / str(upload_id) / f"{version_id}.json"
    if not manifest_path.is_file():
        raise HTTPException(status_code=404, detail="Dataset version not found")
    import json
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {"upload_id": str(upload_id), "version_id": version_id,
            **compare_drift(manifest["before_profile"], manifest["after_profile"])}
