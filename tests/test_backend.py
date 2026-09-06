from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import Base
from backend.models import Mandi, Notice, Notification, PaymentStatus, Slot, TokenStatus, User, UserRole
from backend.services.notice_service import active_notices, validate_notice_dates, validate_notice_target
from backend.seed_data import CENTER_DATA
from backend.services.auth_service import hash_password, verify_password
from backend.services.booking_service import create_booking
from backend.services.procurement_service import decide, record_quality, record_weighment, transition, update_payment
from backend.services.queue_service import queue_snapshot


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        mandi = Mandi(name="Test Mandi", location="Test", hourly_capacity=10, available_crops=["Wheat"])
        slot = Slot(mandi=mandi, date=__import__("datetime").date.today(), start_time=__import__("datetime").time(8), end_time=__import__("datetime").time(10), max_tonnage=Decimal("20"), booked_tonnage=Decimal("0"))
        farmer = User(phone="+911234567890", role=UserRole.FARMER, password_hash=hash_password("password123"))
        officer = User(phone="+919876543210", role=UserRole.OFFICER, password_hash=hash_password("password123"))
        session.add_all([mandi, slot, farmer, officer])
        session.commit()
        yield session, slot, farmer, officer


def test_password_hash_and_booking_are_idempotent(db):
    session, slot, farmer, _ = db
    assert verify_password("password123", farmer.password_hash)
    first = create_booking(session, slot.id, farmer, farmer.phone, "Wheat", Decimal("2"))
    second = create_booking(session, slot.id, farmer, farmer.phone, "Wheat", Decimal("2"))
    assert first.id == second.id
    assert first.token_code.startswith("KSN-")


def test_valid_lifecycle_and_history(db):
    session, slot, farmer, officer = db
    token = create_booking(session, slot.id, farmer, farmer.phone, "Wheat", Decimal("2"))
    for state in (TokenStatus.ARRIVED, TokenStatus.WAITING, TokenStatus.QUALITY_CHECK):
        token = transition(session, token.id, state, officer)
    token = record_quality(session, token.id, officer, "A", Decimal("11.8"), "ACCEPTED", None, None)
    token = record_weighment(session, token.id, officer, Decimal("52"), Decimal("2"), "WB-1", None)
    token = decide(session, token.id, officer, True, None)
    assert token.status == TokenStatus.PAYMENT_PENDING
    payment = update_payment(session, token.id, officer, PaymentStatus.INITIATED)
    assert payment.status == PaymentStatus.INITIATED
    update_payment(session, token.id, officer, PaymentStatus.PROCESSING)
    update_payment(session, token.id, officer, PaymentStatus.COMPLETED)
    assert token.status == TokenStatus.PAYMENT_COMPLETED
    assert len(token.status_history) >= 7


def test_invalid_transition_and_weights_are_rejected(db):
    session, slot, farmer, officer = db
    token = create_booking(session, slot.id, farmer, farmer.phone, "Wheat", Decimal("2"))
    with pytest.raises(Exception):
        transition(session, token.id, TokenStatus.PAYMENT_COMPLETED, officer)
    transition(session, token.id, TokenStatus.ARRIVED, officer)
    transition(session, token.id, TokenStatus.WAITING, officer)
    transition(session, token.id, TokenStatus.QUALITY_CHECK, officer)
    with pytest.raises(Exception):
        record_quality(session, token.id, officer, "C", Decimal("5"), "REJECTED", None, None)


def test_farmer_cannot_run_officer_workflow_or_skip_payment(db):
    session, slot, farmer, officer = db
    token = create_booking(session, slot.id, farmer, farmer.phone, "Wheat", Decimal("2"))
    with pytest.raises(Exception):
        transition(session, token.id, TokenStatus.ARRIVED, farmer)
    with pytest.raises(Exception):
        update_payment(session, token.id, farmer, PaymentStatus.COMPLETED)


def test_queue_position_and_eta(db):
    session, slot, farmer, officer = db
    first = create_booking(session, slot.id, farmer, farmer.phone, "Wheat", Decimal("1"))
    other = User(phone="+911111111111", role=UserRole.FARMER, password_hash=hash_password("password123"))
    session.add(other)
    session.commit()
    second = create_booking(session, slot.id, other, other.phone, "Wheat", Decimal("1"))
    transition(session, first.id, TokenStatus.ARRIVED, officer)
    transition(session, first.id, TokenStatus.WAITING, officer)
    transition(session, second.id, TokenStatus.ARRIVED, officer)
    transition(session, second.id, TokenStatus.WAITING, officer)
    snapshot = queue_snapshot(session, second)
    assert snapshot["queue_position"] == 2
    assert snapshot["people_ahead"] == 1
    assert snapshot["estimated_wait_minutes"] > 0


def test_demo_configuration_uses_quintals_and_moong_msp():
    assert settings.demo_start_date.isoformat() == "2026-09-05"
    assert settings.demo_end_date.isoformat() == "2026-09-17"
    assert settings.demo_start_date <= settings.demo_end_date
    assert settings.crop_msp("Moong") == Decimal("8780")
    assert Decimal("1.000") * Decimal("10") == Decimal("10.000")
    assert Decimal("4.000") * Decimal("10") == Decimal("40.000")


