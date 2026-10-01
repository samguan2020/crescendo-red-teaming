"""
Shared parsing helpers for LLM-authored strategy output.

Attacker LLMs return free-form text; each strategy expects a JSON object
somewhere inside it. Centralizing the extraction keeps every strategy focused
on its own schema instead of re-implementing the same parsing boilerplate, and
keeps the attacker port a pure text-in/text-out contract.
"""
from __future__ import annotations

import json
import re

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json_object(text: str | None) -> dict | None:
    """Best-effort extraction of a single JSON object from LLM text.

    Tries, in order: the whole string (fast path for an already-JSON reply),
    a fenced ```json block, then the first ``{...}`` span. Returns None when
    nothing parses into an object.
    """
    if not text:
        return None
    stripped = text.strip()

    try:
        data = json.loads(stripped)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    fence = _JSON_FENCE_RE.search(stripped)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass

    match = _JSON_OBJECT_RE.search(stripped)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None
