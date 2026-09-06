from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Token, TokenStatus

ACTIVE_STATUSES = {
    TokenStatus.ARRIVED, TokenStatus.WAITING, TokenStatus.QUALITY_CHECK, TokenStatus.WEIGHMENT,
    TokenStatus.IN_YARD, TokenStatus.WEIGHING,
}
SERVING_STATUSES = {TokenStatus.QUALITY_CHECK, TokenStatus.WEIGHMENT, TokenStatus.WEIGHING}


def queue_snapshot(db: Session, token: Token) -> dict:
    tokens = list(db.scalars(select(Token).where(Token.mandi_id == token.mandi_id).order_by(Token.created_at, Token.id)))
    active = [item for item in tokens if item.status in ACTIVE_STATUSES]
    current = next((item for item in active if item.status in SERVING_STATUSES), None)
    if token not in active:
        return {
            "token_number": token.token_code,
            "queue_position": None,
            "people_ahead": 0,
            "current_serving": current.token_code if current else None,
            "estimated_wait_minutes": 0,
            "last_updated_at": token.last_updated_at or datetime.now(timezone.utc),
            "freshness": "FRESH",
        }
    index = active.index(token)
    people_ahead = index
    updated = max((item.last_updated_at for item in active if item.last_updated_at), default=datetime.now(timezone.utc))
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    age_seconds = max(0, (datetime.now(timezone.utc) - updated).total_seconds())
    freshness = "FRESH" if age_seconds <= 120 else "DELAYED" if age_seconds <= 600 else "STALE"
    return {
        "token_number": token.token_code,
        "queue_position": index + 1,
        "people_ahead": people_ahead,
        "current_serving": current.token_code if current else None,
        "estimated_wait_minutes": people_ahead * settings.eta_fallback_minutes,
        "last_updated_at": updated,
        "freshness": freshness,
    }