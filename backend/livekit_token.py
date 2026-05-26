import os, time, json
from pathlib import Path
from datetime import timedelta
from livekit import api as lkapi

# Load .env from repo root
_env_path = Path(__file__).resolve().parent.parent / '.env'
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

LIVEKIT_URL = os.getenv("ACE_LIVEKIT_WS_URL", "ws://localhost:7880")
LIVEKIT_API_KEY = os.getenv("ACE_LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.getenv("ACE_LIVEKIT_API_SECRET", "secret")

def room_name(org_slug: str, sid: str) -> str:
    return f"ace-{org_slug}-{sid}"

def manager_token(org_slug: str, sid: str, user_id: int, display_name: str) -> str:
    token = lkapi.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
        .with_identity(f"mgr-{user_id}-{sid}") \
        .with_name(display_name) \
        .with_grants(lkapi.VideoGrants(room_join=True, room=room_name(org_slug, sid),
                                        can_publish=True, can_subscribe=True)) \
        .with_ttl(timedelta(hours=1)) \
        .to_jwt()
    return token

def visitor_token(org_slug: str, sid: str) -> str:
    token = lkapi.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
        .with_identity(f"visitor-{sid}") \
        .with_name("Visitor") \
        .with_grants(lkapi.VideoGrants(room_join=True, room=room_name(org_slug, sid),
                                        can_publish=False, can_subscribe=True)) \
        .with_ttl(timedelta(hours=1)) \
        .to_jwt()
    return token

def ws_url() -> str:
    return LIVEKIT_URL
