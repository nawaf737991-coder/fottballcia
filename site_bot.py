#!/usr/bin/env python3
"""
بوت بيانات موقع Fottballcia (GitHub Pages) - بدون مكتبات خارجية.
يكتب ملفات JSON في مجلد data/ والموقع يقرأها.

الأوضاع:
  python site_bot.py live      -> data/live.json   (المباريات الجارية)
  python site_bot.py matches   -> data/today.json + data/results.json (مباريات اليوم والنتائج)
  python site_bot.py news      -> data/news.json   (أخبار معاد صياغتها بالعربي)
  python site_bot.py auto      -> يشغّل المناسب حسب الوقت (يستخدمه GitHub Actions)

المتغيرات: API_FOOTBALL_KEY, ANTHROPIC_API_KEY
اختياري: REVIEW_NEWS=1  -> الأخبار تُحفظ في data/news_pending.json للمراجعة ولا تظهر في الموقع
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import sports_bot as sb

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")

MATCHES_EVERY = 30 * 60      # كل 30 دقيقة
NEWS_EVERY = 3 * 60 * 60     # كل 3 ساعات
TABLES_EVERY = 3 * 60 * 60   # الترتيب والهدافين كل 3 ساعات (~18 طلب)
DAYS_EVERY = 3 * 60 * 60     # مباريات الأيام السابقة والقادمة (اختيار التاريخ) ~8 طلبات
DAYS_BACK, DAYS_AHEAD = 3, 7
TABLE_LEAGUES = [
    (39, "الدوري الإنجليزي"), (140, "الدوري الإسباني"), (307, "الدوري السعودي"),
    (135, "الدوري الإيطالي"), (78, "الدوري الألماني"), (61, "الدوري الفرنسي"),
    (2, "دوري أبطال أوروبا"), (12, "دوري أبطال أفريقيا"), (17, "دوري أبطال آسيا للنخبة"),
]
KEEP_NEWS = 60
KEEP_DAYS = 7


# ---------- ملفات البيانات ----------
def read(name, default):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write(name, obj):
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, name)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(path + ".tmp", path)


def now_iso():
    return datetime.now(sb.TZ).isoformat(timespec="seconds")


def events(fx):
    hid = fx["teams"]["home"]["id"]
    out = []
    for e in fx.get("events") or []:
        if e.get("type") not in ("Goal", "Card", "Var"):
            continue
        out.append({
            "m": (e.get("time") or {}).get("elapsed"),
            "x": (e.get("time") or {}).get("extra"),
            "s": "h" if (e.get("team") or {}).get("id") == hid else "a",
            "t": e["type"],
            "d": e.get("detail") or "",
            "p": (e.get("player") or {}).get("name"),
        })
    return out


def _w(fx):
    import quality as Q
    return Q.is_women(fx["teams"]["home"]["name"], fx["teams"]["away"]["name"], fx["league"].get("name"))
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
        "ev": events(fx),
    }


# ---------- المباشر ----------
def run_live():
    fx = [slim(f) for f in sb.fetch_live() if not _w(f)]
    old = read("live.json", {})
    # لو ما فيه مباريات قبل وبعد، نحدّث الملف مرة في الساعة فقط (لتقليل الـ commits)
    if not fx and not old.get("matches") and old.get("ts") and time.time() - old["ts"] < 3600:
        print("لا مباريات جارية، تخطي الكتابة")
        return
    write("live.json", {"updated": now_iso(), "ts": int(time.time()), "matches": fx})
    print(f"live: {len(fx)} مباراة")


# ---------- مباريات اليوم والنتائج ----------
def make_intro(done):
    lines = [f"{m['league']}: {m['home']} {m['gh']}-{m['ga']} {m['away']}" for m in done[:60]]
    try:
        return sb.claude(
            "اكتب مقدمة قصيرة (3 جمل كحد أقصى) بالعربي لمقال نتائج مباريات اليوم، "
            "اعتمد فقط على النتائج التالية ولا تضف أي معلومة أو لاعب أو حدث غير موجود فيها:\n"
            + "\n".join(lines),
            max_tokens=300,
        ).strip()
    except Exception as e:
        print("تعذر توليد المقدمة:", e)
        return ""


def run_matches():
    now = datetime.now(sb.TZ)
    dates = [now.strftime("%Y-%m-%d")]
    if now.hour < 5:  # بعد منتصف الليل: نكمل نتائج أمس أيضًا
        dates.insert(0, (now - timedelta(days=1)).strftime("%Y-%m-%d"))

    results = read("results.json", {"days": []})
    days = {d["date"]: d for d in results.get("days", [])}

    for date in dates:
        fx = [slim(f) for f in sb.football("fixtures", date=date, timezone="Asia/Riyadh") if not _w(f)]
        fx.sort(key=lambda m: m["time"])
        if date == dates[-1]:
            write("today.json", {"date": date, "updated": now_iso(), "matches": fx})
        done = [m for m in fx if m["status"] in sb.FINISHED]
        if not done:
            continue
        entry = days.get(date, {"date": date, "intro": "", "count": 0})
        if entry.get("count") != len(done) or not entry.get("intro"):
            entry["intro"] = make_intro(done)
            entry["count"] = len(done)
        entry["matches"] = done
        days[date] = entry

    out = sorted(days.values(), key=lambda d: d["date"], reverse=True)[:KEEP_DAYS]
    write("results.json", {"updated": now_iso(), "days": out})
    print(f"matches: {len(out)} أيام")


# ---------- مباريات أيام أخرى (اختيار التاريخ في الموقع) ----------
def run_days():
    """data/days/YYYY-MM-DD.json لكل يوم من -3 إلى +7 (اليوم نفسه في today.json)"""
    now = datetime.now(sb.TZ)
    folder = os.path.join(DATA, "days")
    os.makedirs(folder, exist_ok=True)
    wanted = []
    for off in range(-DAYS_BACK, DAYS_AHEAD + 1):
        if off == 0:
            continue
        date = (now + timedelta(days=off)).strftime("%Y-%m-%d")
        wanted.append(date)
        path = os.path.join(folder, date + ".json")
        # الأيام الماضية (قبل أمس) لا تتغير: نجلبها مرة واحدة فقط
        if off < -1 and os.path.exists(path):
            continue
        try:
            fx = [slim(f) for f in sb.football("fixtures", date=date, timezone="Asia/Riyadh") if not _w(f)]
        except Exception as e:
            print("تعذر جلب", date, e)
            continue
        if off > 0:
            for m in fx:
                m.pop("ev", None)
        fx.sort(key=lambda m: m["time"])
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"date": date, "updated": now_iso(), "matches": fx}, f, ensure_ascii=False, separators=(",", ":"))
        print(f"days: {date} ({len(fx)} مباراة)")
    for name in os.listdir(folder):
        if name.endswith(".json") and name[:-5] not in wanted and name != "index.json":
            os.remove(os.path.join(folder, name))
    write("days/index.json", {"updated": now_iso(), "today": now.strftime("%Y-%m-%d"), "dates": sorted(wanted)})


# ---------- الأخبار ----------
def run_news():
    review = os.environ.get("REVIEW_NEWS", "0") == "1"
    target = "news_pending.json" if review else "news.json"
    store = read(target, {"items": []})
    items = store.get("items", [])
    seen = set(read("news_seen.json", []))
    added = 0

    for feed in sb.NEWS_FEEDS:
        if added >= sb.MAX_NEWS_PER_RUN:
            break
        try:
            req = urllib.request.Request(feed, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                root = ET.fromstring(r.read())
        except Exception as e:
            print("فشل الخلاصة", feed, e)
            continue
        for item in root.iter("item"):
            if added >= sb.MAX_NEWS_PER_RUN:
                break
            link = (item.findtext("link") or "").strip()
            if not re.match(r"^https?://", link):
                continue
            key = hashlib.md5(link.encode()).hexdigest()
            if key in seen:
                continue
            title = (item.findtext("title") or "").strip()
            desc = re.sub(r"<[^>]+>", "", item.findtext("description") or "").strip()
            import quality as Q
            if Q.is_women(title, desc, link) or Q.news_score(title, desc) < 1:
                continue
            try:
                text = sb.claude(
                    "أنت محرر رياضي. اكتب خبرًا قصيرًا بالعربي (80-120 كلمة) بأسلوبك الخاص بالكامل "
                    "اعتمادًا فقط على العنوان والوصف التاليين. لا تنسخ الصياغة الأصلية ولا تضف معلومات أو "
                    "أرقام غير مذكورة. السطر الأول عنوان الخبر فقط، ثم فقرة الخبر.\n\n"
                    f"العنوان: {title}\nالوصف: {desc}",
                    max_tokens=500,
                ).strip()
            except Exception as e:
                print("تعذر كتابة الخبر:", e)
                continue
            first, _, rest = text.partition("\n")
            head = first.strip().strip("#* ").strip()
            body = rest.replace("**", "").strip()
            seen.add(key)  # نسجله حتى لا نعيد المحاولة على خبر فاشل
            if not head or not body:
                continue
            items.insert(0, {
                "id": key[:12],
                "title": head,
                "body": body,
                "source": urllib.parse.urlparse(link).netloc,
                "link": link,
                "date": now_iso(),
            })
            added += 1
            print("خبر:", head)

    write(target, {"updated": now_iso(), "items": items[:KEEP_NEWS]})
    write("news_seen.json", list(seen)[-800:])


# ---------- الترتيب والهدافين ----------
def current_season(lid):
    res = sb.football("leagues", id=lid, current="true")
    for s_ in (res[0].get("seasons") if res else []) or []:
        if s_.get("current"):
            return s_.get("year")
    return None


def run_tables():
    old = {l["id"]: l for l in read("tables.json", {}).get("leagues", [])}
    out = []
    for lid, name in TABLE_LEAGUES:
        try:
            season = current_season(lid)
            if not season:
                raise ValueError("لا يوجد موسم حالي")
            st = sb.football("standings", league=lid, season=season)
            groups = ((st[0].get("league") or {}).get("standings") if st else None) or []
            rows = []
            multi = lid in (12, 17) and len(groups) > 1
            flat = [(r, (r.get("group") or "")) for g in groups for r in g] if multi else [(r, "") for r in (groups[0] if groups else [])]
            for r, gname in flat:
                a = r.get("all") or {}
                g = a.get("goals") or {}
                rows.append({
                    "r": r.get("rank"), "t": (r.get("team") or {}).get("name"),
                    "l": (r.get("team") or {}).get("logo"), "p": a.get("played"),
                    "w": a.get("win"), "d": a.get("draw"), "ls": a.get("lose"),
                    "gd": r.get("goalsDiff"), "pts": r.get("points"), "f": r.get("form") or "", "g": gname,
                })
            sc = []
            try:
                tops = sb.football("players/topscorers", league=lid, season=season)[:10]
            except Exception:
                tops = []
            for x in tops:
                pl = x.get("player") or {}
                stt = (x.get("statistics") or [{}])[0]
                sc.append({
                    "n": pl.get("name"), "ph": pl.get("photo"),
                    "t": (stt.get("team") or {}).get("name"), "tl": (stt.get("team") or {}).get("logo"),
                    "g": (stt.get("goals") or {}).get("total") or 0,
                    "a": (stt.get("goals") or {}).get("assists") or 0,
                    "pen": (stt.get("penalty") or {}).get("scored") or 0,
                })
            if not rows:
                raise ValueError("ترتيب فارغ")
            out.append({"id": lid, "name": name, "season": season, "table": rows, "scorers": sc})
            print(f"tables: {name} {season} ({len(rows)} فريق، {len(sc)} هداف)")
        except Exception as e:
            print("تعذر ترتيب", name, e)
            if lid in old:
                out.append(old[lid])
    if out:
        write("tables.json", {"updated": now_iso(), "leagues": out})


# ---------- تشغيل تلقائي ----------
def due(meta, key, every):
    return time.time() - meta.get(key, 0) >= every - 120


def run_auto():
    meta = read("meta.json", {})
    try:
        run_live()
    except Exception as e:
        print("خطأ live:", e)
    for key, every, fn in (("matches", MATCHES_EVERY, run_matches), ("tables", TABLES_EVERY, run_tables), ("days", DAYS_EVERY, run_days)):
        if due(meta, key, every):
            try:
                fn()
                meta[key] = int(time.time())
            except Exception as e:
                print(f"خطأ {key}:", e)
    write("meta.json", meta)


MODES = {"live": run_live, "matches": run_matches, "news": run_news, "tables": run_tables, "days": run_days, "auto": run_auto}

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    if mode not in MODES:
        sys.exit(__doc__)
    MODES[mode]()
