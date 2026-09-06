from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..models import Payment, PaymentStatus, ProcurementStatusHistory, QualityInspection, Token, TokenStatus, User, UserRole, Weighment
from .notification_service import notify, notify_sms


def transaction(db: Session):
    if db.in_transaction():
        db.commit()
    return db.begin()


def require_officer(actor: User) -> None:
    if actor.role not in (UserRole.OFFICER, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="Officer permissions are required")

VALID_TRANSITIONS = {
    TokenStatus.BOOKED: {TokenStatus.ARRIVED},
    TokenStatus.ARRIVED: {TokenStatus.WAITING},
    TokenStatus.WAITING: {TokenStatus.QUALITY_CHECK},
    TokenStatus.QUALITY_CHECK: {TokenStatus.WEIGHMENT, TokenStatus.REJECTED},
    TokenStatus.WEIGHMENT: {TokenStatus.ACCEPTED, TokenStatus.REJECTED},
    TokenStatus.ACCEPTED: {TokenStatus.PAYMENT_PENDING},
    TokenStatus.PAYMENT_PENDING: {TokenStatus.PAYMENT_INITIATED},
    TokenStatus.PAYMENT_INITIATED: {TokenStatus.PAYMENT_PROCESSING},
    TokenStatus.PAYMENT_PROCESSING: {TokenStatus.PAYMENT_COMPLETED, TokenStatus.PAYMENT_FAILED},
    TokenStatus.PAYMENT_FAILED: {TokenStatus.PAYMENT_INITIATED},
    TokenStatus.IN_YARD: {TokenStatus.WEIGHING, TokenStatus.COMPLETED},
    TokenStatus.WEIGHING: {TokenStatus.COMPLETED},
}


def add_history(db: Session, token: Token, previous: TokenStatus | None, new: TokenStatus, actor: User | None, remarks: str | None = None) -> None:
    db.add(ProcurementStatusHistory(token_id=token.id, previous_status=previous, new_status=new, changed_by_id=actor.id if actor else None, remarks=remarks))


def transition(db: Session, token_id: int, new_status: TokenStatus, actor: User, remarks: str | None = None) -> Token:
    require_officer(actor)
    with transaction(db):
        token = db.scalar(select(Token).where(Token.id == token_id).with_for_update().options(selectinload(Token.farmer)))
        if token is None:
            raise HTTPException(status_code=404, detail="Token not found")
        if actor.role.value == "FARMER" and token.farmer_id != actor.id:
            raise HTTPException(status_code=403, detail="Token does not belong to this farmer")
        allowed = VALID_TRANSITIONS.get(token.status, set())
        if new_status not in allowed:
            raise HTTPException(status_code=409, detail=f"Invalid transition: {token.status.value} -> {new_status.value}")
        previous = token.status
        token.status = new_status
        if new_status == TokenStatus.ARRIVED:
            token.arrived_at = datetime.now(timezone.utc)
        add_history(db, token, previous, new_status, actor, remarks)
        notify(db, token.farmer, token, "TOKEN_STATUS_UPDATED", "Procurement status updated", f"Your token is now {new_status.value}.")
        if new_status == TokenStatus.WAITING:
            from .queue_service import queue_snapshot
            queue = queue_snapshot(db, token)
            if queue["queue_position"] is not None and queue["queue_position"] <= 2:
                notify_sms(db, token.farmer, token, "TURN_APPROACHING", "Your turn is approaching", f"Kisan Setu: Your turn is approaching. Token: {token.token_code}. Estimated wait: {queue['estimated_wait_minutes']} minutes. Please be ready at the procurement center.")
        db.flush()
        return token


def record_quality(db: Session, token_id: int, actor: User, grade: str | None, moisture: Decimal | None, decision: str, remarks: str | None, rejection_reason: str | None) -> Token:
    require_officer(actor)
    if moisture is not None and moisture < 0:
        raise HTTPException(status_code=422, detail="Moisture cannot be negative")
    if decision == "REJECTED" and not rejection_reason:
        raise HTTPException(status_code=422, detail="Rejection reason is required")
    with transaction(db):
        token = db.scalar(select(Token).where(Token.id == token_id).with_for_update().options(selectinload(Token.farmer)))
        if token is None:
            raise HTTPException(status_code=404, detail="Token not found")
        if token.status != TokenStatus.QUALITY_CHECK:
            raise HTTPException(status_code=409, detail="Quality inspection requires QUALITY_CHECK status")
        if token.quality_inspection:
            inspection = token.quality_inspection
            inspection.grade, inspection.moisture_percentage, inspection.decision = grade, moisture, decision
            inspection.remarks, inspection.rejection_reason = remarks, rejection_reason
        else:
            inspection = QualityInspection(token_id=token.id, inspector_id=actor.id, grade=grade, moisture_percentage=moisture, decision=decision, remarks=remarks, rejection_reason=rejection_reason)
            db.add(inspection)
        next_status = TokenStatus.REJECTED if decision == "REJECTED" else TokenStatus.WEIGHMENT
        add_history(db, token, token.status, next_status, actor, rejection_reason or remarks)
        token.status = next_status
        notify(db, token.farmer, token, "QUALITY_COMPLETED", "Quality inspection completed", rejection_reason or f"Quality result: {decision}.")
        notify_sms(db, token.farmer, token, "QUALITY_COMPLETED", "Quality inspection completed", f"Kisan Setu: Quality inspection completed for token {token.token_code}. Please wait for the next procurement step.")
        db.flush()
        return token


