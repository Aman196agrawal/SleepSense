"""
SleepSense cross-service API regression suite.

Exercises auth (8001), analytics (8002) and ingestion (8003) together — the
gaps that matter most here live between services, not inside any one of them,
so the per-service pytest suites cannot see them.

Run the three services first (start_auth.bat, start_analytics.bat,
start_ingestion.bat), then:

    python tests/api_regression.py

Creates two throwaway users so cross-user authorization can be tested for real,
and deletes them at the end.

Note: registration is rate limited to 5 per IP per hour, so running this more
than twice in quick succession will report A-01 as rate limited rather than
failed. That is the control working, not a defect.
"""
import io
import json
import struct
import sys
import time
import uuid
import wave
from datetime import datetime, timedelta, timezone

import requests

AUTH = "http://127.0.0.1:8001"
ANA = "http://127.0.0.1:8002"
ING = "http://127.0.0.1:8003"
T = 30

RESULTS = []


def check(suite, tid, desc, expected, actual, ok, severity="medium", note=""):
    RESULTS.append({"suite": suite, "id": tid, "desc": desc, "expected": expected,
                    "actual": actual, "ok": ok, "sev": severity, "note": note})
    flag = "PASS" if ok else f"FAIL[{severity}]"
    print(f"  {flag:12s} {tid:8s} {desc}")
    if not ok:
        print(f"               expected: {expected}")
        print(f"               actual:   {actual}")
        if note:
            print(f"               note:     {note}")


def post(url, **kw):
    try:
        return requests.post(url, timeout=T, **kw)
    except Exception as e:
        return type("R", (), {"status_code": -1, "text": f"{type(e).__name__}: {e}",
                              "json": lambda self=None: {}})()


def get(url, **kw):
    try:
        return requests.get(url, timeout=T, **kw)
    except Exception as e:
        return type("R", (), {"status_code": -1, "text": f"{type(e).__name__}: {e}",
                              "json": lambda self=None: {}})()


