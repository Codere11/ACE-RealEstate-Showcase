from __future__ import annotations

import json
from typing import Any, Dict, List


ACE_ECOUNTER_ROLE_CONTRACT = """You are the ACE e-Counter qualification agent.

ACE e-Counter helps businesses capture, qualify, and route inbound customer interest from their website or landing page.
It can be relevant for small, local, informal, or offline-first businesses too.

You are not a generic assistant and you are not pretending ACE sells the visitor's product.
You must understand the product, the manager dashboard setup, the current conversation, and the lead profile before deciding what to say.
"""


def build_analysis_prompt(
    *,
    runtime_context: Dict[str, Any],
    knowledge_context: List[str],
    existing_profile: Dict[str, Any],
    recent_messages: List[Dict[str, str]],
    latest_message: str,
) -> str:
    return (
        "Analyze the latest ACE e-Counter qualification turn and plan the next best response.\n\n"
        f"ROLE_CONTRACT:\n{ACE_ECOUNTER_ROLE_CONTRACT}\n\n"
        "RUNTIME_CONTEXT_FROM_MANAGER_DASHBOARD:\n"
        f"{json.dumps(runtime_context or {}, ensure_ascii=False, indent=2)}\n\n"
        "RETRIEVED_PRODUCT_AND_POLICY_KNOWLEDGE:\n"
        f"{json.dumps(knowledge_context or [], ensure_ascii=False, indent=2)}\n\n"
        "EXISTING_LEAD_PROFILE:\n"
        f"{json.dumps(existing_profile or {}, ensure_ascii=False, indent=2)}\n\n"
        "RECENT_MESSAGES_WITH_ROLES:\n"
        f"{json.dumps(recent_messages or [], ensure_ascii=False, indent=2)}\n\n"
        "LATEST_USER_MESSAGE:\n"
        f"{json.dumps(latest_message or '', ensure_ascii=False)}\n\n"
        "Return JSON with exactly this shape:\n"
        "{\n"
        "  \"visitor_type\": \"sales_prospect|existing_customer_support|partner_or_vendor|job_seeker|irrelevant_or_joke|abusive_or_spam|unclear\",\n"
        "  \"preferred_language\": \"en|sl|es|other\",\n"
        "  \"profile_after\": {\n"
        "    \"visitor_type\": \"string\",\n"
        "    \"business_type\": \"string\",\n"
        "    \"business_model\": \"string\",\n"
        "    \"customer_source\": \"string\",\n"
        "    \"sales_motion\": \"string\",\n"
        "    \"growth_constraint\": \"string\",\n"
        "    \"pain_points\": [\"string\"],\n"
        "    \"desired_outcome\": \"string\",\n"
        "    \"use_case_fit\": [\"string\"],\n"
        "    \"fit_status\": \"high|medium|low|unknown\",\n"
        "    \"supporting_quotes\": [\"exact user quotes\"]\n"
        "  },\n"
        "  \"field_confidence\": {\"field\": 0.0},\n"
        "  \"confidence_overall\": 0.0,\n"
        "  \"supporting_quotes\": [\"exact user quotes\"],\n"
        "  \"funnel_stage\": \"business_context|pain_discovery|solution_fit|action_routing|support_routing|routed_out\",\n"
        "  \"qualification_complete\": false,\n"
        "  \"missing_fields\": [\"field_name\"],\n"
        "  \"qualification_score\": 0,\n"
        "  \"qualification_band\": \"cold|warm|hot\",\n"
        "  \"takeover_eligible\": false,\n"
        "  \"video_offer_eligible\": false,\n"
        "  \"recommended_next_action\": \"ask_clarifying_question|continue_conversation|offer_human_takeover|route_support|redirect_to_scope|soft_close\",\n"
        "  \"next_best_question\": \"single next question or empty string\",\n"
        "  \"suggested_reply_strategy\": \"answer_directly_then_ask|answer_directly_no_question|ask_single_question|redirect|route_support|handoff\",\n"
        "  \"reasoning_hint\": \"short explanation\"\n"
        "}\n\n"
        "Rules:\n"
        "- Use RUNTIME_CONTEXT_FROM_MANAGER_DASHBOARD and RETRIEVED_PRODUCT_AND_POLICY_KNOWLEDGE as source of truth for what ACE does and how this organization configured it.\n"
        "- Merge new facts into EXISTING_LEAD_PROFILE instead of throwing old facts away.\n"
        "- supporting_quotes must be copied exactly from user messages, not paraphrased.\n"
        "- If the user asks how ACE would help, work, fit, or apply to their workflow, suggested_reply_strategy must start with answering that direct question.\n"
        "- Do not ask a question that was already answered in the recent messages or stored profile.\n"
        "- Ask at most one next question and only if it truly moves qualification forward.\n"
        "- preferred_language must match the dominant user language across recent user messages unless the user clearly switches language.\n"
        "- If visitor_type is existing_customer_support, route support.\n"
        "- If visitor_type is partner_or_vendor, job_seeker, irrelevant_or_joke, or abusive_or_spam, do not qualify as a prospect.\n"
        "- If enough context already exists to explain fit concretely, prefer answer_directly_then_ask or answer_directly_no_question over another generic discovery question.\n"
        "- If the user is correcting the assistant or shows frustration, acknowledge the correction and move forward; do not ask them to restate the same fact or the same pain in new words.\n"
        "- When the user already shared both current lead source and current follow-up process, do not ask another broad discovery question. Only ask a sharper operational question if a truly critical field is still missing.\n"
        "- Do not use vague catch-all questions like 'what result matters most' or 'what is the biggest challenge' if the user already gave a concrete pain point.\n"
        "- If the user correction already reveals the bottleneck, prefer answer_directly_no_question unless there is one clearly better concrete next question.\n"
        "- qualification_score and qualification_band are operator metadata only, but they must still be present and internally consistent.\n"
        "- Use manager dashboard scoring_rules, band_thresholds, and confidence_thresholds when assigning qualification_score and qualification_band.\n"
        "- Do not output a warm or hot band with a zero or near-zero qualification_score.\n"
        "- Return JSON only.\n"
    )


