from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    signup_date: Mapped[date] = mapped_column(Date, nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    preferred_device: Mapped[str] = mapped_column(String(50), nullable=False)
    acquisition_channel: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_type: Mapped[str] = mapped_column(String(50), nullable=False)

    sessions: Mapped[list["Session"]] = relationship(back_populates="customer")
    events: Mapped[list["Event"]] = relationship(back_populates="customer")
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Product(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="product")


class Session(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    device: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[str] = mapped_column(String(100), nullable=False)
    campaign: Mapped[str | None] = mapped_column(String(150), nullable=True)
    app_version: Mapped[str] = mapped_column(String(50), nullable=False)
    landing_page: Mapped[str] = mapped_column(String(255), nullable=False)

    customer: Mapped[Customer] = relationship(back_populates="sessions")
    events: Mapped[list["Event"]] = relationship(back_populates="session")
    orders: Mapped[list["Order"]] = relationship(back_populates="session")
    payment_attempt: Mapped["PaymentAttempt | None"] = relationship(back_populates="session", uselist=False)


class Event(Base):
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)

    session: Mapped[Session] = relationship(back_populates="events")
    customer: Mapped[Customer] = relationship(back_populates="events")


class Order(Base):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.customer_id"), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), nullable=False, index=True)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    gross_margin: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    acquisition_channel: Mapped[str] = mapped_column(String(100), nullable=False)
    campaign: Mapped[str | None] = mapped_column(String(150), nullable=True)
    low_quality_acquisition: Mapped[bool] = mapped_column(Boolean, nullable=False)

    customer: Mapped[Customer] = relationship(back_populates="orders")
    session: Mapped[Session] = relationship(back_populates="orders")
    product: Mapped[Product] = relationship(back_populates="orders")


class PaymentAttempt(Base):
    __tablename__ = "payment_attempts"

    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"), primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    device: Mapped[str] = mapped_column(String(50), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    app_version: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(50), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped[Session] = relationship(back_populates="payment_attempt")


class MarketingSpend(Base):
    __tablename__ = "marketing_spend"

    date: Mapped[date] = mapped_column(Date, primary_key=True)
    channel: Mapped[str] = mapped_column(String(100), primary_key=True)
    spend: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False)
