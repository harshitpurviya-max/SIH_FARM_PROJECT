"""Deterministic Kisan Setu demonstration data.

This seed intentionally uses a fixed demo booking window and supports a realistic
Madhya Pradesh procurement flow. The database stores operational quantities in
quintals while the existing schema keeps legacy field names such as
expected_tonnage for compatibility.
"""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from .config import settings
from .database import Base, SessionLocal, engine
from .models import (
    Booking, Mandi, Notice, Notification, Payment, PaymentStatus, ProcurementStatusHistory,
    QualityInspection, RequiredDocument, Slot, Token, TokenStatus, User, UserRole, Weighment,
)
from .services.auth_service import hash_password

DEMO_FARMER_PHONE = "+910000000001"
DEMO_FARMER_PASSWORD = "Kisan@2026"
DEMO_OFFICER_PHONE = "+910000000002"
DEMO_OFFICER_PASSWORD = "Mandi@2026"

CENTER_DATA = [
    ("Ganj Basoda Procurement Center", "Ganj Basoda", "Vidisha", "Madhya Pradesh", "Demo Procurement Center, Ganj Basoda, Vidisha, Madhya Pradesh", ["Wheat", "Maize", "Moong", "Gram"]),
    ("Vidisha Central Procurement Center", "Vidisha", "Vidisha", "Madhya Pradesh", "Demo Procurement Center, Vidisha, Madhya Pradesh", ["Wheat", "Maize", "Moong", "Gram"]),
    ("Biaora Procurement Center", "Biaora", "Rajgarh", "Madhya Pradesh", "Demo Procurement Center, Bhaura, Rajgarh, Madhya Pradesh", ["Wheat", "Gram", "Mustard", "Moong"]),
    ("Rajgarh Central Procurement Center", "Rajgarh", "Rajgarh", "Madhya Pradesh", "Demo Procurement Center, Rajgarh, Madhya Pradesh", ["Wheat", "Gram", "Mustard", "Moong"]),
    ("Shamshabad Procurement Center", "Shamshabad", "Vidisha", "Madhya Pradesh", "Demo Procurement Center, Shamshabad, Vidisha, Madhya Pradesh", ["Wheat", "Maize", "Mustard", "Moong"]),
    ("Sendhwa Procurement Center", "Sendhwa", "Barwani", "Madhya Pradesh", "Demo Procurement Center, Sendhwa, Barwani, Madhya Pradesh", ["Maize", "Moong", "Wheat", "Gram"]),
    ("Barwani Central Procurement Center", "Barwani", "Barwani", "Madhya Pradesh", "Demo Procurement Center, Barwani, Madhya Pradesh", ["Maize", "Moong", "Wheat", "Gram"]),
    ("Guna Procurement Center", "Guna", "Guna", "Madhya Pradesh", "Demo Procurement Center, Guna, Madhya Pradesh", ["Wheat", "Gram", "Mustard", "Moong"]),
    ("Guna Rural Procurement Center", "Raghogarh", "Guna", "Madhya Pradesh", "Demo Procurement Center, Raghogarh, Guna, Madhya Pradesh", ["Wheat", "Gram", "Mustard", "Moong"]),
    ("Indore Central Procurement Center", "Indore", "Indore", "Madhya Pradesh", "Demo Procurement Center, Indore, Madhya Pradesh", ["Wheat", "Maize", "Soybean", "Moong"]),
    ("Rau Procurement Center", "Rau", "Indore", "Madhya Pradesh", "Demo Procurement Center, Rau, Indore, Madhya Pradesh", ["Wheat", "Soybean", "Moong"]),
    ("Sanwer Procurement Center", "Sanwer", "Indore", "Madhya Pradesh", "Demo Procurement Center, Sanwer, Indore, Madhya Pradesh", ["Wheat", "Maize", "Soybean"]),
    ("Ujjain Central Procurement Center", "Ujjain", "Ujjain", "Madhya Pradesh", "Demo Procurement Center, Ujjain, Madhya Pradesh", ["Wheat", "Soybean", "Moong", "Gram"]),
    ("Nagda Procurement Center", "Nagda", "Ujjain", "Madhya Pradesh", "Demo Procurement Center, Nagda, Ujjain, Madhya Pradesh", ["Wheat", "Soybean", "Moong"]),
    ("Tarana Procurement Center", "Tarana", "Ujjain", "Madhya Pradesh", "Demo Procurement Center, Tarana, Ujjain, Madhya Pradesh", ["Wheat", "Gram", "Moong"]),
    ("Dewas Central Procurement Center", "Dewas", "Dewas", "Madhya Pradesh", "Demo Procurement Center, Dewas, Madhya Pradesh", ["Wheat", "Soybean", "Moong", "Gram"]),
    ("Sonkatch Procurement Center", "Sonkatch", "Dewas", "Madhya Pradesh", "Demo Procurement Center, Sonkatch, Dewas, Madhya Pradesh", ["Wheat", "Soybean", "Moong"]),
    ("Bagli Procurement Center", "Bagli", "Dewas", "Madhya Pradesh", "Demo Procurement Center, Bagli, Dewas, Madhya Pradesh", ["Wheat", "Gram", "Moong"]),
    ("Khandwa Central Procurement Center", "Khandwa", "Khandwa", "Madhya Pradesh", "Demo Procurement Center, Khandwa, Madhya Pradesh", ["Wheat", "Cotton", "Soybean", "Moong"]),
    ("Pandhana Procurement Center", "Pandhana", "Khandwa", "Madhya Pradesh", "Demo Procurement Center, Pandhana, Khandwa, Madhya Pradesh", ["Wheat", "Cotton", "Moong"]),
    ("Harsud Procurement Center", "Harsud", "Khandwa", "Madhya Pradesh", "Demo Procurement Center, Harsud, Khandwa, Madhya Pradesh", ["Wheat", "Cotton", "Soybean"]),
    ("Khargone Central Procurement Center", "Khargone", "Khargone", "Madhya Pradesh", "Demo Procurement Center, Khargone, Madhya Pradesh", ["Wheat", "Cotton", "Soybean", "Moong"]),
    ("Kasrawad Procurement Center", "Kasrawad", "Khargone", "Madhya Pradesh", "Demo Procurement Center, Kasrawad, Khargone, Madhya Pradesh", ["Wheat", "Cotton", "Moong"]),
    ("Barwaha Procurement Center", "Barwaha", "Khargone", "Madhya Pradesh", "Demo Procurement Center, Barwaha, Khargone, Madhya Pradesh", ["Wheat", "Cotton", "Soybean"]),
]
SLOT_WINDOWS = [(time(hour), time(hour + 1), Decimal("40.000")) for hour in (8, 9, 10, 11, 13, 14, 15)]


