from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from ..models import Mandi, Notice


def validate_notice_target(db: Session, scope: str, district: str | None, center_id: int | None) -> None:
    if scope == "GLOBAL" and (district or center_id):
        raise HTTPException(status_code=422, detail="Global notices cannot target a district or center")
    if scope == "DISTRICT" and (not district or center_id):
        raise HTTPException(status_code=422, detail="District notices require only a district")
    if scope == "CENTER":
        center = db.get(Mandi, center_id) if center_id else None
        if center is None:
            raise HTTPException(status_code=404, detail="Procurement center not found")
        if district and center.district != district:
            raise HTTPException(status_code=422, detail="Center does not belong to the selected district")
    if scope == "CENTER" and not center_id:
        raise HTTPException(status_code=422, detail="Center notices require a procurement center")


def validate_notice_dates(published_at: datetime | None, expires_at: datetime | None) -> None:
    if published_at and expires_at and expires_at < published_at:
        raise HTTPException(status_code=422, detail="Expiry cannot be before publication")


def active_notices(db: Session, district: str | None = None, center_id: int | None = None) -> list[Notice]:
    now = datetime.now(timezone.utc)
    query = select(Notice).options(joinedload(Notice.center)).where(
        Notice.status == "PUBLISHED",
        or_(Notice.published_at.is_(None), Notice.published_at <= now),
        or_(Notice.expires_at.is_(None), Notice.expires_at >= now),
    )
    visibility = [Notice.scope == "GLOBAL"]
    if district:
        visibility.append((Notice.scope == "DISTRICT") & (Notice.district == district))
    if center_id:
        visibility.append((Notice.scope == "CENTER") & (Notice.center_id == center_id))
    return list(db.scalars(query.where(or_(*visibility)).order_by(Notice.published_at.desc(), Notice.id.desc())))