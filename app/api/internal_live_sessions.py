from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.db import SessionLocal
from app.services.live_session_service import service as live_session_service
from app.services.livekit_service import service as livekit_service

router = APIRouter(prefix="/api/internal/live-sessions", tags=["internal-live-sessions"])


class InternalLiveSessionRequest(BaseModel):
    organization_id: int = Field(..., ge=1)
    sid: str = Field(..., min_length=1, max_length=64)
    manager_user_id: int | None = None
    manager_display_name: str = Field(..., min_length=1, max_length=160)


class InternalLiveSessionEndRequest(BaseModel):
    organization_id: int = Field(..., ge=1)
    session_id: int = Field(..., ge=1)
    manager_display_name: str = Field(..., min_length=1, max_length=160)


@router.post("/current")
def current(payload: InternalLiveSessionRequest, request: Request):
    with SessionLocal() as db:
        session = live_session_service.get_current(db, organization_id=payload.organization_id, sid=payload.sid)
        if not session:
            return None
        ws_url = _ws_url(request)
        token = livekit_service.manager_token(
            room_name=session.room_name or live_session_service._room_name(organization_id=payload.organization_id, sid=payload.sid),
            identity=f"manager-{payload.manager_user_id or 0}-sid-{payload.sid}",
            display_name=payload.manager_display_name,
        )
        return _serialize_live_session(session, ws_url=ws_url, token=token)


@router.post("/preview")
def preview(payload: InternalLiveSessionRequest, request: Request):
    with SessionLocal() as db:
        session = live_session_service.upsert_preview(
            db,
            organization_id=payload.organization_id,
            sid=payload.sid,
            manager_user_id=payload.manager_user_id,
            manager_display_name=payload.manager_display_name,
        )
        ws_url = _ws_url(request)
        token = livekit_service.manager_token(
            room_name=session.room_name or live_session_service._room_name(organization_id=payload.organization_id, sid=payload.sid),
            identity=f"manager-{payload.manager_user_id or 0}-sid-{payload.sid}",
            display_name=payload.manager_display_name,
        )
        return _serialize_live_session(session, ws_url=ws_url, token=token)


@router.post("/go-live")
def go_live(payload: InternalLiveSessionRequest, request: Request):
    with SessionLocal() as db:
        session = live_session_service.go_live(
            db,
            organization_id=payload.organization_id,
            sid=payload.sid,
            manager_user_id=payload.manager_user_id,
            manager_display_name=payload.manager_display_name,
        )
        ws_url = _ws_url(request)
        token = livekit_service.manager_token(
            room_name=session.room_name or live_session_service._room_name(organization_id=payload.organization_id, sid=payload.sid),
            identity=f"manager-{payload.manager_user_id or 0}-sid-{payload.sid}",
            display_name=payload.manager_display_name,
        )
        return _serialize_live_session(session, ws_url=ws_url, token=token)


@router.post("/end")
def end(payload: InternalLiveSessionEndRequest, request: Request):
    with SessionLocal() as db:
        session = live_session_service.end_session(db, organization_id=payload.organization_id, session_id=payload.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Live session not found")
        return _serialize_live_session(session, ws_url=_ws_url(request), token=None)


@router.get("/public/{organization_id}")
def public_state(organization_id: int, sid: str, request: Request):
    with SessionLocal() as db:
        state = live_session_service.public_state(db, organization_id=organization_id, sid=sid)
        if state.get("status") == "live" and state.get("room_name"):
            state["ws_url"] = _ws_url(request)
            state["token"] = livekit_service.visitor_token(
                room_name=state["room_name"],
                identity=f"visitor-sid-{sid}",
                display_name="Visitor",
            )
        return state


def _ws_url(request: Request) -> str:
    return livekit_service.resolved_ws_url(request.headers.get("host"), request.headers.get("x-forwarded-proto", request.url.scheme))


def _serialize_live_session(session, *, ws_url: str, token: str | None = None) -> dict:
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
        "ws_url": ws_url,
        "token": token,
        "started_at": session.started_at,
        "live_at": session.live_at,
        "ended_at": session.ended_at,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }
