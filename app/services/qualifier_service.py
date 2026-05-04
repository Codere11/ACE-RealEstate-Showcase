from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.orm import LeadProfile, Organization, Qualifier, QualifierRun
from app.qualification.graph import run_qualification_graph
from app.qualification.state import TurnDecision, TurnInterpretation
from app.services import chat_store
from app.services.llm_service import LLMService

logger = logging.getLogger("ace.qualifier_service")


@dataclass
class QualificationResult:
    organization_id: int
    sid: str
    qualifier_id: Optional[int]
    qualifier_version: int
    profile: Dict[str, Any]
    field_confidence: Dict[str, float]
    qualification_score: int
    qualification_band: str
    confidence_overall: float
    reasoning: str
    recommended_next_action: str
    missing_fields: list[str]
    takeover_eligible: bool
    video_offer_eligible: bool
    model_name: Optional[str]
    lead_profile_id: int
    assistant_reply: str


class QualifierService:
    def __init__(self, llm_service: Optional[LLMService] = None) -> None:
        self.llm = llm_service or LLMService()

    def get_active_qualifier(self, db: Session, organization_id: int) -> Optional[Qualifier]:
        return db.query(Qualifier).filter(
            Qualifier.organization_id == organization_id,
            Qualifier.status == "live",
        ).first()

    def resolve_org_from_runtime(
        self,
        db: Session,
        *,
        tenant_slug: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Optional[Organization]:
        slug = (tenant_slug or "").strip()
        if not slug and isinstance(meta, dict):
            slug = str(
                meta.get("organization_slug")
                or meta.get("org_slug")
                or meta.get("tenant_slug")
                or ""
            ).strip()
        if not slug:
            return None
        return db.query(Organization).filter(
            Organization.slug == slug,
            Organization.active == True,
        ).first()

    def get_lead_profile(self, db: Session, organization_id: int, sid: str) -> Optional[LeadProfile]:
        return db.query(LeadProfile).filter(
            LeadProfile.organization_id == organization_id,
            LeadProfile.sid == sid,
        ).first()

    def qualify_message(
        self,
        db: Session,
        *,
        sid: str,
        message: str,
        tenant_slug: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
        trigger: str = "user_message",
    ) -> Optional[QualificationResult]:
        text = (message or "").strip()
        if not db or not sid or not text or text.startswith("/"):
            return None

        org = self.resolve_org_from_runtime(db, tenant_slug=tenant_slug, meta=meta)
        if not org:
            return None

        qualifier = self.get_active_qualifier(db, org.id)
        if not qualifier:
            return None

        existing = self.get_lead_profile(db, org.id, sid)
        profile_before = dict(existing.profile or {}) if existing and existing.profile else {}
        score_before = existing.qualification_score if existing else None
        band_before = existing.qualification_band if existing else None
        started = time.perf_counter()

        recent_messages = [
            {"role": str(m.get("role") or "user"), "text": str(m.get("text") or "")}
            for m in chat_store.list_messages(sid)[-8:]
            if str(m.get("text") or "").strip()
        ]

        graph_state = run_qualification_graph(
            llm=self.llm,
            qualifier=qualifier,
            latest_message=text,
            recent_messages=recent_messages,
            profile_before=profile_before,
        )

        interpretation: TurnInterpretation = graph_state.get("interpretation") or TurnInterpretation()
        decision: TurnDecision = graph_state.get("decision") or TurnDecision()
        profile_after = dict(interpretation.profile_after or profile_before)
        profile_after["visitor_type"] = interpretation.visitor_type or profile_after.get("visitor_type") or "unclear"
        profile_after["funnel_stage"] = decision.funnel_stage or profile_after.get("funnel_stage") or "business_context"
        profile_after["qualification_complete"] = bool(decision.qualification_complete)
        if interpretation.supporting_quotes:
            profile_after["supporting_quotes"] = interpretation.supporting_quotes
        self._set_disqualify_reason(profile_after, profile_after["visitor_type"], decision.recommended_next_action)

        assistant_reply = (decision.reply or self._fallback_reply(text, profile_after)).strip()
        reasoning = self._combine_reasoning(interpretation.reasoning_hint, decision.reasoning_hint)
        model_name = decision.model_name or interpretation.model_name or self.llm.model_name
        field_confidence = {k: float(v) for k, v in interpretation.field_confidence.items()}
        confidence_overall = float(decision.confidence_overall or interpretation.confidence_overall or 0.0)
        qualification_score = int(decision.qualification_score or 0)
        qualification_band = decision.qualification_band or "cold"

        if existing:
            lead_profile = existing
        else:
            lead_profile = LeadProfile(organization_id=org.id, sid=sid)
            db.add(lead_profile)

        lead_profile.qualifier_id = qualifier.id
        lead_profile.qualifier_version = qualifier.version
        lead_profile.profile = profile_after
        lead_profile.field_confidence = field_confidence
        lead_profile.qualification_score = qualification_score
        lead_profile.qualification_band = qualification_band
        lead_profile.confidence_overall = confidence_overall
        lead_profile.reasoning = reasoning
        lead_profile.recommended_next_action = decision.recommended_next_action or "ask_clarifying_question"
        lead_profile.missing_fields = list(decision.missing_fields or [])
        lead_profile.takeover_eligible = bool(decision.takeover_eligible)
        lead_profile.video_offer_eligible = bool(decision.video_offer_eligible)
        lead_profile.last_qualified_at = datetime.utcnow()

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        run = QualifierRun(
            organization_id=org.id,
            sid=sid,
            qualifier_id=qualifier.id,
            qualifier_version=qualifier.version,
            trigger=trigger,
            input_excerpt=text[:1000],
            output_profile_patch=profile_after,
            score_before=score_before,
            score_after=qualification_score,
            band_before=band_before,
            band_after=qualification_band,
            confidence_overall=confidence_overall,
            reasoning=reasoning,
            takeover_eligible=bool(decision.takeover_eligible),
            video_offer_eligible=bool(decision.video_offer_eligible),
            model_name=model_name,
            latency_ms=elapsed_ms,
        )
        db.add(run)
        db.commit()
        db.refresh(lead_profile)

        logger.info(
            "qualified sid=%s org=%s qualifier=%s score=%s band=%s next=%s",
            sid,
            org.slug,
            qualifier.slug,
            qualification_score,
            qualification_band,
            decision.recommended_next_action,
        )

        return QualificationResult(
            organization_id=org.id,
            sid=sid,
            qualifier_id=qualifier.id,
            qualifier_version=qualifier.version,
            profile=profile_after,
            field_confidence=field_confidence,
            qualification_score=qualification_score,
            qualification_band=qualification_band,
            confidence_overall=confidence_overall,
            reasoning=reasoning,
            recommended_next_action=decision.recommended_next_action or "ask_clarifying_question",
            missing_fields=list(decision.missing_fields or []),
            takeover_eligible=bool(decision.takeover_eligible),
            video_offer_eligible=bool(decision.video_offer_eligible),
            model_name=model_name,
            lead_profile_id=lead_profile.id,
            assistant_reply=assistant_reply,
        )

    def _fallback_reply(self, latest_message: str, profile: Dict[str, Any]) -> str:
        visitor_type = str(profile.get("visitor_type") or "unclear")
        if visitor_type == "existing_customer_support":
            return "Če ste obstoječa stranka, na kratko opišite težavo in pustite kontakt, pa vas usmerimo naprej."
        if visitor_type in {"partner_or_vendor", "job_seeker", "irrelevant_or_joke", "abusive_or_spam"}:
            return "Pomagam lahko pri ACE e-Counter kvalifikaciji in naslednjih korakih. Če želite preveriti, ali je primeren za vaš posel, mi na kratko opišite situacijo."
        if self._looks_slovenian(latest_message):
            return "Na kratko mi opišite vaš posel in kako danes dobivate stranke, pa preverim, kako vam lahko ACE e-Counter pomaga."
        return "Briefly describe your business and how customers reach you today, and I’ll check how ACE e-Counter could help."

    def _combine_reasoning(self, interpretation_reason: str, decision_reason: str) -> str:
        parts = [p.strip() for p in [interpretation_reason, decision_reason] if p and p.strip()]
        return "; ".join(dict.fromkeys(parts)) or "Qualification updated"

    def _set_disqualify_reason(self, profile: Dict[str, Any], visitor_type: str, next_action: str) -> None:
        if next_action == "route_support":
            profile.pop("disqualify_reason", None)
            return
        if visitor_type == "irrelevant_or_joke":
            profile["disqualify_reason"] = "out_of_scope"
        elif visitor_type == "abusive_or_spam":
            profile["disqualify_reason"] = "abusive_or_spam"
        elif visitor_type == "partner_or_vendor":
            profile["disqualify_reason"] = "partner_or_vendor"
        elif visitor_type == "job_seeker":
            profile["disqualify_reason"] = "job_seeker"
        else:
            profile.pop("disqualify_reason", None)

    def _looks_slovenian(self, text: str) -> bool:
        lowered = (text or "").lower()
        return any(token in lowered for token in [" kako ", " ali ", " sem ", " prodajam", " podjet", " strank", " povpraš"])


service = QualifierService()
