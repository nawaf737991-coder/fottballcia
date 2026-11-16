#!/usr/bin/env python3
"""
بوت موقع رياضي على بلوقر (بدون مكتبات خارجية - بايثون فقط)

الأوضاع:
  python sports_bot.py results   -> مقال نتائج مباريات اليوم (يتحدث نفس المقال كل مرة)
  python sports_bot.py live      -> مقال "النتائج المباشرة" يتحدث لحظيًا
  python sports_bot.py news      -> أخبار جديدة من RSS يعاد كتابتها بالعربي وتنشر

المتغيرات المطلوبة (Environment Variables):
  API_FOOTBALL_KEY      مفتاح API-Football (api-sports.io)
  ANTHROPIC_API_KEY     مفتاح Claude API
  BLOGGER_BLOG_ID       رقم مدونتك
  GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN   لصلاحية النشر على بلوقر
اختياري:
  PUBLISH_AS_DRAFT=1    ينشر كمسودة للمراجعة أول (مفعّل افتراضيًا للأخبار)
"""
import hashlib
import html
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=3))  # توقيت الرياض
STATE_FILE = "state.json"
CLAUDE_MODEL = "claude-sonnet-5-5"

# مصادر الأخبار (RSS) - عدّلها كما تحب
NEWS_FEEDS = [
    "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "https://www.espn.com/espn/rss/soccer/news",
]
MAX_NEWS_PER_RUN = 3

FINISHED = {"FT", "AET", "PEN"}
LIVE = {"1H", "HT", "2H", "ET", "BT", "P", "LIVE"}


# ---------- أدوات عامة ----------
def env(name, required=True):
    v = os.environ.get(name, "")
    if required and not v:
        sys.exit(f"المتغير {name} غير موجود")
    return v


def http(url, method="GET", headers=None, data=None):
    body = None
    headers = dict(headers or {})
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ---------- API-Football ----------
def football(path, **params):
    q = urllib.parse.urlencode(params)
    data = http(
        f"https://v3.football.api-sports.io/{path}?{q}",
        headers={"x-apisports-key": env("API_FOOTBALL_KEY")},
    )
    return data.get("response", [])


def group_by_league(fixtures):
    groups = defaultdict(list)
    for fx in fixtures:
        key = f"{fx['league']['country']} - {fx['league']['name']}"
        groups[key].append(fx)
    return groups


def matches_table(fixtures, show_minute=False):
    out = []
    for league, items in sorted(group_by_league(fixtures).items()):
        out.append(f"<h3>{html.escape(league)}</h3>")
        out.append('<table border="1" cellpadding="6" style="border-collapse:collapse;width:100%;text-align:center">')
        for fx in items:
            h, a = fx["teams"]["home"]["name"], fx["teams"]["away"]["name"]
            gh, ga = fx["goals"]["home"], fx["goals"]["away"]
            score = f"{gh if gh is not None else '-'} : {ga if ga is not None else '-'}"
            status = fx["fixture"]["status"]
            extra = ""
            if show_minute:
                m = status.get("elapsed")
                extra = f"<td>{'استراحة' if status['short'] == 'HT' else (str(m) + chr(39) if m else '')}</td>"
            out.append(
                f"<tr><td>{html.escape(h)}</td><td><b>{score}</b></td>"
                f"<td>{html.escape(a)}</td>{extra}</tr>"
            )
        out.append("</table>")
    return "\n".join(out)


