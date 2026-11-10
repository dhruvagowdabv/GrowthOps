from pathlib import Path

from app.services.business_intelligence import analyze_business


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_business_analysis_calculates_kpis_funnel_and_contributions(tmp_path: Path) -> None:
    write(
        tmp_path / "orders.csv",
        "order_id,customer_id,session_id,amount,gross_margin,cost,discount,date,region,acquisition_channel,campaign,product_id,payment_method,low_quality_acquisition\n"
        "O1,C1,S1,100,30,70,0,2026-01-01,North,Search,A,P1,UPI,False\n"
        "O2,C2,S2,50,10,40,0,2026-01-02,South,Email,B,P2,Card,False\n"
        "O3,C1,S3,40,8,32,0,2026-01-08,North,Search,A,P1,UPI,False\n",
    )
    write(
        tmp_path / "sessions.csv",
        "session_id,date,device,channel,app_version,region\n"
        "S1,2026-01-01,Mobile,Search,4.2.0,North\n"
        "S2,2026-01-02,Desktop,Email,4.1.0,South\n"
        "S3,2026-01-08,Mobile,Search,4.2.0,North\n",
    )
    write(
        tmp_path / "events.csv",
        "event_id,session_id,timestamp,event_type\n"
        "E1,S1,2026-01-01 10:00:00,session_start\n"
        "E2,S1,2026-01-01 10:01:00,product_view\n"
        "E3,S1,2026-01-01 10:02:00,add_to_cart\n"
        "E4,S1,2026-01-01 10:03:00,purchase\n",
    )
    write(tmp_path / "products.csv", "product_id,category,price,cost\nP1,Electronics,100,70\nP2,Fashion,50,40\n")
    write(tmp_path / "customers.csv", "customer_id,customer_type\nC1,Returning\nC2,New\n")
    write(
        tmp_path / "marketing_spend.csv",
        "date,channel,spend,impressions,clicks\n"
        "2026-01-01,Search,20,1000,100\n"
        "2026-01-02,Email,10,500,50\n",
    )
    write(
        tmp_path / "payment_attempts.csv",
        "session_id,date,payment_status\nS1,2026-01-01,failed\nS2,2026-01-02,success\n",
    )

    result = analyze_business(tmp_path, "2026-01-01", "2026-01-02")
    assert result["kpis"]["revenue"]["current"] == 150.0
    assert result["kpis"]["orders"]["current"] == 2
    assert result["kpis"]["conversion_rate_percent"]["current"] == 100.0
    assert result["kpis"]["payment_failure_rate_percent"]["current"] == 50.0
    assert [item["stage"] for item in result["funnel"]] == ["session_start", "product_view", "add_to_cart", "purchase"]
    assert "contribution_to_net_change_percent" in result["revenue_contributions"]["region"][0]
    assert "Mobile" in {item["value"] for item in result["revenue_contributions"]["device"]}
    assert result["marketing_efficiency"]
    assert result["marketing_efficiency"][0]["current_roas"] is not None
    assert "device" in result["funnel_segment_breakdowns"]


def test_business_analysis_rejects_reversed_period(tmp_path: Path) -> None:
    write(tmp_path / "orders.csv", "order_id,amount,date\nO1,10,2026-01-01\n")
    try:
        analyze_business(tmp_path, "2026-01-02", "2026-01-01")
    except ValueError as exc:
        assert "on or before" in str(exc)
    else:
        raise AssertionError("Expected invalid date range")
