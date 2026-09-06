from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import PaymentStatus, TokenStatus, UserRole


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    phone: str
    full_name: str | None = None
    farmer_id: str | None = None
    role: UserRole


class RegisterRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=20)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=150)
    role: UserRole = UserRole.FARMER


class LoginRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=20)
    password: str


class ForgotPasswordRequest(BaseModel):
    phone: str = Field(min_length=7, max_length=20)


class VerifyOtpRequest(ForgotPasswordRequest):
    otp: str = Field(min_length=6, max_length=6)


class ResetPasswordRequest(VerifyOtpRequest):
    new_password: str = Field(min_length=8, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class MandiRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    district: str | None = None
    state: str | None = None
    location: str
    address: str | None = None
    daily_capacity_quintals: Decimal | None = None
    hourly_capacity: int
    is_active: bool = True
    procurement_window_start: time | None = None
    procurement_window_end: time | None = None
    available_crops: list[str] | None = None
    last_updated_at: datetime | None = None


class SlotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    mandi_id: int
    mandi: MandiRead
    date: date
    start_time: time
    end_time: time
    max_tonnage: Decimal
    booked_tonnage: Decimal


class BookingCreate(BaseModel):
    slot_id: int | None = Field(default=None, gt=0)
    farmer_phone: str | None = Field(default=None, min_length=7, max_length=20)
    crop_type: str = Field(min_length=1, max_length=100)
    expected_tonnage: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=3)
    quantity_quintals: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=3)
    expected_quintals: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=3)

    @model_validator(mode="before")
    @classmethod
    def normalize_quantity(cls, values):
        if not isinstance(values, dict):
            return values
        quantity = values.get("expected_tonnage")
        for key in ("quantity_quintals", "expected_quintals"):
            if values.get(key) is not None:
                quantity = values[key]
                break
        if quantity is not None and "expected_tonnage" not in values:
            values["expected_tonnage"] = quantity
        return values


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slot_id: int
    farmer_phone: str
    crop_type: str
    expected_tonnage: Decimal
    status: TokenStatus
    token_code: str
    qr_hash: str
    booking_id: int | None = None
    mandi_id: int | None = None
    created_at: datetime | None = None
    last_updated_at: datetime | None = None
    farmer_display_id: str | None = None
    district: str | None = None
    mandi_name: str | None = None


class TokenStatusUpdate(BaseModel):
    status: TokenStatus
    remarks: str | None = Field(default=None, max_length=500)


class QualityCreate(BaseModel):
    grade: str | None = Field(default=None, max_length=20)
    moisture_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    decision: str = Field(pattern="^(ACCEPTED|REJECTED)$")
    remarks: str | None = Field(default=None, max_length=1000)
    rejection_reason: str | None = Field(default=None, max_length=1000)


class WeighmentCreate(BaseModel):
    gross_weight: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    tare_weight: Decimal = Field(ge=0, max_digits=10, decimal_places=3)
    reference_number: str | None = Field(default=None, max_length=100)
    remarks: str | None = Field(default=None, max_length=1000)


class DecisionCreate(BaseModel):
    accepted: bool
    reason: str | None = Field(default=None, max_length=1000)


class PaymentUpdate(BaseModel):
    status: PaymentStatus


class RequiredDocumentCreate(BaseModel):
    document_key: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=255)
    is_required: bool = True


class RequiredDocumentRead(RequiredDocumentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    mandi_id: int


class QueueRead(BaseModel):
    token_number: str
    queue_position: int | None
    people_ahead: int
    current_serving: str | None
    estimated_wait_minutes: int
    last_updated_at: datetime
    freshness: str


class StatusHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    previous_status: TokenStatus | None
    new_status: TokenStatus
    changed_by_id: int | None
    remarks: str | None
    changed_at: datetime


class ActiveProcurementRead(BaseModel):
    token: BookingRead
    mandi: MandiRead | None
    slot: SlotRead | None
    queue: QueueRead
    timeline: list[StatusHistoryRead]
    quality: dict | None = None
    weighment: dict | None = None
    payment: dict | None = None


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    token_id: int | None
    notification_type: str
    event_type: str
    phone_number: str | None = None
    channel: str
    delivery_status: str
    title: str
    message: str
    is_read: bool
    created_at: datetime
    sent_at: datetime | None = None


class NoticeCreate(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=5, max_length=3000)
    title_en: str | None = Field(default=None, max_length=180)
    title_hi: str | None = Field(default=None, max_length=180)
    title_mr: str | None = Field(default=None, max_length=180)
    description_en: str | None = Field(default=None, max_length=3000)
    description_hi: str | None = Field(default=None, max_length=3000)
    description_mr: str | None = Field(default=None, max_length=3000)
    notice_type: str = Field(pattern="^(GENERAL|IMPORTANT|NEW|DISTRICT|CENTER|PAYMENT|SYSTEM|INFO)$")
    scope: str = Field(pattern="^(GLOBAL|DISTRICT|CENTER)$")
    district: str | None = Field(default=None, min_length=2, max_length=120)
    center_id: int | None = Field(default=None, gt=0)
    published_at: datetime | None = None
    expires_at: datetime | None = None
    status: str = Field(default="DRAFT", pattern="^(DRAFT|PUBLISHED|EXPIRED|ARCHIVED)$")


class NoticeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=180)
    description: str | None = Field(default=None, min_length=5, max_length=3000)
    title_en: str | None = Field(default=None, max_length=180)
    title_hi: str | None = Field(default=None, max_length=180)
    title_mr: str | None = Field(default=None, max_length=180)
    description_en: str | None = Field(default=None, max_length=3000)
    description_hi: str | None = Field(default=None, max_length=3000)
    description_mr: str | None = Field(default=None, max_length=3000)
    notice_type: str | None = Field(default=None, pattern="^(GENERAL|IMPORTANT|NEW|DISTRICT|CENTER|PAYMENT|SYSTEM|INFO)$")
    scope: str | None = Field(default=None, pattern="^(GLOBAL|DISTRICT|CENTER)$")
    district: str | None = Field(default=None, min_length=2, max_length=120)
    center_id: int | None = Field(default=None, gt=0)
    published_at: datetime | None = None
    expires_at: datetime | None = None
    status: str | None = Field(default=None, pattern="^(DRAFT|PUBLISHED|EXPIRED|ARCHIVED)$")


class NoticeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str
    title_en: str | None = None
    title_hi: str | None = None
    title_mr: str | None = None
    description_en: str | None = None
    description_hi: str | None = None
    description_mr: str | None = None
    notice_type: str
    scope: str
    district: str | None
    center_id: int | None
    status: str
    published_at: datetime | None
    expires_at: datetime | None
    created_by: int
    created_at: datetime
    updated_at: datetime
    center: MandiRead | None = None
