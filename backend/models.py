from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class TokenStatus(str, Enum):
    BOOKED = "BOOKED"
    ARRIVED = "ARRIVED"
    WAITING = "WAITING"
    QUALITY_CHECK = "QUALITY_CHECK"
    WEIGHMENT = "WEIGHMENT"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAYMENT_INITIATED = "PAYMENT_INITIATED"
    PAYMENT_PROCESSING = "PAYMENT_PROCESSING"
    PAYMENT_COMPLETED = "PAYMENT_COMPLETED"
    PAYMENT_FAILED = "PAYMENT_FAILED"

    # Kept for existing bookings created by the first version of the app.
    IN_YARD = "IN_YARD"
    WEIGHING = "WEIGHING"
    COMPLETED = "COMPLETED"


class UserRole(str, Enum):
    FARMER = "FARMER"
    OFFICER = "OFFICER"
    ADMIN = "ADMIN"


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    INITIATED = "INITIATED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Mandi(Base):
    __tablename__ = "mandis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    district: Mapped[str] = mapped_column(String(120), nullable=True)
    state: Mapped[str] = mapped_column(String(120), nullable=True, default="Madhya Pradesh")
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=True)
    daily_capacity_quintals: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=True, default=Decimal("200.00"))
    hourly_capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    procurement_window_start: Mapped[time] = mapped_column(Time, nullable=True)
    procurement_window_end: Mapped[time] = mapped_column(Time, nullable=True)
    available_crops: Mapped[list] = mapped_column(JSON, nullable=True)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    slots: Mapped[list["Slot"]] = relationship(back_populates="mandi")
    tokens: Mapped[list["Token"]] = relationship(back_populates="mandi")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=True)
    farmer_id: Mapped[str] = mapped_column(String(40), nullable=True, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(UserRole, name="user_role"), nullable=False, default=UserRole.FARMER
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    bookings: Mapped[list["Booking"]] = relationship(back_populates="farmer")


class Slot(Base):
    __tablename__ = "slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mandi_id: Mapped[int] = mapped_column(ForeignKey("mandis.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    max_tonnage: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    booked_tonnage: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    mandi: Mapped[Mandi] = relationship(back_populates="slots")
    tokens: Mapped[list["Token"]] = relationship(back_populates="slot")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="slot")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"), nullable=False, index=True)
    crop_type: Mapped[str] = mapped_column(String(100), nullable=False)
    expected_tonnage: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    farmer: Mapped[User] = relationship(back_populates="bookings")
    slot: Mapped[Slot] = relationship(back_populates="bookings")
    token: Mapped["Token"] = relationship(back_populates="booking", uselist=False)


