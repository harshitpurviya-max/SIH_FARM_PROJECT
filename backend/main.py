from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .config import settings
from .database import Base, engine, get_db
from .models import Booking, Mandi, Notice, Notification, Payment, RequiredDocument, Slot, Token, TokenStatus, User, UserRole
from .realtime import ConnectionManager
from .schemas import (
    ActiveProcurementRead, AuthResponse, BookingCreate, BookingRead, DecisionCreate, ForgotPasswordRequest,
    LoginRequest, MandiRead, NotificationRead, PaymentUpdate, QualityCreate, QueueRead, RegisterRequest,
    NoticeCreate, NoticeRead, NoticeUpdate, RequiredDocumentCreate, RequiredDocumentRead, ResetPasswordRequest, SlotRead, StatusHistoryRead,
    TokenStatusUpdate, UserRead, VerifyOtpRequest, WeighmentCreate,
)
from .services.auth_service import (
    authenticate,
    create_access_token,
    create_demo_otp,
    current_user,
    generate_demo_farmer_id,
    hash_password,
    optional_current_user,
    require_roles,
    reset_password_for_phone,
)
from .services.booking_service import create_booking
from .services.procurement_service import decide, record_quality, record_weighment, transition, update_payment
from .services.queue_service import queue_snapshot
from .services.notice_service import active_notices, validate_notice_dates, validate_notice_target

manager = ConnectionManager(settings.redis_url)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    await manager.start()
    yield
    await manager.stop()


app = FastAPI(title="SIHFarm Procurement API", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://sih-farm-project.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def token_event(token: Token, event_type: str = "TOKEN_STATUS_UPDATED") -> dict:
    return {"type": event_type, "token": {"id": token.id, "token_number": token.token_code, "status": token.status.value, "last_updated_at": token.last_updated_at.isoformat() if token.last_updated_at else None}}


def user_token(token: Token, user: User) -> None:
    if user.role == UserRole.FARMER and token.farmer_id != user.id:
        raise HTTPException(status_code=403, detail="This procurement does not belong to you")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/register", response_model=AuthResponse, status_code=201)
def register(request: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    if request.role != UserRole.FARMER:
        raise HTTPException(status_code=403, detail="Public registration only creates farmer accounts")
    if db.scalar(select(User).where(User.phone == request.phone)):
        raise HTTPException(status_code=409, detail="A user with this phone already exists")
    user = User(
        phone=request.phone,
        full_name=request.full_name,
        role=UserRole.FARMER,
        farmer_id=generate_demo_farmer_id(0),
        password_hash=hash_password(request.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user.farmer_id = generate_demo_farmer_id(user.id)
    db.commit()
    db.refresh(user)
    return {"access_token": create_access_token(user), "user": user}


@app.post("/api/auth/login", response_model=AuthResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> dict:
    user = authenticate(db, request.phone, request.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid phone or password")
    return {"access_token": create_access_token(user), "user": user}


@app.get("/api/auth/me", response_model=UserRead)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)) -> User:
    if not user.farmer_id:
        user.farmer_id = generate_demo_farmer_id(user.id)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@app.get("/api/demo-config")
def demo_config() -> dict:
    return {
        "start_date": settings.demo_start_date.isoformat(),
        "end_date": settings.demo_end_date.isoformat(),
        "unit": "quintal",
        "slot_windows": [
            {"start": "08:00:00", "end": "09:00:00"},
            {"start": "09:00:00", "end": "10:00:00"},
            {"start": "10:00:00", "end": "11:00:00"},
            {"start": "11:00:00", "end": "12:00:00"},
            {"start": "13:00:00", "end": "14:00:00"},
            {"start": "14:00:00", "end": "15:00:00"},
            {"start": "15:00:00", "end": "16:00:00"},
        ],
    }


@app.get("/api/notices", response_model=list[NoticeRead])
def list_notices(
    district: str | None = Query(default=None),
    center_id: int | None = Query(default=None, gt=0),
    user: User | None = Depends(optional_current_user),
    db: Session = Depends(get_db),
) -> list[Notice]:
    if user is None and (district or center_id):
        raise HTTPException(status_code=401, detail="Authentication required for targeted notices")
    return active_notices(db, district, center_id)


@app.get("/api/notices/{notice_id}", response_model=NoticeRead)
def notice_details(
    notice_id: int,
    district: str | None = Query(default=None),
    center_id: int | None = Query(default=None, gt=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Notice:
    notice = db.get(Notice, notice_id)
    if notice is None or notice.status != "PUBLISHED":
        raise HTTPException(status_code=404, detail="Notice not found")
    now = datetime.now(timezone.utc)
    if notice.published_at and notice.published_at > now or notice.expires_at and notice.expires_at < now:
        raise HTTPException(status_code=404, detail="Notice is not active")
    if notice not in active_notices(db, district, center_id):
        raise HTTPException(status_code=404, detail="Notice is not relevant to this context")
    return notice


@app.post("/api/officer/notices", response_model=NoticeRead, status_code=201)
async def create_notice(request: NoticeCreate, user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)), db: Session = Depends(get_db)) -> Notice:
    validate_notice_target(db, request.scope, request.district, request.center_id)
    validate_notice_dates(request.published_at, request.expires_at)
    values = request.model_dump()
    values["title_en"] = values.get("title_en") or values["title"]
    values["description_en"] = values.get("description_en") or values["description"]
    if values["status"] == "PUBLISHED" and values["published_at"] is None:
        values["published_at"] = datetime.now(timezone.utc)
    notice = Notice(created_by=user.id, **values)
    db.add(notice)
    db.commit()
    db.refresh(notice)
    if notice.status == "PUBLISHED":
        try:
            await manager.publish({"type": "NOTICE_PUBLISHED", "notice_id": notice.id})
        except Exception:
            pass
    return notice


@app.get("/api/officer/notices", response_model=list[NoticeRead])
def officer_notices(user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)), db: Session = Depends(get_db)) -> list[Notice]:
    return list(db.scalars(select(Notice).options(joinedload(Notice.center)).order_by(Notice.created_at.desc())))


@app.patch("/api/officer/notices/{notice_id}", response_model=NoticeRead)
async def update_notice(notice_id: int, request: NoticeUpdate, user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)), db: Session = Depends(get_db)) -> Notice:
    notice = db.get(Notice, notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found")
    values = request.model_dump(exclude_unset=True)
    scope = values.get("scope", notice.scope)
    district = values.get("district", notice.district)
    center_id = values.get("center_id", notice.center_id)
    validate_notice_target(db, scope, district, center_id)
    validate_notice_dates(values.get("published_at", notice.published_at), values.get("expires_at", notice.expires_at))
    for key, value in values.items():
        setattr(notice, key, value)
    if notice.status == "PUBLISHED" and notice.published_at is None:
        notice.published_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(notice)
    if notice.status == "PUBLISHED":
        try:
            await manager.publish({"type": "NOTICE_PUBLISHED", "notice_id": notice.id})
        except Exception:
            pass
    return notice


@app.delete("/api/officer/notices/{notice_id}", status_code=204)
def archive_notice(notice_id: int, user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)), db: Session = Depends(get_db)) -> None:
    notice = db.get(Notice, notice_id)
    if notice is None:
        raise HTTPException(status_code=404, detail="Notice not found")
    notice.status = "ARCHIVED"
    db.commit()


