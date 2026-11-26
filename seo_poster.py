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

import time
import sports_bot as sb
import quality as Q

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
    12: "دوري أبطال أفريقيا",
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


def slug_words(text, n=8):
    """كلمات إنجليزية قصيرة لرابط المقال (Blogger يبني الرابط من عنوان النشر الأول)"""
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    stop = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "at", "is", "with", "as", "by"}
    words = [w for w in words if w not in stop and (len(w) > 1 or w.isdigit())][:n]
    return " ".join(words) if len(words) >= 2 else ""
def publish(title, content, labels, slug="", draft=None):
    draft = DRAFT if draft is None else draft
    if DRY:
        print("=== DRY ===", title, "| slug:", slug, labels)
        print(content)
        return
    first = slug if (slug and not draft) else title
    post = sb.publish(first, content, labels, draft=draft)
    if first != title:
        # نرجع العنوان العربي فورًا ويبقى الرابط الإنجليزي
        for i in range(3):
            try:
                sb.blogger(f"/posts/{post['id']}", "PATCH", {"title": title})
                break
            except Exception as e:
                print("تعذر تحديث العنوان، إعادة المحاولة", why(e), flush=True)
                time.sleep(5)
        else:
            print("::warning::نُشر بعنوان إنجليزي ولم يُحدَّث: " + post.get("url", ""), flush=True)
    print("نُشر" + (" (مسودة)" if draft else "") + ":", title, post.get("url", ""))


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
    if "invalid_grant" in text or "unauthorized_client" in text:
        raise BillingStop("صلاحية Blogger منتهية (GOOGLE_REFRESH_TOKEN) - جدّد التوكن ليستأنف النشر")
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


# ---------- الصور و SEO ----------
IMG_BASE = os.environ.get("IMG_BASE", "https://nawaf737991-coder.github.io/fottballcia/img/")
SITE_NAME = "عالم المستديرة"
SITE_URL = "https://www.fottballcia.com/"


def image_name(slug, key):
    base = "-".join((slug or "").split())[:70] or "post"
    return datetime.now(sb.TZ).strftime("%Y/%m/") + f"{base}-{hashlib.md5(key.encode()).hexdigest()[:6]}.jpg"


def make_cover(kind, name, **kw):
    """يولد صورة الغلاف ويحفظها في img/ (تنشرها GitHub Pages). يرجع الرابط أو "" عند الفشل"""
    try:
        import cover
        path = os.path.join(ROOT, "img", name)
        if kind == "match":
            cover.match_cover(path, **kw)
        elif kind == "photo":
            cover.photo_cover(path, **kw)
        elif kind == "teams":
            cover.teams_cover(path, **kw)
        else:
            cover.news_cover(path, **kw)
        return IMG_BASE + name
    except Exception as e:
        print("تعذر إنشاء الصورة:", e, flush=True)
        return ""


def related_links(label, limit=3):
    """روابط داخلية لآخر المقالات من نفس التصنيف"""
    try:
        data = sb.blogger("/posts", maxResults=limit + 2, labels=label, fetchBodies="false",
                          status="live", orderBy="published")
        items = [(i["title"], i["url"]) for i in data.get("items", []) if i.get("url")][:limit]
    except Exception as e:
        print("تعذر جلب المقالات ذات الصلة:", why(e), flush=True)
        return ""
    if not items:
        return ""
    esc = html.escape
    lis = "".join(f'<li><a href="{esc(u)}">{esc(t)}</a></li>' for t, u in items)
    return f"<h2>اقرأ أيضًا</h2><ul>{lis}</ul>"


def clean_tags(tags, limit=3):
    out = []
    for t in tags or []:
        t = re.sub(r"[,<>\"]", "", str(t)).strip()
        if 2 <= len(t) <= 30 and t not in out:
            out.append(t)
    return out[:limit]