def get_or_create_user(db, phone, name, role, password):
    user = db.scalar(select(User).where(User.phone == phone))
    if user is None:
        user = User(phone=phone, full_name=name, role=role, password_hash=hash_password(password))
        db.add(user)
        db.flush()
    if not user.farmer_id and role == UserRole.FARMER:
        user.farmer_id = f"MP-FRM-{100000 + user.id}"
    return user


def create_demo_token(db, farmer, officer, mandi, slot, code, status, crop, quantity, quality=None, weight=None, payment=None):
    existing = db.scalar(select(Token).where(Token.token_code == code))
    if existing:
        return existing
    booking = Booking(farmer_id=farmer.id, slot_id=slot.id, crop_type=crop, expected_tonnage=quantity)
    db.add(booking)
    db.flush()
    token = Token(
        booking_id=booking.id,
        farmer_id=farmer.id,
        mandi_id=mandi.id,
        slot_id=slot.id,
        farmer_phone=farmer.phone,
        crop_type=crop,
        expected_tonnage=quantity,
        status=status,
        token_code=code,
        qr_hash=f"demo-{code.lower()}-{booking.id:032d}"[:64],
    )
    db.add(token)
    db.flush()
    history = [TokenStatus.BOOKED]
    if status in {TokenStatus.ARRIVED, TokenStatus.WAITING, TokenStatus.QUALITY_CHECK, TokenStatus.WEIGHMENT, TokenStatus.ACCEPTED, TokenStatus.PAYMENT_PENDING, TokenStatus.PAYMENT_INITIATED, TokenStatus.PAYMENT_PROCESSING, TokenStatus.PAYMENT_COMPLETED}:
        history += [TokenStatus.ARRIVED, TokenStatus.WAITING]
    if status in {TokenStatus.QUALITY_CHECK, TokenStatus.WEIGHMENT, TokenStatus.ACCEPTED, TokenStatus.PAYMENT_PENDING, TokenStatus.PAYMENT_INITIATED, TokenStatus.PAYMENT_PROCESSING, TokenStatus.PAYMENT_COMPLETED}:
        history += [TokenStatus.QUALITY_CHECK]
    if status in {TokenStatus.WEIGHMENT, TokenStatus.ACCEPTED, TokenStatus.PAYMENT_PENDING, TokenStatus.PAYMENT_INITIATED, TokenStatus.PAYMENT_PROCESSING, TokenStatus.PAYMENT_COMPLETED}:
        history += [TokenStatus.WEIGHMENT]
    if status in {TokenStatus.ACCEPTED, TokenStatus.PAYMENT_PENDING, TokenStatus.PAYMENT_INITIATED, TokenStatus.PAYMENT_PROCESSING, TokenStatus.PAYMENT_COMPLETED}:
        history += [TokenStatus.ACCEPTED, TokenStatus.PAYMENT_PENDING]
    if status == TokenStatus.REJECTED:
        history += [TokenStatus.QUALITY_CHECK, TokenStatus.REJECTED]
    for index, new_status in enumerate(history):
        db.add(ProcurementStatusHistory(token_id=token.id, previous_status=history[index - 1] if index else None, new_status=new_status, changed_by_id=officer.id, remarks="Synthetic demo record"))
    if quality:
        db.add(QualityInspection(token_id=token.id, inspector_id=officer.id, grade=quality[0], moisture_percentage=quality[1], decision=quality[2], remarks=quality[3]))
    if weight:
        db.add(Weighment(token_id=token.id, operator_id=officer.id, gross_weight=weight[0], tare_weight=weight[1], net_weight=weight[0] - weight[1], reference_number=f"DEMO-{code}", remarks="Synthetic demo record"))
    if payment:
        db.add(Payment(token_id=token.id, farmer_id=farmer.id, amount=payment[0], status=payment[1], reference_number=f"PAY-{code[4:]}", failure_reason=None))
    db.add(Notification(recipient_id=farmer.id, token_id=token.id, notification_type="DEMO_RECORD", title="Kisan Setu demo journey", message=f"Demo token {code} is ready for presentation."))
    return token


