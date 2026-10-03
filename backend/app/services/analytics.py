"""Backward-compatible analytics service facade.

Business-table-specific analytics intentionally do not live here. New callers
should use ``analytics_engine.analyze_csv`` and the analytics API endpoints.
"""

from sqlalchemy.orm import Session

from app.models.upload import Upload
from app.services.analytics_engine import analyze_csv


def get_overview(db: Session) -> dict:
    """Return a generic overview of all uploaded datasets."""
    records = db.query(Upload).order_by(Upload.created_at.desc()).all()
    datasets = []
    total_rows = 0
    total_columns = 0

    for record in records:
        try:
            analytics = analyze_csv(record.storage_path)
        except (FileNotFoundError, ValueError):
            analytics = None

        summary = analytics["summary"] if analytics else None
        if summary:
            total_rows += summary["row_count"]
            total_columns += summary["column_count"]

        datasets.append({
            "upload_id": str(record.upload_id),
            "filename": record.filename,
            "status": record.status,
            "file_size_bytes": record.file_size_bytes,
            "created_at": record.created_at.isoformat(),
            "summary": summary,
        })

    return {
        "summary": {
            "dataset_count": len(datasets),
            "total_rows": total_rows,
            "total_columns": total_columns,
        },
        "datasets": datasets,
    }
