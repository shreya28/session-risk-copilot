"""Run: python -m pytest -q   (or: python tests/test_engine.py)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.pop("ANTHROPIC_API_KEY", None)

from app import rag, service, store


def decisions(name):
    return [r["result"]["decision"] for r in service.run_scenario(name)]


def test_normal_is_allowed():
    assert set(decisions("normal")) == {"allow"}


def test_account_takeover_blocked():
    assert "block" in decisions("account_takeover")


def test_impossible_travel_step_up():
    assert "step_up" in decisions("impossible_travel")


def test_session_hijack_blocked_at_role_change():
    assert decisions("session_hijack")[-1] == "block"


def test_mass_export_blocked():
    assert decisions("mass_export")[-1] == "block"


def test_rag_finds_right_playbook():
    assert rag.get_kb().search("session token used from different device")[0]["id"].startswith("session_hijacking")


def test_offline_agent_investigates():
    run = service.run_scenario("session_hijack")[-1]
    out = service.investigate(run["event"], run["result"])
    assert out["verdict"] == "likely_session_hijack" and len(out["trace"]) == 4


def test_llm_never_sees_raw_identifiers():
    from app import privacy
    e = service.run_scenario("normal")[0]["event"]
    blob = str(privacy.redact_event(e))
    assert e["ip"] not in blob and e["user_id"] not in blob and "user_agent" not in blob


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("PASS", n)