def test_booking_quantity_validation_uses_quintals(db):
    session, slot, farmer, _ = db
    with pytest.raises(Exception):
        create_booking(session, slot.id, farmer, farmer.phone, "Wheat", Decimal("0"))
    with pytest.raises(Exception):
        create_booking(session, slot.id, farmer, farmer.phone, "Wheat", Decimal("999"))


def test_demo_catalog_has_nine_districts_and_multiple_centers():
    districts = {item[2] for item in CENTER_DATA}
    assert districts == {"Vidisha", "Rajgarh", "Barwani", "Guna", "Indore", "Ujjain", "Dewas", "Khandwa", "Khargone"}
    assert all(sum(item[2] == district for item in CENTER_DATA) >= 2 for district in districts)
    assert all(item[3] == "Madhya Pradesh" and item[0].endswith("Center") for item in CENTER_DATA)


def test_sms_events_are_generated_once_and_failure_isolated(db, monkeypatch):
    session, slot, farmer, officer = db
    token = create_booking(session, slot.id, farmer, farmer.phone, "Wheat", Decimal("2"))
    sms = session.query(Notification).filter_by(token_id=token.id, channel="SMS", event_type="BOOKING_CONFIRMED").all()
    assert len(sms) == 1
    from backend.services.notification_service import notify_sms
    notify_sms(session, farmer, token, "BOOKING_CONFIRMED", "Booking confirmed", "duplicate")
    session.flush()
    assert session.query(Notification).filter_by(token_id=token.id, channel="SMS", event_type="BOOKING_CONFIRMED").count() == 1

    monkeypatch.setattr("backend.services.sms_service.get_sms_service", lambda: (_ for _ in ()).throw(RuntimeError("provider unavailable")))
    failed = notify_sms(session, farmer, token, "TEST_FAILURE", "Test", "Failure should be isolated")
    session.flush()
    assert failed.delivery_status == "FAILED"
    transition(session, token.id, TokenStatus.ARRIVED, officer)
    assert token.status == TokenStatus.ARRIVED


def test_lifecycle_sms_events_cover_quality_acceptance_and_payment(db):
    session, slot, farmer, officer = db
    token = create_booking(session, slot.id, farmer, farmer.phone, "Wheat", Decimal("2"))
    for state in (TokenStatus.ARRIVED, TokenStatus.WAITING, TokenStatus.QUALITY_CHECK):
        transition(session, token.id, state, officer)
    record_quality(session, token.id, officer, "A", Decimal("11.8"), "ACCEPTED", None, None)
    record_weighment(session, token.id, officer, Decimal("22"), Decimal("2"), "SMS-1", None)
    decide(session, token.id, officer, True, None)
    update_payment(session, token.id, officer, PaymentStatus.INITIATED)
    update_payment(session, token.id, officer, PaymentStatus.PROCESSING)
    update_payment(session, token.id, officer, PaymentStatus.COMPLETED)
    events = {item.event_type for item in session.query(Notification).filter_by(token_id=token.id, channel="SMS")}
    assert {"BOOKING_CONFIRMED", "TURN_APPROACHING", "QUALITY_COMPLETED", "PROCUREMENT_ACCEPTED", "PAYMENT_INITIATED", "PAYMENT_COMPLETED"} <= events


def test_notice_visibility_and_expiry_are_backend_filtered(db):
    session, slot, farmer, officer = db
    session.query(Mandi).filter(Mandi.id == slot.mandi_id).update({"district": "Indore"})
    second_mandi = Mandi(name="Rau Demo Center", district="Indore", location="Rau, Indore", hourly_capacity=10, available_crops=["Wheat"])
    other_mandi = Mandi(name="Ujjain Demo Center", district="Ujjain", location="Ujjain", hourly_capacity=10, available_crops=["Wheat"])
    session.add_all([second_mandi, other_mandi]); session.flush()
    now = datetime.now(timezone.utc)
    session.add_all([
        Notice(title="Global", description="Global demo notice", notice_type="GENERAL", scope="GLOBAL", status="PUBLISHED", published_at=now, created_by=officer.id),
        Notice(title="Indore", description="Indore demo notice", notice_type="DISTRICT", scope="DISTRICT", district="Indore", status="PUBLISHED", published_at=now, created_by=officer.id),
        Notice(title="Rau", description="Rau demo notice", notice_type="CENTER", scope="CENTER", district="Indore", center_id=second_mandi.id, status="PUBLISHED", published_at=now, created_by=officer.id),
        Notice(title="Expired", description="Expired demo notice", notice_type="IMPORTANT", scope="GLOBAL", status="PUBLISHED", published_at=now - timedelta(days=2), expires_at=now - timedelta(days=1), created_by=officer.id),
        Notice(title="Archived", description="Archived demo notice", notice_type="GENERAL", scope="GLOBAL", status="ARCHIVED", created_by=officer.id),
    ])
    session.commit()
    assert {item.title for item in active_notices(session)} == {"Global"}
    assert {item.title for item in active_notices(session, "Indore")} == {"Global", "Indore"}
    assert {item.title for item in active_notices(session, "Indore", second_mandi.id)} == {"Global", "Indore", "Rau"}
    validate_notice_dates(now, now + timedelta(days=1))
    with pytest.raises(Exception):
        validate_notice_dates(now, now - timedelta(days=1))
    validate_notice_target(session, "GLOBAL", None, None)