@app.get("/api/districts")
def districts(db: Session = Depends(get_db)) -> list[str]:
    values = [item.district for item in db.scalars(select(Mandi).where(Mandi.is_active.is_(True))).all() if item.district]
    return list(dict.fromkeys(values))


@app.get("/api/mandis/district/{district}")
def mandis_by_district(district: str, db: Session = Depends(get_db)) -> list[MandiRead]:
    return list(db.scalars(select(Mandi).where(Mandi.is_active.is_(True), Mandi.district == district).order_by(Mandi.name)))


@app.get("/api/crops")
def crops(db: Session = Depends(get_db)) -> list[str]:
    crop_names = set(settings.demo_crop_msp)
    for mandi in db.scalars(select(Mandi).where(Mandi.is_active.is_(True))).all():
        if mandi.available_crops:
            crop_names.update(mandi.available_crops)
    return sorted(crop_names)


@app.get("/api/crops/{crop_name}/msp")
def crop_msp(crop_name: str, db: Session = Depends(get_db)) -> dict:
    normalized = crop_name.strip().title()
    value = settings.crop_msp(normalized)
    return {
        "crop": normalized,
        "msp": float(value),
        "unit": "quintal",
        "source_name": "Government of India",
        "source_year": "2026-27",
        "season": "Kharif",
        "currency": "INR",
    }


@app.post("/api/auth/forgot-password")
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.phone == request.phone))
    if user is None:
        raise HTTPException(status_code=404, detail="No farmer account found for this mobile number")
    otp = create_demo_otp(request.phone)
    return {"message": "OTP sent to demo device", "demo_otp": otp}


@app.post("/api/auth/verify-otp")
def verify_otp(request: VerifyOtpRequest, db: Session = Depends(get_db)) -> dict:
    user = db.scalar(select(User).where(User.phone == request.phone))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    from .services.auth_service import verify_demo_otp

    if not verify_demo_otp(request.phone, request.otp):
        raise HTTPException(status_code=401, detail="Invalid or expired OTP")
    return {"message": "OTP verified"}


