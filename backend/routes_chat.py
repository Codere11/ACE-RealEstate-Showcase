import json as _json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Organization, Lead, ConversationMessage, Qualifier, LeadEvent, ConvRole, LeadStatus, new_sid
from auth import get_current_user, get_platform_admin, User
from events import publish_event
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime, timezone

router = APIRouter()

# ══════ SCHEMAS ══════
class ChatRequest(BaseModel):
    sid: Optional[str] = None
    message: str
    tenant_slug: Optional[str] = "demo"
    meta: Optional[dict] = None

class StaffMessageRequest(BaseModel):
    orgId: int
    sid: str
    text: str

# ══════ HELPERS ══════
async def get_org_by_slug(db: AsyncSession, slug: str) -> Organization:
    org = (await db.execute(select(Organization).where(Organization.slug == slug, Organization.active == True))).scalar_one_or_none()
    if not org: raise HTTPException(404, "Organization not found")
    return org

async def get_lead(db: AsyncSession, org_id: int, sid: str) -> Lead:
    lead = (await db.execute(select(Lead).where(Lead.organization_id == org_id, Lead.sid == sid))).scalar_one_or_none()
    if not lead: raise HTTPException(404, "Lead not found")
    return lead

async def get_or_create_lead(db: AsyncSession, org_id: int, sid: Optional[str]) -> Lead:
    if sid:
        lead = (await db.execute(select(Lead).where(Lead.organization_id == org_id, Lead.sid == sid))).scalar_one_or_none()
        if lead: return lead
    lead = Lead(organization_id=org_id, sid=new_sid(), display_name="Visitor " + new_sid()[-6:])
    db.add(lead)
    return lead

