from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.upload import Upload
from app.services.analytics_engine import analyze_csv
from app.services.relationships import discover_relationships


router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _dataset_record(record: Upload, include_analytics: bool = True) -> dict:
    analytics = analyze_csv(record.storage_path) if include_analytics else None
    return {
        "upload_id": str(record.upload_id),
        "filename": record.filename,
        "status": record.status,
        "file_size_bytes": record.file_size_bytes,
        "created_at": record.created_at.isoformat(),
        "analytics": analytics,
    }


@router.get("/overview")
def analytics_overview(
    upload_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Generic analytics overview; no business-table assumptions."""
    if upload_id is not None:
        record = db.get(Upload, upload_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Upload not found")
        return _dataset_record(record)

    records = db.query(Upload).order_by(Upload.created_at.desc()).all()
    datasets = [_dataset_record(record, include_analytics=False) for record in records]
    total_rows = 0
    total_columns = 0

    for dataset, record in zip(datasets, records):
        try:
            analytics = analyze_csv(record.storage_path)
            dataset["summary"] = analytics["summary"]
            total_rows += analytics["summary"]["row_count"]
            total_columns += analytics["summary"]["column_count"]
        except (FileNotFoundError, ValueError):
            dataset["summary"] = None

    return {
        "summary": {
            "dataset_count": len(datasets),
            "total_rows": total_rows,
            "total_columns": total_columns,
        },
        "datasets": datasets,
    }


@router.get("/relationships")
def analytics_relationships(
    upload_ids: list[UUID] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Discover likely relationships between uploaded datasets."""
    records = db.query(Upload).order_by(Upload.created_at.desc()).all()
    if upload_ids:
        requested = set(upload_ids)
        records = [record for record in records if record.upload_id in requested]

    datasets = []
    for record in records:
        try:
            analytics = analyze_csv(record.storage_path)
        except (FileNotFoundError, ValueError):
            continue
        datasets.append({
            "upload_id": str(record.upload_id),
            "filename": record.filename,
            "path": record.storage_path,
            "analytics": analytics,
        })

    return {
        "dataset_count": len(datasets),
        "relationships": discover_relationships(datasets),
    }
