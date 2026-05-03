from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.permissions import AuthContext, require_org_admin, require_org_user
from app.core.db import get_db
from app.models.schemas import LiveSessionCreate, LiveSessionResponse
from app.services import event_bus
from app.services.live_session_service import service as live_session_service
from app.services.livekit_service import service as livekit_service

router = APIRouter(prefix="/api/organizations/{org_id}/live-sessions", tags=["live-sessions"])


def _ensure_org_access(org_id: int, auth: AuthContext) -> None:
    if auth.organization_id != org_id:
        raise HTTPException(status_code=403, detail="You can only access live sessions in your own organization")


def _event_payload(session) -> dict:
    return {
        "id": session.id,
        "sid": session.sid,
        "status": session.status,
        "managerDisplayName": session.manager_display_name,
        "roomName": session.room_name,
        "stageMessage": session.stage_message,
        "liveAt": session.live_at.isoformat() if session.live_at else None,
        "endedAt": session.ended_at.isoformat() if session.ended_at else None,
    }


def _serialize_live_session(session, *, token: str | None = None) -> dict:
    return {
        "id": session.id,
        "organization_id": session.organization_id,
        "sid": session.sid,
        "manager_user_id": session.manager_user_id,
        "manager_display_name": session.manager_display_name,
        "provider": session.provider,
        "status": session.status,
        "room_name": session.room_name,
        "stage_message": session.stage_message,
        "ws_url": livekit_service.ws_url,
        "token": token,
        "started_at": session.started_at,
        "live_at": session.live_at,
        "ended_at": session.ended_at,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


@router.get("/current", response_model=LiveSessionResponse | None)
def get_current_live_session(
    org_id: int,
    sid: str = Query(..., min_length=1, max_length=64),
    auth: AuthContext = Depends(require_org_user),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    session = live_session_service.get_current(db, organization_id=org_id, sid=sid)
    if not session:
        return None
    token = livekit_service.manager_token(
        room_name=session.room_name or live_session_service._room_name(organization_id=org_id, sid=sid),
        identity=f"manager-{auth.user_id}-sid-{sid}",
        display_name=auth.username,
    )
    return _serialize_live_session(session, token=token)


@router.post("/preview", response_model=LiveSessionResponse)
def start_live_preview(
    org_id: int,
    payload: LiveSessionCreate,
    auth: AuthContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    session = live_session_service.upsert_preview(
        db,
        organization_id=org_id,
        sid=payload.sid,
        manager_user_id=auth.user_id,
        manager_display_name=auth.username,
    )
    token = livekit_service.manager_token(
        room_name=session.room_name or live_session_service._room_name(organization_id=org_id, sid=payload.sid),
        identity=f"manager-{auth.user_id}-sid-{payload.sid}",
        display_name=auth.username,
    )
    return _serialize_live_session(session, token=token)


@router.post("/go-live", response_model=LiveSessionResponse)
async def go_live(
    org_id: int,
    payload: LiveSessionCreate,
    auth: AuthContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    session = live_session_service.go_live(
        db,
        organization_id=org_id,
        sid=payload.sid,
        manager_user_id=auth.user_id,
        manager_display_name=auth.username,
    )
    await event_bus.publish(session.sid, "live_session.live", _event_payload(session))
    await event_bus.publish(session.sid, "message.created", {
        "role": "assistant",
        "text": f"{session.manager_display_name} is joining to help live.",
        "timestamp": int(session.updated_at.timestamp()),
    })
    token = livekit_service.manager_token(
        room_name=session.room_name or live_session_service._room_name(organization_id=org_id, sid=payload.sid),
        identity=f"manager-{auth.user_id}-sid-{payload.sid}",
        display_name=auth.username,
    )
    return _serialize_live_session(session, token=token)


@router.post("/{session_id}/end", response_model=LiveSessionResponse)
async def end_live_session(
    org_id: int,
    session_id: int,
    auth: AuthContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    session = live_session_service.end_session(db, organization_id=org_id, session_id=session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Live session not found")
    await event_bus.publish(session.sid, "live_session.ended", _event_payload(session))
    await event_bus.publish(session.sid, "message.created", {
        "role": "assistant",
        "text": "Live help has ended.",
        "timestamp": int(session.updated_at.timestamp()),
    })
    return _serialize_live_session(session)