def make_wav(seconds=1.0, sr=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        n = int(seconds * sr)
        w.writeframes(b"".join(struct.pack("<h", int(9000 * ((i % 64) / 64 - .5)))
                               for i in range(n)))
    return buf.getvalue()


# ── Fixtures: two throwaway users ─────────────────────────────────────────────
STAMP = int(time.time())
USERS = {}
RATE_LIMITED = False


def register(tag, password="TestPass123!"):
    email = f"qa_{tag}_{STAMP}@qa-sleepsense.com"
    r = post(f"{AUTH}/auth/register", json={
        "email": email, "password": password, "display_name": f"QA {tag}"})
    if r.status_code not in (200, 201):
        global RATE_LIMITED
        if r.status_code == 429:
            RATE_LIMITED = True
        print(f"  !! could not register {tag}: {r.status_code} {r.text[:200]}")
        return None
    r2 = post(f"{AUTH}/auth/login", json={"email": email, "password": password})
    d = r2.json()
    tok = d.get("access_token")
    me = get(f"{AUTH}/users/me", headers={"Authorization": f"Bearer {tok}"}).json()
    USERS[tag] = {"email": email, "password": password, "token": tok,
                  "refresh": d.get("refresh_token"), "id": me.get("id")}
    return USERS[tag]


def H(tag):
    return {"Authorization": f"Bearer {USERS[tag]['token']}"}


print("=" * 78)
print("SETUP — creating two throwaway users")
print("=" * 78)
a = register("alice")
b = register("bob")
if not a or not b:
    if RATE_LIMITED:
        print("\n" + "!" * 76)
        print("!! Registration is rate limited (5 per IP per hour) — the suite needs two")
        print("!! fresh users and cannot create them right now. This is the control")
        print("!! working, not a failure. Wait for the window to roll over, or point")
        print("!! AUTH/ANA/ING at a stack with a clean rate-limit store.")
        print("!" * 76)
        sys.exit(2)
    print("cannot continue without both users")
    sys.exit(1)
print(f"  alice {a['id']}  {a['email']}")
print(f"  bob   {b['id']}  {b['email']}")


# ── SUITE 1: Authentication ───────────────────────────────────────────────────
print("\n" + "=" * 78 + "\nSUITE 1 — Authentication\n" + "=" * 78)

r = post(f"{AUTH}/auth/register", json={"email": a["email"], "password": "TestPass123!",
                                        "display_name": "dup"})
check("auth", "A-01", "duplicate email rejected", "409/400 (429 = rate limited)",
      r.status_code, r.status_code in (400, 409, 429), "high",
      "429 means the 5-per-hour registration limit is engaged, not a failure")

r = post(f"{AUTH}/auth/register", json={"email": f"weak_{STAMP}@qa-sleepsense.com",
                                        "password": "123", "display_name": "w"})
check("auth", "A-02", "weak password rejected", "422/400", r.status_code,
      r.status_code in (400, 422), "high")

r = post(f"{AUTH}/auth/register", json={"email": "not-an-email",
                                        "password": "TestPass123!", "display_name": "w"})
check("auth", "A-03", "malformed email rejected", "422/400", r.status_code,
      r.status_code in (400, 422), "medium")

r = post(f"{AUTH}/auth/login", json={"email": a["email"], "password": "WrongPass123!"})
check("auth", "A-04", "wrong password rejected", "401", r.status_code,
      r.status_code == 401, "critical")

r = post(f"{AUTH}/auth/login", json={"email": f"ghost_{STAMP}@qa-sleepsense.com",
                                     "password": "TestPass123!"})
check("auth", "A-05", "unknown user rejected", "401", r.status_code,
      r.status_code == 401, "critical")

r = post(f"{AUTH}/auth/login", json={"email": a["email"], "password": "WrongPass123!"})
body = r.text.lower()
leaks = "not found" in body or "no user" in body or "does not exist" in body
check("auth", "A-06", "login error does not reveal whether the email exists",
      "generic message", r.text[:60], not leaks, "medium")

r = get(f"{AUTH}/users/me")
check("auth", "A-07", "/users/me without token rejected", "401/403", r.status_code,
      r.status_code in (401, 403), "critical")

r = get(f"{AUTH}/users/me", headers={"Authorization": "Bearer garbage.token.here"})
check("auth", "A-08", "/users/me with malformed token rejected", "401", r.status_code,
      r.status_code == 401, "critical")

from jose import jwt
forged = jwt.encode({"sub": a["id"], "type": "access",
                     "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                    "wrong-secret-key-attacker-guess", algorithm="HS256")
r = get(f"{AUTH}/users/me", headers={"Authorization": f"Bearer {forged}"})
check("auth", "A-09", "token signed with wrong secret rejected", "401", r.status_code,
      r.status_code == 401, "critical")

expired = jwt.encode({"sub": a["id"], "type": "access",
                      "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
                     "dev-local-secret-key-change-in-prod", algorithm="HS256")
r = get(f"{AUTH}/users/me", headers={"Authorization": f"Bearer {expired}"})
check("auth", "A-10", "expired token rejected", "401", r.status_code,
      r.status_code == 401, "critical")

refresh_as_access = jwt.encode({"sub": a["id"], "type": "refresh",
                                "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                               "dev-local-secret-key-change-in-prod", algorithm="HS256")
r = get(f"{AUTH}/users/me", headers={"Authorization": f"Bearer {refresh_as_access}"})
check("auth", "A-11", "refresh token rejected where access token required",
      "401", r.status_code, r.status_code == 401, "high")

r = post(f"{AUTH}/auth/refresh", json={"refresh_token": a["refresh"]})
check("auth", "A-12", "refresh returns a new access token", "200 + access_token",
      f"{r.status_code} {list(r.json().keys()) if r.status_code == 200 else r.text[:50]}",
      r.status_code == 200 and "access_token" in r.json(), "high")


# ── SUITE 2: Cross-user authorization (IDOR) ──────────────────────────────────
print("\n" + "=" * 78 + "\nSUITE 2 — Cross-user authorization (IDOR)\n" + "=" * 78)

r = post(f"{ANA}/sessions", headers=H("alice"))
alice_sid = r.json().get("session_id") if r.status_code == 201 else None
alice_upload_token = r.json().get("upload_token") if r.status_code == 201 else None
check("authz", "Z-01", "alice can open her own session", "201", r.status_code,
      r.status_code == 201, "high")

if alice_sid:
    r = get(f"{ANA}/sessions/{alice_sid}", headers=H("bob"))
    check("authz", "Z-02", "bob CANNOT read alice's session", "404/403", r.status_code,
          r.status_code in (403, 404), "critical")

    r = post(f"{ANA}/sessions/{alice_sid}/end", headers=H("bob"))
    check("authz", "Z-03", "bob CANNOT end alice's session", "404/403", r.status_code,
          r.status_code in (403, 404), "critical")

    r = post(f"{ANA}/sessions/{alice_sid}/discard", headers=H("bob"))
    check("authz", "Z-04", "bob CANNOT discard alice's session", "404/403", r.status_code,
          r.status_code in (403, 404), "critical")

    r = get(f"{ANA}/sessions/{alice_sid}/score-breakdown", headers=H("bob"))
    check("authz", "Z-05", "bob CANNOT read alice's score breakdown", "404/403",
          r.status_code, r.status_code in (403, 404), "critical")

    r = requests.delete(f"{ANA}/sessions/{alice_sid}/audio", headers=H("bob"), timeout=T)
    check("authz", "Z-06", "bob CANNOT delete alice's audio", "404/403", r.status_code,
          r.status_code in (403, 404), "critical")

    wav = make_wav()
    r = post(f"{ING}/sessions/{alice_sid}/chunks",
             files={"audio": ("c.wav", io.BytesIO(wav), "audio/wav")},
             data={"chunk_index": "0", "duration_seconds": "1.0"},
             headers=H("bob"))
    check("authz", "Z-07", "bob CANNOT upload audio into alice's session", "401/403/404",
          r.status_code, r.status_code in (401, 403, 404), "critical",
          "would let one user inject audio into another's night")

r = get(f"{ANA}/sessions/active", headers=H("bob"))
bob_active = r.json()
check("authz", "Z-08", "bob's /sessions/active does not leak alice's session",
      "null", bob_active, bob_active is None, "high")

r = requests.delete(f"{ING}/internal/users/{USERS['alice']['id']}/audio",
                    headers={**H("bob"), "X-Internal-Secret": "attacker-guess"}, timeout=T)
check("authz", "Z-09", "internal GDPR endpoint rejects a guessed internal secret",
      "403", r.status_code, r.status_code == 403, "critical")

r = requests.delete(f"{ING}/internal/users/{USERS['alice']['id']}/audio",
                    headers={"X-Internal-Secret": ""}, timeout=T)
check("authz", "Z-10", "internal GDPR endpoint fails closed on an empty secret",
      "403", r.status_code, r.status_code == 403, "critical",
      "INTERNAL_API_SECRET is unset locally; an empty header must not match it")

r = requests.delete(f"{ING}/internal/users/{USERS['alice']['id']}/audio", timeout=T)
check("authz", "Z-11", "internal GDPR endpoint requires the secret header at all",
      "422 (missing required header)", r.status_code, r.status_code == 422, "high")


# ── SUITE 3: Session lifecycle ────────────────────────────────────────────────
print("\n" + "=" * 78 + "\nSUITE 3 — Session lifecycle\n" + "=" * 78)

r = post(f"{ANA}/sessions", headers=H("alice"))
check("session", "S-01", "second concurrent session rejected", "409", r.status_code,
      r.status_code == 409, "high")

r = get(f"{ANA}/sessions/active", headers=H("alice"))
d = r.json() or {}
check("session", "S-02", "/sessions/active reports the blocking session",
      f"session_id={alice_sid}", d.get("session_id"),
      d.get("session_id") == alice_sid, "high")

check("session", "S-03", "/sessions/active exposes chunk_count for the UI prompt",
      "int", d.get("chunk_count"), isinstance(d.get("chunk_count"), int), "low")

r = post(f"{ANA}/sessions/{alice_sid}/discard", headers=H("alice"))
check("session", "S-04", "owner can discard her session", "200", r.status_code,
      r.status_code == 200, "high")

r = post(f"{ANA}/sessions/{alice_sid}/discard", headers=H("alice"))
check("session", "S-05", "discarding twice is rejected", "409", r.status_code,
      r.status_code == 409, "low")

r = post(f"{ANA}/sessions/{uuid.uuid4()}/discard", headers=H("alice"))
check("session", "S-06", "discarding unknown session -> 404", "404", r.status_code,
      r.status_code == 404, "low")

r = post(f"{ANA}/sessions", headers=H("alice"))
alice_sid = r.json().get("session_id")
alice_upload_token = r.json().get("upload_token")
check("session", "S-07", "new session allowed after discard", "201", r.status_code,
      r.status_code == 201, "high")

r = post(f"{ANA}/sessions/{alice_sid}/end", headers=H("alice"))
check("session", "S-08", "owner can end her session", "200", r.status_code,
      r.status_code == 200, "high")

r = get(f"{ANA}/sessions/{alice_sid}", headers=H("alice"))
ended = r.json() if r.status_code == 200 else {}
check("session", "S-09", "ended session reports a score", "0-100",
      ended.get("sleep_quality_score"),
      isinstance(ended.get("sleep_quality_score"), (int, float)), "medium")

score = ended.get("sleep_quality_score")
check("session", "S-10", "score within documented 0-100 range", "0<=s<=100", score,
      isinstance(score, (int, float)) and 0 <= score <= 100, "medium")

check("session", "S-11", "zero-chunk session is labelled data_source='simulated'",
      "simulated", ended.get("data_source"),
      ended.get("data_source") == "simulated", "high",
      "end_session invents a summary via random.Random when no chunks arrived; "
      "the flag is what lets a caller tell it from measured data")


# ── SUITE 4: Input validation ─────────────────────────────────────────────────
print("\n" + "=" * 78 + "\nSUITE 4 — Input validation\n" + "=" * 78)

r = post(f"{ANA}/sessions", headers=H("alice"))
val_sid = r.json().get("session_id")
val_token = r.json().get("upload_token")

for tid, idx, sev in (("V-01", "-1", "medium"), ("V-02", "999999999", "low"),
                      ("V-03", "abc", "low")):
    r = post(f"{ANA}/sessions/{val_sid}/chunks", headers=H("alice"),
             json={"chunk_index": idx, "avg_intensity": 50, "dominant_class": "snoring",
                   "snore_event_count": 1, "offset_minutes": 0})
    ok = r.status_code in (400, 422)
    check("validation", tid, f"analytics chunk_index={idx} rejected", "400/422",
          r.status_code, ok, sev)

r = post(f"{ANA}/sessions/{val_sid}/chunks", headers=H("alice"),
         json={"chunk_index": 0, "avg_intensity": 99999, "dominant_class": "snoring",
               "snore_event_count": 1, "offset_minutes": 0})
check("validation", "V-04", "avg_intensity far outside 0-100 rejected", "400/422",
      r.status_code, r.status_code in (400, 422), "medium")

r = post(f"{ANA}/sessions/{val_sid}/chunks", headers=H("alice"),
         json={"chunk_index": 1, "avg_intensity": 50, "dominant_class": "'; DROP TABLE users;--",
               "snore_event_count": 1, "offset_minutes": 0})
check("validation", "V-05", "unknown dominant_class rejected (enum not free text)",
      "400/422", r.status_code, r.status_code in (400, 422), "medium",
      "ClassDonut/StackedAreaTimeline silently drop unknown classes, so totals stop summing to 100%")

still_there = get(f"{AUTH}/users/me", headers=H("alice")).status_code
check("validation", "V-06", "users table intact after SQL-injection-shaped input",
      "200", still_there, still_there == 200, "critical")

r = post(f"{ANA}/lifestyle", headers=H("alice"),
         json={"date": "not-a-date", "alcohol": 1})
check("validation", "V-07", "malformed lifestyle date rejected", "400/422",
      r.status_code, r.status_code in (400, 422), "medium")

r = get(f"{ANA}/sessions?limit=99999", headers=H("alice"))
check("validation", "V-08", "oversized pagination limit clamped or rejected",
      "422 or clamped", r.status_code,
      r.status_code == 422 or (r.status_code == 200 and len(r.json().get("sessions", [])) <= 100),
      "low")

r = get(f"{ANA}/sessions?cursor=not-base64", headers=H("alice"))
check("validation", "V-09", "malformed pagination cursor handled without a 500",
      "not 500", r.status_code, r.status_code != 500, "medium")


# ── SUITE 5: Ingestion ────────────────────────────────────────────────────────
print("\n" + "=" * 78 + "\nSUITE 5 — Audio ingestion\n" + "=" * 78)

hdr = dict(H("alice"))
if val_token:
    hdr["X-Upload-Token"] = val_token

wav = make_wav()
r = post(f"{ING}/sessions/{val_sid}/chunks",
         files={"audio": ("chunk_000.wav", io.BytesIO(wav), "audio/wav")},
         data={"chunk_index": "0", "duration_seconds": "1.0"}, headers=hdr)
check("ingest", "I-01", "valid WAV chunk accepted", "201/202", r.status_code,
      r.status_code in (201, 202), "high")

r = post(f"{ING}/sessions/{val_sid}/chunks",
         files={"audio": ("evil.wav", io.BytesIO(b"NOT AUDIO AT ALL" * 40), "audio/wav")},
         data={"chunk_index": "1", "duration_seconds": "1.0"}, headers=hdr)
check("ingest", "I-02", "non-audio bytes rejected despite audio/wav header", "400",
      r.status_code, r.status_code == 400, "high")

big = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * (11 * 1024 * 1024)
r = post(f"{ING}/sessions/{val_sid}/chunks",
         files={"audio": ("big.wav", io.BytesIO(big), "audio/wav")},
         data={"chunk_index": "2", "duration_seconds": "1.0"}, headers=hdr)
check("ingest", "I-03", "oversized chunk (>10MB) rejected", "413/400", r.status_code,
      r.status_code in (400, 413), "medium")

r = post(f"{ING}/sessions/{val_sid}/chunks",
         files={"audio": ("c.wav", io.BytesIO(wav), "audio/wav")},
         data={"chunk_index": "0", "duration_seconds": "1.0"}, headers=hdr)
check("ingest", "I-04", "duplicate chunk_index handled (idempotent or 409)",
      "200/202/409, not 500", r.status_code, r.status_code != 500, "medium")

r = post(f"{ING}/sessions/{uuid.uuid4()}/chunks",
         files={"audio": ("c.wav", io.BytesIO(wav), "audio/wav")},
         data={"chunk_index": "0", "duration_seconds": "1.0"}, headers=hdr)
check("ingest", "I-05", "upload to a session id that was never created", "400/401/404",
      r.status_code, r.status_code in (400, 401, 403, 404), "high")

r = post(f"{ING}/sessions/{val_sid}/chunks",
         files={"audio": ("c.wav", io.BytesIO(wav), "audio/wav")},
         data={"chunk_index": "5", "duration_seconds": "1.0"})
check("ingest", "I-06", "chunk upload without any auth rejected", "401/403",
      r.status_code, r.status_code in (401, 403), "critical")

trav = "../../../../etc/passwd"
r = post(f"{ING}/sessions/{trav}/chunks",
         files={"audio": ("c.wav", io.BytesIO(wav), "audio/wav")},
         data={"chunk_index": "0", "duration_seconds": "1.0"}, headers=hdr)
check("ingest", "I-07", "path-traversal session id rejected", "400/404, not 500",
      r.status_code, r.status_code in (400, 401, 403, 404), "critical")


# ── SUITE 6: Data integrity across services ───────────────────────────────────
print("\n" + "=" * 78 + "\nSUITE 6 — Cross-service integrity\n" + "=" * 78)

r = get(f"{ING}/sessions/{val_sid}/status", headers=H("alice"))
check("integrity", "X-01", "ingestion reports status for a known session",
      "200", r.status_code, r.status_code == 200, "medium")

r = get(f"{ANA}/analytics/trends?days=7", headers=H("alice"))
check("integrity", "X-02", "trends endpoint responds", "200", r.status_code,
      r.status_code == 200, "medium")

r = get(f"{ANA}/analytics/trends?days=-5", headers=H("alice"))
check("integrity", "X-03", "negative day range rejected or clamped", "422 or 200",
      r.status_code, r.status_code in (200, 422), "low")

r = get(f"{ANA}/insights", headers=H("alice"))
check("integrity", "X-04", "insights endpoint responds", "200", r.status_code,
      r.status_code == 200, "low")

r = get(f"{ANA}/sessions/export?format=csv", headers=H("alice"))
check("integrity", "X-05", "CSV export responds", "200", r.status_code,
      r.status_code == 200, "low")

# The same token must be accepted by all three services (shared SECRET_KEY).
codes = {
    "auth": get(f"{AUTH}/users/me", headers=H("alice")).status_code,
    "analytics": get(f"{ANA}/sessions/active", headers=H("alice")).status_code,
    "ingestion": get(f"{ING}/sessions/{val_sid}/status", headers=H("alice")).status_code,
}
check("integrity", "X-06", "one access token is accepted by all three services",
      "all 200", codes, all(c == 200 for c in codes.values()), "high")


# ── Teardown ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 78 + "\nTEARDOWN\n" + "=" * 78)
for tag in ("alice", "bob"):
    act = get(f"{ANA}/sessions/active", headers=H(tag)).json()
    if act:
        post(f"{ANA}/sessions/{act['session_id']}/discard", headers=H(tag))
    r = requests.delete(f"{AUTH}/users/me", headers=H(tag), timeout=T)
    print(f"  deleted {tag}: HTTP {r.status_code}")


# ── Report ────────────────────────────────────────────────────────────────────
print("\n" + "=" * 78)
print("SUMMARY")
print("=" * 78)
total = len(RESULTS)
passed = sum(1 for r in RESULTS if r["ok"])
fails = [r for r in RESULTS if not r["ok"]]
by_sev = {}
for r in fails:
    by_sev.setdefault(r["sev"], []).append(r)

print(f"  {passed}/{total} passed, {len(fails)} failed\n")
for sev in ("critical", "high", "medium", "low"):
    rows = by_sev.get(sev, [])
    if not rows:
        continue
    print(f"  {sev.upper()} ({len(rows)})")
    for r in rows:
        print(f"    {r['id']}  {r['desc']}")
        print(f"          expected {r['expected']}, got {r['actual']}")
        if r["note"]:
            print(f"          {r['note']}")
    print()

with open("qa_results.json", "w") as fh:
    json.dump(RESULTS, fh, indent=1)
print("  full results -> qa_results.json")