def wrap_article(title, description, image_url, body, label, credit_html=""):
    """صورة بارزة في البداية + المحتوى + روابط داخلية + بيانات منظمة NewsArticle"""
    esc = html.escape
    parts = []
    if image_url:
        parts.append(
            f'<div class="post-cover" style="margin:0 0 16px"><img src="{esc(image_url)}" alt="{esc(title)}" '
            f'title="{esc(title)}" width="1200" height="675" style="width:100%;height:auto;border-radius:12px"/>'
            + (f'<div style="font-size:12px;color:#7a8a82;margin-top:4px">{credit_html}</div>' if credit_html else "")
            + "</div>"
        )
    parts.append(body)
    rel = related_links(label)
    if rel:
        parts.append(rel)
    now = datetime.now(sb.TZ).isoformat(timespec="seconds")
    ld = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": title[:110],
        "description": (description or "")[:160],
        "datePublished": now,
        "dateModified": now,
        "inLanguage": "ar",
        "author": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL},
        "publisher": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL},
    }
    if image_url:
        ld["image"] = [image_url]
    parts.append('<script type="application/ld+json">' +
                 json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    return "\n".join(parts)


def source_text(link, limit=3500):
    """نص المقال الأصلي (فقرات المقال فقط) ليكتب Gemini مقالًا أغنى بالمعلومات"""
    try:
        req = urllib.request.Request(link, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            page = r.read().decode("utf-8", "replace")
    except Exception:
        return ""
    m = re.search(r"<article\b.*?</article>", page, re.S)
    page = m.group(0) if m else page
    paras = []
    for p in re.findall(r"<p\b[^>]*>(.*?)</p>", page, re.S):
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", p))).strip()
        if len(t) > 50 and "cookie" not in t.lower():
            paras.append(t)
    out = "\n".join(paras)
    return out[:limit]


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
        "fid": fx["fixture"]["id"], "lid": fx["league"]["id"], "hid": hid, "aid": fx["teams"]["away"]["id"],
        "league": fx["league"]["name"],
        "round": fx["league"].get("round"),
        "home": home,
        "away": away,
        "score": f"{fx['goals']['home']}-{fx['goals']['away']}",
        "status": fx["fixture"]["status"]["short"],
        "venue": (fx["fixture"].get("venue") or {}).get("name"),
        "events": ev,
    }


STAT_AR = {
    "Ball Possession": "الاستحواذ", "Total Shots": "إجمالي التسديدات", "Shots on Goal": "تسديدات على المرمى",
    "Corner Kicks": "الركنيات", "Fouls": "الأخطاء", "Offsides": "التسلل", "Goalkeeper Saves": "تصديات الحارس",
    "Total passes": "التمريرات", "Passes %": "دقة التمرير", "expected_goals": "الأهداف المتوقعة (xG)",
    "Yellow Cards": "البطاقات الصفراء", "Red Cards": "البطاقات الحمراء",
}


def match_stats(fid):
    """إحصائيات الفريقين: {اسم الإحصائية بالعربي: [المضيف, الضيف]}"""
    try:
        res = sb.football("fixtures/statistics", fixture=fid)
    except Exception as e:
        print("تعذر جلب الإحصائيات:", e, flush=True)
        return {}
    if len(res) != 2:
        return {}
    vals = [{x["type"]: x["value"] for x in t.get("statistics") or []} for t in res]
    out = {}
    for k, ar in STAT_AR.items():
        a, b = vals[0].get(k), vals[1].get(k)
        if a is None and b is None:
            continue
        out[ar] = [a if a is not None else 0, b if b is not None else 0]
    return out


def match_lineups(fid):
    try:
        res = sb.football("fixtures/lineups", fixture=fid)
    except Exception as e:
        print("تعذر جلب التشكيلات:", e, flush=True)
        return []
    out = []
    for t in res[:2]:
        out.append({
            "team": (t.get("team") or {}).get("name"),
            "formation": t.get("formation"),
            "coach": (t.get("coach") or {}).get("name"),
            "xi": [((x.get("player") or {}).get("name")) for x in t.get("startXI") or []],
        })
    return out


TABLE_SLUG = {307: "saudi-league-table", 39: "premier-league-table", 140: "laliga-table", 135: "serie-table",
              78: "bundesliga-table", 61: "ligue1-table", 2: "champions-league-table", 12: "caf-champions-league-table",
              17: "afc-champions-league-table"}
def tweets_html(fid):
    """تضمين تغريدات رسمية فقط من data/embed_tweets.json (التضمين فقط، بلا تحميل فيديو)"""
    try:
        with open(os.path.join(ROOT, "data", "embed_tweets.json"), encoding="utf-8") as f:
            d = json.load(f)
        d = d.get("matches", d)
        items = [x if isinstance(x, dict) else {"u": x} for x in (d.get(str(fid)) or [])][:4]
        with open(os.path.join(ROOT, "data", "official_accounts.json"), encoding="utf-8") as f:
            official = {x.lower() for x in json.load(f)["accounts"]}
    except Exception:
        return ""
    out = []
    for it in items:
        m = re.match(r"^https://(?:x|twitter)\.com/([A-Za-z0-9_]{1,15})/status/\d+$", it.get("u", ""))
        if m and m.group(1).lower() in official:
            out.append(f'<blockquote class="twitter-tweet" data-lang="ar" data-dnt="true"><a href="{html.escape(it["u"])}"></a></blockquote>')
    if not out:
        return ""
    return "<h2>مقاطع المباراة</h2>" + "".join(out)
def extras_html(facts, data, league_ar):
    """صندوق المباريات القادمة + روابط + زر تفاصيل المباراة"""
    esc = html.escape
    out = ['<h2>المباريات القادمة</h2>']
    names = {facts.get("hid"): data.get("home_ar") or facts["home"], facts.get("aid"): data.get("away_ar") or facts["away"]}
    rows = []
    for tid, nm in names.items():
        try:
            nx = sb.football("fixtures", team=tid, next=1)
        except Exception:
            nx = []
        if nx:
            f = nx[0]
            dt = datetime.fromisoformat(f["fixture"]["date"]).astimezone(sb.TZ).strftime("%Y-%m-%d %H:%M")
            vs = f["teams"]["away"]["name"] if f["teams"]["home"]["id"] == tid else f["teams"]["home"]["name"]
            rows.append(f'<li><strong>{esc(nm)}</strong> يلاقي {esc(vs)} ({esc(f["league"]["name"])}) - {dt} بتوقيت السعودية '
                        f'<a href="{SITE_URL.rstrip("/")}/p/match.html?id={f["fixture"]["id"]}">تفاصيل</a></li>')
    out.append("<ul>" + "".join(rows) + "</ul>" if rows else "<p>لم يُحدَّد موعد المباراة القادمة بعد.</p>")
    links = [f'<a href="{SITE_URL.rstrip("/")}/p/matches-today.html">مباريات اليوم</a>']
    if TABLE_SLUG.get(facts.get("lid")):
        links.append(f'<a href="{SITE_URL.rstrip("/")}/p/{TABLE_SLUG[facts["lid"]]}.html">ترتيب {esc(league_ar)}</a>')
    out.append("<p>" + " · ".join(links) + "</p>")
    if facts.get("fid"):
        out.append(f'<p style="text-align:center"><a href="{SITE_URL.rstrip("/")}/p/match.html?id={facts["fid"]}" '
                   'style="display:inline-block;background:#153a5b;color:#fff;padding:10px 26px;border-radius:24px;'
                   'font-weight:800;text-decoration:none">تفاصيل المباراة</a></p>')
    return "\n".join(out)
def report_html(facts, data, league_ar):
    esc = html.escape
    parts = [f'<p style="font-size:13px;color:#5b6b7c;margin:0 0 8px">بقلم: <strong>فريق عالم المستديرة</strong> · '
             f'آخر تحديث: {datetime.now(sb.TZ).strftime("%Y-%m-%d %H:%M")} بتوقيت السعودية</p>',
             f"<p><strong>{esc(data['intro'])}</strong></p>"]
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
    stats = facts.get("stats") or {}
    if stats:
        hn, an = esc(data.get("home_ar") or facts["home"]), esc(data.get("away_ar") or facts["away"])
        parts.append("<h2>أرقام المباراة</h2>")
        parts.append('<table style="width:100%;border-collapse:collapse;text-align:center">'
                     f'<thead><tr><th style="padding:6px;border-bottom:2px solid #ccc">{hn}</th>'
                     '<th style="padding:6px;border-bottom:2px solid #ccc">الإحصائية</th>'
                     f'<th style="padding:6px;border-bottom:2px solid #ccc">{an}</th></tr></thead><tbody>')
        for k, (a, b) in stats.items():
            parts.append(f'<tr><td style="padding:6px;border-bottom:1px solid #eee">{esc(str(a))}</td>'
                         f'<td style="padding:6px;border-bottom:1px solid #eee">{esc(k)}</td>'
                         f'<td style="padding:6px;border-bottom:1px solid #eee">{esc(str(b))}</td></tr>')
        parts.append("</tbody></table>")
    if data.get("analysis"):
        parts.append("<h2>قراءة فنية في الأرقام</h2>")
        parts += [f"<p>{esc(p)}</p>" for p in data["analysis"]]
    lu = facts.get("lineups") or []
    if lu and any(t.get("xi") for t in lu):
        parts.append("<h2>التشكيلة الأساسية</h2>")
        names = [data.get("home_ar") or facts["home"], data.get("away_ar") or facts["away"]]
        for i, t in enumerate(lu):
            head = f"{names[i] if i < 2 else t['team']}"
            if t.get("formation"):
                head += f" ({t['formation']})"
            if t.get("coach"):
                head += f" - المدرب: {t['coach']}"
            parts.append(f"<p><strong>{esc(head)}</strong>: {esc('، '.join(n for n in t['xi'] if n))}</p>")
    if data.get("conclusion"):
        parts.append("<h2>ماذا تعني النتيجة؟</h2>")
        parts.append(f"<p>{esc(data['conclusion'])}</p>")
    parts.append(tweets_html(facts.get("fid")))
    parts.append(extras_html(facts, data, league_ar))
    parts.append(
        f'<p><small>{esc(league_ar)} - آخر تحديث: {datetime.now(sb.TZ).strftime("%Y-%m-%d %H:%M")} بتوقيت الرياض. '
        "تابع نتائج المباريات المباشرة على الصفحة الرئيسية لعالم المستديرة.</small></p>"
    )
    return "\n".join(parts)


def run_reports():
    st = load()
    done = set(st["reports"])
    dc = Q.day_counts(st)
    cap = int(os.environ.get("DAILY_REPORTS", "2"))
    limit = min(int(os.environ.get("MAX_REPORTS", "1")), cap - dc["rep"])
    if limit <= 0:
        print("اكتملت حصة تقارير اليوم")
        return
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
             and f["fixture"]["id"] not in done
             and not Q.is_women(f["teams"]["home"]["name"], f["teams"]["away"]["name"], f["league"].get("name"))
             and (Q.team_big(f) >= 1 or f["league"]["id"] in (2, 12, 17, 1))]
    # الأهم أولًا: حسب ترتيب الدوريات في القائمة
    order = list(LEAGUES)
    cands.sort(key=lambda f: (-Q.team_big(f), order.index(f["league"]["id"])))
    print("مباريات مرشحة:", len(cands), flush=True)
    try:
        _reports_loop(st, cands, limit)
    finally:
        save(st)


