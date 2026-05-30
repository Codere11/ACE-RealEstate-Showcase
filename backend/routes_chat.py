import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app.qualification.tools import set_db_context
import json as _json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Organization, Lead, ConversationMessage, Qualifier, LeadEvent, Booking, ConvRole, LeadStatus, new_sid
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
    
    # Capture contact info from message if present
    import re
    if not lead.phone:
        phone_match = re.search(r'(\+?\d[\d\s]{7,}\d)', req.message)
        if phone_match:
            lead.phone = phone_match.group(1).strip()
    if not lead.email:
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.+-]+', req.message)
        if email_match:
            lead.email = email_match.group(0).strip()
    if lead.phone or lead.email:
        await db.commit()  # persist contact immediately
    set_db_context(org.id, lead.sid, lead.phone, lead.email)
    
    if qualifier:
        try:
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
            
            # Persist conversation stage so context carries across turns
            profile = dict(lead.qualifier_profile or {})
            profile["conversation_stage"] = state.get("conversation_stage", "")
            profile["hours_mentioned"] = state.get("hours_mentioned", False)
            profile["services_presented"] = state.get("services_presented", False)
            profile["service_interest"] = state.get("service_interest", "")
            profile["booking_date"] = state.get("booking_date", "")
            profile["booking_time"] = state.get("booking_time", "")
            profile["last_booking_id"] = state.get("last_booking_id") or profile.get("last_booking_id")
            lead.qualifier_profile = profile
            await save_message(db, lead, ConvRole.ASSISTANT, reply)
            await db.commit()

            # If a booking was just confirmed, publish event for real-time dashboard updates
            if state.get("booking_confirmed"):
                result = await db.execute(
                    select(Booking).where(Booking.organization_id == org.id)
                        .order_by(desc(Booking.id)).limit(1)
                )
                last_booking = result.scalar_one_or_none()
                if last_booking:
                    await publish_event(org.id, lead.sid, "booking.created", {
                        "id": last_booking.id,
                        "bookingDate": last_booking.booking_date,
                        "bookingTime": last_booking.booking_time,
                        "serviceName": last_booking.service_name,
                        "customerName": last_booking.customer_name,
                        "durationMin": last_booking.duration_min,
                        "priceEur": last_booking.price_eur,
                    })

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

# ══════ BOOKINGS ══════
class CreateBookingRequest(BaseModel):
    sid: Optional[str] = None
    customer_name: str = ""
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    service_id: str
    booking_date: str
    booking_time: str
    notes: Optional[str] = None

@router.get("/api/organizations/{org_id}/bookings")
async def list_bookings(org_id: int, date_from: Optional[str] = None, date_to: Optional[str] = None, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await check_org_access(user, org_id)
    q = select(Booking).where(Booking.organization_id == org_id, Booking.status != 'cancelled')
    if date_from:
        q = q.where(Booking.booking_date >= date_from)
    if date_to:
        q = q.where(Booking.booking_date <= date_to)
    bookings = (await db.execute(q.order_by(Booking.booking_date, Booking.booking_time))).scalars().all()
    return [{"id": b.id, "serviceId": b.service_id, "serviceName": b.service_name,
             "durationMin": b.duration_min, "priceEur": b.price_eur,
             "bookingDate": b.booking_date, "bookingTime": b.booking_time,
             "customerName": b.customer_name, "customerPhone": b.customer_phone,
             "customerEmail": b.customer_email, "status": b.status, "notes": b.notes,
             "addons": b.addons or [], "leadId": b.lead_id} for b in bookings]

@router.post("/api/organizations/{org_id}/bookings")
async def create_booking(org_id: int, req: CreateBookingRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await check_org_access(user, org_id)
    svc = next((s for s in [
        {"id": "nega-obraza", "name": "Nega obraza", "dur": 45, "price": 45},
        {"id": "maska-obraza", "name": "Maska obraza", "dur": 30, "price": 30},
        {"id": "ciscenje-obraza", "name": "Čiščenje obraza", "dur": 60, "price": 60}
    ] if s["id"] == req.service_id), None)
    if not svc: raise HTTPException(400, f"Unknown service: {req.service_id}")
    # Conflict check: overlap-aware, not just exact time
    all_bookings = (await db.execute(select(Booking.booking_time, Booking.duration_min).where(
        Booking.organization_id == org_id, Booking.booking_date == req.booking_date,
        Booking.status != 'cancelled'
    ))).all()
    b_h, b_m = map(int, req.booking_time.split(":"))
    b_start = b_h * 60 + b_m
    b_end = b_start + svc["dur"]
    for (bk_time, bk_dur) in all_bookings:
        bh, bm = map(int, bk_time.split(":"))
        bk_start = bh * 60 + bm
        bk_end = bk_start + bk_dur
        if b_start < bk_end and b_end > bk_start:
            raise HTTPException(409, f"Termin {req.booking_date} {req.booking_time} se prekriva z obstoječo rezervacijo")
    lead = None
    if req.sid:
        lead = (await db.execute(select(Lead).where(Lead.organization_id == org_id, Lead.sid == req.sid))).scalar_one_or_none()
    b = Booking(organization_id=org_id, lead_id=lead.id if lead else None,
                service_id=svc["id"], service_name=svc["name"], duration_min=svc["dur"], price_eur=svc["price"],
                booking_date=req.booking_date, booking_time=req.booking_time,
                customer_name=req.customer_name or (lead.display_name if lead else ""),
                customer_phone=req.customer_phone or (lead.phone if lead else None),
                customer_email=req.customer_email or (lead.email if lead else None),
                notes=req.notes)
    db.add(b); await db.commit()
    await publish_event(org_id, req.sid or "*", "booking.created", {
        "id": b.id, "bookingDate": b.booking_date, "bookingTime": b.booking_time,
        "serviceName": b.service_name, "customerName": b.customer_name
    })
    return {"ok": True, "id": b.id}

@router.delete("/api/organizations/{org_id}/bookings/{booking_id}")
async def delete_booking(org_id: int, booking_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await check_org_access(user, org_id)
    b = (await db.execute(select(Booking).where(Booking.id == booking_id, Booking.organization_id == org_id))).scalar_one_or_none()
    if not b: raise HTTPException(404, "Booking not found")
    b.status = 'cancelled'
    await db.commit()
    await publish_event(org_id, b.lead.sid if b.lead else "*", "booking.cancelled", {"id": b.id})
    return {"ok": True}

# ══════ LOGIN ══════
from fastapi import Form
from auth import verify_password, create_token

@router.post("/login")
async def login(username: str = Form(...), password: str = Form(...), db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return {"token": create_token(user.id, user.username, user.role), "role": user.role}