async def save_message(db: AsyncSession, lead: Lead, role: ConvRole, text: str):
    msg = ConversationMessage(organization_id=lead.organization_id, lead_id=lead.id, role=role, text=text)
    db.add(msg)
    lead.last_message_preview = text[:500] if text else None
    lead.last_message_at = datetime.now(timezone.utc)
    await publish_event(lead.organization_id, lead.sid, "message.created",
        {"role": role.value, "text": text, "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000)})
    await publish_event(lead.organization_id, lead.sid, "lead.touched",
        {"lastMessage": text[:100] if text else None, "survey_progress": lead.survey_progress or 0,
         "takeover_active": lead.takeover_active, "status": lead.status.value if lead.status else "OPEN_CHAT"})

async def check_org_access(user: User, org_id: int):
    if user.role == "PLATFORM_ADMIN": return
    if user.organization_id != org_id: raise HTTPException(403, "Access denied")

# ══════ CHAT ══════
@router.post("/chat")
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    slug = req.tenant_slug or (req.meta.get("organization_slug", "demo") if req.meta else "demo")
    org = await get_org_by_slug(db, str(slug))
    lead = await get_or_create_lead(db, org.id, req.sid)
    
    await db.flush()  # ensure lead.id is available
    
    if not req.message.strip():
        return {"sid": lead.sid, "reply": "Dober dan! Dobrodošli. Kako vam lahko pomagamo?", 
                "chatMode": "open", "storyComplete": False, "surveyProgress": 100,
                "currentStep": None, "completionTitle": None, "completionSubtitle": None}
    
    await save_message(db, lead, ConvRole.USER, req.message)
    await db.commit()
    
    # During takeover, AI stays silent — staff handles the conversation
    if lead.takeover_active:
        return {"sid": lead.sid, "reply": None, "chatMode": "open", "storyComplete": False,
                "surveyProgress": 100, "currentStep": None, "completionTitle": None, "completionSubtitle": None}
    
    qualifier = (await db.execute(select(Qualifier).where(Qualifier.organization_id == org.id, Qualifier.status == "live"))).scalar_one_or_none()
    
    if qualifier:
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from app.qualification.graph import run_qualification_graph
            from app.services.llm_service import LLMService
            from types import SimpleNamespace
            llm = LLMService()
            q = SimpleNamespace(**{k: getattr(qualifier, k, None) for k in ["name","slug","status","system_prompt","assistant_style","goal_definition","field_schema","required_fields","scoring_rules","band_thresholds","confidence_thresholds","takeover_rules","video_offer_rules","rag_enabled","knowledge_source_ids","max_clarifying_questions","contact_capture_policy","version","version_notes"]})
            msgs_result = await db.execute(select(ConversationMessage).where(ConversationMessage.lead_id == lead.id).order_by(desc(ConversationMessage.created_at)).limit(8))
            recent = [{"role": m.role, "text": m.text} for m in reversed(msgs_result.scalars().all())]
            
            state = run_qualification_graph(llm=llm, qualifier=q, latest_message=req.message, recent_messages=recent, profile_before=lead.qualifier_profile or {})
            decision = state.get("decision")
            reply = (getattr(decision, 'reply', None) or "Hvala za vaše sporočilo.").strip()
            await save_message(db, lead, ConvRole.ASSISTANT, reply)
            await db.commit()
            
            return {"sid": lead.sid, "reply": reply, "chatMode": "open", "storyComplete": False,
                    "surveyProgress": 100, "currentStep": None, "completionTitle": None, "completionSubtitle": None}
        except Exception as e:
            import traceback; traceback.print_exc()
            fallback = "Oprostite, AI trenutno ni na voljo. Ekipa vas bo kontaktirala kmalu."
            await save_message(db, lead, ConvRole.ASSISTANT, fallback)
            await db.commit()
            return {"sid": lead.sid, "reply": fallback, "chatMode": "open", "storyComplete": False,
                    "surveyProgress": 100, "currentStep": None, "completionTitle": None, "completionSubtitle": None}
    else:
        # Survey fallback
        reply = "Katero storitev iščete? (Nega obraza, Masaža, Manikura, Pedikura...)"
        await save_message(db, lead, ConvRole.ASSISTANT, reply)
        await db.commit()
        return {"sid": lead.sid, "reply": reply, "chatMode": "guided", "storyComplete": False,
                "surveyProgress": 0, "currentStep": {"orderIndex": 1, "questionType": "SINGLE_CHOICE",
                "title": "Katero storitev iščete?", "description": "", "placeholder": "",
                "options": ["Nega obraza", "Masaža", "Manikura", "Pedikura", "Depilacija", "Nekaj drugega"]},
                "completionTitle": None, "completionSubtitle": None}

# ══════ STAFF TAKEOVER ══════
@router.post("/chat/staff")
async def staff_message(req: StaffMessageRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await check_org_access(user, req.orgId)
    lead = await get_lead(db, req.orgId, req.sid)
    
    if not lead.takeover_active:
        lead.takeover_active = True
        lead.status = LeadStatus.HUMAN_TAKEOVER
        await publish_event(lead.organization_id, lead.sid, "lead.takeover.started",
            {"sid": lead.sid, "manager": user.username, "takeover_active": True})
    
    await save_message(db, lead, ConvRole.STAFF, req.text)
    await db.commit()
    
    return {"ok": True, "sid": lead.sid, "takeover": {
        "sid": lead.sid, "active": lead.takeover_active,
        "assignedUser": user.username, "status": lead.status.value
    }}

# ══════ POLL EVENTS ══════
@router.get("/chat-events/poll")
async def poll_events(sid: str, since: int = 0, timeout: float = 1, limit: int = 50, tenantSlug: str = "demo", db: AsyncSession = Depends(get_db)):
    org = await get_org_by_slug(db, tenantSlug)
    from models import LeadEvent
    from sqlalchemy import and_
    if sid == "*":
        events = (await db.execute(select(LeadEvent).where(LeadEvent.organization_id == org.id, LeadEvent.id > since).order_by(LeadEvent.id).limit(limit))).scalars().all()
    else:
        events = (await db.execute(select(LeadEvent).where(LeadEvent.organization_id == org.id, LeadEvent.sid == sid, LeadEvent.id > since).order_by(LeadEvent.id).limit(limit))).scalars().all()
    result = [{"type": e.event_type, "sid": e.sid, "payload": (_json.loads(e.payload_json) if isinstance(e.payload_json, str) else e.payload_json), "_seq": e.id} for e in events]
    next_seq = max([e.id for e in events], default=since)
    return {"ok": True, "events": result, "next": next_seq}

# ══════ LEADS ══════
@router.get("/api/organizations/{org_id}/leads")
async def list_leads(org_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await check_org_access(user, org_id)
    leads = (await db.execute(select(Lead).where(Lead.organization_id == org_id).order_by(desc(Lead.staff_requested), desc(Lead.last_message_at)))).scalars().all()
    result = []
    for l in leads:
        score = l.qualification_score or l.survey_progress or 0
        interest = "High" if score >= 70 else "Medium" if score >= 40 else "Low"
        result.append({
            "id": l.sid, "sid": l.sid, "name": l.display_name or "Visitor",
            "industry": (l.qualifier_profile or {}).get("industry", "Unknown"),
            "score": score, "stage": l.status.value if l.status else "OPEN_CHAT",
            "compatibility": l.takeover_eligible or l.video_offer_eligible,
            "interest": interest, "phoneText": l.phone, "emailText": l.email,
            "phone": bool(l.phone), "email": bool(l.email), "adsExp": False,
            "lastMessage": l.last_message_preview,
            "lastSeenSec": int(l.last_message_at.timestamp()) if l.last_message_at else 0,
            "notes": l.qualification_reasoning,
            "surveyProgress": l.survey_progress or 0,
            "takeoverActive": l.takeover_active,
            "status": l.status.value if l.status else "OPEN_CHAT",
            "staffRequested": l.staff_requested
        })
    return result

@router.get("/api/organizations/{org_id}/leads/{sid}/messages")
async def get_messages(org_id: int, sid: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await check_org_access(user, org_id)
    lead = await get_lead(db, org_id, sid)
    msgs = (await db.execute(select(ConversationMessage).where(ConversationMessage.lead_id == lead.id).order_by(ConversationMessage.created_at))).scalars().all()
    return [{"role": m.role, "text": m.text, "timestamp": int(m.created_at.timestamp() * 1000)} for m in msgs]

@router.get("/api/public/organizations/{slug}/leads/{sid}/messages")
async def public_messages(slug: str, sid: str, db: AsyncSession = Depends(get_db)):
    org = await get_org_by_slug(db, slug)
    lead = await get_lead(db, org.id, sid)
    msgs = (await db.execute(select(ConversationMessage).where(ConversationMessage.lead_id == lead.id).order_by(ConversationMessage.created_at))).scalars().all()
    return [{"role": m.role, "text": m.text, "timestamp": int(m.created_at.timestamp() * 1000)} for m in msgs]

@router.post("/api/public/organizations/{slug}/leads/{sid}/request-staff")
async def request_staff(slug: str, sid: str, db: AsyncSession = Depends(get_db)):
    org = await get_org_by_slug(db, slug)
    lead = await get_lead(db, org.id, sid)
    lead.staff_requested = True
    await publish_event(org.id, sid, "lead.staff-requested", {"sid": sid, "staff_requested": True})
    await db.commit()
    return {"ok": True, "sid": sid}

@router.post("/api/organizations/{org_id}/leads/{sid}/takeover/end")
async def end_takeover(org_id: int, sid: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await check_org_access(user, org_id)
    lead = await get_lead(db, org_id, sid)
    lead.takeover_active = False
    lead.status = LeadStatus.OPEN_CHAT
    await publish_event(org_id, sid, "lead.takeover.ended", {"sid": sid, "takeover_active": False})
    await db.commit()
    return {"ok": True, "sid": sid}

@router.delete("/api/organizations/{org_id}/leads/{sid}")
async def delete_lead(org_id: int, sid: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await check_org_access(user, org_id)
    lead = await get_lead(db, org_id, sid)
    await publish_event(org_id, sid, "lead.deleted", {"sid": sid, "deleted": True})
    await db.delete(lead)
    await db.commit()
    return {"ok": True, "sid": sid}

# ══════ LIVE SESSIONS (CAMERA) ══════
class LiveSessionRequest(BaseModel):
    sid: str

@router.post("/api/organizations/{org_id}/live-sessions/go-live")
async def go_live(org_id: int, req: LiveSessionRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await check_org_access(user, org_id)
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one()
    from livekit_token import room_name as _rn, manager_token
    token = manager_token(org.slug, req.sid, user.id, user.username)
    await publish_event(org_id, req.sid, "live_session.started", {
        "sid": req.sid, "status": "live", "roomName": _rn(org.slug, req.sid),
        "managerDisplayName": user.username
    })
    return {"ok": True, "sid": req.sid, "roomName": _rn(org.slug, req.sid), "token": token, "wsUrl": ws_url()}

@router.post("/api/organizations/{org_id}/live-sessions/end")
async def end_live(org_id: int, req: LiveSessionRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await check_org_access(user, org_id)
    await publish_event(org_id, req.sid, "live_session.ended", {"sid": req.sid, "status": "ended"})
    return {"ok": True, "sid": req.sid}

@router.get("/api/public/organizations/{slug}/live-session")
async def public_live_state(slug: str, sid: str = Query(...), db: AsyncSession = Depends(get_db)):
    from livekit_token import visitor_token, room_name as _rn, ws_url as _ws
    # Check if there's an active live session by looking for recent live_session.started event without ended
    from sqlalchemy import desc
    events = (await db.execute(
        select(LeadEvent).where(
            LeadEvent.sid == sid,
            LeadEvent.event_type.in_(["live_session.started", "live_session.ended"])
        ).order_by(desc(LeadEvent.id)).limit(1)
    )).scalars().all()
    active = False
    manager_name = ""
    if events and events[0].event_type == "live_session.started":
        active = True
        p = events[0].payload_json
        if isinstance(p, str): p = _json.loads(p)
        manager_name = p.get("managerDisplayName", "")
    
    org = await get_org_by_slug(db, slug)
    token = visitor_token(slug, sid) if active else None
    return {
        "sid": sid, "status": "live" if active else "idle",
        "managerDisplayName": manager_name,
        "roomName": _rn(slug, sid) if active else None,
        "wsUrl": _ws() if active else None,
        "token": token
    }

from livekit_token import ws_url

# ══════ LOGIN ══════
from fastapi import Form
from auth import verify_password, create_token

@router.post("/login")
async def login(username: str = Form(...), password: str = Form(...), db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return {"token": create_token(user.id, user.username, user.role), "role": user.role}
