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
    """Thin LLM client for qualification graph nodes."""

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

    def call_text(self, system_prompt: str, user_prompt: str, *, temperature: float = 0.2) -> str:
        client = self._client_or_none()
        if client is None:
            return ""
        try:
            resp = client.chat.completions.create(
                model=self.model_name,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return ((resp.choices or [None])[0].message.content or "").strip()
        except Exception as e:  # pragma: no cover
            logger.warning("llm text call failed provider=%s model=%s err=%s", self.provider, self.model_name, e)
            return ""

    def call_text_stream(self, system_prompt: str, user_prompt: str, *, temperature: float = 0.2):
        """Stream tokens. Yields each token string. Caller iterates."""
        client = self._client_or_none()
        if client is None:
            yield ""
            return
        try:
            stream = client.chat.completions.create(
                model=self.model_name,
                temperature=temperature,
                stream=True,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            for chunk in stream:
                delta = (chunk.choices or [None])[0]
                if delta and delta.delta and delta.delta.content:
                    yield delta.delta.content
        except Exception as e:
            logger.warning("llm stream failed err=%s", e)
            yield ""

    def call_with_tools(self, system_prompt: str, messages: list, tools: list, *, temperature: float = 0, required: bool = False) -> dict:
        """Returns {'text': str} if LLM answered, or {'tool_calls': [{id, name, args}]} if it wants tools."""
        client = self._client_or_none()
        if client is None:
            return {"text": ""}
        try:
            full_msgs = [{"role": "system", "content": system_prompt}] + messages
            kwargs = dict(
                model=self.model_name, temperature=temperature, messages=full_msgs, tools=tools,
            )
            kwargs["tool_choice"] = "required" if required else "auto"
            resp = client.chat.completions.create(**kwargs)
            msg = (resp.choices or [None])[0].message
            if msg.tool_calls:
                return {"tool_calls": [{"id": t.id, "name": t.function.name, "args": json.loads(t.function.arguments)} for t in msg.tool_calls]}
            return {"text": (msg.content or "").strip()}
        except Exception as e:
            logger.warning("llm tool call failed err=%s", e)
            return {"text": ""}

    def stream_reply(self, system_prompt: str, messages: list, *, temperature: float = 0.2):
        """Stream tokens for the final reply. Yields token strings."""
        client = self._client_or_none()
        if client is None:
            yield ""
            return
        try:
            full_msgs = [{"role": "system", "content": system_prompt}] + messages
            full_msgs.append({"role": "user", "content": "Odgovori v slovenščini, z vikanjem, 1-3 stavke. Bodi kratek in naraven."})
            stream = client.chat.completions.create(
                model=self.model_name, temperature=temperature, stream=True, messages=full_msgs,
            )
            for chunk in stream:
                delta = (chunk.choices or [None])[0]
                if delta and delta.delta and delta.delta.content:
                    yield delta.delta.content
        except Exception as e:
            logger.warning("llm stream failed err=%s", e)
            yield ""

    def call_json_response(self, system_prompt: str, messages: list, *, temperature: float = 0) -> str:
        """Final call to get JSON {"rep": "..."} after tool loop."""
        client = self._client_or_none()
        if client is None:
            return ""
        try:
            full_msgs = [{"role": "system", "content": system_prompt}] + messages
            full_msgs.append({"role": "user", "content": "PREBERI zgodovino pogovora. Če si že povedal/a da je salon zaprt — NE ponavljaj. Če si že naštel/a storitve — NE ponavljaj. Če je to samo 'dober dan' sredi pogovora — ne predstavljaj se ponovno. Bodi kratek (1-3 stavke). Odgovori v slovenščini. Vrni JSON: {\"rep\":\"tvoj odgovor\"}"})
            resp = client.chat.completions.create(
                model=self.model_name,
                temperature=temperature,
                response_format={"type": "json_object"},
                messages=full_msgs,
            )
            content = (resp.choices[0].message.content or "{}").strip()
            return json.loads(content).get("rep", "") if content.startswith("{") else content
        except Exception as e:
            logger.warning("llm json response failed err=%s", e)
            return ""