def record_weighment(db: Session, token_id: int, actor: User, gross: Decimal, tare: Decimal, reference: str | None, remarks: str | None) -> Token:
    require_officer(actor)
    if gross <= 0 or tare < 0 or tare >= gross:
        raise HTTPException(status_code=422, detail="Weights must satisfy gross > tare >= 0")
    with transaction(db):
        token = db.scalar(select(Token).where(Token.id == token_id).with_for_update().options(selectinload(Token.farmer)))
        if token is None:
            raise HTTPException(status_code=404, detail="Token not found")
        if token.status != TokenStatus.WEIGHMENT:
            raise HTTPException(status_code=409, detail="Weighment requires WEIGHMENT status")
        if token.weighment:
            raise HTTPException(status_code=409, detail="Weighment already recorded")
        db.add(Weighment(token_id=token.id, operator_id=actor.id, gross_weight=gross, tare_weight=tare, net_weight=gross - tare, reference_number=reference, remarks=remarks))
        notify(db, token.farmer, token, "WEIGHMENT_COMPLETED", "Weighment completed", f"Net weight: {gross - tare}.")
        db.flush()
        return token


def decide(db: Session, token_id: int, actor: User, accepted: bool, reason: str | None) -> Token:
    require_officer(actor)
    if not accepted and not reason:
        raise HTTPException(status_code=422, detail="Rejection reason is required")
    with transaction(db):
        token = db.scalar(select(Token).where(Token.id == token_id).with_for_update().options(selectinload(Token.farmer)))
        if token is None:
            raise HTTPException(status_code=404, detail="Token not found")
        if token.status != TokenStatus.WEIGHMENT:
            raise HTTPException(status_code=409, detail="Procurement decision requires WEIGHMENT status")
        if token.weighment is None:
            raise HTTPException(status_code=409, detail="Record weighment before making a procurement decision")
        first_status = TokenStatus.ACCEPTED if accepted else TokenStatus.REJECTED
        add_history(db, token, token.status, first_status, actor, reason)
        token.status = first_status
        if accepted:
            add_history(db, token, TokenStatus.ACCEPTED, TokenStatus.PAYMENT_PENDING, actor, "Procurement accepted")
            token.status = TokenStatus.PAYMENT_PENDING
            if token.payment is None:
                token.payment = Payment(
                    token_id=token.id,
                    farmer_id=token.farmer_id,
                    amount=token.expected_tonnage * settings.demo_price_per_tonne,
                    status=PaymentStatus.PENDING,
                )
                db.add(token.payment)
            notify_sms(db, token.farmer, token, "PROCUREMENT_ACCEPTED", "Procurement accepted", f"Kisan Setu: Procurement accepted for token {token.token_code}. Quantity: {token.expected_tonnage:.2f} quintals. Proceeding to payment processing.")
        notify(db, token.farmer, token, "PROCUREMENT_DECISION", "Procurement decision", reason or "Procurement accepted.")
        db.flush()
        return token


def update_payment(db: Session, token_id: int, actor: User, new_status: PaymentStatus) -> Payment:
    require_officer(actor)
    with transaction(db):
        token = db.scalar(select(Token).where(Token.id == token_id).with_for_update().options(selectinload(Token.farmer)))
        if token is None:
            raise HTTPException(status_code=404, detail="Token not found")
        expected = {
            TokenStatus.PAYMENT_PENDING: (PaymentStatus.PENDING, {PaymentStatus.INITIATED}, TokenStatus.PAYMENT_INITIATED),
            TokenStatus.PAYMENT_INITIATED: (PaymentStatus.INITIATED, {PaymentStatus.PROCESSING}, TokenStatus.PAYMENT_PROCESSING),
            TokenStatus.PAYMENT_PROCESSING: (PaymentStatus.PROCESSING, {PaymentStatus.COMPLETED, PaymentStatus.FAILED}, None),
        }
        if token.status not in expected:
            raise HTTPException(status_code=409, detail="Invalid payment transition")
        current_payment_status, allowed_targets, next_token_status = expected[token.status]
        payment = token.payment or Payment(
            token_id=token.id,
            farmer_id=token.farmer_id,
            amount=token.expected_tonnage * settings.demo_price_per_tonne,
            status=current_payment_status,
        )
        if payment.status != current_payment_status or new_status not in allowed_targets:
            raise HTTPException(status_code=409, detail="Invalid payment transition")
        payment.status = new_status
        if payment.id is None:
            db.add(payment)
        if next_token_status is None:
            next_token_status = TokenStatus.PAYMENT_COMPLETED if new_status == PaymentStatus.COMPLETED else TokenStatus.PAYMENT_FAILED
        add_history(db, token, token.status, next_token_status, actor, f"Payment {new_status.value}")
        token.status = next_token_status
        notify(db, token.farmer, token, "PAYMENT_UPDATED", "Payment updated", f"Payment is {new_status.value}.")
        sms_event = {
            PaymentStatus.INITIATED: ("PAYMENT_INITIATED", "Payment initiated", f"Kisan Setu: Payment has been initiated for token {token.token_code}. Amount: ₹{payment.amount:,.2f}."),
            PaymentStatus.COMPLETED: ("PAYMENT_COMPLETED", "Payment completed", f"Kisan Setu: Payment completed successfully for token {token.token_code}. Amount: ₹{payment.amount:,.2f}. Thank you for using Kisan Setu."),
            PaymentStatus.FAILED: ("PAYMENT_FAILED", "Payment failed", f"Kisan Setu: Payment could not be completed for token {token.token_code}. Please contact the mandi officer."),
        }.get(new_status)
        if sms_event:
            notify_sms(db, token.farmer, token, sms_event[0], sms_event[1], sms_event[2])
        db.flush()
        return payment