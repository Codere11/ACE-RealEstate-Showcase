from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.core.env import load_local_env

load_local_env()

logger = logging.getLogger("ace.llm_service")

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - keep startup safe if SDK unavailable
    OpenAI = None  # type: ignore


@dataclass
class LLMExtractionResult:
    profile_patch: Dict[str, Any]
    field_confidence: Dict[str, float]
    reasoning_hint: str = ""
    model_name: Optional[str] = None
    used_llm: bool = False


@dataclass
class LLMReplyResult:
    reply: str
    reasoning_hint: str = ""
    model_name: Optional[str] = None
    used_llm: bool = False


class LLMService:
    """
    Minimal structured extraction wrapper.

    We intentionally keep this simple and deterministic:
    - one provider path (OpenAI)
    - one JSON output contract
    - safe fallback to no-op on any failure

    LangGraph can later orchestrate this as one node in the qualifier graph.
    """

    def __init__(self) -> None:
        self.provider = os.getenv("ACE_LLM_PROVIDER", "none").strip().lower()
        self.model = os.getenv("ACE_LLM_MODEL", "gpt-4.1-mini").strip()
        self.api_key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("ACE_OPENAI_API_KEY")
            or ""
        ).strip()
        self._client = None

    def is_available(self) -> bool:
        return self.provider in {"openai"} and bool(self.api_key) and OpenAI is not None

    def _client_or_none(self):
        if not self.is_available():
            return None
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def extract_profile_patch(
        self,
        *,
        system_prompt: str,
        goal_definition: str,
        field_schema: Dict[str, Any] | None,
        existing_profile: Dict[str, Any] | None,
        messages: List[str],
    ) -> LLMExtractionResult:
        if not self.is_available() or not field_schema or not messages:
            return LLMExtractionResult(profile_patch={}, field_confidence={}, used_llm=False)

        client = self._client_or_none()
        if client is None:
            return LLMExtractionResult(profile_patch={}, field_confidence={}, used_llm=False)

        schema_keys = list((field_schema or {}).keys())
        prompt = self._build_prompt(
            system_prompt=system_prompt,
            goal_definition=goal_definition,
            field_schema=field_schema or {},
            existing_profile=existing_profile or {},
            messages=messages,
        )

        try:
            resp = client.chat.completions.create(
                model=self.model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "You are a careful qualification extractor. Return only valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            content = ((resp.choices or [None])[0].message.content or "{}").strip()
            parsed = json.loads(content)
            patch = parsed.get("profile_patch") or {}
            conf = parsed.get("field_confidence") or {}
            reasoning = str(parsed.get("reasoning_hint") or "").strip()

            safe_patch = {
                k: v for k, v in patch.items()
                if k in schema_keys and v not in (None, "", [], {})
            }
            safe_conf: Dict[str, float] = {}
            for k, v in conf.items():
                if k not in schema_keys:
                    continue
                try:
                    safe_conf[k] = max(0.0, min(1.0, float(v)))
                except Exception:
                    continue

            return LLMExtractionResult(
                profile_patch=safe_patch,
                field_confidence=safe_conf,
                reasoning_hint=reasoning[:500],
                model_name=self.model,
                used_llm=True,
            )
        except Exception as e:
            logger.warning("LLM extraction failed provider=%s model=%s err=%s", self.provider, self.model, e)
            return LLMExtractionResult(profile_patch={}, field_confidence={}, used_llm=False)

    def generate_reply(
        self,
        *,
        system_prompt: str,
        goal_definition: str,
        assistant_style: str,
        profile: Dict[str, Any],
        missing_fields: List[str],
        messages: List[str],
        takeover_eligible: bool,
        video_offer_eligible: bool,
    ) -> LLMReplyResult:
        if not self.is_available() or not messages:
            return LLMReplyResult(
                reply="Razumem. Nadaljujeva v prostem pogovoru — povej mi malo več, da te lahko usmerim naprej.",
                used_llm=False,
            )

        client = self._client_or_none()
        if client is None:
            return LLMReplyResult(
                reply="Razumem. Nadaljujeva v prostem pogovoru — povej mi malo več, da te lahko usmerim naprej.",
                used_llm=False,
            )

        prompt = self._build_reply_prompt(
            system_prompt=system_prompt,
            goal_definition=goal_definition,
            assistant_style=assistant_style,
            profile=profile,
            missing_fields=missing_fields,
            messages=messages,
            takeover_eligible=takeover_eligible,
            video_offer_eligible=video_offer_eligible,
        )

        try:
            resp = client.chat.completions.create(
                model=self.model,
                temperature=0.35,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": "You are a strong lead-qualification conversational assistant. Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
            )
            content = ((resp.choices or [None])[0].message.content or "{}").strip()
            parsed = json.loads(content)
            reply = str(parsed.get("reply") or "").strip()
            reasoning = str(parsed.get("reasoning_hint") or "").strip()
            if not reply:
                reply = "Razumem. Nadaljujeva v prostem pogovoru — povej mi malo več, da te lahko usmerim naprej."
            return LLMReplyResult(
                reply=reply[:1200],
                reasoning_hint=reasoning[:400],
                model_name=self.model,
                used_llm=True,
            )
        except Exception as e:
            logger.warning("LLM reply generation failed provider=%s model=%s err=%s", self.provider, self.model, e)
            return LLMReplyResult(
                reply="Razumem. Nadaljujeva v prostem pogovoru — povej mi malo več, da te lahko usmerim naprej.",
                used_llm=False,
            )

    def _build_prompt(
        self,
        *,
        system_prompt: str,
        goal_definition: str,
        field_schema: Dict[str, Any],
        existing_profile: Dict[str, Any],
        messages: List[str],
    ) -> str:
        return (
            "Extract structured qualification data from the recent conversation.\n\n"
            f"SYSTEM_PROMPT:\n{system_prompt or ''}\n\n"
            f"GOAL:\n{goal_definition or ''}\n\n"
            "FIELD_SCHEMA (extract only these fields):\n"
            f"{json.dumps(field_schema, ensure_ascii=False, indent=2)}\n\n"
            "EXISTING_PROFILE (already known facts; do not overwrite with weaker guesses):\n"
            f"{json.dumps(existing_profile or {}, ensure_ascii=False, indent=2)}\n\n"
            "RECENT_MESSAGES:\n"
            f"{json.dumps(messages, ensure_ascii=False, indent=2)}\n\n"
            "Return JSON with exactly this shape:\n"
            "{\n"
            "  \"profile_patch\": {\"field\": \"value or boolean or array\"},\n"
            "  \"field_confidence\": {\"field\": 0.0},\n"
            "  \"reasoning_hint\": \"short operator-facing explanation\"\n"
            "}\n\n"
            "Rules:\n"
            "- Use only fields from FIELD_SCHEMA.\n"
            "- Omit unknown fields from profile_patch.\n"
            "- Confidence must be 0..1.\n"
            "- Be conservative.\n"
            "- Return JSON only."
        )

    def _build_reply_prompt(
        self,
        *,
        system_prompt: str,
        goal_definition: str,
        assistant_style: str,
        profile: Dict[str, Any],
        missing_fields: List[str],
        messages: List[str],
        takeover_eligible: bool,
        video_offer_eligible: bool,
    ) -> str:
        return (
            "Generate the next assistant reply for a lead-qualification conversation.\n\n"
            f"CORE_INSTRUCTIONS:\n{system_prompt or ''}\n\n"
            f"QUALIFICATION_GOAL:\n{goal_definition or ''}\n\n"
            f"ASSISTANT_STYLE:\n{assistant_style or ''}\n\n"
            "KNOWN_PROFILE:\n"
            f"{json.dumps(profile or {}, ensure_ascii=False, indent=2)}\n\n"
            "MISSING_FIELDS:\n"
            f"{json.dumps(missing_fields or [], ensure_ascii=False)}\n\n"
            "RECENT_MESSAGES:\n"
            f"{json.dumps(messages, ensure_ascii=False, indent=2)}\n\n"
            f"TAKEOVER_ELIGIBLE: {json.dumps(bool(takeover_eligible))}\n"
            f"VIDEO_OFFER_ELIGIBLE: {json.dumps(bool(video_offer_eligible))}\n\n"
            "Return JSON with this shape:\n"
            "{\n"
            "  \"reply\": \"assistant message\",\n"
            "  \"reasoning_hint\": \"short operator-facing note\"\n"
            "}\n\n"
            "Rules:\n"
            "- Speak like a competent sales/qualification assistant, not a form bot.\n"
            "- Answer the user's actual question first if they asked one.\n"
            "- Then ask at most one useful follow-up question if needed.\n"
            "- Do not repeat generic filler.\n"
            "- Do not invent listings, inventory, or facts you do not know.\n"
            "- If information is missing, ask one precise question that improves qualification.\n"
            "- Keep it concise, useful, and engaging.\n"
            "- Return JSON only."
        )
