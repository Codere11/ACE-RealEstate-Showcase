from __future__ import annotations

import re
from typing import Any, Dict, List

ACE_PRODUCT_BRIEF = [
    "ACE e-Counter is a website visitor-intake and qualification system for inbound customer interest.",
    "ACE engages visitors on landing pages, asks focused qualification questions, captures useful lead details, and routes strong opportunities to a manager or next step.",
    "ACE is not a marketplace or seller of the visitor's product. It helps the business handle inquiries, qualify demand, and improve follow-up.",
]


def build_runtime_context(qualifier: Any) -> Dict[str, Any]:
    field_schema = qualifier_field_schema(qualifier)
    required_fields = [str(v).strip() for v in list(getattr(qualifier, "required_fields", []) or []) if str(v).strip()]
    takeover_rules = dict(getattr(qualifier, "takeover_rules", {}) or {})
    video_offer_rules = dict(getattr(qualifier, "video_offer_rules", {}) or {})
    scoring_rules = dict(getattr(qualifier, "scoring_rules", {}) or {})
    band_thresholds = dict(getattr(qualifier, "band_thresholds", {}) or {})
    confidence_thresholds = dict(getattr(qualifier, "confidence_thresholds", {}) or {})
    context = {
        "name": str(getattr(qualifier, "name", "ACE e-Counter") or "ACE e-Counter").strip(),
        "slug": str(getattr(qualifier, "slug", "ace-e-counter") or "ace-e-counter").strip(),
        "system_prompt": str(getattr(qualifier, "system_prompt", "") or "").strip(),
        "assistant_style": str(getattr(qualifier, "assistant_style", "") or "").strip(),
        "goal_definition": str(getattr(qualifier, "goal_definition", "") or "").strip(),
        "contact_capture_policy": str(getattr(qualifier, "contact_capture_policy", "") or "").strip(),
        "version_notes": str(getattr(qualifier, "version_notes", "") or "").strip(),
        "required_fields": required_fields,
        "field_schema": field_schema,
        "max_clarifying_questions": int(getattr(qualifier, "max_clarifying_questions", 3) or 3),
        "scoring_rules": scoring_rules,
        "band_thresholds": band_thresholds,
        "confidence_thresholds": confidence_thresholds,
        "takeover_rules": takeover_rules,
        "video_offer_rules": video_offer_rules,
        "knowledge_snippets": _knowledge_snippets(
            system_prompt=str(getattr(qualifier, "system_prompt", "") or "").strip(),
            goal_definition=str(getattr(qualifier, "goal_definition", "") or "").strip(),
            assistant_style=str(getattr(qualifier, "assistant_style", "") or "").strip(),
            contact_capture_policy=str(getattr(qualifier, "contact_capture_policy", "") or "").strip(),
            version_notes=str(getattr(qualifier, "version_notes", "") or "").strip(),
            field_schema=field_schema,
            required_fields=required_fields,
            scoring_rules=scoring_rules,
            band_thresholds=band_thresholds,
            confidence_thresholds=confidence_thresholds,
            takeover_rules=takeover_rules,
            video_offer_rules=video_offer_rules,
        ),
    }
    return context


def retrieve_knowledge(runtime_context: Dict[str, Any], recent_messages: List[Dict[str, str]], *, limit: int = 6) -> List[str]:
    snippets = [str(s).strip() for s in list(runtime_context.get("knowledge_snippets") or []) if str(s).strip()]
    if not snippets:
        return ACE_PRODUCT_BRIEF[:]
    query = " ".join(str(m.get("text") or "") for m in recent_messages[-8:] if str(m.get("text") or "").strip())
    query_tokens = _tokens(query)
    scored = []
    for index, snippet in enumerate(snippets):
        snippet_tokens = _tokens(snippet)
        overlap = len(query_tokens & snippet_tokens)
        scored.append((overlap, -index, snippet))
    scored.sort(reverse=True)
    selected = [snippet for overlap, _, snippet in scored if overlap > 0][:limit]
    for snippet in snippets:
        if len(selected) >= limit:
            break
        if snippet not in selected:
            selected.append(snippet)
    return selected[:limit]


def qualifier_field_schema(qualifier: Any) -> List[Dict[str, Any]]:
    raw = getattr(qualifier, "field_schema", None) or []
    if isinstance(raw, dict):
        raw = raw.get("fields") or []
    out: List[Dict[str, Any]] = []
    for item in list(raw or []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("key") or "").strip()
        if not name:
            continue
        out.append({
            "name": name,
            "label": str(item.get("label") or name).strip(),
            "type": str(item.get("type") or item.get("field_type") or "string").strip(),
            "required": bool(item.get("required")),
            "description": str(item.get("description") or item.get("prompt") or "").strip(),
        })
    return out


def _knowledge_snippets(
    *,
    system_prompt: str,
    goal_definition: str,
    assistant_style: str,
    contact_capture_policy: str,
    version_notes: str,
    field_schema: List[Dict[str, Any]],
    required_fields: List[str],
    scoring_rules: Dict[str, Any],
    band_thresholds: Dict[str, Any],
    confidence_thresholds: Dict[str, Any],
    takeover_rules: Dict[str, Any],
    video_offer_rules: Dict[str, Any],
) -> List[str]:
    snippets = list(ACE_PRODUCT_BRIEF)
    if goal_definition:
        snippets.append(f"Qualification goal: {goal_definition}")
    if system_prompt:
        snippets.append(f"Manager dashboard instructions: {system_prompt}")
    if assistant_style:
        snippets.append(f"Preferred assistant style: {assistant_style}")
    if required_fields:
        snippets.append("Required qualification fields: " + ", ".join(required_fields))
    if field_schema:
        capture_lines = []
        for item in field_schema[:8]:
            bit = f"{item['label']} ({item['type']})"
            if item.get("required"):
                bit += ", required"
            if item.get("description"):
                bit += f": {item['description']}"
            capture_lines.append(bit)
        snippets.append("Manager dashboard field schema: " + " | ".join(capture_lines))
    if contact_capture_policy:
        snippets.append(f"Contact capture policy: {contact_capture_policy}")
    if scoring_rules:
        snippets.append("Scoring rules from manager dashboard: " + _rule_summary(scoring_rules))
    if band_thresholds:
        snippets.append("Qualification band thresholds: " + _rule_summary(band_thresholds))
    if confidence_thresholds:
        snippets.append("Confidence thresholds: " + _rule_summary(confidence_thresholds))
    if takeover_rules:
        snippets.append("Human takeover policy: " + _rule_summary(takeover_rules))
    if video_offer_rules:
        snippets.append("Video offer policy: " + _rule_summary(video_offer_rules))
    if version_notes:
        snippets.append(f"Version notes: {version_notes}")
    return snippets


def _rule_summary(rules: Dict[str, Any]) -> str:
    parts = []
    for key, value in list(rules.items())[:8]:
        if value is None or value == "":
            continue
        parts.append(f"{key}={value}")
    return ", ".join(parts) if parts else "none specified"


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9_+-]{3,}", (text or "").lower())}
