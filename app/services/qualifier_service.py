from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, TypedDict

from sqlalchemy.orm import Session

from app.models.orm import Organization, Qualifier, LeadProfile, QualifierRun
from app.services.llm_service import LLMService, LLMReplyResult
from app.services import chat_store

try:
    from langgraph.graph import StateGraph, END
except Exception:  # pragma: no cover
    StateGraph = None  # type: ignore
    END = "__end__"  # type: ignore

logger = logging.getLogger("ace.qualifier_service")

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-()]{7,}\d)")

EXPLICIT_HUMAN_PATTERNS = [
    "human", "person", "specialist", "agent", "representative", "call me",
    "talk to someone", "speak to someone", "video call", "can i talk",
    "človek", "agent", "pokličite", "lahko govorim", "video",
]

HIGH_URGENCY_PATTERNS = [
    "urgent", "asap", "immediately", "today", "now", "emergency",
    "nujno", "takoj", "čim prej", "danes",
]

SHORT_TIMELINE_PATTERNS = [
    "this week", "today", "tomorrow", "right away", "next few days",
    "ta teden", "danes", "jutri", "čim prej",
]

PRICE_OBJECTION_PATTERNS = [
    "expensive", "too much", "price", "cost", "budget", "drago", "cena",
]


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


class QualifierGraphState(TypedDict, total=False):
    qualifier: Qualifier
    message: str
    messages: list[str]
    profile_before: Dict[str, Any]
    heuristic_patch: Dict[str, Any]
    heuristic_conf: Dict[str, float]
    heuristic_reasoning: str
    llm_patch: Dict[str, Any]
    llm_conf: Dict[str, float]
    llm_reasoning: str
    profile_after: Dict[str, Any]
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

        recent_msgs = [m.get("text", "") for m in chat_store.list_messages(sid)[-6:] if m.get("text")]
        convo_for_extraction = (recent_msgs + [text])[-8:]

        graph_state = self._run_qualification_graph(
            qualifier=qualifier,
            message=text,
            messages=convo_for_extraction,
            profile_before=profile_before,
        )

        profile_after = graph_state.get("profile_after", profile_before)
        merged_conf = graph_state.get("field_confidence", {})
        score = int(graph_state.get("qualification_score", 0))
        band = str(graph_state.get("qualification_band", "cold"))
        overall_conf = float(graph_state.get("confidence_overall", 0.3))
        reasoning = str(graph_state.get("reasoning", "Qualification updated"))
        next_action = str(graph_state.get("recommended_next_action", "continue_conversation"))
        missing_fields = list(graph_state.get("missing_fields", []))
        takeover_eligible = bool(graph_state.get("takeover_eligible", False))
        video_offer_eligible = bool(graph_state.get("video_offer_eligible", False))
        assistant_reply = str(graph_state.get("assistant_reply") or "Razumem. Nadaljujeva v prostem pogovoru — povej mi malo več, da te lahko usmerim naprej.")
        model_name = graph_state.get("model_name")

        merged_patch = dict(graph_state.get("llm_patch", {}) or {})
        for k, v in dict(graph_state.get("heuristic_patch", {}) or {}).items():
            merged_patch.setdefault(k, v)

        if existing:
            lead_profile = existing
        else:
            lead_profile = LeadProfile(
                organization_id=org.id,
                sid=sid,
            )
            db.add(lead_profile)

        lead_profile.qualifier_id = qualifier.id
        lead_profile.qualifier_version = qualifier.version
        lead_profile.profile = profile_after
        lead_profile.field_confidence = merged_conf
        lead_profile.qualification_score = score
        lead_profile.qualification_band = band
        lead_profile.confidence_overall = overall_conf
        lead_profile.reasoning = reasoning
        lead_profile.recommended_next_action = next_action
        lead_profile.missing_fields = missing_fields
        lead_profile.takeover_eligible = takeover_eligible
        lead_profile.video_offer_eligible = video_offer_eligible
        lead_profile.last_qualified_at = datetime.utcnow()

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        run = QualifierRun(
            organization_id=org.id,
            sid=sid,
            qualifier_id=qualifier.id,
            qualifier_version=qualifier.version,
            trigger=trigger,
            input_excerpt=text[:1000],
            output_profile_patch=merged_patch,
            score_before=score_before,
            score_after=score,
            band_before=band_before,
            band_after=band,
            confidence_overall=overall_conf,
            reasoning=reasoning,
            takeover_eligible=takeover_eligible,
            video_offer_eligible=video_offer_eligible,
            model_name=model_name,
            latency_ms=elapsed_ms,
        )
        db.add(run)
        db.commit()
        db.refresh(lead_profile)

        logger.info(
            "qualified sid=%s org=%s qualifier=%s score=%s band=%s takeover=%s video=%s",
            sid,
            org.slug,
            qualifier.slug,
            score,
            band,
            takeover_eligible,
            video_offer_eligible,
        )

        return QualificationResult(
            organization_id=org.id,
            sid=sid,
            qualifier_id=qualifier.id,
            qualifier_version=qualifier.version,
            profile=profile_after,
            field_confidence={k: float(v) for k, v in merged_conf.items()},
            qualification_score=score,
            qualification_band=band,
            confidence_overall=overall_conf,
            reasoning=reasoning,
            recommended_next_action=next_action,
            missing_fields=missing_fields,
            takeover_eligible=takeover_eligible,
            video_offer_eligible=video_offer_eligible,
            model_name=model_name,
            lead_profile_id=lead_profile.id,
            assistant_reply=assistant_reply,
        )

    def _run_qualification_graph(
        self,
        *,
        qualifier: Qualifier,
        message: str,
        messages: list[str],
        profile_before: Dict[str, Any],
    ) -> QualifierGraphState:
        state: QualifierGraphState = {
            "qualifier": qualifier,
            "message": message,
            "messages": messages,
            "profile_before": profile_before,
        }

        if StateGraph is None:
            state = self._node_extract(state)
            state = self._node_score(state)
            state = self._node_reply(state)
            return state

        graph = StateGraph(QualifierGraphState)
        graph.add_node("extract", self._node_extract)
        graph.add_node("score", self._node_score)
        graph.add_node("reply", self._node_reply)
        graph.set_entry_point("extract")
        graph.add_edge("extract", "score")
        graph.add_edge("score", "reply")
        graph.add_edge("reply", END)
        app = graph.compile()
        return app.invoke(state)

    def _node_extract(self, state: QualifierGraphState) -> QualifierGraphState:
        qualifier = state["qualifier"]
        message = state["message"]
        profile_before = state.get("profile_before", {}) or {}
        messages = state.get("messages", []) or [message]

        heuristic_patch, heuristic_conf, heuristic_reasoning = self._heuristic_extract(message)
        llm_result = self.llm.extract_profile_patch(
            system_prompt=qualifier.system_prompt,
            goal_definition=qualifier.goal_definition,
            field_schema=qualifier.field_schema or {},
            existing_profile=profile_before,
            messages=messages,
        )

        field_confidence = dict(heuristic_conf)
        field_confidence.update(llm_result.field_confidence or {})

        profile_after = dict(profile_before)
        for key, value in {**heuristic_patch, **(llm_result.profile_patch or {})}.items():
            if value not in (None, "", [], {}):
                profile_after[key] = value

        state.update({
            "heuristic_patch": heuristic_patch,
            "heuristic_conf": heuristic_conf,
            "heuristic_reasoning": heuristic_reasoning,
            "llm_patch": llm_result.profile_patch or {},
            "llm_conf": llm_result.field_confidence or {},
            "llm_reasoning": llm_result.reasoning_hint,
            "profile_after": profile_after,
            "field_confidence": field_confidence,
            "model_name": llm_result.model_name,
        })
        return state

    def _node_score(self, state: QualifierGraphState) -> QualifierGraphState:
        qualifier = state["qualifier"]
        message = state["message"]
        profile_after = state.get("profile_after", {}) or {}
        field_confidence = state.get("field_confidence", {}) or {}
        heuristic_reasoning = str(state.get("heuristic_reasoning") or "")
        llm_reasoning = str(state.get("llm_reasoning") or "")

        score, band, overall_conf, reasoning, takeover_eligible, video_offer_eligible, next_action = self._score_profile(
            qualifier=qualifier,
            message=message,
            profile=profile_after,
            field_confidence=field_confidence,
            heuristic_reasoning=heuristic_reasoning,
            llm_reasoning=llm_reasoning,
        )
        missing_fields = [
            field for field in (qualifier.required_fields or [])
            if not profile_after.get(field)
        ]
        state.update({
            "qualification_score": score,
            "qualification_band": band,
            "confidence_overall": overall_conf,
            "reasoning": reasoning,
            "recommended_next_action": next_action,
            "missing_fields": missing_fields,
            "takeover_eligible": takeover_eligible,
            "video_offer_eligible": video_offer_eligible,
        })
        return state

    def _node_reply(self, state: QualifierGraphState) -> QualifierGraphState:
        qualifier = state["qualifier"]
        reply_result: LLMReplyResult = self.llm.generate_reply(
            system_prompt=qualifier.system_prompt,
            goal_definition=qualifier.goal_definition,
            assistant_style=qualifier.assistant_style,
            profile=state.get("profile_after", {}) or {},
            missing_fields=state.get("missing_fields", []) or [],
            messages=state.get("messages", []) or [state["message"]],
            takeover_eligible=bool(state.get("takeover_eligible", False)),
            video_offer_eligible=bool(state.get("video_offer_eligible", False)),
        )
        if reply_result.model_name and not state.get("model_name"):
            state["model_name"] = reply_result.model_name
        state["assistant_reply"] = reply_result.reply
        return state

    def _heuristic_extract(self, text: str) -> tuple[Dict[str, Any], Dict[str, float], str]:
        lowered = text.lower()
        patch: Dict[str, Any] = {}
        conf: Dict[str, float] = {}
        reasons: list[str] = []

        if len(text) >= 8:
            patch["intent"] = text[:240]
            conf["intent"] = 0.55
            reasons.append("captured latest intent message")

        email_match = EMAIL_RE.search(text)
        if email_match:
            patch["contact_email"] = email_match.group(0)
            conf["contact_email"] = 0.97
            reasons.append("email detected")

        phone_match = PHONE_RE.search(text)
        if phone_match:
            phone = phone_match.group(0).strip()
            if len([c for c in phone if c.isdigit()]) >= 8:
                patch["contact_phone"] = phone
                conf["contact_phone"] = 0.92
                reasons.append("phone detected")

        if any(p in lowered for p in EXPLICIT_HUMAN_PATTERNS):
            patch["human_request"] = True
            conf["human_request"] = 0.95
            reasons.append("explicit human request")

        if any(p in lowered for p in HIGH_URGENCY_PATTERNS):
            patch["urgency"] = "high"
            conf["urgency"] = 0.86
            reasons.append("high urgency language")

        if any(p in lowered for p in SHORT_TIMELINE_PATTERNS):
            patch["timeline"] = "short_term"
            conf["timeline"] = 0.76
            reasons.append("short timeline language")

        objections = []
        if any(p in lowered for p in PRICE_OBJECTION_PATTERNS):
            objections.append("price")
        if objections:
            patch["objections"] = objections
            conf["objections"] = 0.72
            reasons.append("objection language detected")

        return patch, conf, "; ".join(reasons)

    def _score_profile(
        self,
        *,
        qualifier: Qualifier,
        message: str,
        profile: Dict[str, Any],
        field_confidence: Dict[str, float],
        heuristic_reasoning: str,
        llm_reasoning: str,
    ) -> tuple[int, str, float, str, bool, bool, str]:
        score = 35
        reasons: list[str] = []
        lowered = message.lower()

        if len(message) >= 24:
            score += 10
            reasons.append("meaningful free-text input")

        if profile.get("urgency") == "high":
            score += 25
            reasons.append("high urgency")

        if profile.get("timeline") == "short_term":
            score += 10
            reasons.append("short timeline")

        if profile.get("contact_email"):
            score += 12
            reasons.append("email captured")

        if profile.get("contact_phone"):
            score += 12
            reasons.append("phone captured")

        if profile.get("human_request"):
            score += 20
            reasons.append("explicit human request")

        if isinstance(profile.get("objections"), list) and profile.get("objections"):
            score += 3
            reasons.append("objection surfaced")

        score = max(0, min(100, score))

        thresholds = qualifier.band_thresholds or {}
        hot_min = int(thresholds.get("hot_min", 80))
        warm_min = int(thresholds.get("warm_min", 50))
        if score >= hot_min:
            band = "hot"
        elif score >= warm_min:
            band = "warm"
        else:
            band = "cold"

        confidences = [float(v) for v in field_confidence.values() if v is not None]
        overall_conf = round(sum(confidences) / len(confidences), 3) if confidences else 0.3
        if profile.get("human_request"):
            overall_conf = max(overall_conf, 0.9)

        conf_thresholds = qualifier.confidence_thresholds or {}
        takeover_conf_min = float(conf_thresholds.get("overall_min_for_takeover", 0.7))

        human_requested = bool(profile.get("human_request")) or any(p in lowered for p in EXPLICIT_HUMAN_PATTERNS)
        takeover_rules = qualifier.takeover_rules or {}
        allow_explicit = takeover_rules.get("offer_on_explicit_human_request", True)
        allow_hot = takeover_rules.get("offer_on_hot_band", True)

        takeover_eligible = (
            (allow_explicit and human_requested)
            or (allow_hot and band == "hot" and overall_conf >= takeover_conf_min)
        )

        video_rules = qualifier.video_offer_rules or {}
        video_enabled = bool(video_rules.get("enabled", False))
        requires_takeover = bool(video_rules.get("requires_takeover_eligible", True))
        video_offer_eligible = video_enabled and (takeover_eligible if requires_takeover else band == "hot")

        next_action = "continue_conversation"
        if takeover_eligible:
            next_action = "offer_human_takeover"
        elif qualifier.required_fields:
            missing = [f for f in qualifier.required_fields if not profile.get(f)]
            if missing:
                next_action = "ask_clarifying_question"

        merged_reasons = reasons[:]
        if heuristic_reasoning:
            merged_reasons.append(heuristic_reasoning)
        if llm_reasoning:
            merged_reasons.append(llm_reasoning)
        reasoning = "; ".join(dict.fromkeys([r for r in merged_reasons if r])) or "Qualification updated"

        return score, band, overall_conf, reasoning, takeover_eligible, video_offer_eligible, next_action


service = QualifierService()
