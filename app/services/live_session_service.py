from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.orm import LiveSession


class LiveSessionService:
    def get_current(self, db: Session, *, organization_id: int, sid: str) -> LiveSession | None:
        return (
            db.query(LiveSession)
            .filter(LiveSession.organization_id == organization_id, LiveSession.sid == sid)
            .order_by(LiveSession.created_at.desc(), LiveSession.id.desc())
            .first()
        )

    def upsert_preview(
        self,
        db: Session,
        *,
        organization_id: int,
        sid: str,
        manager_user_id: int | None,
        manager_display_name: str,
    ) -> LiveSession:
        current = self.get_current(db, organization_id=organization_id, sid=sid)
        if current and current.status in {"preview", "live"}:
            current.status = "preview"
            current.manager_user_id = manager_user_id
            current.manager_display_name = manager_display_name
            current.ended_at = None
            current.stage_message = f"{manager_display_name} is getting ready to help live."
            db.add(current)
            db.commit()
            db.refresh(current)
            return current

        session = LiveSession(
            organization_id=organization_id,
            sid=sid,
            manager_user_id=manager_user_id,
            manager_display_name=manager_display_name,
            provider="livekit",
            status="preview",
            room_name=self._room_name(organization_id=organization_id, sid=sid),
            stage_message=f"{manager_display_name} is getting ready to help live.",
            started_at=datetime.utcnow(),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def go_live(
        self,
        db: Session,
        *,
        organization_id: int,
        sid: str,
        manager_user_id: int | None,
        manager_display_name: str,
    ) -> LiveSession:
        session = self.upsert_preview(
            db,
            organization_id=organization_id,
            sid=sid,
            manager_user_id=manager_user_id,
            manager_display_name=manager_display_name,
        )
        session.status = "live"
        session.manager_user_id = manager_user_id
        session.manager_display_name = manager_display_name
        session.live_at = datetime.utcnow()
        session.ended_at = None
        session.stage_message = f"{manager_display_name} is joining to help."
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def end_session(self, db: Session, *, organization_id: int, session_id: int) -> LiveSession | None:
        session = (
            db.query(LiveSession)
            .filter(LiveSession.organization_id == organization_id, LiveSession.id == session_id)
            .first()
        )
        if not session:
            return None
        session.status = "ended"
        session.ended_at = datetime.utcnow()
        session.stage_message = "Live help has ended."
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def public_state(self, db: Session, *, organization_id: int, sid: str) -> dict:
        session = self.get_current(db, organization_id=organization_id, sid=sid)
        if not session:
            return {
                "sid": sid,
                "status": "idle",
                "manager_display_name": "",
                "room_name": None,
                "stage_message": "",
                "live_at": None,
                "ended_at": None,
            }
        return {
            "sid": sid,
            "status": session.status,
            "manager_display_name": session.manager_display_name,
            "room_name": session.room_name,
            "stage_message": session.stage_message,
            "live_at": session.live_at,
            "ended_at": session.ended_at,
        }

    def _room_name(self, *, organization_id: int, sid: str) -> str:
        safe_sid = "".join(ch for ch in sid if ch.isalnum() or ch in {"-", "_"})[:48] or "sid"
        return f"org-{organization_id}-live-{safe_sid}"


service = LiveSessionService()