def create_demo_notice(db, officer, title_en, description_en, title_hi, description_hi, title_mr, description_mr, notice_type, scope, district=None, center_id=None):
    legacy_title = title_en.replace("–", "-")
    candidates = list(db.scalars(select(Notice).where(Notice.title_en.in_([title_en, legacy_title])).order_by(Notice.id)))
    if not candidates and title_en.startswith("Kharif Procurement"):
        candidates = list(db.scalars(select(Notice).where(Notice.title_en.like("Kharif Procurement%")).order_by(Notice.id)))
    notice = candidates[0] if candidates else None
    for duplicate in candidates[1:]:
        duplicate.status = "ARCHIVED"
    if notice is None:
        notice = Notice(
            title=title_en,
            description=description_en,
            title_en=title_en,
            title_hi=title_hi,
            title_mr=title_mr,
            description_en=description_en,
            description_hi=description_hi,
            description_mr=description_mr,
            notice_type=notice_type,
            scope=scope,
            district=district,
            center_id=center_id,
            status="PUBLISHED",
            published_at=datetime.combine(settings.demo_start_date, time.min, tzinfo=timezone.utc),
            created_by=officer.id,
        )
        db.add(notice)
    else:
        notice.title = title_en
        notice.description = description_en
        notice.title_en = title_en
        notice.title_hi = title_hi
        notice.title_mr = title_mr
        notice.description_en = description_en
        notice.description_hi = description_hi
        notice.description_mr = description_mr
        notice.notice_type = notice_type
        notice.scope = scope
        notice.district = district
        notice.center_id = center_id
        notice.status = "PUBLISHED"
    return notice


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal.begin() as db:
        farmer = get_or_create_user(db, DEMO_FARMER_PHONE, "Demo Farmer", UserRole.FARMER, DEMO_FARMER_PASSWORD)
        officer = get_or_create_user(db, DEMO_OFFICER_PHONE, "Demo Mandi Officer", UserRole.OFFICER, DEMO_OFFICER_PASSWORD)
        today = settings.demo_start_date
        end_date = settings.demo_end_date
        for index, (name, city, district, state, address, crops) in enumerate(CENTER_DATA):
            mandi = db.scalar(select(Mandi).where(Mandi.name == name))
            if mandi is None:
                mandi = Mandi(
                    name=name,
                    district=district,
                    state=state,
                    location=f"{city}, {district}, {state}",
                    address=address,
                    daily_capacity_quintals=Decimal("400.00"),
                    hourly_capacity=45 + (index % 5) * 10,
                    is_active=True,
                    procurement_window_start=time(8),
                    procurement_window_end=time(16),
                    available_crops=crops,
                )
                db.add(mandi)
                db.flush()
            current_day = today
            while current_day <= end_date:
                for start_time, end_time, capacity in SLOT_WINDOWS:
                    if db.scalar(select(Slot).where(Slot.mandi_id == mandi.id, Slot.date == current_day, Slot.start_time == start_time)) is None:
                        db.add(Slot(mandi_id=mandi.id, date=current_day, start_time=start_time, end_time=end_time, max_tonnage=capacity, booked_tonnage=Decimal("0.000")))
                current_day += timedelta(days=1)
            for key, label, description in (
                ("identity", "Identity proof", "Required document for this demo center"),
                ("land", "Land or cultivation document", "Required document for this demo center"),
                ("bank", "Bank/payment details", "Used for demo payment tracking"),
            ):
                if db.scalar(select(RequiredDocument).where(RequiredDocument.mandi_id == mandi.id, RequiredDocument.document_key == key)) is None:
                    db.add(RequiredDocument(mandi_id=mandi.id, document_key=key, label=label, description=description, is_required=True))
        db.flush()
        rau = db.scalar(select(Mandi).where(Mandi.name == "Rau Procurement Center"))
        create_demo_notice(db, officer, "Kharif Procurement 2026–27", "DEMO NOTICE: Procurement slots are currently available at selected procurement centers. Farmers are advised to book their arrival slot in advance.", "खरीफ खरीद 2026–27", "चयनित खरीद केंद्रों पर खरीद स्लॉट उपलब्ध हैं। किसानों को सलाह दी जाती है कि वे पहले से अपना आगमन स्लॉट बुक करें।", "खरीप खरेदी 2026–27", "निवडक खरेदी केंद्रांवर खरेदी स्लॉट उपलब्ध आहेत. शेतकऱ्यांनी आपली आगमन वेळ आधीच बुक करावी.", "NEW", "GLOBAL")
        create_demo_notice(db, officer, "MSP Information Updated", "DEMO NOTICE: Current MSP information is displayed while selecting your crop during booking.", "MSP जानकारी अपडेट", "बुकिंग के दौरान चयनित फसल का वर्तमान न्यूनतम समर्थन मूल्य (MSP) प्रदर्शित किया जाता है।", "MSP माहिती अद्ययावत", "बुकिंगदरम्यान निवडलेल्या पिकाचा सध्याचा किमान आधारभूत दर (MSP) प्रदर्शित केला जातो.", "INFO", "GLOBAL")
        create_demo_notice(db, officer, "Track Your Payment", "DEMO NOTICE: After accepted procurement, farmers can track payment progress directly through Kisan Setu.", "अपने भुगतान की स्थिति देखें", "स्वीकृत खरीद के बाद किसान Kisan Setu पर भुगतान की प्रगति देख सकते हैं।", "तुमच्या पेमेंटची स्थिती पहा", "खरेदी स्वीकृत झाल्यानंतर शेतकरी Kisan Setu वर पेमेंटची प्रगती पाहू शकतात.", "PAYMENT", "GLOBAL")
        create_demo_notice(db, officer, "Indore District Procurement Update", "DEMO NOTICE: Farmers booking procurement in Indore should select their preferred procurement center and allotted slot before arriving at the mandi.", "इंदौर जिला खरीद अपडेट", "इंदौर में खरीद बुक करने वाले किसानों को मंडी पहुंचने से पहले अपना पसंदीदा खरीद केंद्र और निर्धारित स्लॉट चुनना चाहिए।", "इंदूर जिल्हा खरेदी अपडेट", "इंदूरमध्ये खरेदी बुक करणाऱ्या शेतकऱ्यांनी मंडीत येण्यापूर्वी पसंतीचे खरेदी केंद्र आणि दिलेला स्लॉट निवडावा.", "DISTRICT", "DISTRICT", "Indore")
        if rau:
            create_demo_notice(db, officer, "Rau Procurement Center Notice", "DEMO NOTICE: Please arrive at the Rau Procurement Center during your allotted appointment slot to avoid unnecessary waiting.", "राऊ खरीद केंद्र सूचना", "अनावश्यक प्रतीक्षा से बचने के लिए किसान अपने निर्धारित समय पर राऊ खरीद केंद्र पहुंचें।", "राऊ खरेदी केंद्र सूचना", "अनावश्यक प्रतीक्षा टाळण्यासाठी शेतकऱ्यांनी दिलेल्या वेळेत राऊ खरेदी केंद्रावर पोहोचावे.", "CENTER", "CENTER", "Indore", rau.id)
        primary_center = db.scalar(select(Mandi).where(Mandi.name == "Ganj Basoda Procurement Center"))
        demo_slots = list(db.scalars(select(Slot).where(Slot.mandi_id == primary_center.id, Slot.date == settings.demo_start_date).order_by(Slot.start_time).limit(6)))
        for slot in demo_slots:
            slot.booked_tonnage = Decimal("25.000")
        create_demo_token(db, farmer, officer, primary_center, demo_slots[0], "KSN-3071", TokenStatus.WAITING, "Maize", Decimal("40.000"))
        create_demo_token(db, farmer, officer, primary_center, demo_slots[1], "KSN-3072", TokenStatus.QUALITY_CHECK, "Maize", Decimal("35.000"), ("A", Decimal("11.80"), "ACCEPTED", "Good quality produce"))
        create_demo_token(db, farmer, officer, primary_center, demo_slots[2], "KSN-3073", TokenStatus.WEIGHMENT, "Moong", Decimal("32.000"), ("A", Decimal("10.20"), "ACCEPTED", "Moong quality within the demo range"))
        create_demo_token(db, farmer, officer, primary_center, demo_slots[3], "KSN-3074", TokenStatus.PAYMENT_PROCESSING, "Wheat", Decimal("30.000"), ("A", Decimal("11.20"), "ACCEPTED", "Accepted for procurement"), (Decimal("52.400"), Decimal("2.400")), (Decimal("77400.00"), PaymentStatus.PROCESSING))
        create_demo_token(db, farmer, officer, primary_center, demo_slots[4], "KSN-3075", TokenStatus.PAYMENT_COMPLETED, "Wheat", Decimal("28.000"), ("A", Decimal("10.90"), "ACCEPTED", "Completed demo journey"), (Decimal("40.000"), Decimal("2.000")), (Decimal("72420.00"), PaymentStatus.COMPLETED))
        create_demo_token(db, farmer, officer, primary_center, demo_slots[5], "KSN-3076", TokenStatus.REJECTED, "Mustard", Decimal("20.000"), ("C", Decimal("18.20"), "REJECTED", "Moisture exceeds demo procurement limit"))
    print(f"Seeded {len(CENTER_DATA)} Kisan Setu centers and demo slots from {settings.demo_start_date.isoformat()} to {settings.demo_end_date.isoformat()}.")
    print(f"Demo farmer: {DEMO_FARMER_PHONE} / {DEMO_FARMER_PASSWORD}")
    print(f"Demo officer: {DEMO_OFFICER_PHONE} / {DEMO_OFFICER_PASSWORD}")


if __name__ == "__main__":
    seed()
