from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.orm import Organization
from app.models.schemas import PublicLiveSessionResponse
from app.services.live_session_service import service as live_session_service
from app.services.livekit_service import service as livekit_service

router = APIRouter(tags=["public-live-sessions"])


@router.get("/api/public/organizations/{org_slug}/live-session", response_model=PublicLiveSessionResponse)
def get_public_live_session(
    org_slug: str,
    sid: str = Query(..., min_length=1, max_length=64),
    db: Session = Depends(get_db),
):
    organization = db.query(Organization).filter(Organization.slug == org_slug).first()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    state = live_session_service.public_state(db, organization_id=organization.id, sid=sid)
    if state.get("status") == "live" and state.get("room_name"):
        state["ws_url"] = livekit_service.ws_url
        state["token"] = livekit_service.visitor_token(
            room_name=state["room_name"],
            identity=f"visitor-sid-{sid}",
            display_name="Visitor",
        )
    return state
