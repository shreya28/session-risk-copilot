"""Developer-first REST API.  Run: uvicorn app.main:app --reload"""
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from . import service, simulator

app = FastAPI(title="Session Risk Copilot API", version="1.0")


class ActionEvent(BaseModel):
    user_id: str
    session_id: str
    ts: str
    action: str
    ip: str
    country: str
    device_id: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    user_agent: Optional[str] = None
    amount: Optional[float] = None
    rows: Optional[int] = None


class Question(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/v1/evaluate-action")
def evaluate(e: ActionEvent):
    return service.evaluate_action(e.model_dump(exclude_none=True))


@app.post("/v1/investigate")
def investigate(e: ActionEvent):
    ev = e.model_dump(exclude_none=True)
    res = service.evaluate_action(ev)
    return {"evaluation": res, "investigation": service.investigate(ev, res)}


@app.post("/v1/analyst")
def analyst(q: Question):
    return service.analyst(q.question)


@app.get("/v1/scenarios")
def scenarios():
    return {k: {"title": v["title"], "description": v["description"]} for k, v in simulator.SCENARIOS.items()}


@app.post("/v1/scenarios/{name}/run")
def run(name: str):
    return service.run_scenario(name)
