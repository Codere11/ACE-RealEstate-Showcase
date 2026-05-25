from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models import Organization, User, UserRole
from auth import get_current_user, hash_password
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/admin")

@router.get("/organizations")
async def list_orgs(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role != "PLATFORM_ADMIN":
        raise HTTPException(403, "Admin only")
    orgs = (await db.execute(select(Organization).order_by(Organization.name))).scalars().all()
    return [{"id": o.id, "name": o.name, "slug": o.slug, "active": o.active} for o in orgs]

class CreateOrgRequest(BaseModel):
    name: str
    slug: str
    active: Optional[bool] = True

@router.post("/organizations")
async def create_org(req: CreateOrgRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role != "PLATFORM_ADMIN":
        raise HTTPException(403, "Admin only")
    existing = (await db.execute(select(Organization).where(Organization.slug == req.slug))).scalar_one_or_none()
    if existing:
        raise HTTPException(409, "Slug already exists")
    org = Organization(name=req.name, slug=req.slug, active=req.active)
    db.add(org); await db.commit()
    return {"id": org.id, "name": org.name, "slug": org.slug, "active": org.active}

@router.get("/users")
async def list_users(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role != "PLATFORM_ADMIN":
        raise HTTPException(403, "Admin only")
    users = (await db.execute(select(User).order_by(User.username))).scalars().all()
    return [{"id": u.id, "username": u.username, "email": u.email, "role": u.role,
             "active": u.active, "organization_id": u.organization_id} for u in users]

class CreateUserRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str = "ORG_USER"
    organization_id: Optional[int] = None

@router.post("/users")
async def create_user(req: CreateUserRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role != "PLATFORM_ADMIN":
        raise HTTPException(403, "Admin only")
    u = User(username=req.username, email=req.email,
             password_hash=hash_password(req.password), visible_password=req.password,
             role=UserRole(req.role), active=True,
             organization_id=req.organization_id)
    db.add(u); await db.commit()
    return {"id": u.id, "username": u.username, "email": u.email, "role": u.role}
