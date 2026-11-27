#!/usr/bin/env python3
"""
صفحات المباريات الكبيرة (سياسة 27 نوفمبر - تعديل المساء):
- بدل مقالات المواعيد: صفحة واحدة لكل مباراة كبيرة (3-5 يوميًا) فيها ودجت مركز المباراة + فقرة فريدة + SportsEvent JSON-LD.
- بعد نهاية المباراة تُحدَّث نفس الصفحة (نفس الرابط) إلى تقرير كامل بأسلوب كووورة وعنوان بصيغة النتيجة.
- لا تُحسب من حد الـ10 مقالات يوميًا.
python match_pages.py        (DRY_RUN=1 للتجربة بدون نشر)
"""
import html
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import sports_bot as sb
import seo_poster as sp
import quality as Q
import previews as pv

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "data", "match_pages_state.json")
DRY = os.environ.get("DRY_RUN", "0") == "1"
SITE = "https://www.fottballcia.com"
esc = html.escape
RUH = ZoneInfo("Asia/Riyadh")

# بطولات المنتخبات (معرفات API-Football) + منتخبات كبيرة
NAT_LEAGUES = {1: "كأس العالم", 4: "كأس أمم أوروبا", 5: "دوري الأمم الأوروبية", 6: "كأس أمم أفريقيا", 7: "كأس آسيا",
               9: "كوبا أمريكا", 32: "تصفيات كأس العالم - أوروبا", 34: "تصفيات كأس العالم - أمريكا الجنوبية",
               29: "تصفيات كأس العالم - أفريقيا", 30: "تصفيات كأس العالم - آسيا"}
NAT_BIG = {"Saudi Arabia", "Egypt", "Morocco", "Algeria", "Tunisia", "Brazil", "Argentina", "France", "Spain", "England",
           "Germany", "Portugal", "Italy", "Netherlands", "Belgium", "Croatia", "Uruguay", "Japan", "South Korea"}
KNOCKOUT_LEAGUES = (2, 12, 17, 3)

# صيغ العناوين (ممنوع: موعد، بث مباشر، مشاهدة، رابط)
TITLES = [
    "مباراة {H} و{A} مباشر | {L}",
    "نتيجة مباراة {H} و{A} لحظة بلحظة",
    "{H} ضد {A}: الأهداف والأحداث مباشرة",
    "متابعة مباراة {H} و{A} أولاً بأول",
    "{H} و{A}: النتيجة وأبرز الأحداث لحظة بلحظة | {L}",
    "تابع مباراة {H} و{A} أولاً بأول | {L}",
]
BAN = re.compile(r"بث مباشر|مشاهدة|روابط|رابط|مواعيد|موعد|(?<![\u0621-\u064A])بث(?![\u0621-\u064A])")


def clean(s):
    if not isinstance(s, str):
        return s
    for a, b in (("بث مباشر", "مباشر"), ("مشاهدة", "متابعة"), ("روابط", "صفحات"), ("رابط", "صفحة"),
                 ("مواعيد", "أوقات"), ("موعد", "توقيت")):
        s = s.replace(a, b)
    return s


