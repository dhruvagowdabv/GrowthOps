from fastapi import FastAPI

from app.api.analytics import router as analytics_router
from app.api.uploads import router as uploads_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.include_router(uploads_router)
app.include_router(analytics_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}