def match_image(data, slug, fid, title, league_ar, full, home_ar, away_ar):
    """صورة نجم المباراة -> صورة الملعب -> شعارا الفريقين، مع النتيجة والشعارين على الصورة"""
    import photos
    esc = html.escape
    t = full.get("teams", {})
    g = full.get("goals", {})
    th, ta = t.get("home", {}), t.get("away", {})
    name = image_name(slug, str(fid))
    score = dict(home_logo=th.get("logo"), away_logo=ta.get("logo"), home_goals=g.get("home"), away_goals=g.get("away"))
    venue = (data.get("venue_en") or "").strip() or ((full.get("fixture") or {}).get("venue") or {}).get("name") or ""
    for subj in ((data.get("star_en") or "").strip(), venue):
        ph = photos.wiki_photo(subj) if subj else None
        if not ph:
            continue
        img = make_cover("photo", name, title=title, kicker=league_ar, date_text="", photo_bytes=ph["bytes"],
                         credit=f'Photo: {ph["credit"]} / {ph["license"]}', score=score)
        if img:
            return img, (f'الصورة: {esc(ph["credit"])} عبر <a href="{esc(ph["page"])}" rel="nofollow noopener" '
                         f'target="_blank">ويكيميديا كومنز</a> ({esc(ph["license"])})')
    img = make_cover("match", name, title=title, league=league_ar,
                     date_text=(full.get("fixture", {}).get("date") or "")[:10],
                     home_name=home_ar, away_name=away_ar,
                     home_logo=th.get("logo"), away_logo=ta.get("logo"),
                     home_goals=g.get("home"), away_goals=g.get("away"))
    return img, ""
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
            facts["stats"] = match_stats(fid)
            facts["lineups"] = match_lineups(fid)
            league_ar = LEAGUES[f["league"]["id"]]
            raw = sb.claude(
                "أنت محرر رياضي عربي محترف في موقع أخبار كرة قدم. اكتب تقرير مباراة بالعربي الفصيح المبسط "
                "اعتمادًا فقط على البيانات التالية. ممنوع إضافة أي معلومة أو رقم أو لاعب أو تاريخ غير موجود فيها، "
                "وممنوع التخمين عن ترتيب الدوري أو الأداء العام. استخدم الأسماء العربية المعروفة للفرق واللاعبين "
                "المشهورين فقط، وما لا تعرف اسمه العربي اتركه كما هو بالإنجليزية.\n"
                "أعد JSON فقط بهذا الشكل بدون أي نص آخر:\n"
                '{"title": "عنوان جذاب للبحث بحدود 60 حرفًا يحتوي اسمي الفريقين والنتيجة",'
                ' "description": "وصف للبحث بحدود 150 حرفًا",'
                ' "home_ar": "اسم الفريق المضيف بالعربي", "away_ar": "اسم الفريق الضيف بالعربي",'
                ' "intro": "مقدمة من 3 جمل تحتوي الاسمين والنتيجة والبطولة والجولة والملعب إن وجد",'
                ' "paragraphs": ["فقرة من 4 جمل على الأقل عن مجريات الشوط الأول وفق الأحداث", "فقرة من 4 جمل عن الشوط الثاني والأهداف والبطاقات والتبديلات", "فقرة عن أبرز اللاعبين المذكورين في الأحداث ودورهم"],'
                ' "analysis": ["فقرة من 4 جمل تحلل الإحصائيات (الاستحواذ والتسديدات والتمريرات) وماذا تقول عن أسلوب كل فريق", "فقرة تقارن فاعلية الفريقين الهجومية والدفاعية بالأرقام والتشكيلة"],'
                ' "conclusion": "فقرة ختامية من 3 جمل عن دلالة النتيجة للفريقين دون تخمين ترتيب الدوري",'
                ' "star_en": "عنوان صفحة ويكيبيديا الإنجليزية بالضبط لأبرز لاعب في الفريق الفائز من البيانات (صاحب هدف، أو أشهر لاعب فيه عند التعادل) مثل Erling Haaland، أو فارغ",'
                ' "venue_en": "عنوان صفحة ويكيبيديا الإنجليزية لملعب المباراة إن وُجد في البيانات، أو فارغ"}\n'
                "اجعل التقرير مركزًا بلا حشو أو تكرار. المطلوب أن يكون مجموع النص 300 كلمة على الأقل. إن لم توجد إحصائيات فاترك analysis فارغة وأطل الفقرات الأخرى.\n\n"
                f"البطولة: {league_ar}\nالبيانات: {json.dumps(facts, ensure_ascii=False)}",
                max_tokens=4000,
            )
            data = parse_json(raw)
            if not data.get("title") or not data.get("intro"):
                raise ValueError("مخرجات ناقصة")
            data = Q.proofread(data)
            prose = " ".join([data.get("intro", ""), data.get("conclusion", "")] + list(data.get("paragraphs") or [])
                             + list(data.get("analysis") or []))
            if len(prose.split()) < 230:
                st["reports"].append(fid)  # لا نعيد المحاولة على نفس المباراة حتى لا نستهلك حصة Gemini
                raise ValueError(f"التقرير قصير ({len(prose.split())} كلمة)")
            t = full.get("teams", {})
            g = full.get("goals", {})
            th, ta = t.get("home", {}), t.get("away", {})
            slug = slug_words(f'{th.get("name", "")} vs {ta.get("name", "")} '
                              f'{g.get("home", "")} {g.get("away", "")}', 10)
            title = data["title"].strip()
            home_ar = (data.get("home_ar") or th.get("name") or "").strip()
            away_ar = (data.get("away_ar") or ta.get("name") or "").strip()
            img, credit = match_image(data, slug, fid, title, league_ar, full, home_ar, away_ar)
            body = wrap_article(title, data.get("description") or data.get("intro"), img,
                                report_html(facts, data, league_ar), league_ar, credit)
            if credit:
                body = body.replace('<div class="post-cover"', '<div class="post-cover" data-ph="1"', 1)
            publish(title, body, ["تقارير المباريات", league_ar] + clean_tags([home_ar, away_ar]), slug=slug)
            st["reports"].append(fid)
            Q.day_counts(st)["rep"] += 1
            made += 1
        except Exception as e:
            check_billing(e)
            fails += 1
            print("فشل تقرير", fid, why(e), flush=True)
    print(f"تقارير: {made}")