class Token(Base):
    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), unique=True, index=True, nullable=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    mandi_id: Mapped[int] = mapped_column(ForeignKey("mandis.id"), index=True, nullable=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"), nullable=False, index=True)
    farmer_phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    crop_type: Mapped[str] = mapped_column(String(100), nullable=False)
    expected_tonnage: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    status: Mapped[TokenStatus] = mapped_column(
        SqlEnum(TokenStatus, name="token_status"), nullable=False, default=TokenStatus.BOOKED
    )
    token_code: Mapped[str] = mapped_column(String(12), nullable=False, unique=True, index=True)
    qr_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    arrived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    slot: Mapped[Slot] = relationship(back_populates="tokens")
    booking: Mapped[Booking] = relationship(back_populates="token")
    farmer: Mapped[User] = relationship(foreign_keys=[farmer_id])
    mandi: Mapped[Mandi] = relationship(back_populates="tokens")
    status_history: Mapped[list["ProcurementStatusHistory"]] = relationship(back_populates="token")
    quality_inspection: Mapped["QualityInspection"] = relationship(back_populates="token", uselist=False)
    weighment: Mapped["Weighment"] = relationship(back_populates="token", uselist=False)
    payment: Mapped["Payment"] = relationship(back_populates="token", uselist=False)

    @property
    def farmer_display_id(self) -> str | None:
        return self.farmer.farmer_id if self.farmer else None

    @property
    def district(self) -> str | None:
        return self.mandi.district if self.mandi else None

    @property
    def mandi_name(self) -> str | None:
        return self.mandi.name if self.mandi else None


class ProcurementStatusHistory(Base):
    __tablename__ = "procurement_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_id: Mapped[int] = mapped_column(ForeignKey("tokens.id"), nullable=False, index=True)
    previous_status: Mapped[TokenStatus] = mapped_column(SqlEnum(TokenStatus, name="token_status"), nullable=True)
    new_status: Mapped[TokenStatus] = mapped_column(SqlEnum(TokenStatus, name="token_status"), nullable=False)
    changed_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    remarks: Mapped[str] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    token: Mapped[Token] = relationship(back_populates="status_history")


class QualityInspection(Base):
    __tablename__ = "quality_inspections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_id: Mapped[int] = mapped_column(ForeignKey("tokens.id"), nullable=False, unique=True)
    inspector_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    grade: Mapped[str] = mapped_column(String(20), nullable=True)
    moisture_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=True)
    decision: Mapped[str] = mapped_column(String(20), nullable=True)
    remarks: Mapped[str] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str] = mapped_column(Text, nullable=True)
    inspected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    token: Mapped[Token] = relationship(back_populates="quality_inspection")


class Weighment(Base):
    __tablename__ = "weighments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_id: Mapped[int] = mapped_column(ForeignKey("tokens.id"), nullable=False, unique=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    gross_weight: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    tare_weight: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    net_weight: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    reference_number: Mapped[str] = mapped_column(String(100), nullable=True)
    remarks: Mapped[str] = mapped_column(Text, nullable=True)
    weighed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    token: Mapped[Token] = relationship(back_populates="weighment")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_id: Mapped[int] = mapped_column(ForeignKey("tokens.id"), nullable=False, unique=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        SqlEnum(PaymentStatus, name="payment_status"), nullable=False, default=PaymentStatus.PENDING
    )
    initiated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    reference_number: Mapped[str] = mapped_column(String(100), nullable=True)
    failure_reason: Mapped[str] = mapped_column(Text, nullable=True)
    token: Mapped[Token] = relationship(back_populates="payment")


class RequiredDocument(Base):
    __tablename__ = "required_documents"
    __table_args__ = (UniqueConstraint("mandi_id", "document_key", name="uq_required_document_mandi_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mandi_id: Mapped[int] = mapped_column(ForeignKey("mandis.id"), nullable=False, index=True)
    document_key: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_id: Mapped[int] = mapped_column(ForeignKey("tokens.id"), nullable=True, index=True)
    notification_type: Mapped[str] = mapped_column(String(60), nullable=False)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, default="IN_APP")
    phone_number: Mapped[str] = mapped_column(String(20), nullable=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="IN_APP")
    delivery_status: Mapped[str] = mapped_column(String(20), nullable=False, default="CREATED")
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)


class Notice(Base):
    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    title_en: Mapped[str] = mapped_column(String(180), nullable=True)
    title_hi: Mapped[str] = mapped_column(String(180), nullable=True)
    title_mr: Mapped[str] = mapped_column(String(180), nullable=True)
    description_en: Mapped[str] = mapped_column(Text, nullable=True)
    description_hi: Mapped[str] = mapped_column(Text, nullable=True)
    description_mr: Mapped[str] = mapped_column(Text, nullable=True)
    notice_type: Mapped[str] = mapped_column(String(30), nullable=False, default="GENERAL")
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="GLOBAL")
    district: Mapped[str] = mapped_column(String(120), nullable=True, index=True)
    center_id: Mapped[int] = mapped_column(ForeignKey("mandis.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    center: Mapped[Mandi] = relationship()
