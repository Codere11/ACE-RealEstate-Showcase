from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.permissions import AuthContext, require_org_admin, require_org_user
from app.core.db import get_db
from app.models.orm import Qualifier, LeadProfile, QualifierRun
from app.models.schemas import (
    QualifierCreate,
    QualifierUpdate,
    QualifierResponse,
    LeadProfileResponse,
    QualifierRunResponse,
)

router = APIRouter(prefix="/api/organizations/{org_id}/qualifiers", tags=["qualifiers"])


def _ensure_org_access(org_id: int, auth: AuthContext) -> None:
    if auth.organization_id != org_id:
        raise HTTPException(
            status_code=403,
            detail="You can only access qualifiers in your own organization",
        )


def _ensure_single_live_qualifier(db: Session, org_id: int, exclude_id: Optional[int] = None) -> None:
    query = db.query(Qualifier).filter(
        Qualifier.organization_id == org_id,
        Qualifier.status == "live",
    )
    if exclude_id is not None:
        query = query.filter(Qualifier.id != exclude_id)
    existing = query.first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Organization already has a live qualifier ('{existing.slug}'). Archive it first.",
        )


def _get_qualifier_or_404(db: Session, org_id: int, qualifier_id: int) -> Qualifier:
    qualifier = db.query(Qualifier).filter(
        Qualifier.organization_id == org_id,
        Qualifier.id == qualifier_id,
    ).first()
    if not qualifier:
        raise HTTPException(status_code=404, detail="Qualifier not found")
    return qualifier


def _ensure_slug_unique(db: Session, org_id: int, slug: str, exclude_id: Optional[int] = None) -> None:
    query = db.query(Qualifier).filter(
        Qualifier.organization_id == org_id,
        Qualifier.slug == slug,
    )
    if exclude_id is not None:
        query = query.filter(Qualifier.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=400, detail=f"Qualifier with slug '{slug}' already exists")


def _validate_publishable(qualifier: Qualifier) -> None:
    if not (qualifier.system_prompt or "").strip():
        raise HTTPException(status_code=400, detail="Cannot publish qualifier without system_prompt")
    if not qualifier.field_schema:
        raise HTTPException(status_code=400, detail="Cannot publish qualifier without field_schema")


def _runtime_fields_present(payload: QualifierUpdate) -> bool:
    data = payload.model_dump(exclude_unset=True)
    mutable_live_exceptions = {"status"}
    return any(k not in mutable_live_exceptions for k in data.keys())


@router.get("", response_model=List[QualifierResponse])
def list_qualifiers(
    org_id: int,
    status: Optional[str] = Query(default=None),
    skip: int = 0,
    limit: int = 100,
    auth: AuthContext = Depends(require_org_user),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)

    query = db.query(Qualifier).filter(Qualifier.organization_id == org_id)
    if status:
        if status not in {"draft", "live", "archived"}:
            raise HTTPException(status_code=400, detail="Invalid status filter")
        query = query.filter(Qualifier.status == status)
    return query.order_by(Qualifier.updated_at.desc()).offset(skip).limit(limit).all()