@app.post("/api/auth/reset-password")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict:
    user = reset_password_for_phone(db, request.phone, request.otp, request.new_password)
    return {"message": "Password updated successfully", "user": user}


@app.get("/api/mandis", response_model=list[MandiRead])
def list_mandis(db: Session = Depends(get_db)) -> list[Mandi]:
    return list(db.scalars(select(Mandi).where(Mandi.is_active.is_(True)).order_by(Mandi.name)))


@app.get("/api/mandis/{mandi_id}", response_model=MandiRead)
def get_mandi(mandi_id: int, db: Session = Depends(get_db)) -> Mandi:
    mandi = db.get(Mandi, mandi_id)
    if mandi is None:
        raise HTTPException(status_code=404, detail="Mandi not found")
    return mandi


@app.get("/api/slots", response_model=list[SlotRead])
def list_slots(db: Session = Depends(get_db)) -> list[Slot]:
    query = select(Slot).options(selectinload(Slot.mandi)).order_by(Slot.date, Slot.start_time)
    return list(db.scalars(query))


@app.get("/api/mandis/{mandi_id}/slots", response_model=list[SlotRead])
def list_mandi_slots(mandi_id: int, db: Session = Depends(get_db)) -> list[Slot]:
    query = select(Slot).where(Slot.mandi_id == mandi_id).options(selectinload(Slot.mandi)).order_by(Slot.date, Slot.start_time)
    return list(db.scalars(query))


@app.post("/api/bookings", response_model=BookingRead, status_code=201)
def create_farmer_booking(request: BookingCreate, user: User = Depends(require_roles(UserRole.FARMER)), db: Session = Depends(get_db)) -> Token:
    token = create_booking(db, request.slot_id if hasattr(request, "slot_id") else 0, user, user.phone, request.crop_type, request.expected_tonnage)
    return token


@app.post("/api/slots/{slot_id}/book", response_model=BookingRead, status_code=201)
def legacy_book_slot(slot_id: int, booking: BookingCreate, user: User | None = Depends(optional_current_user), db: Session = Depends(get_db)) -> Token:
    token = create_booking(db, slot_id, user, booking.farmer_phone or (user.phone if user else ""), booking.crop_type, booking.expected_tonnage)
    return token


@app.get("/api/tokens", response_model=list[BookingRead])
def list_tokens(user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)), db: Session = Depends(get_db)) -> list[Token]:
    return list(db.scalars(select(Token).order_by(Token.id.desc())))


@app.get("/api/farmer/bookings", response_model=list[BookingRead])
def farmer_bookings(user: User = Depends(require_roles(UserRole.FARMER)), db: Session = Depends(get_db)) -> list[Token]:
    return list(db.scalars(select(Token).where(Token.farmer_id == user.id).order_by(Token.id.desc())))


@app.get("/api/tokens/{token_id}", response_model=BookingRead)
def token_details(token_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Token:
    token = db.get(Token, token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="Token not found")
    user_token(token, user)
    return token


@app.patch("/api/tokens/{token_id}/status", response_model=BookingRead)
async def update_token_status(token_id: int, update: TokenStatusUpdate, user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)), db: Session = Depends(get_db)) -> Token:
    token = transition(db, token_id, update.status, user, update.remarks)
    await manager.publish(token_event(token))
    return token


@app.post("/api/officer/tokens/{token_id}/arrival", response_model=BookingRead)
async def mark_arrival(token_id: int, user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)), db: Session = Depends(get_db)) -> Token:
    token = transition(db, token_id, TokenStatus.ARRIVED, user, "Farmer arrived at mandi")
    await manager.publish(token_event(token))
    return token


@app.get("/api/tokens/{token_id}/queue", response_model=QueueRead)
def token_queue(token_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    token = db.get(Token, token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="Token not found")
    user_token(token, user)
    return queue_snapshot(db, token)


@app.get("/api/officer/mandis/{mandi_id}/queue", response_model=list[BookingRead])
def officer_queue(mandi_id: int, user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)), db: Session = Depends(get_db)) -> list[Token]:
    return list(db.scalars(select(Token).where(Token.mandi_id == mandi_id).order_by(Token.created_at, Token.id)))


