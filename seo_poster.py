#!/usr/bin/env python3
"""
ناشر مقالات السيو على بلوقر (بدون مكتبات خارجية).

python seo_poster.py reports   -> تقارير مباريات منتهية (من بيانات API-Football الحقيقية)
python seo_poster.py news      -> أخبار من RSS تُعاد صياغتها بالعربي
python seo_poster.py all       -> الاثنين

المتغيرات:
  API_FOOTBALL_KEY, ANTHROPIC_API_KEY
  BLOGGER_BLOG_ID, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN
اختياري:
  SEO_DRAFT=1        (الافتراضي) ينشر كمسودة للمراجعة. ضعه 0 للنشر المباشر.
  MAX_REPORTS=3      أقصى عدد تقارير في كل تشغيل
  MAX_NEWS=2         أقصى عدد أخبار في كل تشغيل
  DRY_RUN=1          يطبع المقال ولا ينشر
"""
import hashlib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import sports_bot as sb

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "data", "seo_state.json")

# الدوريات المهمة فقط (حتى تكون المقالات ذات قيمة بحثية)
LEAGUES = {
    307: "الدوري السعودي للمحترفين",
    39: "الدوري الإنجليزي الممتاز",
    140: "الدوري الإسباني",
    135: "الدوري الإيطالي",
    78: "الدوري الألماني",
    61: "الدوري الفرنسي",
    2: "دوري أبطال أوروبا",
    3: "الدوري الأوروبي",
    848: "دوري المؤتمر الأوروبي",
    17: "دوري أبطال آسيا للنخبة",
    1: "كأس العالم",
    32: "تصفيات كأس العالم - أوروبا",
    30: "تصفيات كأس العالم - آسيا",
    29: "تصفيات كأس العالم - أفريقيا",
}
FINISHED = {"FT", "AET", "PEN"}
DRAFT = os.environ.get("SEO_DRAFT", "1") == "1"
DRY = os.environ.get("DRY_RUN", "0") == "1"


def load():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"reports": [], "news": []}


