from __future__ import annotations

import json
from typing import Any, Dict, List


def _prune(value: Any) -> Any:
    if isinstance(value, dict):
        out = {k: _prune(v) for k, v in value.items() if v not in (None, "", [], {})}
        return {k: v for k, v in out.items() if v not in (None, "", [], {})}
    if isinstance(value, list):
        out = [_prune(v) for v in value if v not in (None, "", [], {})]
        return [v for v in out if v not in (None, "", [], {})]
    return value


def _compact_messages(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    compact = []
    for item in items[-4:]:
        role = str(item.get("role") or "user")
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        compact.append({"r": role, "t": text})
    return compact


ACE_ECOUNTER_ROLE_CONTRACT = """You are the ACE e-Counter qualification agent.

ACE e-Counter helps businesses capture, qualify, and route inbound customer interest from their website or landing page.
It can be relevant for small, local, informal, or offline-first businesses too.

You are not a generic assistant and you are not pretending ACE sells the visitor's product.
You must understand the product, the manager dashboard setup, the current conversation, and the lead profile before deciding what to say.
"""


def build_qualify_prompt(
    *,
    runtime_context: Dict[str, Any],
    knowledge_context: List[str],
    existing_profile: Dict[str, Any],
    recent_messages: List[Dict[str, str]],
    latest_message: str,
) -> str:
    compact_runtime = json.dumps(_prune(runtime_context or {}), ensure_ascii=False, separators=(",", ":"))
    compact_knowledge = json.dumps((knowledge_context or [])[:4], ensure_ascii=False, separators=(",", ":"))
    compact_profile = json.dumps(_prune(existing_profile or {}), ensure_ascii=False, separators=(",", ":"))
    compact_messages = json.dumps(_compact_messages(recent_messages or []), ensure_ascii=False, separators=(",", ":"))
    compact_latest = json.dumps(latest_message or "", ensure_ascii=False)
    return (
        "Analyze the turn, update qualification state, and write the final reply in one JSON response.\n\n"
        f"ROLE_CONTRACT:\n{ACE_ECOUNTER_ROLE_CONTRACT}\n\n"
        f"RUNTIME_CONTEXT:{compact_runtime}\n"
        f"KNOWLEDGE:{compact_knowledge}\n"
        f"PROFILE:{compact_profile}\n"
        f"MESSAGES:{compact_messages}\n"
        f"LATEST:{compact_latest}\n\n"
        "Return one compact JSON object with these keys:\n"
        "{"
        "\"vt\":\"sales_prospect|existing_customer_support|partner_or_vendor|job_seeker|irrelevant_or_joke|abusive_or_spam|unclear\","
        "\"lang\":\"en|sl|es|other\","
        "\"p\":{"
        "\"business_type\":\"string\","
        "\"business_model\":\"string\","
        "\"customer_source\":\"string\","
        "\"sales_motion\":\"string\","
        "\"growth_constraint\":\"string\","
        "\"pain_points\":[\"string\"],"
        "\"desired_outcome\":\"string\","
        "\"use_case_fit\":[\"string\"],"
        "\"fit_status\":\"high|medium|low|unknown\","
        "\"supporting_quotes\":[\"exact user quotes\"]},"
        "\"fc\":{\"field\":0.0},"
        "\"co\":0.0,"
        "\"sq\":[\"exact user quotes\"],"
        "\"stage\":\"business_context|pain_discovery|solution_fit|action_routing|support_routing|routed_out\","
        "\"done\":false,"
        "\"miss\":[\"field_name\"],"
        "\"score\":0,"
        "\"band\":\"cold|warm|hot\","
        "\"to\":false,"
        "\"vo\":false,"
        "\"act\":\"ask_clarifying_question|continue_conversation|offer_human_takeover|route_support|redirect_to_scope|soft_close\","
        "\"q\":\"single next question or empty string\","
        "\"strat\":\"answer_directly_then_ask|answer_directly_no_question|ask_single_question|redirect|route_support|handoff\","
        "\"why\":\"short explanation\","
        "\"rep\":\"final assistant reply text\"}"
        "\n\nRules:\n"
        "- Use RUNTIME_CONTEXT.static_prompt_block plus KNOWLEDGE as source of truth for what ACE does and how this organization configured it.\n"
        "- Merge new facts into PROFILE; do not discard known facts.\n"
        "- supporting_quotes must copy user words exactly.\n"
        "- If user asks how ACE helps, works, or fits, answer that directly first.\n"
        "- Do not ask a question already answered in MESSAGES or PROFILE.\n"
        "- Ask at most one question, only if it truly moves qualification forward.\n"
        "- If user already gave lead source and follow-up process, avoid broad discovery.\n"
        "- If user says the process is manual or just corrected you, do not ask another process or timing question. Usually acknowledge and either explain fit or ask only for the concrete missing field.\n"
        "- If user correction reveals the bottleneck, acknowledge it and usually prefer answer_directly_no_question.\n"
        "- Avoid vague catch-all questions when pain is already concrete.\n"
        "- preferred_language must match dominant user language unless the user clearly switches.\n"
        "- If visitor_type is existing_customer_support, route support and do not ask qualification questions.\n"
        "- If visitor_type is partner_or_vendor, job_seeker, irrelevant_or_joke, or abusive_or_spam, do not qualify as a prospect.\n"
        "- Use manager scoring_rules, band_thresholds, and confidence_thresholds for qualification_score and qualification_band.\n"
        "- Do not output warm or hot band with zero or near-zero score.\n"
        "- Return JSON only.\n"
    )
