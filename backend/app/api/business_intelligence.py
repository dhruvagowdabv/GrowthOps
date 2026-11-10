from fastapi import APIRouter, HTTPException, Query

from app.core.config import get_settings
from app.services.business_intelligence import analyze_business
from app.services.explanation_engine import build_explanation, generate_recommendations

router = APIRouter(prefix="/api/business", tags=["business-intelligence"])


@router.get("/analysis")
def business_analysis(
    start_date: str | None = Query(default=None, description="Inclusive YYYY-MM-DD"),
    end_date: str | None = Query(default=None, description="Inclusive YYYY-MM-DD"),
    dimensions: list[str] | None = Query(default=None),
) -> dict:
    """Return e-commerce KPIs, period changes, funnel observations and segment contributions."""
    settings = get_settings()
    data_dir = getattr(settings, "business_data_dir", "data/business")
    try:
        result = analyze_business(data_dir, start_date=start_date, end_date=end_date, dimensions=dimensions)
        result["explanation"] = build_explanation(result)
        result["recommendations"] = generate_recommendations(result)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
