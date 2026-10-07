import os

import pandas as pd
import streamlit as st

try:  # Streamlit Cloud secrets -> env vars
    for k in ("GEMINI_API_KEY", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "ANTHROPIC_API_KEY"):
        if k in st.secrets:
            os.environ.setdefault(k, st.secrets[k])
except Exception:
    pass

from app import llm, privacy, service, simulator

st.set_page_config(page_title="Session Risk Copilot", page_icon="🛡️", layout="wide")
st.title("🛡️ Session Risk Copilot")
st.caption("Continuous post-login session security: deterministic risk engine + LLM explainer + RAG playbooks + investigation agent.")

if llm.llm_available():
    st.success(f"Live LLM mode: {llm.label()}")
else:
    st.info("Offline demo mode: add GEMINI_API_KEY (free) to enable the LLM explainer, agent and analyst chat.")

tab1, tab2, tab3 = st.tabs(["Attack simulator", "Analyst chat (RAG)", "How it works"])

with tab1:
    names = list(simulator.SCENARIOS)
    name = st.selectbox("Scenario", names, format_func=lambda n: simulator.SCENARIOS[n]["title"])
    st.write(simulator.SCENARIOS[name]["description"])
    if st.button("▶ Run scenario", type="primary"):
        st.session_state.run = service.run_scenario(name)
        st.session_state.inv = {}

    run = st.session_state.get("run")
    if run:
        icon = {"allow": "🟢", "step_up": "🟠", "block": "🔴"}
        st.dataframe(pd.DataFrame([{
            "time": r["event"]["ts"][11:], "action": r["event"]["action"], "country": r["event"]["country"],
            "device": r["event"]["device_id"], "risk": r["result"]["risk_score"],
            "decision": f"{icon[r['result']['decision']]} {r['result']['decision']}"} for r in run]),
            use_container_width=True, hide_index=True)

        i = st.selectbox("Inspect event", range(len(run)),
                         index=max(range(len(run)), key=lambda j: run[j]["result"]["risk_score"]),
                         format_func=lambda j: f"{run[j]['event']['ts'][11:]}  {run[j]['event']['action']}")
        ev, res = run[i]["event"], run[i]["result"]
        c1, c2 = st.columns([1, 2])
        c1.metric("Risk score", res["risk_score"], res["decision"].upper(), delta_color="off")
        c2.markdown(f"**Explanation** {'(LLM)' if res['llm_used'] else '(template)'}\n\n{res['explanation']}")
        if res["signals"]:
            st.dataframe(pd.DataFrame(res["signals"]), use_container_width=True, hide_index=True)
        with st.expander("🔒 What the LLM actually sees (redacted payload)"):
            st.json(privacy.redact_event(ev))

        if st.button("🕵️ Investigate with AI agent"):
            with st.spinner("Agent investigating..."):
                st.session_state.inv[i] = service.investigate(ev, res)
        inv = st.session_state.get("inv", {}).get(i)
        if inv:
            st.subheader(f"Verdict: {inv['verdict'].replace('_', ' ')}  (confidence {inv['confidence']})")
            st.caption(f"Mode: {inv['mode']}" + (f" - {inv['note']}" if inv.get("note") else ""))
            st.write(inv["summary"])
            st.markdown("**Recommended actions**\n" + "\n".join(f"- {a}" for a in inv["recommended_actions"]))
            st.markdown("**Playbooks used (RAG):** " + ", ".join(inv.get("playbook_refs", [])))
            for t in inv["trace"]:
                with st.expander(f"🔧 Tool call: {t['tool']}"):
                    st.json({"args": t["args"], "result": t["result"]})

with tab2:
    st.write("Ask about response procedures or recent flagged sessions. Answers are grounded in the playbooks via RAG.")
    st.session_state.setdefault("chat", [])
    for m in st.session_state.chat:
        with st.chat_message(m["role"]):
            st.write(m["text"])
    if q := st.chat_input("e.g. How should I respond to a bulk export right after login?"):
        st.session_state.chat.append({"role": "user", "text": q})
        a = service.analyst(q)
        st.session_state.chat.append({"role": "assistant", "text": a["answer"] + f"\n\nSources: {', '.join(a['sources'])}"})
        st.rerun()

with tab3:
    st.markdown("""
**Pipeline:** event → privacy redaction → deterministic risk engine → decision (allow / step-up / block) → LLM explanation → agent investigation → RAG playbooks.

| Concept | Where |
|---|---|
| LLM application | Explainer, agent and analyst chat (`app/llm.py`, `app/service.py`) |
| Prompt engineering | Role, hard rules, grounding, strict JSON schema, few-shot (`app/prompts.py`) |
| RAG | TF-IDF retrieval over security playbooks (`app/rag.py`, `knowledge/`) |
| AI agent | Claude tool use with 4 tools and a reasoning loop (`app/agent.py`) |
| Automation | Event → decision → explanation → recommended actions with no manual steps |
| Privacy-first | Pseudonymous refs only; raw IPs and IDs never reach the LLM (`app/privacy.py`) |
| Safety design | The LLM explains but never decides; tool output treated as data |
""")
