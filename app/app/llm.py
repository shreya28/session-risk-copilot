"""Thin LLM wrapper.

Providers (first match wins):
  1. GEMINI_API_KEY (free tier from Google AI Studio) or LLM_API_KEY + LLM_BASE_URL (any OpenAI-compatible API)
  2. ANTHROPIC_API_KEY
  3. none -> offline mode (templates + deterministic agent planner)
"""
from __future__ import annotations

import json
import os
import re

from . import prompts

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
_cache: dict = {}


def provider():
    if os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY"):
        return "openai"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def model() -> str:
    if provider() == "openai":
        return os.getenv("LLM_MODEL", DEFAULT_GEMINI_MODEL)
    return os.getenv("LLM_MODEL") or os.getenv("SRC_MODEL", "claude-sonnet-4-6")


def label() -> str:
    p = provider()
    if p == "openai":
        host = "Gemini" if not os.getenv("LLM_BASE_URL") else "OpenAI-compatible API"
        return f"{host} ({model()})"
    return f"Anthropic ({model()})" if p else "offline"


def client():
    p = provider()
    if p is None:
        return None
    if p not in _cache:
        if p == "openai":
            from openai import OpenAI
            _cache[p] = OpenAI(api_key=os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY"),
                               base_url=os.getenv("LLM_BASE_URL", GEMINI_BASE))
        else:
            import anthropic
            _cache[p] = anthropic.Anthropic()
    return _cache[p]


def llm_available() -> bool:
    return provider() is not None


def parse_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text).strip()
    return json.loads(text[text.index("{"): text.rindex("}") + 1])


def complete(system: str, user: str, max_tokens: int = 500) -> str:
    c = client()
    if provider() == "openai":
        # No max_tokens here on purpose: Gemini "thinking" models spend output tokens on reasoning
        # and a small cap can return an empty answer. The prompts already ask for short outputs.
        r = c.chat.completions.create(model=model(), messages=[
            {"role": "system", "content": system}, {"role": "user", "content": user}])
        return r.choices[0].message.content or ""
    r = c.messages.create(model=model(), max_tokens=max_tokens, system=system,
                          messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in r.content if b.type == "text")


def template_explanation(result: dict) -> str:
    top = sorted(result["signals"], key=lambda s: -s["weight"])[:2]
    why = "; ".join(s["detail"] for s in top) or "no risk signals"
    nxt = {"block": "Revoke the session and re-verify the user.",
           "step_up": "Require MFA before completing this action.",
           "allow": "No action needed."}[result["decision"]]
    return f"Score {result['risk_score']} ({result['decision']}): {why}. {nxt}"


def explain(safe_event: dict, result: dict) -> tuple[str, bool]:
    if client() is None:
        return template_explanation(result), False
    try:
        payload = {"event": safe_event, "risk_score": result["risk_score"], "decision": result["decision"],
                   "signals": [{k: s[k] for k in ("name", "weight", "detail")} for s in result["signals"]]}
        return parse_json(complete(prompts.EXPLAINER, json.dumps(payload)))["explanation"], True
    except Exception:
        return template_explanation(result), False
