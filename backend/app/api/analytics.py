from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.analytics import get_overview


router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/overview")
def analytics_overview(db: Session = Depends(get_db)) -> dict:
    return get_overview(db)
