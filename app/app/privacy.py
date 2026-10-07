"""Privacy-first layer: raw identifiers never reach the LLM, only stable pseudonymous refs."""
from __future__ import annotations

import hashlib

_REVERSE: dict[str, str] = {}


def _ref(prefix: str, value: str) -> str:
    ref = f"{prefix}_{hashlib.sha256(value.encode()).hexdigest()[:8]}"
    _REVERSE[ref] = value
    return ref


def user_ref(user_id): return _ref("user", user_id)
def session_ref(session_id): return _ref("sess", session_id)
def device_ref(device_id): return _ref("dev", device_id)
def resolve(ref: str):
    return _REVERSE.get(ref)


def redact_event(e: dict) -> dict:
    """What the LLM is allowed to see: no IPs, emails, user agents or exact coordinates."""
    out = {
        "user_ref": user_ref(e["user_id"]),
        "session_ref": session_ref(e["session_id"]),
        "device_ref": device_ref(e["device_id"]),
        "ts": e["ts"],
        "action": e["action"],
        "country": e["country"],
    }
    for k in ("amount", "rows"):
        if k in e:
            out[k] = e[k]
    return out


def redact_baseline(b: dict) -> dict:
    return {
        "device_refs": [device_ref(d) for d in b["devices"]],
        "countries": b["countries"],
        "active_hours": list(b["active_hours"]),
        "avg_export_rows": b["avg_export_rows"],
        "avg_payment": b["avg_payment"],
    }