# ---------- الأخبار ----------
LAST_IMAGE_KIND = ""
def news_image(data, slug, key, ar_title, tags):
    """الأولوية: صورة حرة حقيقية للاعب/المدرب -> شعارا الفريقين -> تصميم الموقع"""
    global LAST_IMAGE_KIND
    import photos
    esc = html.escape
    LAST_IMAGE_KIND = "news"
    kicker = tags[0] if tags else "أخبار كرة القدم"
    date_text = datetime.now(sb.TZ).strftime("%Y-%m-%d")
    name = image_name(slug, key)
    subj = (data.get("photo_subject_en") or "").strip()
    ph = photos.wiki_photo(subj) if subj else None
    if ph:
        img = make_cover("photo", name, title=ar_title, kicker=kicker, date_text=date_text,
                         photo_bytes=ph["bytes"], credit=f'Photo: {ph["credit"]} / {ph["license"]}')
        if img:
            LAST_IMAGE_KIND = "photo"
            credit = (f'الصورة: {esc(ph["credit"])} عبر <a href="{esc(ph["page"])}" rel="nofollow noopener" '
                      f'target="_blank">ويكيميديا كومنز</a> ({esc(ph["license"])})')
            return img, credit
    teams = [t for t in (data.get("teams_en") or []) if isinstance(t, str) and t.strip()][:2]
    teams_ar = [t for t in (data.get("teams_ar") or []) if isinstance(t, str)]
    if len(teams) == 2:
        logos = [photos.team_logo(t, sb.football) for t in teams]
        if all(logos):
            ar_n = teams_ar if len(teams_ar) == 2 else teams
            img = make_cover("teams", name, title=ar_title, kicker=kicker, date_text=date_text,
                             home_name=ar_n[0], away_name=ar_n[1], home_logo=logos[0], away_logo=logos[1])
            if img:
                LAST_IMAGE_KIND = "teams"
                return img, ""
    return make_cover("news", name, title=ar_title, kicker=kicker, date_text=date_text), ""
