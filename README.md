# 🛡️ Session Risk Copilot

An AI layer for **continuous, post-login session security**. Authentication checks who you are at login; this project watches what happens *after* login and decides, in real time, whether a sensitive action (payment, data export, role change, account recovery) should be **allowed, challenged with MFA, or blocked**. An LLM then explains the decision, and a tool-using agent investigates flagged sessions using RAG over security playbooks.

> Inspired by the continuous session security problem space. Built as a learning project, not a production security product.

**Live demo:** _add link_ · **Demo GIF:** _add gif_

## Architecture

```
session event
   │
   ▼
privacy.py ── pseudonymous refs only (no raw IP / email / UA to the LLM)
   │
   ▼
risk_engine.py ── deterministic signals + score ──► allow | step_up | block
   │
   ├─► llm.py      LLM explanation (prompt-engineered, JSON output)
   ├─► agent.py    Claude tool-use agent ─► get_session_history, get_user_baseline,
   │                                         check_geo_velocity, search_playbooks (RAG)
   └─► rag.py      TF-IDF retrieval over knowledge/*.md playbooks
```

## What it demonstrates

| Skill | Implementation |
|---|---|
| LLM applications | Explainer, investigation agent, analyst chat, REST API + Streamlit UI |
| Prompt engineering | Role, hard rules, grounding, strict JSON schema, few-shot example (`app/prompts.py`) |
| RAG | Chunked playbooks ranked by TF-IDF cosine, cited by chunk id (`app/rag.py`) |
| AI agents | Tool-calling loop with 4 tools and a bounded step budget (`app/agent.py`) |
| Automation | Event → decision → explanation → recommended response, no manual steps |
| Security design | LLM explains but never decides; tool results treated as untrusted data; privacy-first redaction |

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env            # optional: add ANTHROPIC_API_KEY
export ANTHROPIC_API_KEY=...    # without a key the app runs in offline demo mode
streamlit run streamlit_app.py  # UI
uvicorn app.main:app --reload   # API (docs at /docs)
python -m pytest -q             # tests
```

Example API call:

```bash
curl -X POST localhost:8000/v1/evaluate-action -H 'content-type: application/json' -d '{
  "user_id":"u_1","session_id":"s_1","ts":"2026-10-07T03:05:00","action":"payment",
  "ip":"95.24.18.3","country":"RU","device_id":"new-device","amount":2000}'
```

## Deploy (free)

Push to GitHub → [Streamlit Community Cloud](https://streamlit.io/cloud) → select `streamlit_app.py` → add `ANTHROPIC_API_KEY` under Secrets.

## Limitations and next steps

- Rule-based scoring with hand-set weights; a real system would learn per-user baselines.
- In-memory store; production would use Redis/Postgres.
- TF-IDF retrieval; could upgrade to embeddings + a vector DB.
- Add behavioral biometrics (typing cadence), evals for the explainer, and prompt-injection tests.
