"""Tool-using investigation agent (Claude tool use) with an offline planner fallback."""
from __future__ import annotations

import json

from . import llm, privacy, prompts, rag, store
from .risk_engine import haversine_km

TOOLS = [
    {"name": "get_session_history", "description": "All events (redacted) recorded in one session, oldest first.",
     "input_schema": {"type": "object", "properties": {"session_ref": {"type": "string"}}, "required": ["session_ref"]}},
    {"name": "get_user_baseline", "description": "The user's normal devices, countries, active hours and typical export/payment sizes.",
     "input_schema": {"type": "object", "properties": {"user_ref": {"type": "string"}}, "required": ["user_ref"]}},
    {"name": "check_geo_velocity", "description": "Travel legs between consecutive events of a user with distance, minutes and implied speed.",
     "input_schema": {"type": "object", "properties": {"user_ref": {"type": "string"}}, "required": ["user_ref"]}},
    {"name": "search_playbooks", "description": "Search the security response playbooks (RAG) and return the best matching sections.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
]


def run_tool(name: str, args: dict):
    if name == "get_session_history":
        real = privacy.resolve(args.get("session_ref", ""))
        return [privacy.redact_event(e) for e in store.all_events() if e["session_id"] == real]
    if name == "get_user_baseline":
        real = privacy.resolve(args.get("user_ref", ""))
        return privacy.redact_baseline(store.BASELINES[real]) if real in store.BASELINES else {"error": "unknown user_ref"}
    if name == "check_geo_velocity":
        real = privacy.resolve(args.get("user_ref", ""))
        evs, legs = store.history(real), []
        for a, b in zip(evs, evs[1:]):
            if None in (a.get("lat"), b.get("lat")):
                continue
            km = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
            mins = (llm_ts(b) - llm_ts(a)).total_seconds() / 60
            if km > 300 and mins > 0:
                legs.append({"from": a["country"], "to": b["country"], "km": round(km), "minutes": round(mins),
                             "kmh": round(km / (mins / 60))})
        return legs
    if name == "search_playbooks":
        return [{"id": h["id"], "heading": h["heading"], "excerpt": h["text"][:600]}
                for h in rag.get_kb().search(args.get("query", ""), 3)]
    return {"error": f"unknown tool {name}"}


def llm_ts(e):
    from datetime import datetime
    return datetime.fromisoformat(e["ts"])


def investigate(event: dict, result: dict) -> dict:
    if llm.client() is None:
        return _offline(result)
    try:
        return _online_openai(event, result) if llm.provider() == "openai" else _online_anthropic(event, result)
    except Exception as exc:
        out = _offline(result)
        out["note"] = f"LLM call failed ({type(exc).__name__}: {str(exc)[:120]}); showing the offline planner instead."
        return out


def _task(event: dict, result: dict) -> dict:
    return {"flagged_event": privacy.redact_event(event),
            "engine_result": {"risk_score": result["risk_score"], "decision": result["decision"],
                              "signals": [{"name": s["name"], "weight": s["weight"], "detail": s["detail"]}
                                          for s in result["signals"]]}}


def _openai_tools() -> list[dict]:
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                              "parameters": t["input_schema"]}} for t in TOOLS]


def _online_openai(event: dict, result: dict) -> dict:
    """Tool-calling loop for OpenAI-compatible APIs (Gemini free tier, Groq, OpenRouter, ...)."""
    messages = [{"role": "system", "content": prompts.AGENT},
                {"role": "user", "content": json.dumps(_task(event, result))}]
    trace = []
    msg = None
    for _ in range(6):
        resp = llm.client().chat.completions.create(model=llm.model(), tools=_openai_tools(), messages=messages)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            break
        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [{"id": tc.id, "type": "function",
                                         "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                                        for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            out = run_tool(tc.function.name, args)
            trace.append({"tool": tc.function.name, "args": args, "result": out})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(out)})
    final = llm.parse_json(msg.content or "")
    final.update(trace=trace, mode="llm_agent")
    return final


def _online_anthropic(event: dict, result: dict) -> dict:
    messages, trace = [{"role": "user", "content": json.dumps(_task(event, result))}], []
    for _ in range(6):
        resp = llm.client().messages.create(model=llm.model(), max_tokens=1200, system=prompts.AGENT,
                                            tools=TOOLS, messages=messages)
        if resp.stop_reason != "tool_use":
            break
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                out = run_tool(block.name, block.input)
                trace.append({"tool": block.name, "args": block.input, "result": out})
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(out)})
        messages.append({"role": "user", "content": results})
    final = llm.parse_json("".join(b.text for b in resp.content if b.type == "text"))
    final.update(trace=trace, mode="llm_agent")
    return final


def _offline(result: dict) -> dict:
    trace = []

    def call(name, args, why):
        out = run_tool(name, args)
        trace.append({"tool": name, "args": args, "why": why, "result": out})
        return out

    call("get_session_history", {"session_ref": result["session_ref"]}, "Reconstruct the session")
    call("get_user_baseline", {"user_ref": result["user_ref"]}, "Compare with normal behavior")
    call("check_geo_velocity", {"user_ref": result["user_ref"]}, "Check location plausibility")
    names = {s["name"] for s in result["signals"]}
    hits = call("search_playbooks", {"query": " ".join(sorted(names)).replace("_", " ")}, "Find the response playbook")

    if result["risk_score"] < 35:
        verdict = "benign"
    elif names & {"session_device_switch", "session_geo_switch"}:
        verdict = "likely_session_hijack"
    elif "bulk_export" in names:
        verdict = "possible_data_exfiltration"
    elif "impossible_travel" in names or {"new_device", "new_country"} <= names:
        verdict = "likely_account_takeover"
    else:
        verdict = "suspicious_needs_review"
    actions = {"block": ["Revoke the session", "Force password reset and re-verify via MFA", "Notify the account owner and security team"],
               "step_up": ["Require MFA step-up before completing the action", "Monitor the next actions in this session"],
               "allow": ["No action needed"]}[result["decision"]]
    detail = "; ".join(s["detail"] for s in sorted(result["signals"], key=lambda s: -s["weight"])[:3])
    return {"verdict": verdict, "confidence": round(min(0.95, 0.4 + result["risk_score"] / 200), 2),
            "summary": f"{verdict.replace('_', ' ').title()}. {detail or 'No risk signals.'}",
            "recommended_actions": actions, "playbook_refs": [h["id"] for h in hits], "trace": trace,
            "mode": "offline_planner"}