def run_news():
    st = load()
    seen = set(st["news"])
    try:
        _news_loop(seen, st)
    finally:
        st["news"] = list(seen)
        save(st)
def _collect(seen, recent):
    cands = []
    keys_n = set()
    for feed in sb.NEWS_FEEDS:
        try:
            req = urllib.request.Request(feed, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                root = ET.fromstring(r.read())
        except Exception as e:
            print("فشل الخلاصة", feed, e)
            continue
        for item in root.iter("item"):
            link = (item.findtext("link") or "").strip()
            if not re.match(r"^https?://", link):
                continue
            if "/live/" in link or not re.search(r"football|soccer", link):
                continue
            key = hashlib.md5(Q.norm_link(link).encode()).hexdigest()
            if key in seen or hashlib.md5(link.encode()).hexdigest() in seen or key in keys_n:
                continue
            title = (item.findtext("title") or "").strip()
            desc = re.sub(r"<[^>]+>", "", item.findtext("description") or "").strip()
            if Q.is_dup(title, recent) or any(Q.same_story(title, c[3]) for c in cands):
                seen.add(key)
                continue
            keys_n.add(key)
            if len(desc) < 40:
                seen.add(key)
                continue
            if Q.is_women(title, desc, link):
                seen.add(key)
                continue
            sc = Q.news_score(title, desc)
            if sc < 1:
                continue  # خبر غير مهم: لا نكتب عنه
            cands.append((sc, link, key, title, desc))
    cands.sort(key=lambda c: -c[0])
    return cands
def _news_loop(seen, st):
    made = 0
    dc = Q.day_counts(st)
    cap_live = int(os.environ.get("DAILY_NEWS", "2"))
    cap_draft = int(os.environ.get("DAILY_DRAFTS", "3"))
    per_run = int(os.environ.get("MAX_NEWS", "1"))
    recent = st.setdefault("titles", [])
    cands = _collect(seen, recent)
    print("أخبار مرشحة:", len(cands), flush=True)
    for sc, link, key, title, desc in cands:
        if made >= per_run:
            break
        # المسودات للأهم (درجة 3+ أو الأعلى) وتُنشر يدويًا؛ والباقي ينشر مباشرة
        want_draft = dc["draft"] < cap_draft and (sc >= 3 or dc["pub"] >= cap_live)
        if not want_draft and dc["pub"] >= cap_live:
            break
        if not want_draft and dc["pub"] >= Q.spread_allowed(cap_live):
            break
        if True:
            try:
                src = source_text(link, 7000)
                if len(src or "") < 900:
                    seen.add(key)  # المصدر قصير جدًا لكتابة مقال غني
                    print("تخطي خبر بمصدر قصير:", title, flush=True)
                    continue
                raw = sb.claude(
                    "أنت محرر رياضي عربي محترف في موقع عالم المستديرة. اكتب مقالًا إخباريًا أصليًا بالعربية "
                    "الفصحى المبسطة مركزًا ومباشرًا بلا حشو ولا تكرار بطول 350 إلى 500 كلمة اعتمادًا فقط على المعلومات الموجودة في المصدر أدناه. "
                    "لا تترجم حرفيًا ولا تنسخ الجمل، بل أعد الصياغة بأسلوبك ورتّب المعلومات واشرح السياق للقارئ العربي، "
                    "وممنوع إضافة أي معلومة أو رقم أو تصريح أو تاريخ غير موجود في المصدر. "
                    "استخدم الأسماء العربية المعروفة للأندية واللاعبين.\n"
                    "أعد JSON فقط بهذا الشكل:\n"
                    '{"title": "عنوان واضح للبحث بحدود 60 حرفًا يتضمن الاسم الأبرز",'
                    ' "description": "وصف للبحث بحدود 150 حرفًا",'
                    ' "intro": "فقرة افتتاحية من جملتين تلخص الخبر",'
                    ' "sections": [{"heading": "عنوان فرعي", "paragraphs": ["فقرة", "فقرة"]},'
                    ' {"heading": "عنوان فرعي", "paragraphs": ["فقرة", "فقرة"]},'
                    ' {"heading": "عنوان فرعي عن الخلفية والسياق", "paragraphs": ["فقرة"]},'
                    ' {"heading": "عنوان فرعي عن ما ينتظر الفريق/اللاعب بحسب المصدر", "paragraphs": ["فقرة"]}],'
                    ' "takeaways": ["3 نقاط مختصرة لأهم ما في الخبر"],'
                    ' "tags": ["حتى 3 أسماء أندية أو منتخبات أو بطولات بالعربي"],'
                    ' "photo_subject_en": "عنوان صفحة ويكيبيديا الإنجليزية للاعب أو المدرب الأبرز في الخبر بالضبط مثل Erling Haaland أو فارغ",'
                    ' "teams_en": ["الاسم الإنجليزي للناديين أو المنتخبين إذا كان الخبر عن مواجهة بينهما، وإلا نادٍ واحد أو قائمة فارغة"],'
                    ' "teams_ar": ["نفس الفرق بالعربي وبنفس الترتيب"]}\n\n'
                    f"العنوان: {title}\nالوصف: {desc}\nنص المصدر:\n{src or desc}",
                    max_tokens=3000,
                )
                data = parse_json(raw)
                if not data.get("title") or not data.get("sections"):
                    raise ValueError("مخرجات ناقصة")
                data = Q.proofread(data)
                esc = html.escape
                ar_title = data["title"].strip()
                body = f"<p>{esc(data.get('intro', ''))}</p>" if data.get("intro") else ""
                for sec in data["sections"]:
                    if sec.get("heading"):
                        body += f"<h2>{esc(sec['heading'])}</h2>"
                    body += "".join(f"<p>{esc(p)}</p>" for p in sec.get("paragraphs", []))
                tk = [t for t in (data.get("takeaways") or []) if isinstance(t, str) and t.strip()][:4]
                if tk:
                    body += "<h2>أبرز النقاط</h2><ul>" + "".join(f"<li>{esc(t)}</li>" for t in tk) + "</ul>"
                n_words = len(re.sub(r"<[^>]+>", " ", body).split())
                if n_words < 250:
                    seen.add(key)  # لا نعيد المحاولة على نفس الخبر
                    raise ValueError(f"المقال أقصر من المطلوب ({n_words} كلمة)")
                body += (f'<p><small>المصدر: <a href="{esc(link)}" rel="nofollow noopener" target="_blank">'
                         f"{esc(urllib.parse.urlparse(link).netloc)}</a></small></p>")
                slug = slug_words(title)
                tags = clean_tags(data.get("tags"))
                img, credit = news_image(data, slug, key, ar_title, tags)
                body = wrap_article(ar_title, data.get("description") or data.get("intro"), img, body,
                                    "أخبار كرة القدم", credit)
                if LAST_IMAGE_KIND in ("photo", "teams"):
                    body = body.replace('<div class="post-cover"', '<div class="post-cover" data-ph="1"', 1)
                publish(ar_title, body, ["أخبار كرة القدم"] + tags, slug=slug, draft=want_draft)
                seen.add(key)
                dc["draft" if want_draft else "pub"] += 1
                recent.append(title)
                del recent[:-300]
                made += 1
            except Exception as e:
                check_billing(e)
                print("فشل خبر", why(e), flush=True)
    print(f"أخبار: {made}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    try:
        try:
            sb.blogger_token()  # تحقق من صلاحية Blogger قبل كتابة أي مقال
        except Exception as e:
            check_billing(e)
            raise
        if mode in ("reports", "all"):
            run_reports()
        if mode in ("news", "all"):
            run_news()
    except BillingStop as e:
        print("::error::" + str(e), flush=True)
        sys.exit(1)
