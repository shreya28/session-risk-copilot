"""Deterministic risk engine. The LLM never makes the decision; it only explains it."""
from __future__ import annotations

from datetime import datetime
from math import asin, cos, radians, sin, sqrt

SENSITIVE = {
    "payment": 15,
    "data_export": 20,
    "role_change": 25,
    "password_change": 20,
    "email_change": 20,
    "account_recovery": 25,
}
CREDENTIAL_CHANGES = {"password_change", "email_change", "account_recovery"}
STEP_UP_AT = 35
BLOCK_AT = 70

DEFAULT_BASELINE = {
    "devices": [],
    "countries": [],
    "active_hours": (8, 23),
    "avg_export_rows": 200,
    "avg_payment": 150,
}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = radians(lat1), radians(lat2)
    dphi, dl = p2 - p1, radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def _ts(e) -> datetime:
    return datetime.fromisoformat(e["ts"])


def decide(score: int) -> str:
    if score >= BLOCK_AT:
        return "block"
    if score >= STEP_UP_AT:
        return "step_up"
    return "allow"


def evaluate(event: dict, history: list[dict], baseline: dict) -> dict:
    """Score one event given the user's history (oldest first) and baseline."""
    signals: list[dict] = []

    def add(name, weight, detail):
        signals.append({"name": name, "weight": weight, "detail": detail})

    action = event["action"]
    session_events = [e for e in history if e["session_id"] == event["session_id"]]

    if action in SENSITIVE:
        add("sensitive_action", SENSITIVE[action], f"'{action}' is a high-risk action")
    if event["device_id"] not in baseline["devices"]:
        add("new_device", 20, "Device has never been seen for this user")
    if event["country"] not in baseline["countries"]:
        add("new_country", 20, f"Country {event['country']} is outside the user's normal locations")

    prev = history[-1] if history else None
    if prev and None not in (prev.get("lat"), prev.get("lon"), event.get("lat"), event.get("lon")):
        hours = (_ts(event) - _ts(prev)).total_seconds() / 3600
        km = haversine_km(prev["lat"], prev["lon"], event["lat"], event["lon"])
        if hours > 0 and km > 300:
            speed = km / hours
            msg = f"{km:.0f} km from {prev['country']} to {event['country']} in {hours * 60:.0f} min (~{speed:.0f} km/h)"
            if speed > 900:
                add("impossible_travel", 40, msg)
            elif speed > 500:
                add("fast_travel", 20, msg)

    if session_events:
        first = session_events[0]
        if first["device_id"] != event["device_id"]:
            add("session_device_switch", 45, "Device changed in the middle of an existing session")
        elif first["country"] != event["country"]:
            add("session_geo_switch", 35, "Country changed in the middle of an existing session")

    start, end = baseline["active_hours"]
    if not start <= _ts(event).hour <= end:
        add("unusual_hour", 10, f"Activity at {_ts(event):%H:%M}, outside the user's usual hours")

    login = next((e for e in session_events if e["action"] == "login"), None)
    if login and action in SENSITIVE:
        secs = (_ts(event) - _ts(login)).total_seconds()
        if secs < 120:
            add("rapid_sensitive_action", 15, f"Sensitive action only {secs:.0f}s after login")

    if action == "data_export" and event.get("rows", 0) > 5 * baseline["avg_export_rows"]:
        add("bulk_export", 35, f"Exporting {event['rows']} rows vs a normal ~{baseline['avg_export_rows']}")
    if action == "payment" and event.get("amount", 0) > 5 * baseline["avg_payment"]:
        add("large_payment", 25, f"Payment of {event['amount']} vs a normal ~{baseline['avg_payment']}")

    if action in {"payment", "data_export", "role_change"} and any(
        e["action"] in CREDENTIAL_CHANGES for e in session_events
    ):
        add("credential_change_then_sensitive", 25, "Credentials were changed earlier in this session")

    score = min(100, sum(s["weight"] for s in signals))
    return {"risk_score": score, "decision": decide(score), "signals": signals, "action": action, "ts": event["ts"]}