# ---------- Claude ----------
def claude(prompt, max_tokens=900):
    data = http(
        "https://api.anthropic.com/v1/messages",
        method="POST",
        headers={"x-api-key": env("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01"},
        data={
            "model": CLAUDE_MODEL,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    return "".join(b.get("text", "") for b in data.get("content", []))


# ---------- Blogger ----------
_token = {}


def blogger_token():
    if "t" not in _token:
        body = urllib.parse.urlencode({
            "client_id": env("GOOGLE_CLIENT_ID"),
            "client_secret": env("GOOGLE_CLIENT_SECRET"),
            "refresh_token": env("GOOGLE_REFRESH_TOKEN"),
            "grant_type": "refresh_token",
        }).encode()
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body)
        with urllib.request.urlopen(req, timeout=60) as r:
            _token["t"] = json.loads(r.read())["access_token"]
    return _token["t"]


def blogger(path, method="GET", data=None, **params):
    q = urllib.parse.urlencode(params)
    base = f"https://www.googleapis.com/blogger/v3/blogs/{env('BLOGGER_BLOG_ID')}"
    return http(
        f"{base}{path}?{q}",
        method=method,
        headers={"Authorization": f"Bearer {blogger_token()}"},
        data=data,
    )


def publish(title, content, labels, draft=False):
    return blogger("/posts/", "POST", {"title": title, "content": content, "labels": labels},
                   isDraft=str(draft).lower())


def update(post_id, title, content):
    return blogger(f"/posts/{post_id}", "PATCH", {"title": title, "content": content})


# ---------- الأوضاع ----------
def run_results():
    state = load_state()
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    fixtures = [f for f in football("fixtures", date=today, timezone="Asia/Riyadh")
                if f["fixture"]["status"]["short"] in FINISHED]
    if not fixtures:
        print("ما فيه مباريات منتهية بعد")
        return

    summary_data = [
        f"{f['league']['name']}: {f['teams']['home']['name']} {f['goals']['home']}-{f['goals']['away']} {f['teams']['away']['name']}"
        for f in fixtures
    ]
    intro = claude(
        "اكتب مقدمة قصيرة (3 جمل كحد أقصى) بالعربي لمقال نتائج مباريات اليوم، "
        "اعتمد فقط على النتائج التالية ولا تضف أي معلومة أو لاعب أو حدث غير موجود فيها:\n"
        + "\n".join(summary_data),
        max_tokens=300,
    )
    content = f"<p>{html.escape(intro)}</p>\n{matches_table(fixtures)}"
    title = f"نتائج مباريات اليوم {today}"

    posts = state.setdefault("results_posts", {})
    if today in posts:
        update(posts[today], title, content)
        print("تم تحديث مقال النتائج")
    else:
        posts[today] = publish(title, content, ["نتائج المباريات"])["id"]
        print("تم نشر مقال النتائج")
    save_state(state)


def fetch_live():
    return [f for f in football("fixtures", live="all") if f["fixture"]["status"]["short"] in LIVE]


def run_live(fixtures=None):
    state = load_state()
    if fixtures is None:
        fixtures = fetch_live()
    now = datetime.now(TZ).strftime("%H:%M")
    if fixtures:
        body = matches_table(fixtures, show_minute=True)
    else:
        body = "<p>لا توجد مباريات جارية حاليًا.</p>"
    content = f"<p>آخر تحديث: {now} (بتوقيت الرياض)</p>\n{body}"
    title = "النتائج المباشرة للمباريات الآن"

    if state.get("live_post"):
        update(state["live_post"], title, content)
    else:
        state["live_post"] = publish(title, content, ["مباشر"])["id"]
    save_state(state)
    print(f"تم التحديث ({len(fixtures)} مباراة جارية)")


def run_news():
    state = load_state()
    seen = set(state.setdefault("seen_news", []))
    published = 0
    draft = os.environ.get("PUBLISH_AS_DRAFT", "1") == "1"

    for feed in NEWS_FEEDS:
        try:
            with urllib.request.urlopen(urllib.request.Request(feed, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
                root = ET.fromstring(r.read())
        except Exception as e:
            print("فشل الخلاصة", feed, e)
            continue
        for item in root.iter("item"):
            if published >= MAX_NEWS_PER_RUN:
                break
            link = (item.findtext("link") or "").strip()
            key = hashlib.md5(link.encode()).hexdigest()
            if not link or key in seen:
                continue
            title = (item.findtext("title") or "").strip()
            desc = re.sub(r"<[^>]+>", "", item.findtext("description") or "").strip()
            text = claude(
                "أنت محرر رياضي. اكتب خبرًا قصيرًا بالعربي (80-120 كلمة) بأسلوبك الخاص بالكامل "
                "اعتمادًا فقط على العنوان والوصف التاليين. لا تنسخ الصياغة الأصلية ولا تضف معلومات أو "
                "أرقام غير مذكورة. السطر الأول عنوان الخبر فقط، ثم فقرة الخبر.\n\n"
                f"العنوان: {title}\nالوصف: {desc}",
                max_tokens=500,
            ).strip()
            first, _, rest = text.partition("\n")
            content = (
                f"<p>{html.escape(rest.strip())}</p>"
                f'<p><small>المصدر: <a href="{html.escape(link)}" rel="nofollow noopener">{html.escape(urllib.parse.urlparse(link).netloc)}</a></small></p>'
            )
            publish(first.strip("# *"), content, ["أخبار"], draft=draft)
            seen.add(key)
            published += 1
            print("نشر:", first)
    state["seen_news"] = list(seen)[-500:]
    save_state(state)


# ---------- وضع السيرفر المستمر ----------
LIVE_JSON = "live.json"
PORT = int(os.environ.get("PORT", "8080"))


def live_payload(fixtures):
    return {
        "updated": datetime.now(TZ).isoformat(timespec="seconds"),
        "matches": [
            {
                "league": f"{f['league']['country']} - {f['league']['name']}",
                "home": f["teams"]["home"]["name"],
                "away": f["teams"]["away"]["name"],
                "hl": f["teams"]["home"].get("logo"),
                "al": f["teams"]["away"].get("logo"),
                "gh": f["goals"]["home"],
                "ga": f["goals"]["away"],
                "status": f["fixture"]["status"]["short"],
                "minute": f["fixture"]["status"].get("elapsed"),
            }
            for f in fixtures
        ],
    }


class LiveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            with open(LIVE_JSON, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            data = b'{"matches":[]}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def run_loop():
    """يشتغل دائمًا: live.json كل LIVE_INTERVAL ثانية، مقال المباشر كل 5 دقايق،
    النتائج كل 15 دقيقة، الأخبار كل 3 ساعات."""
    threading.Thread(
        target=lambda: HTTPServer(("0.0.0.0", PORT), LiveHandler).serve_forever(), daemon=True
    ).start()
    interval = int(os.environ.get("LIVE_INTERVAL", "30"))
    last = {"post": 0, "results": 0, "news": 0}
    print(f"السيرفر يعمل على المنفذ {PORT}، التحديث كل {interval} ثانية")
    while True:
        now = time.time()
        try:
            fixtures = fetch_live()
            with open(LIVE_JSON + ".tmp", "w", encoding="utf-8") as f:
                json.dump(live_payload(fixtures), f, ensure_ascii=False)
            os.replace(LIVE_JSON + ".tmp", LIVE_JSON)
            if now - last["post"] >= 300:
                run_live(fixtures)
                last["post"] = now
        except Exception as e:
            print("خطأ في المباشر:", e)
        for name, every, fn in (("results", 900, run_results), ("news", 10800, run_news)):
            if now - last[name] >= every:
                try:
                    fn()
                except Exception as e:
                    print(f"خطأ في {name}:", e)
                last[name] = now
        time.sleep(interval)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    {"results": run_results, "live": run_live, "news": run_news, "loop": run_loop}.get(
        mode, lambda: sys.exit(__doc__)
    )()
