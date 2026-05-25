from collections import defaultdict
from fastapi import WebSocket
import json

subscribers: dict[str, set[WebSocket]] = defaultdict(set)

async def publish_event(org_id: int, sid: str, event_type: str, payload: dict):
    from models import LeadEvent
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        event = LeadEvent(organization_id=org_id, sid=sid, event_type=event_type, payload_json=payload)
        db.add(event)
        await db.commit()
        seq = event.id
    
    data = json.dumps({"type": event_type, "sid": sid, "payload": payload, "_seq": seq})
    dead = set()
    for ws in list(subscribers.get(sid, [])):
        try: await ws.send_text(data)
        except: dead.add(ws)
    for ws in list(subscribers.get("*", [])):
        try: await ws.send_text(data)
        except: dead.add(ws)
    for ws in dead:
        for s in subscribers.values():
            s.discard(ws)
