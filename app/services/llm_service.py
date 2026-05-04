from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

from app.core.env import load_local_env

load_local_env()
logger = logging.getLogger("ace.llm_service")

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


class LLMService:
    """Thin JSON-only LLM client for qualification graph nodes."""

    def __init__(self) -> None:
        self.provider = os.getenv("ACE_LLM_PROVIDER", "none").strip().lower()
        self.model_name = os.getenv("ACE_LLM_MODEL", "gpt-4.1-mini").strip()
        self.api_key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("ACE_OPENAI_API_KEY")
            or ""
        ).strip()
        self._client = None

    def is_available(self) -> bool:
        return self.provider == "openai" and bool(self.api_key) and OpenAI is not None

    def _client_or_none(self):
        if not self.is_available():
            return None
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def call_json(self, system_prompt: str, user_prompt: str, *, temperature: float = 0) -> Dict[str, Any]:
        client = self._client_or_none()
        if client is None:
            return {}
        try:
            resp = client.chat.completions.create(
                model=self.model_name,
                temperature=temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = ((resp.choices or [None])[0].message.content or "{}").strip()
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else {}
        except Exception as e:  # pragma: no cover
            logger.warning("llm json call failed provider=%s model=%s err=%s", self.provider, self.model_name, e)
            return {}
