import json
import logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .security import create_token, verify_token, verify_password
from app.core.db import get_db
from app.models.orm import User

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("ace.auth.routes")
SEED_USERS_PATH = Path(__file__).with_name("users_seed.json")


class LoginIn(BaseModel):
    username: str
    password: str


def _load_seed_user(username: str) -> dict | None:
    if not SEED_USERS_PATH.exists():
        return None

    try:
        data = json.loads(SEED_USERS_PATH.read_text())
    except Exception as exc:
        logger.warning("Failed to load seed users from %s: %s", SEED_USERS_PATH, exc)
        return None

    for user in data.get("users", []):
        if user.get("username") == username:
            return user
    return None


@router.post("/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    # Prefer DB-backed users
    user = db.query(User).filter(User.username == payload.username).first()

    if user and user.is_active and verify_password(payload.password, user.hashed_password):
        user.last_login = datetime.utcnow()
        db.commit()

        org_slug = user.organization.slug if user.organization else None
        token = create_token(
            {
                "sub": user.username,
                "user_id": user.id,
                "role": user.role,
                "organization_id": user.organization_id,
                "organization_slug": org_slug,
                # Backward compatibility
                "tenant_id": user.organization_id,
                "tenant_slug": org_slug,
            }
        )

        logger.info("Login success for user '%s' (role=%s)", user.username, user.role)

        return {
            "token": token,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "organization_id": user.organization_id,
                "organization_slug": org_slug,
                "avatar_url": user.avatar_url,
                # Backward compatibility
                "tenant_id": user.organization_id,
                "tenant_slug": org_slug,
            },
        }

    # Legacy fallback for local/demo credentials used by existing tests/docs
    seed_user = _load_seed_user(payload.username)
    if seed_user and seed_user.get("password") == payload.password:
        role = seed_user.get("role", "org_user")
        tenant_slug = seed_user.get("tenant_slug")
        token = create_token(
            {
                "sub": payload.username,
                "role": role,
                "organization_id": None,
                "organization_slug": tenant_slug,
                # Backward compatibility
                "tenant_id": None,
                "tenant_slug": tenant_slug,
                "is_seed_user": True,
            }
        )
        logger.info("Login success for seed user '%s' (role=%s)", payload.username, role)
        return {
            "token": token,
            "user": {
                "username": payload.username,
                "email": None,
                "role": role,
                "organization_id": None,
                "organization_slug": tenant_slug,
                "avatar_url": None,
                # Backward compatibility
                "tenant_id": None,
                "tenant_slug": tenant_slug,
            },
        }

    logger.info("Login failed for user '%s' (not found or inactive)", payload.username)
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/me")
def me(authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    data = verify_token(token)
    if not data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Get full user info from database
    user_id = data.get("user_id")
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.is_active:
            org_slug = user.organization.slug if user.organization else None
            return {
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "organization_id": user.organization_id,
                    "organization_slug": org_slug,
                    "avatar_url": user.avatar_url,
                }
            }
    
    # Fallback to token data only
    return {
        "user": {
            "username": data["sub"],
            "role": data["role"],
            "organization_id": data.get("organization_id") or data.get("tenant_id"),
            "organization_slug": data.get("organization_slug") or data.get("tenant_slug"),
        }
    }
