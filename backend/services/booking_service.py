import hashlib
import secrets
import string
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Booking, Mandi, Slot, Token, TokenStatus, User, UserRole
from .auth_service import hash_password
from .notification_service import notify, notify_sms
from .procurement_service import add_history, transaction


def token_code(db: Session) -> str:
    for _ in range(10):
        value = "KSN-" + "".join(secrets.choice(string.digits) for _ in range(4))
        if db.scalar(select(Token.id).where(Token.token_code == value)) is None:
            return value
    raise HTTPException(status_code=409, detail="Could not generate a unique token")


def create_booking(db: Session, slot_id: int, farmer: User | None, farmer_phone: str, crop_type: str, expected_tonnage: Decimal) -> Token:
    if slot_id <= 0:
        raise HTTPException(status_code=422, detail="A valid slot is required")
    if expected_tonnage <= 0:
        raise HTTPException(status_code=422, detail="Quantity must be greater than zero")
    with transaction(db):
        slot = db.scalar(select(Slot).where(Slot.id == slot_id).with_for_update())
        if slot is None:
            raise HTTPException(status_code=404, detail="Slot not found")
        mandi = db.get(Mandi, slot.mandi_id)
        if mandi is None or not mandi.is_active:
            raise HTTPException(status_code=409, detail="Mandi is unavailable")
        if mandi.available_crops and crop_type not in mandi.available_crops:
            raise HTTPException(status_code=409, detail="Crop is not accepted at this mandi")
        remaining_capacity = slot.max_tonnage - slot.booked_tonnage
        if expected_tonnage > remaining_capacity:
            raise HTTPException(status_code=409, detail="Insufficient slot capacity")
        if expected_tonnage > Decimal("200.000"):
            raise HTTPException(status_code=422, detail="Booking quantity exceeds the demo maximum")
        if farmer is None:
            farmer = db.scalar(select(User).where(User.phone == farmer_phone))
            if farmer is None:
                farmer = User(phone=farmer_phone, role=UserRole.FARMER, password_hash=hash_password(secrets.token_urlsafe(16)))
                db.add(farmer)
                db.flush()
        duplicate = db.scalar(select(Booking).where(
            Booking.farmer_id == farmer.id, Booking.slot_id == slot_id,
            Booking.crop_type == crop_type, Booking.expected_tonnage == expected_tonnage,
        ))
        if duplicate and duplicate.token:
            return duplicate.token
        booking = Booking(farmer_id=farmer.id, slot_id=slot_id, crop_type=crop_type, expected_tonnage=expected_tonnage)
        db.add(booking)
        db.flush()
        code = token_code(db)
        token = Token(
            booking_id=booking.id, farmer_id=farmer.id, mandi_id=slot.mandi_id, slot_id=slot_id,
            farmer_phone=farmer.phone, crop_type=crop_type, expected_tonnage=expected_tonnage,
            status=TokenStatus.BOOKED, token_code=code,
            qr_hash=hashlib.sha256(f"{booking.id}:{code}:{secrets.token_hex(16)}".encode()).hexdigest(),
        )
        db.add(token)
        db.flush()
        add_history(db, token, None, TokenStatus.BOOKED, farmer, "Booking confirmed")
        notify(db, farmer, token, "BOOKING_CONFIRMED", "Booking confirmed", f"Your token is {code}.")
        notify_sms(
            db, farmer, token, "BOOKING_CONFIRMED", "Booking confirmed",
            f"Kisan Setu: Your procurement slot is confirmed. Token: {code}. Center: {mandi.name}. "
            f"Date: {slot.date.strftime('%d %b %Y')}. Time: {slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')}. "
            f"Crop: {crop_type}. Quantity: {expected_tonnage:.2f} quintals.",
        )
        slot.booked_tonnage += expected_tonnage
        return token