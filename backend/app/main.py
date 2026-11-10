from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analytics import router as analytics_router
from app.api.business_intelligence import router as business_router
from app.api.dataset_governance import router as governance_router
from app.api.uploads import router as uploads_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(uploads_router)
app.include_router(analytics_router)
app.include_router(business_router)
app.include_router(governance_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
