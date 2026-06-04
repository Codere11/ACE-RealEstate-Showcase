import json, os
from pathlib import Path

# Load .env from repo root before anything else
_env_path = Path(__file__).resolve().parent.parent / '.env'
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from events import subscribers

@asynccontextmanager
async def lifespan(app: FastAPI):
    from models import Organization, User, Qualifier, UserRole
    from auth import hash_password
    from database import AsyncSessionLocal
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        org = (await db.execute(select(Organization).where(Organization.slug == "demo"))).scalar_one_or_none()
        if not org:
            org = Organization(name="Demo Agency", slug="demo", active=True)
            db.add(org); await db.commit()
        admin = (await db.execute(select(User).where(User.username == "admin"))).scalar_one_or_none()
        if not admin:
            admin = User(username="admin", email="admin@ace.local", password_hash=hash_password("test123"),
                        visible_password="test123", role=UserRole.PLATFORM_ADMIN, active=True)
            db.add(admin); await db.commit()
        qual = (await db.execute(select(Qualifier).where(Qualifier.organization_id == org.id, Qualifier.status == "live"))).scalar_one_or_none()
        if not qual:
            qual = Qualifier(organization_id=org.id, name="AI Receptor", slug="ai-receptor", status="live",
                system_prompt="Ti si AI Receptor za kozmetični salon. Toplo pozdravi obiskovalce, odgovarjaj na vprašanja o storitvah, pomagaj pri izbiri tretmajev in rezerviraj termine.",
                assistant_style="prijazen, topel, profesionalen")
            db.add(qual); await db.commit()
    yield

app = FastAPI(title="ACE Reception Services", lifespan=lifespan)

@app.websocket("/ws/{slug}")
async def ws_endpoint(ws: WebSocket, slug: str):
    from models import Organization
    from database import AsyncSessionLocal
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        org = (await db.execute(select(Organization).where(Organization.slug == slug, Organization.active == True))).scalar_one_or_none()
    if not org:
        await ws.close(code=4004); return
    await ws.accept()
    subscribed_sid = "*"
    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)
            if data.get("type") == "subscribe":
                subscribed_sid = data.get("sid", "*")
                subscribers[subscribed_sid].add(ws)
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        for s in subscribers.values(): s.discard(ws)

from routes_chat import router as chat_router
from routes_admin import router as admin_router
from analize import router as analize_router
app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(analize_router)

# Public payment pages
from app.api.public_payments import router as public_payments_router
app.include_router(public_payments_router)

# SPA fallback: serve index.html for all non-API routes
from fastapi.responses import FileResponse, HTMLResponse
static_dir = os.path.join(os.path.dirname(__file__), "static")

@app.get("/{path:path}")
async def spa_fallback(path: str):
    # API routes handled above — only reaches here if no API route matched
    file_path = os.path.join(static_dir, path)
    if os.path.isfile(file_path):
        return FileResponse(file_path, headers={"Cache-Control": "no-cache"})
    index = os.path.join(static_dir, "index.html")
    if os.path.isfile(index):
        with open(index) as f:
            html = f.read()
        html = html.replace('</head>', '<meta name="build" content="' + str(hash(html)) + '"></head>')
        return HTMLResponse(html, headers={"Cache-Control": "no-cache, no-store, must-revalidate, max-age=0"})
    return {"detail": "Not Found"}
