from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Notification, Token, User


def notify(
    db: Session,
    user: User | None,
    token: Token | None,
    notification_type: str,
    title: str,
    message: str,
) -> Notification | None:
    if user is None:
        return None
    item = Notification(
        recipient_id=user.id,
        token_id=token.id if token else None,
        notification_type=notification_type,
        event_type=notification_type,
        channel="IN_APP",
        delivery_status="CREATED",
        title=title,
        message=message,
    )
    db.add(item)
    return item


def notify_sms(db: Session, user: User | None, token: Token | None, event_type: str, title: str, message: str) -> Notification | None:
    if user is None or token is None:
        return None
    existing = db.scalar(select(Notification).where(
        Notification.token_id == token.id,
        Notification.event_type == event_type,
        Notification.channel == "SMS",
    ))
    if existing:
        return existing
    item = Notification(
        recipient_id=user.id,
        token_id=token.id,
        phone_number=user.phone,
        notification_type=event_type,
        event_type=event_type,
        channel="SMS",
        delivery_status="FAILED",
        title=title,
        message=message,
    )
    try:
        from .sms_service import get_sms_service
        item.delivery_status = get_sms_service().send_sms(user.phone, message)
        item.sent_at = datetime.now(timezone.utc)
    except Exception:
        item.delivery_status = "FAILED"
    db.add(item)
    return item