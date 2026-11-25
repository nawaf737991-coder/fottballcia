"""مركز المباراة: يجمع بيانات مباراة واحدة من API-Football مع تخزين مؤقت ذكي.
يُستورد من site_server.py ويخدم GET /match.json?id=FIXTURE_ID
المفتاح يبقى على السيرفر فقط."""
import json
import os
import re
import threading
import time
from datetime import datetime, timedelta, timezone

LIVE = {"1H", "2H", "HT", "ET", "BT", "P", "LIVE", "INT"}
NOT_STARTED = {"NS", "TBD"}
DONE = {"FT", "AET", "PEN", "AWD", "WO"}
WOMEN = re.compile(r"women|femenin|feminin|frauen|femmes|ladies|\bw\b|\(w\)|نساء|سيدات", re.I)
LOCK = threading.Lock()
DAILY = {"day": "", "n": 0}
MAX_NEW_PER_DAY = 600  # حماية لحصة API-Football من الزحف


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, path)


def _cached(dirpath, name, ttl, loader):
    os.makedirs(dirpath, exist_ok=True)
    path = os.path.join(dirpath, name + ".json")
    c = _read(path)
    if c and time.time() - c.get("t", 0) < ttl:
        return c["d"]
    try:
        d = loader()
    except Exception:
        if c:
            return c["d"]
        raise
    _write(path, {"t": time.time(), "d": d})
    return d


def _team(t):
    return {"id": t.get("id"), "name": t.get("name"), "logo": t.get("logo")}


def _stat_val(v):
    if v is None:
        return 0
    if isinstance(v, str) and v.endswith("%"):
        try:
            return float(v[:-1])
        except ValueError:
            return 0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0


