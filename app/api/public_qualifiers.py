from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.orm import Organization, Qualifier

router = APIRouter(prefix="/api/public/organizations", tags=["public-qualifiers"])


@router.get("/{org_slug}/qualifier-active")
def get_public_active_qualifier(org_slug: str, db: Session = Depends(get_db)):
    org = db.query(Organization).filter(
        Organization.slug == org_slug,
        Organization.active == True,
    ).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    qualifier = db.query(Qualifier).filter(
        Qualifier.organization_id == org.id,
        Qualifier.status == "live",
    ).first()

    return {
        "enabled": bool(qualifier),
        "organization_slug": org.slug,
        "qualifier": {
            "id": qualifier.id,
            "slug": qualifier.slug,
            "name": qualifier.name,
            "assistant_style": qualifier.assistant_style,
        } if qualifier else None,
    }
