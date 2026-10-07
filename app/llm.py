"""Thin LLM wrapper (Anthropic). Everything degrades gracefully to offline mode without an API key."""
from __future__ import annotations

import json
import os
import re

from . import prompts

MODEL = os.getenv("SRC_MODEL", "claude-sonnet-4-6")
_client = None


def client():
    global _client
    if _client is None and os.getenv("ANTHROPIC_API_KEY"):
        import anthropic
        _client = anthropic.Anthropic()
    return _client


def llm_available() -> bool:
    return client() is not None


def parse_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text).strip()
    return json.loads(text[text.index("{"): text.rindex("}") + 1])


def complete(system: str, user: str, max_tokens: int = 500) -> str:
    r = client().messages.create(model=MODEL, max_tokens=max_tokens, system=system,
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
