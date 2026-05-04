from __future__ import annotations

import json
from typing import Any, Dict, List


ACE_ECOUNTER_ROLE_CONTRACT = """You are the ACE e-Counter qualification agent.

ACE e-Counter helps businesses capture, qualify, and route customer interest.
It can be relevant for small, local, informal, or offline-first businesses too.

You are not a generic assistant or a seller of unrelated products.
If something is truly out of scope, say so briefly.
If a real business asks whether ACE can help them get more customers or handle inbound interest better, treat that as a valid prospect conversation.
"""


def build_interpret_prompt(
    *,
    system_prompt: str,
    goal_definition: str,
    existing_profile: Dict[str, Any],
    recent_messages: List[Dict[str, str]],
) -> str:
    return (
        "Interpret the latest conversation turn for ACE e-Counter qualification.\n\n"
        f"ROLE_CONTRACT:\n{ACE_ECOUNTER_ROLE_CONTRACT}\n\n"
        f"ORG_GUIDANCE:\n{system_prompt or ''}\n\n"
        f"QUALIFICATION_GOAL:\n{goal_definition or ''}\n\n"
        "EXISTING_PROFILE:\n"
        f"{json.dumps(existing_profile or {}, ensure_ascii=False, indent=2)}\n\n"
        "RECENT_MESSAGES_WITH_ROLES:\n"
        f"{json.dumps(recent_messages, ensure_ascii=False, indent=2)}\n\n"
        "Return JSON with exactly this shape:\n"
        "{\n"
        "  \"visitor_type\": \"sales_prospect|existing_customer_support|partner_or_vendor|job_seeker|irrelevant_or_joke|abusive_or_spam|unclear\",\n"
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
        "  \"reasoning_hint\": \"short explanation\"\n"
        "}\n\n"
        "Rules:\n"
        "- Merge new facts into EXISTING_PROFILE instead of throwing old facts away.\n"
        "- supporting_quotes must be copied exactly from user messages, not paraphrased.\n"
        "- Do not infer fame, social status, demographics, or channels unless clearly supported by the user's words or prior context.\n"
        "- If the user reveals how they currently sell or who they currently sell to, treat that as meaningful business context.\n"
        "- A tiny business can still be a sales prospect if ACE could help it get more customers or handle inquiries better.\n"
        "- If the latest user message asks whether ACE sells a physical product, food, vehicle, or other unrelated item, classify it as irrelevant_or_joke unless the user is clearly describing their own business use case.\n"
        "- Return JSON only."
    )


def build_decide_prompt(
    *,
    assistant_style: str,
    required_fields: List[str],
    latest_message: str,
    recent_messages: List[Dict[str, str]],
    interpretation: Dict[str, Any],
) -> str:
    return (
        "Decide the next ACE e-Counter qualification step and write the reply.\n\n"
        f"ROLE_CONTRACT:\n{ACE_ECOUNTER_ROLE_CONTRACT}\n\n"
        f"ASSISTANT_STYLE:\n{assistant_style or ''}\n\n"
        f"LATEST_USER_MESSAGE:\n{json.dumps(latest_message, ensure_ascii=False)}\n\n"
        "RECENT_MESSAGES_WITH_ROLES:\n"
        f"{json.dumps(recent_messages, ensure_ascii=False, indent=2)}\n\n"
        "INTERPRETATION:\n"
        f"{json.dumps(interpretation or {}, ensure_ascii=False, indent=2)}\n\n"
        "REQUIRED_FIELDS:\n"
        f"{json.dumps(required_fields or [], ensure_ascii=False)}\n\n"
        "Return JSON with exactly this shape:\n"
        "{\n"
        "  \"reply\": \"assistant message\",\n"
        "  \"recommended_next_action\": \"ask_clarifying_question|continue_conversation|offer_human_takeover|route_support|redirect_to_scope|soft_close\",\n"
        "  \"funnel_stage\": \"business_context|pain_discovery|solution_fit|action_routing|support_routing|routed_out\",\n"
        "  \"qualification_complete\": false,\n"
        "  \"missing_fields\": [\"field_name\"],\n"
        "  \"qualification_score\": 0,\n"
        "  \"qualification_band\": \"cold|warm|hot\",\n"
        "  \"takeover_eligible\": false,\n"
        "  \"video_offer_eligible\": false,\n"
        "  \"confidence_overall\": 0.0,\n"
        "  \"reasoning_hint\": \"short explanation\"\n"
        "}\n\n"
        "Rules:\n"
        "- Write the reply in the same language as the latest user message.\n"
        "- Ask at most one question.\n"
        "- If visitor_type is existing_customer_support, route support.\n"
        "- If visitor_type is partner_or_vendor, job_seeker, irrelevant_or_joke, or abusive_or_spam, do not qualify as a prospect.\n"
        "- If the latest user message was a purchase query for an unrelated product, redirect briefly to what ACE e-Counter actually does instead of trying to qualify that product request.\n"
        "- If the interpretation relies on inferred meaning with confidence below 0.75, use a short confirmation-style reply instead of a bold paraphrase.\n"
        "- Stay close to supporting_quotes and profile_after. Do not invent stronger wording than the evidence supports.\n"
        "- If the latest message already answered the previous question, do not ask the same question again in different words. Move to the next narrower question.\n"
        "- If the business is real and ACE could plausibly help, continue qualification even if the business is small or unconventional.\n"
        "- qualification_score and qualification_band are operator metadata only; they must not contradict the chosen action.\n"
        "- Return JSON only."
    )
