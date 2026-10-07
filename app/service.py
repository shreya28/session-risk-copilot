"""Application service layer shared by the FastAPI API and the Streamlit UI."""
from __future__ import annotations

import json

from . import agent, llm, privacy, prompts, rag, risk_engine, simulator, store


def evaluate_action(event: dict, explain: bool = True) -> dict:
    baseline = store.BASELINES.get(event["user_id"], risk_engine.DEFAULT_BASELINE)
    result = risk_engine.evaluate(event, store.history(event["user_id"]), baseline)
    result["user_ref"] = privacy.user_ref(event["user_id"])
    result["session_ref"] = privacy.session_ref(event["session_id"])
    if explain and result["decision"] != "allow":
        result["explanation"], result["llm_used"] = llm.explain(privacy.redact_event(event), result)
    else:
        result["explanation"], result["llm_used"] = llm.template_explanation(result), False
    store.record(event, result)
    return result


def investigate(event: dict, result: dict) -> dict:
    return agent.investigate(event, result)


def run_scenario(name: str) -> list[dict]:
    sc = simulator.SCENARIOS[name]
    store.reset()
    store.seed(simulator.USER, simulator.BASELINE, sc["prior"])
    return [{"event": e, "result": evaluate_action(e)} for e in sc["events"]]


def analyst(question: str) -> dict:
    hits = rag.get_kb().search(question, 3)
    flagged = [{"action": d["action"], "ts": d["ts"], "score": d["risk_score"], "decision": d["decision"],
                "signals": [s["name"] for s in d["signals"]]} for d in store.DECISIONS if d["decision"] != "allow"][-10:]
    if llm.client() is None:
        text = (f"[offline] Best playbook match: {hits[0]['heading']} [{hits[0]['id']}]\n\n{hits[0]['text'][:500]}"
                if hits else "No matching playbook found.")
        return {"answer": text, "sources": [h["id"] for h in hits], "llm_used": False}
    ctx = {"PLAYBOOK EXCERPTS": [{"id": h["id"], "text": h["text"]} for h in hits], "RECENT DECISIONS": flagged}
    try:
        return {"answer": llm.complete(prompts.ANALYST, f"{json.dumps(ctx)}\n\nQuestion: {question}", 500),
                "sources": [h["id"] for h in hits], "llm_used": True}
    except Exception as exc:
        return {"answer": f"LLM call failed ({type(exc).__name__}).", "sources": [], "llm_used": False}
