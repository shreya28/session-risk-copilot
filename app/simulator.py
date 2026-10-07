"""Attack scenario simulator: generates realistic session event streams."""
USER = "u_1001"
BASELINE = {
    "devices": ["dev-macbook-1"],
    "countries": ["IN"],
    "active_hours": (8, 23),
    "avg_export_rows": 200,
    "avg_payment": 150,
}
CHENNAI = ("49.37.12.8", "IN", 13.08, 80.27)
MOSCOW = ("95.24.18.3", "RU", 55.75, 37.62)
LONDON = ("81.2.69.1", "GB", 51.51, -0.13)
D = "2026-10-07T"


def ev(session, t, action, place, device="dev-macbook-1", **extra):
    ip, country, lat, lon = place
    return {"user_id": USER, "session_id": session, "ts": f"{D}{t}", "action": action, "ip": ip,
            "country": country, "lat": lat, "lon": lon, "device_id": device,
            "user_agent": "Mozilla/5.0", **extra}


SCENARIOS = {
    "normal": {
        "title": "Normal user session",
        "description": "Known device, usual city, ordinary payment.",
        "prior": [ev("s0", "09:00:00", "login", CHENNAI)],
        "events": [ev("s1", "14:00:00", "login", CHENNAI), ev("s1", "14:02:00", "view_page", CHENNAI),
                   ev("s1", "14:06:00", "payment", CHENNAI, amount=120)],
    },
    "account_takeover": {
        "title": "Account takeover",
        "description": "Login from a new device in Russia at 3am, instant password change, then a large payment.",
        "prior": [ev("s0", "01:30:00", "login", CHENNAI)],
        "events": [ev("s9", "03:05:00", "login", MOSCOW, device="dev-unknown-55"),
                   ev("s9", "03:05:40", "password_change", MOSCOW, device="dev-unknown-55"),
                   ev("s9", "03:07:00", "payment", MOSCOW, device="dev-unknown-55", amount=2000)],
    },
    "impossible_travel": {
        "title": "Impossible travel",
        "description": "Login in Chennai, then a session from London 25 minutes later (stolen credentials or VPN).",
        "prior": [],
        "events": [ev("s1", "13:00:00", "login", CHENNAI), ev("s2", "13:25:00", "login", LONDON),
                   ev("s2", "13:26:00", "data_export", LONDON, rows=180)],
    },
    "session_hijack": {
        "title": "Session hijack",
        "description": "Same session token suddenly used from a different device to change a user's role.",
        "prior": [],
        "events": [ev("s1", "09:00:00", "login", CHENNAI), ev("s1", "09:05:00", "view_page", CHENNAI),
                   ev("s1", "09:12:00", "role_change", CHENNAI, device="dev-unknown-77")],
    },
    "mass_export": {
        "title": "Mass data export",
        "description": "Right after login, the user exports 50,000 rows (typical is ~200).",
        "prior": [],
        "events": [ev("s1", "10:00:00", "login", CHENNAI), ev("s1", "10:00:45", "data_export", CHENNAI, rows=50000)],
    },
}