def build(api, data_dir, fid):
    base = os.path.join(data_dir, "match")
    st = {"s": ""}

    def core():
        r = api("fixtures", id=fid)
        if not r:
            raise KeyError("not_found")
        return r[0]

    # أولًا: نحتاج الحالة لنعرف مدة التخزين
    path = os.path.join(base, f"{fid}.json")
    c = _read(path)
    ttl = 3600
    if c:
        s = c["d"]["fixture"]["status"]["short"]
        ttl = 25 if s in LIVE else (600 if s in NOT_STARTED else 3600)
    fx = _cached(base, str(fid), ttl, core)
    f, lg, tm = fx["fixture"], fx["league"], fx["teams"]
    status = f["status"]["short"]
    if WOMEN.search(" ".join([tm["home"]["name"] or "", tm["away"]["name"] or "", lg.get("name") or ""])):
        raise KeyError("women")
    hid, aid = tm["home"]["id"], tm["away"]["id"]
    upcoming = status in NOT_STARTED

    out = {
        "id": f["id"], "status": status, "elapsed": f["status"].get("elapsed"), "extra": f["status"].get("extra"),
        "label": f["status"].get("long"), "kickoff": f["date"], "venue": (f.get("venue") or {}).get("name"),
        "city": (f.get("venue") or {}).get("city"), "referee": f.get("referee"),
        "league": {"id": lg["id"], "name": lg["name"], "logo": lg.get("logo"), "round": lg.get("round"),
                   "season": lg.get("season"), "country": lg.get("country")},
        "home": _team(tm["home"]), "away": _team(tm["away"]),
        "goals": fx.get("goals"), "score": fx.get("score"),
    }
    ev = []
    for e in fx.get("events") or []:
        ev.append({"m": (e.get("time") or {}).get("elapsed"), "x": (e.get("time") or {}).get("extra"),
                   "team": (e.get("team") or {}).get("id"), "type": e.get("type"), "detail": e.get("detail"),
                   "p": (e.get("player") or {}).get("name"), "a": (e.get("assist") or {}).get("name"),
                   "comments": e.get("comments")})
    out["events"] = ev
    lu = []
    for l in fx.get("lineups") or []:
        def pl(x):
            p = x.get("player") or {}
            return {"id": p.get("id"), "n": p.get("name"), "num": p.get("number"), "pos": p.get("pos"), "grid": p.get("grid")}
        lu.append({"team": (l.get("team") or {}).get("id"), "formation": l.get("formation"),
                   "coach": (l.get("coach") or {}).get("name"),
                   "xi": [pl(x) for x in l.get("startXI") or []], "subs": [pl(x) for x in l.get("substitutes") or []]})
    out["lineups"] = lu
    stats = {}
    for s in fx.get("statistics") or []:
        side = "h" if (s.get("team") or {}).get("id") == hid else "a"
        for it in s.get("statistics") or []:
            stats.setdefault(it["type"], {})[side] = _stat_val(it.get("value"))
    out["stats"] = [{"t": k, "h": v.get("h", 0), "a": v.get("a", 0)} for k, v in stats.items()]
    # من وإلى: تقييمات اللاعبين (أرقام فقط)
    ratings = {}
    for t in fx.get("players") or []:
        for p in t.get("players") or []:
            s0 = (p.get("statistics") or [{}])[0]
            r = (s0.get("games") or {}).get("rating")
            if r:
                ratings[(p.get("player") or {}).get("id")] = r
    out["ratings"] = ratings

    # بيانات إضافية بتخزين أطول
    def standings():
        r = api("standings", league=lg["id"], season=lg["season"])
        g = ((r[0].get("league") or {}).get("standings") if r else None) or []
        rows = []
        for grp in g:
            for x in grp:
                a = x.get("all") or {}
                rows.append({"r": x.get("rank"), "id": (x.get("team") or {}).get("id"), "t": (x.get("team") or {}).get("name"),
                             "l": (x.get("team") or {}).get("logo"), "p": a.get("played"), "gd": x.get("goalsDiff"),
                             "pts": x.get("points"), "g": x.get("group") if len(g) > 1 else ""})
        return rows
    try:
        out["table"] = _cached(os.path.join(data_dir, "match_x"), f"st_{lg['id']}_{lg['season']}", 1800, standings)
    except Exception:
        out["table"] = []

    def injuries():
        r = api("injuries", fixture=fid)
        return [{"team": (x.get("team") or {}).get("id"), "n": (x.get("player") or {}).get("name"),
                 "type": (x.get("player") or {}).get("type"), "reason": (x.get("player") or {}).get("reason")} for x in r]
    try:
        out["injuries"] = _cached(os.path.join(data_dir, "match_x"), f"inj_{fid}", 3600 if upcoming else 86400, injuries)
    except Exception:
        out["injuries"] = []

    if upcoming:
        def pred():
            r = api("predictions", fixture=fid)
            if not r:
                return {}
            p = r[0].get("predictions") or {}
            return {"home": (p.get("percent") or {}).get("home"), "draw": (p.get("percent") or {}).get("draw"),
                    "away": (p.get("percent") or {}).get("away"), "advice": p.get("advice")}
        try:
            out["prediction"] = _cached(os.path.join(data_dir, "match_x"), f"pr_{fid}", 10800, pred)
        except Exception:
            out["prediction"] = {}

        def lite(x):
            return {"id": x["fixture"]["id"], "date": x["fixture"]["date"], "home": x["teams"]["home"]["name"],
                    "away": x["teams"]["away"]["name"], "gh": x["goals"]["home"], "ga": x["goals"]["away"],
                    "league": x["league"]["name"]}
        try:
            out["h2h"] = _cached(os.path.join(data_dir, "match_x"), f"h2h_{hid}_{aid}", 86400,
                                 lambda: [lite(x) for x in api("fixtures/headtohead", h2h=f"{hid}-{aid}", last=5)])
        except Exception:
            out["h2h"] = []
        for k, tid in (("form_h", hid), ("form_a", aid)):
            try:
                out[k] = _cached(os.path.join(data_dir, "match_x"), f"last_{tid}", 10800,
                                 lambda tid=tid: [lite(x) for x in api("fixtures", team=tid, last=5)])
            except Exception:
                out[k] = []
    out["generated"] = int(time.time())
    return out


def handle(api, data_dir, fid):
    """يرجع (status, payload)"""
    if not fid.isdigit() or len(fid) > 12:
        return 400, {"error": "invalid_id"}
    day = datetime.now(timezone(timedelta(hours=3))).strftime("%Y-%m-%d")
    with LOCK:
        if DAILY["day"] != day:
            DAILY.update(day=day, n=0)
        path = os.path.join(data_dir, "match", f"{fid}.json")
        fresh_needed = not os.path.exists(path)
        if fresh_needed:
            if DAILY["n"] >= MAX_NEW_PER_DAY:
                return 429, {"error": "busy"}
            DAILY["n"] += 1
    try:
        return 200, build(api, data_dir, fid)
    except KeyError as e:
        return 404, {"error": str(e)}
    except Exception as e:
        print("match error", fid, e, flush=True)
        return 502, {"error": "provider_unavailable"}
