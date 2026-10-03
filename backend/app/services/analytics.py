from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.business import Customer, Session as UserSession


def get_overview(db: Session) -> dict:
    total_customers = (
        db.query(func.count(Customer.customer_id)).scalar() or 0
    )

    new_customers = (
        db.query(func.count(Customer.customer_id))
        .filter(Customer.customer_type == "New")
        .scalar()
        or 0
    )

    returning_customers = (
        db.query(func.count(Customer.customer_id))
        .filter(Customer.customer_type == "Returning")
        .scalar()
        or 0
    )

    total_sessions = (
        db.query(func.count(UserSession.session_id)).scalar() or 0
    )

    sessions_per_customer = (
        round(total_sessions / total_customers, 2)
        if total_customers
        else 0
    )

    # -------------------------
    # Customer analytics
    # -------------------------

    customers_by_region = (
        db.query(
            Customer.region,
            func.count(Customer.customer_id).label("count"),
        )
        .group_by(Customer.region)
        .order_by(func.count(Customer.customer_id).desc())
        .all()
    )

    customers_by_device = (
        db.query(
            Customer.preferred_device,
            func.count(Customer.customer_id).label("count"),
        )
        .group_by(Customer.preferred_device)
        .order_by(func.count(Customer.customer_id).desc())
        .all()
    )

    customers_by_acquisition_channel = (
        db.query(
            Customer.acquisition_channel,
            func.count(Customer.customer_id).label("count"),
        )
        .group_by(Customer.acquisition_channel)
        .order_by(func.count(Customer.customer_id).desc())
        .all()
    )

    daily_signups = (
        db.query(
            Customer.signup_date,
            func.count(Customer.customer_id).label("count"),
        )
        .group_by(Customer.signup_date)
        .order_by(Customer.signup_date)
        .all()
    )

    daily_signups_by_channel = (
        db.query(
            Customer.signup_date,
            Customer.acquisition_channel,
            func.count(Customer.customer_id).label("count"),
        )
        .group_by(
            Customer.signup_date,
            Customer.acquisition_channel,
        )
        .order_by(
            Customer.signup_date,
            Customer.acquisition_channel,
        )
        .all()
    )

    # -------------------------
    # Session analytics
    # -------------------------

    sessions_by_channel = (
        db.query(
            UserSession.channel,
            func.count(UserSession.session_id).label("count"),
        )
        .group_by(UserSession.channel)
        .order_by(func.count(UserSession.session_id).desc())
        .all()
    )

    sessions_by_device = (
        db.query(
            UserSession.device,
            func.count(UserSession.session_id).label("count"),
        )
        .group_by(UserSession.device)
        .order_by(func.count(UserSession.session_id).desc())
        .all()
    )

    sessions_by_region = (
        db.query(
            UserSession.region,
            func.count(UserSession.session_id).label("count"),
        )
        .group_by(UserSession.region)
        .order_by(func.count(UserSession.session_id).desc())
        .all()
    )

    daily_sessions = (
        db.query(
            UserSession.date,
            func.count(UserSession.session_id).label("count"),
        )
        .group_by(UserSession.date)
        .order_by(UserSession.date)
        .all()
    )

    return {
        "summary": {
            "total_customers": total_customers,
            "total_sessions": total_sessions,
            "new_customers": new_customers,
            "returning_customers": returning_customers,
            "sessions_per_customer": sessions_per_customer,
        },
        "customers": {
            "by_region": [
                {"region": region, "count": count}
                for region, count in customers_by_region
            ],
            "by_device": [
                {"device": device, "count": count}
                for device, count in customers_by_device
            ],
            "by_acquisition_channel": [
                {"channel": channel, "count": count}
                for channel, count in customers_by_acquisition_channel
            ],
            "daily_signups": [
                {"date": str(date), "count": count}
                for date, count in daily_signups
            ],
            "daily_signups_by_channel": [
                {
                    "date": str(date),
                    "channel": channel,
                    "count": count,
                }
                for date, channel, count in daily_signups_by_channel
            ],
        },
        "sessions": {
            "by_channel": [
                {"channel": channel, "count": count}
                for channel, count in sessions_by_channel
            ],
            "by_device": [
                {"device": device, "count": count}
                for device, count in sessions_by_device
            ],
            "by_region": [
                {"region": region, "count": count}
                for region, count in sessions_by_region
            ],
            "daily": [
                {"date": str(date), "count": count}
                for date, count in daily_sessions
            ],
        },
    }