def load():
    try:
        with open(STATE, encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    d.setdefault("pages", {})
    d.setdefault("styles", {})
    return d


def save(d):
    d["styles"] = dict(sorted(d["styles"].items())[-6:])
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def widget_html(fid):
    return (f'<div id="mc-root" data-id="{fid}"></div>'
            '<script src="https://nawaf737991-coder.github.io/fottballcia/match.js?v=2"></script>')


def sports_ld(pg, full=None):
    ld = {"@context": "https://schema.org", "@type": "SportsEvent", "sport": "Soccer",
          "name": f'{pg["home_ar"]} ضد {pg["away_ar"]}', "startDate": pg["kickoff"],
          "eventStatus": "https://schema.org/EventScheduled",
          "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
          "homeTeam": {"@type": "SportsTeam", "name": pg["home_ar"]},
          "awayTeam": {"@type": "SportsTeam", "name": pg["away_ar"]},
          "competitor": [{"@type": "SportsTeam", "name": pg["home_ar"]}, {"@type": "SportsTeam", "name": pg["away_ar"]}],
          "superEvent": {"@type": "SportsEvent", "name": pg["league_ar"]},
          "description": pg.get("description") or f'{pg["home_ar"]} ضد {pg["away_ar"]} في {pg["league_ar"]}',
          "inLanguage": "ar"}
    if pg.get("venue"):
        loc = {"@type": "Place", "name": pg["venue"]}
        if pg.get("city"):
            loc["address"] = {"@type": "PostalAddress", "addressLocality": pg["city"]}
        ld["location"] = loc
    if pg.get("img"):
        ld["image"] = [pg["img"]]
    return '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>"


def hide_cover(body):
    """الودجت يعرض الفريقين أصلًا؛ نُبقي الصورة في الكود للمشاركة والمصغّرات فقط"""
    return body.replace('<div class="post-cover" style="margin:0 0 16px">', '<div class="post-cover" data-ph="1" style="display:none">', 1)


def fix_covers(ps):
    for fid, pg in ps["pages"].items():
        if pg.get("final") or pg.get("hc") or not pg.get("post_id"):
            continue
        try:
            post = sb.blogger(f"/posts/{pg['post_id']}")
            body = hide_cover(post.get("content", ""))
            if body != post.get("content", "") and not DRY:
                sb.blogger(f"/posts/{pg['post_id']}", "PATCH", {"content": body})
            pg["hc"] = True
            print("أُخفيت الصورة المكررة:", fid, flush=True)
        except Exception as e:
            print("تعذر تعديل الصفحة", fid, sp.why(e), flush=True)


def links_html(pg):
    out = [f'<a href="{SITE}/p/match.html?id={pg["fid"]}">مركز المباراة</a>']
    slug = sp.TABLE_SLUG.get(pg["league_id"])
    if slug:
        out.append(f'<a href="{SITE}/p/{slug}.html">ترتيب {esc(pg["league_ar"])}</a>')
    out.append(f'<a href="{SITE}/p/matches-today.html">مباريات اليوم ونتائجها</a>')
    return "<p>" + " · ".join(out) + "</p>"


# ---------- اختيار المباريات الكبيرة ----------
def score(f, tbl):
    lid = f["league"]["id"]
    h, a = f["teams"]["home"]["name"], f["teams"]["away"]["name"]
    if lid in NAT_LEAGUES:
        s = 55 + 20 * ((h in NAT_BIG) + (a in NAT_BIG)) + (15 if h in NAT_BIG and a in NAT_BIG else 0)
        return s
    if lid not in pv.WEIGHT:
        return 0
    s = pv.importance(f, tbl)
    rnd = (f["league"].get("round") or "").lower()
    if lid in KNOCKOUT_LEAGUES and rnd and not any(k in rnd for k in ("league stage", "group", "regular")):
        s += 25
    return s


def eng(n):
    n = unicodedata.normalize("NFKD", n or "").encode("ascii", "ignore").decode().lower()
    n = re.sub(r"\b(fc|cf|sc|ac|as|fk|sk|club|saudi|de|football)\b", " ", n)
    n = re.sub(r"\bal[- ]", "al", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return "-".join(n.split()[:2]) or "team"


def pick_style(ps, today, n_used_today):
    used_today = ps["styles"].setdefault(today, [])
    prev = [k for k in sorted(ps["styles"]) if k < today]
    yest = set(ps["styles"][prev[-1]]) if prev else set()
    pool = [i for i in range(len(TITLES)) if i not in yest and i not in used_today] \
        or [i for i in range(len(TITLES)) if i not in used_today] or list(range(len(TITLES)))
    i = pool[n_used_today % len(pool)]
    used_today.append(i)
    return i


def facts_for(f, tbl):
    lid = f["league"]["id"]
    h, a = f["teams"]["home"], f["teams"]["away"]
    rows = tbl.get(lid, {})
    sc = []
    try:
        for l in json.load(open(os.path.join(ROOT, "data", "tables.json"), encoding="utf-8"))["leagues"]:
            if l["id"] == lid:
                sc = l.get("scorers") or []
    except Exception:
        pass
    star = lambda t: next(({"name": x["n"], "goals": x["g"], "assists": x["a"]} for x in sc if x["t"] == t), None)
    last = None
    try:
        r = sb.football("fixtures/headtohead", h2h=f'{h["id"]}-{a["id"]}', last=1)
        if r:
            x = r[0]
            last = {"date": x["fixture"]["date"][:10], "league": x["league"]["name"], "home": x["teams"]["home"]["name"],
                    "away": x["teams"]["away"]["name"], "score": f'{x["goals"]["home"]}-{x["goals"]["away"]}'}
    except Exception as e:
        print("تعذر جلب آخر مواجهة:", sp.why(e), flush=True)
    return {"league": pv.LEAGUE_AR.get(lid) or NAT_LEAGUES.get(lid) or f["league"]["name"],
            "round": pv.round_ar(f["league"].get("round")), "venue": (f["fixture"].get("venue") or {}).get("name"),
            "city": (f["fixture"].get("venue") or {}).get("city"),
            "home": h["name"], "away": a["name"],
            "home_standing": rows.get(h["name"]), "away_standing": rows.get(a["name"]),
            "last_meeting": last, "home_top_scorer": star(h["name"]), "away_top_scorer": star(a["name"])}


def write_paragraph(facts):
    nm = pv.names()
    hint = {k: nm[k] for k in (facts["home"], facts["away"]) if k in nm}
    feedback = ""
    for attempt in range(3):
        raw = sb.claude(
            "أنت محرر رياضي عربي في موقع عالم المستديرة. اكتب فقرة واحدة فريدة بالعربي الفصيح المبسط عن مباراة كبيرة، "
            "طولها من 170 إلى 230 كلمة بالضبط تقريبًا، تتناول: أهمية المباراة، وترتيب الفريقين في الجدول (إن وُجد في البيانات)، "
            "وآخر مواجهة بينهما (إن وُجدت)، واللاعب المنتظر (من هداف الفريق في البيانات فقط). "
            "اعتمد فقط على البيانات أدناه، وممنوع اختراع أي معلومة أو رقم أو تاريخ أو تشكيلة أو توقع للنتيجة. "
            "ممنوع منعًا باتًا استخدام الكلمات: موعد، مواعيد، بث، مشاهدة، رابط، قناة. لا تذكر القنوات الناقلة.\n"
            "أعد JSON فقط: {\"home_ar\": \"اسم المضيف بالعربي\", \"away_ar\": \"اسم الضيف بالعربي\", "
            "\"description\": \"وصف للبحث بحدود 150 حرفًا\", \"paragraph\": \"الفقرة\"}\n"
            f"أسماء عربية معروفة: {json.dumps(hint, ensure_ascii=False)}\n{feedback}\n"
            f"البيانات: {json.dumps(facts, ensure_ascii=False)}", max_tokens=2500)
        try:
            d = sp.parse_json(raw)
            d = Q.proofread({k: d[k] for k in ("home_ar", "away_ar", "description", "paragraph")})
        except Exception as e:
            print("مخرجات غير صالحة:", str(e)[:100], flush=True)
            continue
        n = len(d["paragraph"].split())
        if BAN.search(d["paragraph"]) or BAN.search(d["description"]):
            d["paragraph"], d["description"] = clean(d["paragraph"]), clean(d["description"])
        if 150 <= n <= 250:
            return d
        feedback = f"المحاولة السابقة كانت {n} كلمة؛ المطلوب بين 170 و230 كلمة."
    raise ValueError("تعذر كتابة فقرة بطول 150-250 كلمة")


def create_page(f, tbl, ps, st, n_today):
    fid = f["fixture"]["id"]
    facts = facts_for(f, tbl)
    d = write_paragraph(facts)
    nm = pv.names()
    fa = str.maketrans({"چ": "تش", "پ": "ب", "گ": "ج", "ژ": "ج", "ی": "ي", "ک": "ك"})
    H = (nm.get(facts["home"]) or d.get("home_ar") or facts["home"]).translate(fa).strip()
    A = (nm.get(facts["away"]) or d.get("away_ar") or facts["away"]).translate(fa).strip()
    today = datetime.now(RUH).strftime("%Y-%m-%d")
    si = pick_style(ps, today, n_today)
    title = clean(TITLES[si].format(H=H, A=A, L=facts["league"]))
    slug = f'{eng(facts["home"])} vs {eng(facts["away"])} live'
    used = {p.get("slug") for p in ps["pages"].values()}
    if slug in used:
        slug += " " + datetime.fromisoformat(f["fixture"]["date"]).astimezone(RUH).strftime("%m%d")
    ko = datetime.fromisoformat(f["fixture"]["date"]).astimezone(RUH)
    pg = {"fid": fid, "home_ar": H, "away_ar": A, "league_id": f["league"]["id"], "league_ar": facts["league"],
          "kickoff": ko.isoformat(timespec="minutes"), "venue": facts["venue"], "city": facts["city"],
          "description": d["description"], "slug": slug, "style": si, "title": title, "final": False,
          "created": datetime.now(RUH).isoformat(timespec="minutes")}
    name = sp.image_name(slug, f"pg{fid}")
    img = sp.make_cover("teams", name, title=title, kicker=facts["league"],
                        date_text=f"{pv.DAYS[ko.weekday()]} {ko.day} {pv.MONTHS[ko.month - 1]}",
                        home_name=H, away_name=A, home_logo=f["teams"]["home"].get("logo"), away_logo=f["teams"]["away"].get("logo"))
    pg["img"] = img
    body = (widget_html(fid)
            + f"<h2>أهمية المباراة</h2><p>{esc(d['paragraph'])}</p>"
            + links_html(pg) + sports_ld(pg))
    full = sp.wrap_article(title, d["description"], img, body, "صفحات المباريات")
    full = hide_cover(full)
    pg["hc"] = True
    labels = ["صفحات المباريات", facts["league"]] + sp.clean_tags([H, A])
    if DRY:
        print("=== DRY ===", title, "|", slug, "|", len(d["paragraph"].split()), "كلمة")
        print(d["paragraph"])
        return
    sp.publish(title, full, labels, slug=slug, draft=False)
    post = sp._last["post"]
    pg["post_id"], pg["url"] = post["id"], post.get("url", "")
    ps["pages"][str(fid)] = pg
    st.setdefault("report_posts", {})[str(fid)] = post["id"]  # لإضافة التغريدات والفيديو لاحقًا
    print("صفحة مباراة:", title, pg["url"], flush=True)


def create_pages(ps, st):
    now = datetime.now(RUH)
    tbl = pv.tables()
    fx = []
    for d in (now, now + timedelta(days=1)):
        try:
            fx += sb.football("fixtures", date=d.strftime("%Y-%m-%d"), timezone="Asia/Riyadh")
        except Exception as e:
            print("تعذر جلب المباريات:", sp.why(e), flush=True)
    by_day = {}
    for f in fx:
        if f["fixture"]["status"]["short"] not in ("NS", "TBD") or str(f["fixture"]["id"]) in ps["pages"]:
            continue
        if Q.is_women(f["teams"]["home"]["name"], f["teams"]["away"]["name"], f["league"].get("name")):
            continue
        ko = datetime.fromisoformat(f["fixture"]["date"]).astimezone(RUH)
        hrs = (ko - now).total_seconds() / 3600
        if not (0.5 <= hrs <= 30):
            continue
        s = score(f, tbl)
        if s >= 80:
            by_day.setdefault(ko.strftime("%Y-%m-%d"), []).append((s, f))
    cap = int(os.environ.get("PAGES_MAX_DAY", "5"))
    want_min = int(os.environ.get("PAGES_MIN_DAY", "3"))
    thr = int(os.environ.get("MIN_PAGE", "95"))
    todo = []
    for day, lst in sorted(by_day.items()):
        lst.sort(key=lambda x: -x[0])
        have = sum(1 for p in ps["pages"].values() if p["kickoff"][:10] == day)
        strong = [x for x in lst if x[0] >= thr]
        pick = strong[:max(0, cap - have)]
        if have + len(pick) < want_min:
            pick += [x for x in lst if x not in pick][:want_min - have - len(pick)]
        todo += pick
    print("صفحات مرشحة:", [(s, f["teams"]["home"]["name"], f["teams"]["away"]["name"]) for s, f in todo], flush=True)
    made = 0
    today = now.strftime("%Y-%m-%d")
    for s, f in todo:
        if made >= int(os.environ.get("PAGES_PER_RUN", "2")):
            break
        try:
            create_page(f, tbl, ps, st, len(ps["styles"].get(today, [])))
            made += 1
        except Exception as e:
            sp.check_billing(e)
            print("فشل إنشاء صفحة", f["fixture"]["id"], sp.why(e), flush=True)
    print("صفحات جديدة:", made)


def finish_pages(ps, st):
    """بعد نهاية المباراة: تحديث نفس الصفحة إلى تقرير كامل"""
    now = datetime.now(RUH)
    cands = []
    for fid, pg in ps["pages"].items():
        if pg.get("final") or pg.get("dead"):
            continue
        ko = datetime.fromisoformat(pg["kickoff"])
        if now < ko + timedelta(minutes=105):
            continue
        try:
            full = sb.football("fixtures", id=int(fid))[0]
        except Exception as e:
            print("تعذر جلب المباراة", fid, sp.why(e), flush=True)
            continue
        s = full["fixture"]["status"]["short"]
        if s in sp.FINISHED:
            cands.append(full)
        elif s in ("PST", "CANC", "ABD", "AWD", "WO") or now > ko + timedelta(hours=8):
            pg["dead"] = True
            print("مباراة مؤجلة/ملغاة:", fid, s, flush=True)
    print("صفحات جاهزة للتحويل إلى تقرير:", len(cands), flush=True)
    if cands:
        sp._reports_loop(st, cands, 3, pages=ps["pages"])


def main():
    ps, st = load(), sp.load()
    try:
        sb.blogger_token()
        fix_covers(ps)
        create_pages(ps, st)
        finish_pages(ps, st)
    except sp.BillingStop as e:
        print("::error::" + str(e), flush=True)
        sys.exit(1)
    finally:
        if not DRY:
            save(ps)
            sp.save(st)


if __name__ == "__main__":
    main()
