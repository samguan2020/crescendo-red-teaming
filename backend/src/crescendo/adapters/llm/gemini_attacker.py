"""
Gemini attacker adapter - implements AttackerLLMPort via langchain-google-genai.

Thin text-in/text-out wrapper. Strategies own all prompt construction; this
adapter only forwards messages and returns raw text.
"""
from __future__ import annotations

import asyncio
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

_ROLE_MAP = {
    "system": SystemMessage,
    "assistant": AIMessage,
    "ai": AIMessage,
    "user": HumanMessage,
}


def _message_text(message: object) -> str:
    """Collapse a LangChain message into plain text.

    Gemini 3+ returns ``content`` as a list of content blocks, while earlier
    models return a plain string. Strategies expect a string, so we join the
    text blocks (mirroring LangChain's own ``.text`` extraction).
    """
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)


class GeminiAttacker:
    """Implements AttackerLLMPort."""

    def __init__(self, *, model: str, api_key: str, timeout: int = 45) -> None:
        from langchain_google_genai import ChatGoogleGenerativeAI

        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._ChatGoogleGenerativeAI = ChatGoogleGenerativeAI

    def _client(self, temperature: float):
        return self._ChatGoogleGenerativeAI(
            model=self._model,
            google_api_key=self._api_key,
            temperature=temperature,
            convert_system_message_to_human=True,
            timeout=self._timeout,
        )

    async def complete(self, messages: list[dict[str, str]], *, temperature: float) -> str:
        lc_messages = [
            _ROLE_MAP.get(m.get("role", "user"), HumanMessage)(content=m.get("content", ""))
            for m in messages
        ]
        raw = await asyncio.wait_for(
            self._client(temperature).ainvoke(lc_messages),
            timeout=self._timeout + 5,
        )
        return _message_text(raw)