@router.get("/active", response_model=QualifierResponse)
def get_active_qualifier(
    org_id: int,
    auth: AuthContext = Depends(require_org_user),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    qualifier = db.query(Qualifier).filter(
        Qualifier.organization_id == org_id,
        Qualifier.status == "live",
    ).first()
    if not qualifier:
        raise HTTPException(status_code=404, detail="No live qualifier found")
    return qualifier


@router.post("", response_model=QualifierResponse, status_code=201)
def create_qualifier(
    org_id: int,
    payload: QualifierCreate,
    auth: AuthContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    if payload.organization_id != org_id:
        raise HTTPException(status_code=400, detail="Organization ID in payload must match URL")

    _ensure_slug_unique(db, org_id, payload.slug)
    if payload.status == "live":
        _ensure_single_live_qualifier(db, org_id)

    qualifier = Qualifier(
        organization_id=org_id,
        name=payload.name,
        slug=payload.slug,
        status=payload.status,
        system_prompt=payload.system_prompt,
        assistant_style=payload.assistant_style,
        goal_definition=payload.goal_definition,
        field_schema=payload.field_schema,
        required_fields=payload.required_fields,
        scoring_rules=payload.scoring_rules,
        band_thresholds=payload.band_thresholds,
        confidence_thresholds=payload.confidence_thresholds,
        takeover_rules=payload.takeover_rules,
        video_offer_rules=payload.video_offer_rules,
        rag_enabled=payload.rag_enabled,
        knowledge_source_ids=payload.knowledge_source_ids,
        max_clarifying_questions=payload.max_clarifying_questions,
        contact_capture_policy=payload.contact_capture_policy,
        version=payload.version,
        version_notes=payload.version_notes,
        published_at=datetime.utcnow() if payload.status == "live" else None,
    )

    if qualifier.status == "live":
        _validate_publishable(qualifier)

    db.add(qualifier)
    db.commit()
    db.refresh(qualifier)
    return qualifier


@router.get("/lead-profiles", response_model=List[LeadProfileResponse])
def list_lead_profiles(
    org_id: int,
    limit: int = Query(default=200, ge=1, le=1000),
    auth: AuthContext = Depends(require_org_user),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    return db.query(LeadProfile).filter(
        LeadProfile.organization_id == org_id,
    ).order_by(LeadProfile.updated_at.desc()).limit(limit).all()


@router.get("/lead-profiles/{sid}", response_model=LeadProfileResponse)
def get_lead_profile(
    org_id: int,
    sid: str,
    auth: AuthContext = Depends(require_org_user),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    profile = db.query(LeadProfile).filter(
        LeadProfile.organization_id == org_id,
        LeadProfile.sid == sid,
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Lead profile not found")
    return profile


@router.get("/{qualifier_id}", response_model=QualifierResponse)
def get_qualifier(
    org_id: int,
    qualifier_id: int,
    auth: AuthContext = Depends(require_org_user),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    return _get_qualifier_or_404(db, org_id, qualifier_id)


@router.put("/{qualifier_id}", response_model=QualifierResponse)
def update_qualifier(
    org_id: int,
    qualifier_id: int,
    payload: QualifierUpdate,
    auth: AuthContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    qualifier = _get_qualifier_or_404(db, org_id, qualifier_id)

    if qualifier.status == "live" and _runtime_fields_present(payload):
        raise HTTPException(
            status_code=400,
            detail="Cannot edit a live qualifier. Archive it first.",
        )

    data = payload.model_dump(exclude_unset=True)
    if "slug" in data and data["slug"] != qualifier.slug:
        _ensure_slug_unique(db, org_id, data["slug"], exclude_id=qualifier_id)

    if data.get("status") == "live":
        _ensure_single_live_qualifier(db, org_id, exclude_id=qualifier_id)

    for key, value in data.items():
        setattr(qualifier, key, value)

    if qualifier.status == "live":
        _validate_publishable(qualifier)
        qualifier.published_at = qualifier.published_at or datetime.utcnow()

    db.commit()
    db.refresh(qualifier)
    return qualifier


@router.post("/{qualifier_id}/publish", response_model=QualifierResponse)
def publish_qualifier(
    org_id: int,
    qualifier_id: int,
    auth: AuthContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    qualifier = _get_qualifier_or_404(db, org_id, qualifier_id)
    _ensure_single_live_qualifier(db, org_id, exclude_id=qualifier_id)
    _validate_publishable(qualifier)

    qualifier.status = "live"
    qualifier.published_at = qualifier.published_at or datetime.utcnow()
    db.commit()
    db.refresh(qualifier)
    return qualifier


@router.post("/{qualifier_id}/archive", response_model=QualifierResponse)
def archive_qualifier(
    org_id: int,
    qualifier_id: int,
    auth: AuthContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    qualifier = _get_qualifier_or_404(db, org_id, qualifier_id)
    qualifier.status = "archived"
    db.commit()
    db.refresh(qualifier)
    return qualifier


@router.get("/{qualifier_id}/runs", response_model=List[QualifierRunResponse])
def list_qualifier_runs(
    org_id: int,
    qualifier_id: int,
    sid: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    auth: AuthContext = Depends(require_org_user),
    db: Session = Depends(get_db),
):
    _ensure_org_access(org_id, auth)
    _get_qualifier_or_404(db, org_id, qualifier_id)

    query = db.query(QualifierRun).filter(
        QualifierRun.organization_id == org_id,
        QualifierRun.qualifier_id == qualifier_id,
    )
    if sid:
        query = query.filter(QualifierRun.sid == sid)
    return query.order_by(QualifierRun.created_at.desc()).limit(limit).all()
