"""Tests the LLM paths with fake clients (no network, no keys needed)."""
import json, os, sys
from types import SimpleNamespace as NS
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import llm, service


def _fake_openai(responses):
    calls = iter(responses)
    create = lambda **kw: next(calls)
    return NS(chat=NS(completions=NS(create=create)))


def _setup(monkeypatch_env=True):
    for k in ("ANTHROPIC_API_KEY", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        os.environ.pop(k, None)
    os.environ["GEMINI_API_KEY"] = "fake"
    llm._cache.clear()


def test_provider_selection():
    _setup()
    assert llm.provider() == "openai" and "Gemini" in llm.label()
    os.environ.pop("GEMINI_API_KEY"); os.environ["ANTHROPIC_API_KEY"] = "x"
    assert llm.provider() == "anthropic"
    os.environ.pop("ANTHROPIC_API_KEY")
    assert llm.provider() is None and not llm.llm_available()


def test_explain_with_openai_client():
    _setup()
    msg = NS(choices=[NS(message=NS(content='```json\n{"explanation": "Blocked: new device."}\n```', tool_calls=None))])
    llm._cache["openai"] = _fake_openai([msg])
    run = service.run_scenario("session_hijack")
    assert run[-1]["result"]["llm_used"] is True
    assert "Blocked" in run[-1]["result"]["explanation"]


def _scenario_offline(name):
    for k in ("GEMINI_API_KEY", "LLM_API_KEY", "ANTHROPIC_API_KEY"):
        os.environ.pop(k, None)
    llm._cache.clear()
    return service.run_scenario(name)


def test_agent_tool_loop_with_openai_client():
    run = _scenario_offline("session_hijack")
    _setup()
    last = run[-1]
    tc = NS(id="call_1", function=NS(name="get_session_history",
                                      arguments=json.dumps({"session_ref": last["result"]["session_ref"]})))
    step1 = NS(choices=[NS(message=NS(content=None, tool_calls=[tc]))])
    final = {"verdict": "likely_session_hijack", "confidence": 0.9, "summary": "ok",
             "recommended_actions": ["Revoke session"], "playbook_refs": ["session_hijacking#1"]}
    step2 = NS(choices=[NS(message=NS(content=json.dumps(final), tool_calls=None))])
    llm._cache["openai"] = _fake_openai([step1, step2])
    out = service.investigate(last["event"], last["result"])
    assert out["mode"] == "llm_agent" and out["trace"][0]["tool"] == "get_session_history"
    assert len(out["trace"][0]["result"]) == 3


def test_failure_falls_back_to_offline():
    run = _scenario_offline("session_hijack")
    _setup()
    llm._cache["openai"] = _fake_openai([])  # next() raises StopIteration -> exception path
    out = service.investigate(run[-1]["event"], run[-1]["result"])
    assert out["mode"] == "offline_planner" and "failed" in out["note"]


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("PASS", n)
    for k in ("GEMINI_API_KEY",): os.environ.pop(k, None)
