"""In-memory store (swap for Redis/Postgres in production)."""
HISTORY: dict[str, list[dict]] = {}
BASELINES: dict[str, dict] = {}
DECISIONS: list[dict] = []


def reset():
    HISTORY.clear(); BASELINES.clear(); DECISIONS.clear()


def seed(user_id: str, baseline: dict, prior: list[dict]):
    BASELINES[user_id] = baseline
    HISTORY.setdefault(user_id, []).extend(prior)


def history(user_id: str) -> list[dict]:
    return HISTORY.get(user_id, [])


def record(event: dict, result: dict):
    HISTORY.setdefault(event["user_id"], []).append(event)
    DECISIONS.append(result)


def all_events() -> list[dict]:
    return [e for events in HISTORY.values() for e in events]