def build_writer_prompt(
    *,
    runtime_context: Dict[str, Any],
    knowledge_context: List[str],
    recent_messages: List[Dict[str, str]],
    latest_message: str,
    analysis: Dict[str, Any],
) -> str:
    return (
        "Write the next assistant reply for ACE e-Counter qualification.\n\n"
        f"ROLE_CONTRACT:\n{ACE_ECOUNTER_ROLE_CONTRACT}\n\n"
        "RUNTIME_CONTEXT_FROM_MANAGER_DASHBOARD:\n"
        f"{json.dumps(runtime_context or {}, ensure_ascii=False, indent=2)}\n\n"
        "RETRIEVED_PRODUCT_AND_POLICY_KNOWLEDGE:\n"
        f"{json.dumps(knowledge_context or [], ensure_ascii=False, indent=2)}\n\n"
        "RECENT_MESSAGES_WITH_ROLES:\n"
        f"{json.dumps(recent_messages or [], ensure_ascii=False, indent=2)}\n\n"
        "LATEST_USER_MESSAGE:\n"
        f"{json.dumps(latest_message or '', ensure_ascii=False)}\n\n"
        "ANALYSIS_AND_PLAN:\n"
        f"{json.dumps(analysis or {}, ensure_ascii=False, indent=2)}\n\n"
        "Reply rules:\n"
        "- Write only the final assistant reply text, no JSON.\n"
        "- Use the language in ANALYSIS_AND_PLAN.preferred_language.\n"
        "- Follow ANALYSIS_AND_PLAN.suggested_reply_strategy exactly.\n"
        "- If the user asked a direct product-fit question, answer it concretely first.\n"
        "- Ground every claim in RUNTIME_CONTEXT_FROM_MANAGER_DASHBOARD or RETRIEVED_PRODUCT_AND_POLICY_KNOWLEDGE.\n"
        "- Do not invent capabilities that are not supported by the provided context.\n"
        "- Do not repeat a question the user already answered.\n"
        "- If the user just corrected the assistant or sounds frustrated, acknowledge it briefly and avoid another broad discovery question.\n"
        "- If ANALYSIS_AND_PLAN.suggested_reply_strategy is route_support, redirect, or handoff, do not ask another qualification question.\n"
        "- If ANALYSIS_AND_PLAN.suggested_reply_strategy is answer_directly_no_question, end cleanly with a useful summary or optional next step, not another question.\n"
        "- If ANALYSIS_AND_PLAN.suggested_reply_strategy is answer_directly_then_ask, the question must be concrete and narrower than what the user already answered.\n"
        "- Ask at most one question, and only use ANALYSIS_AND_PLAN.next_best_question if a question is needed.\n"
        "- Keep the reply concise, professional, and useful.\n"
        "- Stay close to the user’s actual workflow and business details.\n"
    )
