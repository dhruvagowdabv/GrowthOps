from app.services.explanation_engine import build_explanation, generate_recommendations


def test_explanation_preserves_non_causal_evidence_language() -> None:
    analysis = {
        "period": {"start": "2026-01-01", "end": "2026-01-30"},
        "kpis": {
            "revenue": {"current": 80, "previous": 100, "percentage_change": -20},
            "conversion_rate_percent": {"current": 2, "previous": 3, "percentage_change": -33.33},
            "payment_failure_rate_percent": {"current": 8, "previous": 2, "percentage_change": 300},
        },
        "revenue_contributions": {"region": [{
            "value": "South", "change": -15, "contribution_to_net_change_percent": 75
        }]},
        "payment_failure_contributions": {"device": [{
            "value": "Mobile", "change": 4
        }]},
        "funnel": [{"stage": "checkout_started", "dropoff_from_previous_stage": 20}],
    }
    explanation = build_explanation(analysis)
    assert "not proof of cause" in explanation["narrative"]
    assert explanation["revenue_contributors"][0]["causal_status"] == "not_established"
    recommendations = generate_recommendations(analysis)
    assert any(item["title"] == "Investigate the conversion decline" for item in recommendations)
    assert any(item["title"] == "Investigate increased payment failures" for item in recommendations)
    assert any(item["title"] == "Validate the largest revenue declines" for item in recommendations)