@app.get("/api/tokens/{token_id}/status-history", response_model=list[StatusHistoryRead])
def status_history(token_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list:
    token = db.get(Token, token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="Token not found")
    user_token(token, user)
    return list(token.status_history)


@app.post("/api/officer/tokens/{token_id}/quality", response_model=BookingRead)
async def quality(token_id: int, request: QualityCreate, user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)), db: Session = Depends(get_db)) -> Token:
    token = record_quality(db, token_id, user, request.grade, request.moisture_percentage, request.decision, request.remarks, request.rejection_reason)
    await manager.publish(token_event(token, "QUALITY_UPDATED"))
    return token


@app.get("/api/tokens/{token_id}/quality")
def get_quality(token_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    token = db.get(Token, token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="Token not found")
    user_token(token, user)
    item = token.quality_inspection
    return item.__dict__ if item else {}


@app.post("/api/officer/tokens/{token_id}/weighment", response_model=BookingRead)
async def weighment(token_id: int, request: WeighmentCreate, user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)), db: Session = Depends(get_db)) -> Token:
    token = record_weighment(db, token_id, user, request.gross_weight, request.tare_weight, request.reference_number, request.remarks)
    await manager.publish(token_event(token, "WEIGHMENT_UPDATED"))
    return token


@app.get("/api/tokens/{token_id}/weighment")
def get_weighment(token_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    token = db.get(Token, token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="Token not found")
    user_token(token, user)
    item = token.weighment
    return item.__dict__ if item else {}


@app.post("/api/officer/tokens/{token_id}/decision", response_model=BookingRead)
async def decision(token_id: int, request: DecisionCreate, user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)), db: Session = Depends(get_db)) -> Token:
    token = decide(db, token_id, user, request.accepted, request.reason)
    await manager.publish(token_event(token))
    return token


@app.get("/api/tokens/{token_id}/payment")
def get_payment(token_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    token = db.get(Token, token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="Token not found")
    user_token(token, user)
    item = token.payment
    return item.__dict__ if item else {"status": "PENDING"}


@app.patch("/api/officer/tokens/{token_id}/payment", response_model=dict)
async def payment(token_id: int, request: PaymentUpdate, user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)), db: Session = Depends(get_db)) -> dict:
    item = update_payment(db, token_id, user, request.status)
    await manager.publish({"type": "PAYMENT_UPDATED", "token_id": token_id, "status": request.status.value})
    return {"id": item.id, "status": item.status.value, "amount": item.amount}


@app.get("/api/notifications", response_model=list[NotificationRead])
def notifications(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[Notification]:
    return list(db.scalars(select(Notification).where(Notification.recipient_id == user.id).order_by(Notification.created_at.desc())))


@app.get("/api/officer/tokens/{token_id}/notifications", response_model=list[NotificationRead])
def officer_token_notifications(token_id: int, user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)), db: Session = Depends(get_db)) -> list[Notification]:
    return list(db.scalars(select(Notification).where(Notification.token_id == token_id, Notification.channel == "SMS").order_by(Notification.created_at.desc())))


@app.patch("/api/notifications/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(notification_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Notification:
    item = db.get(Notification, notification_id)
    if item is None or item.recipient_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    item.is_read = True
    db.commit()
    return item


@app.get("/api/mandis/{mandi_id}/required-documents", response_model=list[RequiredDocumentRead])
def required_documents(mandi_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[RequiredDocument]:
    return list(db.scalars(select(RequiredDocument).where(RequiredDocument.mandi_id == mandi_id)))


@app.post("/api/officer/mandis/{mandi_id}/required-documents", response_model=RequiredDocumentRead)
def add_required_document(mandi_id: int, request: RequiredDocumentCreate, user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)), db: Session = Depends(get_db)) -> RequiredDocument:
    item = RequiredDocument(mandi_id=mandi_id, **request.model_dump())
    db.add(item)
    try:
        db.commit()
        db.refresh(item)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Document key already exists for this mandi") from exc
    return item


@app.get("/api/farmer/active-procurement", response_model=ActiveProcurementRead)
def active_procurement(user: User = Depends(require_roles(UserRole.FARMER)), db: Session = Depends(get_db)) -> dict:
    token = db.scalar(select(Token).where(Token.farmer_id == user.id, Token.status.not_in([TokenStatus.COMPLETED, TokenStatus.REJECTED, TokenStatus.PAYMENT_COMPLETED])).order_by(Token.id.desc()))
    if token is None:
        raise HTTPException(status_code=404, detail="No active procurement")
    return {"token": token, "mandi": token.mandi, "slot": token.slot, "queue": queue_snapshot(db, token), "timeline": token.status_history, "quality": token.quality_inspection.__dict__ if token.quality_inspection else None, "weighment": token.weighment.__dict__ if token.weighment else None, "payment": token.payment.__dict__ if token.payment else None}


@app.websocket("/ws/queue")
async def queue_websocket(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
