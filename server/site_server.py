#!/usr/bin/env python3
"""سيرفر المباشر لموقع Fottballcia.
يحدّث live.json كل ~30 ثانية وقت المباريات، و today.json كل 10 دقائق،
ويقدمهما عبر HTTP (خلف Caddy للـ HTTPS). يحتاج فقط API_FOOTBALL_KEY."""
import json
import os
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KEY = os.environ.get("API_FOOTBALL_KEY", "")
DATA = os.environ.get("DATA_DIR", "/var/lib/fottballcia")
EVENTS_DIR = os.path.join(DATA, "events")
PORT = int(os.environ.get("PORT", "8080"))
INTERVAL = int(os.environ.get("LIVE_INTERVAL", "30"))
TZ = timezone(timedelta(hours=3))
LIVE = {"1H", "2H", "HT", "ET", "BT", "P", "LIVE", "INT"}
NOT_STARTED = {"NS", "TBD"}

if not KEY:
    sys.exit("API_FOOTBALL_KEY غير موجود")
os.makedirs(DATA, exist_ok=True)
os.makedirs(EVENTS_DIR, exist_ok=True)


def api(path, **params):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"https://v3.football.api-sports.io/{path}?{q}", headers={"x-apisports-key": KEY}
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        if r.status == 204:
            return []
        body = json.load(r)
    errs = body.get("errors")
    if errs:
        raise RuntimeError(str(errs))
    return body.get("response", [])


def events(raw_events, home_id=None, home_name=None):
    out = []
    for e in raw_events or []:
        if e.get("type") not in ("Goal", "Card", "Var"):
            continue
        team = e.get("team") or {}
        is_home = (home_id is not None and team.get("id") == home_id) or (home_id is None and home_name and team.get("name") == home_name)
        out.append({
            "m": (e.get("time") or {}).get("elapsed"),
            "x": (e.get("time") or {}).get("extra"),
            "s": "h" if is_home else "a",
            "t": e["type"],
            "d": e.get("detail") or "",
            "p": (e.get("player") or {}).get("name"),
        })
    return out


def slim(fx):
    st = fx["fixture"]["status"]
    return {
        "id": fx["fixture"]["id"],
        "league": f"{fx['league']['country']} - {fx['league']['name']}",
        "home": fx["teams"]["home"]["name"],
        "away": fx["teams"]["away"]["name"],
        "hl": fx["teams"]["home"].get("logo"),
        "al": fx["teams"]["away"].get("logo"),
        "gh": fx["goals"]["home"],
        "ga": fx["goals"]["away"],
        "status": st["short"],
        "minute": st.get("elapsed"),
        "time": fx["fixture"]["date"],
        "ev": events(fx.get("events") or [], home_id=fx["teams"]["home"]["id"], home_name=fx["teams"]["home"]["name"]),
    }


def write(name, matches):
    path = os.path.join(DATA, name)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(
            {"updated": datetime.now(TZ).isoformat(timespec="seconds"), "matches": matches},
            f, ensure_ascii=False,
        )
    os.replace(path + ".tmp", path)


def read(name):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f).get("matches", [])
    except Exception:
        return []


EVENT_LOCK = threading.Lock()

def event_cache_ttl(fixture_id):
    for match in read("live.json") + read("today.json"):
        if str(match.get("id")) == str(fixture_id):
            if match.get("status") in LIVE or match.get("status") in NOT_STARTED:
                return 60
            return 86400
    return 86400

def fixture_events(fixture_id, home_name):
    cache_path = os.path.join(EVENTS_DIR, str(fixture_id) + ".json")
    with EVENT_LOCK:
        now = time.time()
        cached = None
        try:
            with open(cache_path, encoding="utf-8") as f:
                cached = json.load(f)
        except (OSError, ValueError):
            pass
        if cached and now - float(cached.get("fetched_at", 0)) < event_cache_ttl(fixture_id):
            return events(cached.get("response", []), home_name=home_name)
        response = api("fixtures/events", fixture=fixture_id)
        tmp_path = cache_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump({"fetched_at": now, "response": response}, f, ensure_ascii=False)
        os.replace(tmp_path, cache_path)
        return events(response, home_name=home_name)


class Handler(BaseHTTPRequestHandler):
    def respond_json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        name = parsed.path.strip("/")
        if name == "events.json":
            query = urllib.parse.parse_qs(parsed.query)
            fixture_id = (query.get("fixture") or [""])[0]
            home_name = ((query.get("home") or [""])[0])[:160]
            if not fixture_id.isdigit() or len(fixture_id) > 12:
                self.respond_json(400, {"error": "invalid_fixture_id", "events": []})
                return
            try:
                result = fixture_events(fixture_id, home_name)
                self.respond_json(200, {"fixture": int(fixture_id), "events": result})
            except Exception as e:
                print("تعذر جلب أحداث المباراة:", e, flush=True)
                self.respond_json(502, {"error": "events_provider_unavailable"})
            return
        if name == "match.json":
            import match_center
            query = urllib.parse.parse_qs(parsed.query)
            code, payload = match_center.handle(api, DATA, (query.get("id") or [""])[0])
            self.respond_json(code, payload)
            return
        if name not in ("live.json", "today.json"):
            self.send_response(404)
            self.end_headers()
            return
        try:
            with open(os.path.join(DATA, name), "rb") as f:
                data = f.read()
        except FileNotFoundError:
            data = b'{"matches":[]}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def is_active(today, live):
    if live:
        return True
    now = datetime.now(timezone.utc)
    for m in today:
        if m["status"] in NOT_STARTED:
            try:
                start = datetime.fromisoformat(m["time"])
            except Exception:
                continue
            if start - timedelta(minutes=10) <= now <= start + timedelta(hours=3):
                return True
    return False


def main():
    threading.Thread(
        target=lambda: ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever(),
        daemon=True,
    ).start()
    print(f"يعمل على المنفذ {PORT}")
    last_today = 0
    live = read("live.json")
    while True:
        wait = 60
        try:
            if time.time() - last_today >= 600:
                date = datetime.now(TZ).strftime("%Y-%m-%d")
                fx = [slim(f) for f in api("fixtures", date=date, timezone="Asia/Riyadh")]
                fx.sort(key=lambda m: m["time"])
                write("today.json", fx)
                last_today = time.time()
            today = read("today.json")
            if is_active(today, live):
                live = [slim(f) for f in api("fixtures", live="all") if f["fixture"]["status"]["short"] in LIVE]
                write("live.json", live)
                wait = INTERVAL
            elif live:
                live = []
                write("live.json", live)
        except Exception as e:
            print("خطأ:", e, flush=True)
            wait = 120
        time.sleep(wait)


if __name__ == "__main__":
    main()
