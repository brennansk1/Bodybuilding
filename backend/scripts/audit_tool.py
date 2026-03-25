#!/usr/bin/env python3
"""
Coronado Audit Tool — CLI for testing and inspecting user data via API.
Usage: python audit_tool.py <command> [args]

Commands:
  login <username> <password>       — Authenticate and save token
  profile                           — Show user profile
  measurements                      — Show latest tape + skinfolds
  diagnostic                        — Run engine1 and show full diagnostic
  pds                               — Show PDS score + components
  muscle-gaps                       — Show muscle gap analysis
  weight-cap                        — Show weight cap + ghost model
  aesthetic-vector                  — Show aesthetic vector analysis
  symmetry                          — Show bilateral symmetry
  body-fat                          — Show body fat estimation details
  ari                               — Show ARI score
  prescription                      — Show nutrition prescription
  meal-plan                         — Show current meal plan
  volume                            — Show volume allocation
  split                             — Show optimal split
  phase                             — Show phase recommendation
  trajectory                        — Show PDS trajectory prediction
  all                               — Run everything and dump full audit
  raw <method> <path> [json_body]   — Raw API call (GET/POST)
"""
import sys
import json
import os
import urllib.request
import urllib.error

BASE = os.environ.get("CORONADO_API", "http://localhost:8000/api/v1")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), ".audit_token")


def _token():
    try:
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def _req(method: str, path: str, body=None):
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    tok = _token()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        print(f"HTTP {e.code}: {body_text}")
        return None


def get(path):
    return _req("GET", path)


def post(path, body=None):
    return _req("POST", path, body)


def pp(data, label=None):
    if label:
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")
    if data is None:
        print("  (no data)")
        return
    if isinstance(data, dict):
        print(json.dumps(data, indent=2, default=str))
    elif isinstance(data, list):
        print(json.dumps(data, indent=2, default=str))
    else:
        print(data)


def cmd_login(args):
    if len(args) < 2:
        print("Usage: login <username> <password>")
        return
    res = post("/auth/login", {"username": args[0], "password": args[1]})
    if res and "access_token" in res:
        with open(TOKEN_FILE, "w") as f:
            f.write(res["access_token"])
        print(f"Logged in as {args[0]}. Token saved.")
    else:
        print("Login failed:", res)


def cmd_profile(_):
    pp(get("/onboarding/profile"), "USER PROFILE")


def cmd_measurements(_):
    pp(get("/checkin/weekly/previous"), "LATEST MEASUREMENTS")


def cmd_diagnostic(_):
    print("Running Engine 1...")
    post("/engine1/run")
    pp(get("/engine1/diagnostic"), "FULL DIAGNOSTIC")


def cmd_pds(_):
    pp(get("/engine1/pds"), "PDS SCORE")


def cmd_muscle_gaps(_):
    pp(get("/engine1/muscle-gaps"), "MUSCLE GAPS")


def cmd_weight_cap(_):
    pp(get("/engine1/weight-cap"), "WEIGHT CAP")


def cmd_aesthetic(_):
    pp(get("/engine1/aesthetic-vector"), "AESTHETIC VECTOR")


def cmd_symmetry(_):
    pp(get("/engine1/symmetry"), "BILATERAL SYMMETRY")


def cmd_body_fat(_):
    d = get("/engine1/diagnostic")
    if d:
        pp(d.get("body_fat"), "BODY FAT")
    else:
        print("No diagnostic data")


def cmd_ari(_):
    pp(get("/engine2/ari"), "ARI SCORE")


def cmd_prescription(_):
    pp(get("/engine3/prescription/current"), "NUTRITION PRESCRIPTION")


def cmd_meal_plan(_):
    pp(get("/engine3/meal-plan/current"), "MEAL PLAN")


def cmd_volume(_):
    pp(get("/engine2/volume-allocation"), "VOLUME ALLOCATION")


def cmd_split(_):
    pp(get("/engine2/optimal-split"), "OPTIMAL SPLIT")


def cmd_phase(_):
    pp(get("/engine1/phase-recommendation"), "PHASE RECOMMENDATION")


def cmd_trajectory(_):
    pp(get("/engine1/pds/trajectory"), "PDS TRAJECTORY")


def cmd_all(_):
    print("="*60)
    print("  CORONADO COMPREHENSIVE AUDIT")
    print("="*60)
    cmd_profile(_)
    cmd_measurements(_)
    print("\nRunning Engine 1...")
    post("/engine1/run")
    cmd_pds(_)
    cmd_muscle_gaps(_)
    cmd_weight_cap(_)
    cmd_aesthetic(_)
    cmd_symmetry(_)
    cmd_body_fat(_)
    cmd_phase(_)
    cmd_trajectory(_)
    cmd_ari(_)
    cmd_volume(_)
    cmd_prescription(_)
    cmd_meal_plan(_)


def cmd_raw(args):
    if len(args) < 2:
        print("Usage: raw <GET|POST> <path> [json_body]")
        return
    method = args[0].upper()
    path = args[1]
    body = json.loads(args[2]) if len(args) > 2 else None
    pp(_req(method, path, body), f"{method} {path}")


COMMANDS = {
    "login": cmd_login,
    "profile": cmd_profile,
    "measurements": cmd_measurements,
    "diagnostic": cmd_diagnostic,
    "pds": cmd_pds,
    "muscle-gaps": cmd_muscle_gaps,
    "weight-cap": cmd_weight_cap,
    "aesthetic-vector": cmd_aesthetic,
    "symmetry": cmd_symmetry,
    "body-fat": cmd_body_fat,
    "ari": cmd_ari,
    "prescription": cmd_prescription,
    "meal-plan": cmd_meal_plan,
    "volume": cmd_volume,
    "split": cmd_split,
    "phase": cmd_phase,
    "trajectory": cmd_trajectory,
    "all": cmd_all,
    "raw": cmd_raw,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    COMMANDS[sys.argv[1]](sys.argv[2:])