def save(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    st["reports"] = st["reports"][-1500:]
    st["news"] = st["news"][-1500:]
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def publish(title, content, labels):
    if DRY:
        print("=== DRY ===", title, labels)
        print(content)
        return
    sb.publish(title, content, labels, draft=DRAFT)
    print("نُشر" + (" (مسودة)" if DRAFT else "") + ":", title)


class BillingStop(Exception):
    """رصيد مزود الذكاء الاصطناعي انتهى: نوقف التشغيل بدل إهدار الأخبار"""


def check_billing(e):
    """يوقف التشغيل عند نفاد الرصيد أو الحصة حتى لا تضيع الأخبار"""
    if isinstance(e, urllib.error.HTTPError):
        try:
            text = e.read().decode("utf-8", "replace")
        except Exception:
            text = ""
        e.read = lambda *a, **k: text.encode("utf-8")
        text = f"HTTP {e.code} {text}"
    else:
        text = str(e)
    if "credit balance" in text:
        raise BillingStop("رصيد Anthropic غير كافٍ - اشحن الرصيد ليستأنف النشر")
    if "HTTP 429" in text or "RESOURCE_EXHAUSTED" in text:
        raise BillingStop("انتهت حصة Gemini - يستأنف النشر تلقائيًا بعد تجددها")


def why(e):
    """سبب الخطأ مع الموقع ونص رد الخادم"""
    if isinstance(e, urllib.error.HTTPError):
        try:
            body = e.read().decode("utf-8", "replace")[:250]
        except Exception:
            body = ""
        return f"HTTP {e.code} من {urllib.parse.urlparse(e.url).netloc} {body}"
    return str(e)


def parse_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("رد غير JSON: " + (text or "")[:150].replace("\n", " "))
    return json.loads(m.group(0))


# ---------- تقارير المباريات ----------
def match_facts(fx):
    hid = fx["teams"]["home"]["id"]
    home, away = fx["teams"]["home"]["name"], fx["teams"]["away"]["name"]
    ev = []
    for e in fx.get("events") or []:
        t = e.get("type")
        if t not in ("Goal", "Card"):
            continue
        ev.append({
            "min": (e.get("time") or {}).get("elapsed"),
            "team": home if (e.get("team") or {}).get("id") == hid else away,
            "type": t,
            "detail": e.get("detail"),
            "player": (e.get("player") or {}).get("name"),
        })
    return {
        "league": fx["league"]["name"],
        "round": fx["league"].get("round"),
        "home": home,
        "away": away,
        "score": f"{fx['goals']['home']}-{fx['goals']['away']}",
        "status": fx["fixture"]["status"]["short"],
        "venue": (fx["fixture"].get("venue") or {}).get("name"),
        "events": ev,
    }


def report_html(facts, data, league_ar):
    esc = html.escape
    parts = [f"<p>{esc(data['intro'])}</p>"]
    parts.append("<h2>ملخص المباراة</h2>")
    parts += [f"<p>{esc(p)}</p>" for p in data.get("paragraphs", [])]
    goals = [e for e in facts["events"] if e["type"] == "Goal"]
    cards = [e for e in facts["events"] if e["type"] == "Card"]
    if goals:
        parts.append("<h2>أهداف المباراة</h2><ul>")
        for e in goals:
            kind = {"Own Goal": " (عكسي)", "Penalty": " (ركلة جزاء)"}.get(e["detail"], "")
            parts.append(f"<li>الدقيقة {e['min']}: {esc(e['player'] or '')}{kind} - {esc(e['team'])}</li>")
        parts.append("</ul>")
    if cards:
        parts.append("<h2>البطاقات</h2><ul>")
        for e in cards:
            c = "حمراء" if "Red" in (e["detail"] or "") else "صفراء"
            parts.append(f"<li>الدقيقة {e['min']}: بطاقة {c} - {esc(e['player'] or '')} ({esc(e['team'])})</li>")
        parts.append("</ul>")
    parts.append(
        f'<p><small>{esc(league_ar)} - آخر تحديث: {datetime.now(sb.TZ).strftime("%Y-%m-%d %H:%M")} بتوقيت الرياض. '
        "تابع نتائج المباريات المباشرة على الصفحة الرئيسية لعالم المستديرة.</small></p>"
    )
    return "\n".join(parts)


def run_reports():
    st = load()
    done = set(st["reports"])
    limit = int(os.environ.get("MAX_REPORTS", "3"))
    made = 0
    fails = 0
    now = datetime.now(sb.TZ)
    cands = []
    for d in (now, now - timedelta(days=1)):
        try:
            cands += sb.football("fixtures", date=d.strftime("%Y-%m-%d"), timezone="Asia/Riyadh")
        except Exception as e:
            print("تعذر جلب المباريات:", e)
    cands = [f for f in cands
             if f["fixture"]["status"]["short"] in FINISHED
             and f["league"]["id"] in LEAGUES
             and f["fixture"]["id"] not in done]
    # الأهم أولًا: حسب ترتيب الدوريات في القائمة
    order = list(LEAGUES)
    cands.sort(key=lambda f: order.index(f["league"]["id"]))
    print("مباريات مرشحة:", len(cands), flush=True)
    try:
        _reports_loop(st, cands, limit)
    finally:
        save(st)


def _reports_loop(st, cands, limit):
    made = 0
    fails = 0
    for f in cands:
        if made >= limit or fails >= 3:
            break
        fid = f["fixture"]["id"]
        try:
            full = sb.football("fixtures", id=fid)[0]
            facts = match_facts(full)
            league_ar = LEAGUES[f["league"]["id"]]
            raw = sb.claude(
                "أنت محرر رياضي عربي محترف في موقع أخبار كرة قدم. اكتب تقرير مباراة بالعربي الفصيح المبسط "
                "اعتمادًا فقط على البيانات التالية. ممنوع إضافة أي معلومة أو رقم أو لاعب أو تاريخ غير موجود فيها، "
                "وممنوع التخمين عن ترتيب الدوري أو الأداء العام. استخدم الأسماء العربية المعروفة للفرق واللاعبين "
                "المشهورين فقط، وما لا تعرف اسمه العربي اتركه كما هو بالإنجليزية.\n"
                "أعد JSON فقط بهذا الشكل بدون أي نص آخر:\n"
                '{"title": "عنوان جذاب للبحث بحدود 60 حرفًا يحتوي اسمي الفريقين والنتيجة",'
                ' "intro": "مقدمة من جملتين تحتوي الاسمين والنتيجة والبطولة",'
                ' "paragraphs": ["فقرة 1 عن مجريات المباراة وفق الأحداث", "فقرة 2 اختيارية"]}\n\n'
                f"البطولة: {league_ar}\nالبيانات: {json.dumps(facts, ensure_ascii=False)}",
                max_tokens=2000,
            )
            data = parse_json(raw)
            if not data.get("title") or not data.get("intro"):
                raise ValueError("مخرجات ناقصة")
            publish(data["title"].strip(), report_html(facts, data, league_ar),
                    ["تقارير المباريات", league_ar])
            st["reports"].append(fid)
            made += 1
        except Exception as e:
            check_billing(e)
            fails += 1
            print("فشل تقرير", fid, why(e), flush=True)
    print(f"تقارير: {made}")


# ---------- الأخبار ----------
def run_news():
    st = load()
    seen = set(st["news"])
    limit = int(os.environ.get("MAX_NEWS", "2"))
    try:
        _news_loop(seen, limit)
    finally:
        st["news"] = list(seen)
        save(st)


def _news_loop(seen, limit):
    made = 0
    for feed in sb.NEWS_FEEDS:
        if made >= limit:
            break
        try:
            req = urllib.request.Request(feed, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                root = ET.fromstring(r.read())
        except Exception as e:
            print("فشل الخلاصة", feed, e)
            continue
        for item in root.iter("item"):
            if made >= limit:
                break
            link = (item.findtext("link") or "").strip()
            if not re.match(r"^https?://", link):
                continue
            key = hashlib.md5(link.encode()).hexdigest()
            if key in seen:
                continue
            title = (item.findtext("title") or "").strip()
            desc = re.sub(r"<[^>]+>", "", item.findtext("description") or "").strip()
            if len(desc) < 40:
                seen.add(key)
                continue
            try:
                raw = sb.claude(
                    "أنت محرر رياضي عربي. اكتب خبرًا بالعربي (120-180 كلمة) بأسلوبك الخاص بالكامل اعتمادًا فقط "
                    "على العنوان والوصف التاليين. لا تنسخ الصياغة ولا تضف معلومة أو رقمًا غير مذكور. "
                    "أعد JSON فقط: "
                    '{"title": "عنوان خبري بحدود 60 حرفًا", "paragraphs": ["فقرة", "فقرة"]}\n\n'
                    f"العنوان: {title}\nالوصف: {desc}",
                    max_tokens=1800,
                )
                data = parse_json(raw)
                if not data.get("title") or not data.get("paragraphs"):
                    raise ValueError("مخرجات ناقصة")
                esc = html.escape
                body = "".join(f"<p>{esc(p)}</p>" for p in data["paragraphs"])
                body += (f'<p><small>المصدر: <a href="{esc(link)}" rel="nofollow noopener">'
                         f"{esc(urllib.parse.urlparse(link).netloc)}</a></small></p>")
                publish(data["title"].strip(), body, ["أخبار كرة القدم"])
                seen.add(key)
                made += 1
            except Exception as e:
                check_billing(e)
                print("فشل خبر", why(e), flush=True)
    print(f"أخبار: {made}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    try:
        if mode in ("reports", "all"):
            run_reports()
        if mode in ("news", "all"):
            run_news()
    except BillingStop as e:
        print("::error::" + str(e), flush=True)
        sys.exit(1)
