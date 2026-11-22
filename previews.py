#!/usr/bin/env python3
"""
مقالات ما قبل المباريات الكبيرة: الموعد + القنوات الناقلة + التشكيلة المتوقعة + الغيابات + التوقع.
python previews.py         -> ينشر مقالات للمباريات الكبيرة القادمة (خلال 6-40 ساعة)
                              ويحدّث المقالات المنشورة بالتشكيلة الرسمية عند إعلانها (قبل المباراة بساعة تقريبًا)
متغيرات: MAX_PREVIEWS (الافتراضي 2 لكل تشغيل)، DAILY_PREVIEWS (الافتراضي 6 في اليوم)، DRY_RUN=1
"""
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import sports_bot as sb
import seo_poster as sp

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "data", "previews_state.json")
DRY = os.environ.get("DRY_RUN", "0") == "1"
esc = html.escape

# وزن البطولة في اختيار "المباراة الكبيرة"
WEIGHT = {307: 50, 2: 48, 39: 45, 140: 42, 17: 40, 135: 35, 78: 33, 61: 30, 3: 25, 848: 15, 1: 50}
LEAGUE_AR = {k: v for k, v in sp.LEAGUES.items()}
TV = {
    307: ["ثمانية"],
    39: ["beIN SPORTS"], 140: ["beIN SPORTS"], 61: ["beIN SPORTS"],
    2: ["beIN SPORTS"], 3: ["beIN SPORTS"], 848: ["beIN SPORTS"],
    135: ["STARZPLAY", "أبوظبي الرياضية", "stc tv (السعودية)"],
    78: ["MBC أكشن", "شاهد"],
    17: ["beIN SPORTS", "الكأس"],
}
BIG = {
    "Al-Hilal Saudi FC", "Al-Nassr", "Al-Ittihad FC", "Al-Ahli Jeddah", "Al-Qadisiyah FC", "Al Shabab",
    "Real Madrid", "Barcelona", "Atletico Madrid", "Manchester City", "Arsenal", "Liverpool", "Chelsea",
    "Manchester United", "Tottenham", "Bayern München", "Borussia Dortmund", "Bayer Leverkusen",
    "Paris Saint Germain", "Marseille", "Inter", "AC Milan", "Juventus", "Napoli", "AS Roma",
}
ZONES = [("السعودية", "Asia/Riyadh"), ("الإمارات", "Asia/Dubai"), ("مصر", "Africa/Cairo"), ("المغرب", "Africa/Casablanca")]
DAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
HMONTHS = ["محرم", "صفر", "ربيع الأول", "ربيع الآخر", "جمادى الأولى", "جمادى الآخرة", "رجب", "شعبان",
           "رمضان", "شوال", "ذو القعدة", "ذو الحجة"]


def load():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"posts": []}


def save(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    st["posts"] = st["posts"][-600:]
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def ar_date(d):
    s = f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d.year}"
    try:
        from hijridate import Gregorian
        h = Gregorian(d.year, d.month, d.day).to_hijri()
        s += f" ({h.day} {HMONTHS[h.month - 1]} {h.year} هـ)"
    except Exception:
        pass
    return s


def round_ar(r):
    if not r:
        return ""
    m = re.search(r"(\d+)\s*$", r)
    n = m.group(1) if m else ""
    for en, ar in (("Regular Season", "الجولة"), ("League Stage", "مرحلة الدوري - الجولة"), ("Group", "دور المجموعات - الجولة"),
                   ("Round of 16", "دور الـ16"), ("Quarter-finals", "ربع النهائي"), ("Semi-finals", "نصف النهائي"), ("Final", "النهائي")):
        if r.startswith(en):
            return (ar + " " + n).strip() if ar.endswith("الجولة") else ar
    return r


def hm(d):
    return d.strftime("%H:%M")


# ---------- البيانات ----------
def tables():
    out = {}
    try:
        with open(os.path.join(ROOT, "data", "tables.json"), encoding="utf-8") as f:
            for lg in json.load(f).get("leagues", []):
                out[lg["id"]] = {r["t"]: r for r in lg.get("table", [])}
    except Exception as e:
        print("تعذر قراءة جدول الترتيب:", e)
    return out


def names():
    try:
        with open(os.path.join(ROOT, "data", "names_cache.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def importance(f, tbl):
    lid = f["league"]["id"]
    s = WEIGHT.get(lid, 0)
    h, a = f["teams"]["home"]["name"], f["teams"]["away"]["name"]
    rows = tbl.get(lid, {})
    rh, ra = (rows.get(h) or {}).get("r"), (rows.get(a) or {}).get("r")
    if rh and ra:
        if rh <= 6 and ra <= 6:
            s += 35
        elif min(rh, ra) <= 3:
            s += 10
    s += 20 * ((h in BIG) + (a in BIG)) + (15 if (h in BIG and a in BIG) else 0)
    return s


def candidates(st):
    now = datetime.now(sb.TZ)
    done = {p["fid"] for p in st["posts"]}
    tbl = tables()
    fx = []
    for d in (now, now + timedelta(days=1), now + timedelta(days=2)):
        try:
            fx += sb.football("fixtures", date=d.strftime("%Y-%m-%d"), timezone="Asia/Riyadh")
        except Exception as e:
            print("تعذر جلب المباريات:", sp.why(e))
    out = []
    for f in fx:
        if f["league"]["id"] not in WEIGHT or f["fixture"]["status"]["short"] not in ("NS", "TBD"):
            continue
        if f["fixture"]["id"] in done:
            continue
        ko = datetime.fromisoformat(f["fixture"]["date"])
        hours = (ko - now).total_seconds() / 3600
        if not (5 <= hours <= 40):
            continue
        sc = importance(f, tbl)
        if sc >= 70:  # مباراة كبيرة فقط
            out.append((sc, f))
    out.sort(key=lambda x: -x[0])
    print("مباريات كبيرة مرشحة:", [(s, f["teams"]["home"]["name"], f["teams"]["away"]["name"]) for s, f in out][:10])
    return [f for _, f in out], tbl


def last_lineup(team_id):
    """تشكيلة الفريق في آخر مباراة رسمية (أساس التشكيلة المتوقعة)"""
    try:
        last = sb.football("fixtures", team=team_id, last=1)
        if not last:
            return None
        lf = last[0]
        res = sb.football("fixtures/lineups", fixture=lf["fixture"]["id"])
        for t in res:
            if (t.get("team") or {}).get("id") == team_id:
                return {
                    "formation": t.get("formation"),
                    "coach": (t.get("coach") or {}).get("name"),
                    "xi": [(x.get("player") or {}).get("name") for x in t.get("startXI") or []],
                    "subs": [(x.get("player") or {}).get("name") for x in (t.get("substitutes") or [])[:7]],
                    "from": f'{lf["teams"]["home"]["name"]} {lf["goals"]["home"]}-{lf["goals"]["away"]} {lf["teams"]["away"]["name"]}',
                }
    except Exception as e:
        print("تعذر جلب آخر تشكيلة:", sp.why(e))
    return None


def injuries(fid):
    try:
        return [{"team": (i.get("team") or {}).get("name"), "player": (i.get("player") or {}).get("name"),
                 "type": (i.get("player") or {}).get("type"), "reason": (i.get("player") or {}).get("reason")}
                for i in sb.football("injuries", fixture=fid)]
    except Exception as e:
        print("تعذر جلب الغيابات:", sp.why(e))
        return []


def prediction(fid):
    try:
        r = sb.football("predictions", fixture=fid)
        return r[0] if r else {}
    except Exception as e:
        print("تعذر جلب التوقع:", sp.why(e))
        return {}


def expected_xi(lu, out_names):
    """نستبعد المصابين/الموقوفين من آخر تشكيلة ونكمل من البدلاء"""
    if not lu or len([p for p in lu["xi"] if p]) < 11:
        return None
    xi = [p for p in lu["xi"] if p and p not in out_names]
    subs = [p for p in lu["subs"] if p and p not in out_names and p not in xi]
    while len(xi) < 11 and subs:
        xi.append(subs.pop(0))
    return xi


# ---------- المقال ----------
def collect(f, tbl):
    fid = f["fixture"]["id"]
    lid = f["league"]["id"]
    h, a = f["teams"]["home"], f["teams"]["away"]
    pred = prediction(fid)
    inj = injuries(fid)
    out_h = {i["player"] for i in inj if i["team"] == h["name"] and i["type"] == "Missing Fixture"}
    out_a = {i["player"] for i in inj if i["team"] == a["name"] and i["type"] == "Missing Fixture"}
    lh, la = last_lineup(h["id"]), last_lineup(a["id"])
    p = pred.get("predictions") or {}
    tp = pred.get("teams") or {}
    h2h = []
    for x in (pred.get("h2h") or [])[:5]:
        try:
            h2h.append({"date": x["fixture"]["date"][:10], "league": x["league"]["name"],
                        "home": x["teams"]["home"]["name"], "away": x["teams"]["away"]["name"],
                        "score": f'{x["goals"]["home"]}-{x["goals"]["away"]}'})
        except Exception:
            pass
    rows = tbl.get(lid, {})
    return {
        "fid": fid, "league_id": lid, "league": LEAGUE_AR.get(lid, f["league"]["name"]),
        "round": round_ar(f["league"].get("round")), "kickoff": f["fixture"]["date"],
        "venue": (f["fixture"].get("venue") or {}).get("name"), "city": (f["fixture"].get("venue") or {}).get("city"),
        "referee": f["fixture"].get("referee"),
        "home": h["name"], "away": a["name"], "home_logo": h.get("logo"), "away_logo": a.get("logo"),
        "home_table": rows.get(h["name"]), "away_table": rows.get(a["name"]),
        "home_form": ((tp.get("home") or {}).get("league") or {}).get("form", "")[-5:] or (rows.get(h["name"]) or {}).get("f"),
        "away_form": ((tp.get("away") or {}).get("league") or {}).get("form", "")[-5:] or (rows.get(a["name"]) or {}).get("f"),
        "home_last5": (tp.get("home") or {}).get("last_5"), "away_last5": (tp.get("away") or {}).get("last_5"),
        "percent": p.get("percent"),
        "comparison": {k: v for k, v in (pred.get("comparison") or {}).items() if k in ("form", "att", "def", "h2h", "total")},
        "h2h": h2h, "injuries": inj,
        "home_lineup": lh, "away_lineup": la,
        "home_xi": expected_xi(lh, out_h), "away_xi": expected_xi(la, out_a),
    }


def write(facts):
    nm = names()
    hint = {k: nm[k] for k in (facts["home"], facts["away"]) if k in nm}
    players = []
    for k in ("home_xi", "away_xi"):
        players += facts.get(k) or []
    players += [i["player"] for i in facts["injuries"] if i.get("player")]
    for k in ("home_lineup", "away_lineup"):
        if (facts.get(k) or {}).get("coach"):
            players.append(facts[k]["coach"])
    players += [x for x in (facts.get("venue"), facts.get("city"), facts.get("referee")) if x]
    small = {k: v for k, v in facts.items() if k not in ("home_lineup", "away_lineup")}
    raw = sb.claude(
        "أنت محرر رياضي عربي محترف. اكتب مقالًا تمهيديًا قبل مباراة كبيرة بالعربي الفصيح المبسط اعتمادًا فقط على "
        "البيانات التالية. اكتب كل أسماء اللاعبين والمدربين بالعربي داخل الفقرات (لا تكتب أي اسم بحروف إنجليزية)، "
        "وممنوع تمامًا ذكر المراهنات أو الرهان أو الاحتمالات المالية. ممنوع اختراع أي رقم أو نتيجة أو اسم أو خبر غير موجود فيها. التشكيلة المتوقعة مبنية على آخر "
        "مباراة مع استبعاد الغائبين، فاذكر ذلك بصيغة التوقع لا الجزم. التوقع النهائي رأي تحريري مبني على الأرقام.\n"
        f"أسماء عربية معتمدة للفرق: {json.dumps(hint, ensure_ascii=False)}\n"
        "أعد JSON فقط بهذا الشكل:\n"
        '{"home_ar": "اسم المضيف بالعربي", "away_ar": "اسم الضيف بالعربي",'
        ' "description": "وصف للبحث بحدود 150 حرفًا يذكر الموعد والقنوات والتشكيلة",'
        ' "intro": "مقدمة من 3 جمل: الفريقان والبطولة والجولة والملعب وأهمية المباراة",'
        ' "form": ["فقرة من 4 جمل عن حالة المضيف (الترتيب والنقاط وآخر النتائج)", "فقرة مماثلة عن الضيف"],'
        ' "h2h": "فقرة عن تاريخ المواجهات الأخيرة إن وجدت، أو فارغ",'
        ' "absences": "فقرة عن الغيابات وأثرها، أو فارغ إن لم توجد",'
        ' "keys": "فقرة عن مفاتيح المباراة والأسلوب المتوقع لكل مدرب بناءً على الأرقام",'
        ' "prediction": "فقرة من 3 جمل تشرح التوقع مع نسب الفوز إن وجدت",'
        ' "predicted_score": "نتيجة متوقعة مثل 2-1 (المضيف-الضيف)",'
        ' "players_ar": {"الاسم الإنجليزي كما هو": "الاسم العربي المعروف"},'
        ' "star_en": "عنوان صفحة ويكيبيديا الإنجليزية لأشهر لاعب في المباراة من التشكيلات، أو فارغ"}\n'
        "ترجم في players_ar كل هذه الأسماء: " + json.dumps(players, ensure_ascii=False) + "\n"
        "المجموع 380 كلمة على الأقل.\n\nالبيانات: " + json.dumps(small, ensure_ascii=False),
        max_tokens=5000,
    )
    data = sp.parse_json(raw)
    pa = {k: v for k, v in (data.get("players_ar") or {}).items() if isinstance(k, str) and isinstance(v, str) and k and v}
    data["players_ar"] = pa
    keys = sorted(pa, key=len, reverse=True)

    def fix(t):
        if not isinstance(t, str):
            return t
        for k in keys:
            t = t.replace(k, pa[k])
        return re.sub(r"\s*(نصيحة|رهان|المراهنات?)[^.،]*", "", t) if re.search("رهان|مراهن", t) else t
    for k, v in list(data.items()):
        if k == "players_ar":
            continue
        data[k] = [fix(x) for x in v] if isinstance(v, list) else fix(v)
    return data


def lineup_block(facts, data, official=None):
    pa = data.get("players_ar") or {}
    tr = lambda n: pa.get(n) or n
    H, A = data["home_ar"], data["away_ar"]
    parts = ['<div data-lu="1">']
    if official:
        parts.append("<h2>التشكيلة الرسمية</h2>")
        parts.append(f'<p>أعلن الفريقان التشكيلة الأساسية قبل انطلاق المباراة (تحديث {datetime.now(sb.TZ).strftime("%H:%M")} بتوقيت السعودية):</p>')
        teams = official
    else:
        parts.append("<h2>التشكيلة المتوقعة</h2>")
        parts.append("<p>التشكيلة المتوقعة مبنية على آخر مباراة لكل فريق بعد استبعاد الغائبين، "
                     "وسنحدّثها هنا بالتشكيلة الرسمية فور إعلانها قبل المباراة بساعة تقريبًا.</p>")
        teams = []
        for side, name in (("home", H), ("away", A)):
            lu = facts.get(f"{side}_lineup") or {}
            teams.append({"name": name, "formation": lu.get("formation"), "coach": lu.get("coach"),
                          "xi": facts.get(f"{side}_xi")})
    for t in teams:
        if not t.get("xi"):
            parts.append(f"<p><strong>{esc(t['name'])}</strong>: لم تتوفر بيانات كافية بعد.</p>")
            continue
        head = t["name"] + (f" ({t['formation']})" if t.get("formation") else "")
        if t.get("coach"):
            head += f" - المدرب: {tr(t['coach'])}"
        parts.append(f"<p><strong>{esc(head)}</strong>: {esc('، '.join(tr(n) for n in t['xi'] if n))}</p>")
    parts.append('<div data-lu-end="1"></div></div>')
    return "\n".join(parts)


def body_html(facts, data):
    pa = data.get("players_ar") or {}
    tr = lambda n: pa.get(n) or n
    H, A = data["home_ar"], data["away_ar"]
    ko = datetime.fromisoformat(facts["kickoff"])
    ch = TV.get(facts["league_id"])
    p = [f"<p>{esc(data['intro'])}</p>", "<h2>موعد المباراة والقنوات الناقلة</h2>"]
    rows = [("المباراة", f"{H} × {A}"), ("البطولة", facts["league"] + (f" - {facts['round']}" if facts.get("round") else "")),
            ("التاريخ", ar_date(ko.astimezone(ZoneInfo("Asia/Riyadh"))))]
    rows.append(("التوقيت", " | ".join(f"{hm(ko.astimezone(ZoneInfo(z)))} {n}" for n, z in ZONES)))
    if facts.get("venue"):
        rows.append(("الملعب", tr(facts["venue"]) + (f"، {tr(facts['city'])}" if facts.get("city") else "")))
    if facts.get("referee"):
        rows.append(("الحكم", tr(facts["referee"])))
    if ch:
        rows.append(("القنوات الناقلة", "، ".join(ch) + " (حقوق البث في الشرق الأوسط وشمال أفريقيا)"))
    p.append('<table style="width:100%;border-collapse:collapse">' + "".join(
        f'<tr><th style="padding:7px;border-bottom:1px solid #e5e5e5;text-align:right;white-space:nowrap">{esc(k)}</th>'
        f'<td style="padding:7px;border-bottom:1px solid #e5e5e5">{esc(v)}</td></tr>' for k, v in rows) + "</table>")
    p.append("<h2>حالة الفريقين قبل المواجهة</h2>")
    p += [f"<p>{esc(x)}</p>" for x in data.get("form") or []]
    if facts["h2h"] and data.get("h2h"):
        p.append("<h2>تاريخ المواجهات الأخيرة</h2>")
        p.append(f"<p>{esc(data['h2h'])}</p><ul>")
        nm = {facts["home"]: H, facts["away"]: A}
        for x in facts["h2h"]:
            p.append(f"<li>{esc(x['date'])}: {esc(nm.get(x['home'], x['home']))} {esc(x['score'])} {esc(nm.get(x['away'], x['away']))}</li>")
        p.append("</ul>")
    inj = [i for i in facts["injuries"] if i.get("player")]
    if inj:
        p.append("<h2>الغيابات</h2>")
        if data.get("absences"):
            p.append(f"<p>{esc(data['absences'])}</p>")
        nm = {facts["home"]: H, facts["away"]: A}
        p.append("<ul>" + "".join(
            f"<li>{esc(tr(i['player']))} ({esc(nm.get(i['team'], i['team'] or ''))})"
            + (" - مشكوك في مشاركته" if i.get("type") == "Questionable" else "") + "</li>" for i in inj[:14]) + "</ul>")
    p.append(lineup_block(facts, data))
    if data.get("keys"):
        p.append("<h2>مفاتيح المباراة</h2>")
        p.append(f"<p>{esc(data['keys'])}</p>")
    p.append("<h2>توقعنا للمباراة</h2>")
    pc = facts.get("percent") or {}
    if pc.get("home"):
        p.append(f"<p><strong>نسب الفوز حسب الأرقام:</strong> {esc(H)} {esc(pc['home'])} - التعادل {esc(pc.get('draw', ''))} - {esc(A)} {esc(pc.get('away', ''))}</p>")
    if data.get("prediction"):
        p.append(f"<p>{esc(data['prediction'])}</p>")
    if data.get("predicted_score"):
        p.append(f"<p><strong>النتيجة المتوقعة:</strong> {esc(H)} {esc(data['predicted_score'])} {esc(A)}</p>")
    p.append("<p><small>التوقعات رأي تحريري مبني على الأرقام وليست نتيجة مؤكدة. تابع المباراة مباشرة بالأحداث "
             "والنتيجة لحظة بلحظة على الصفحة الرئيسية لعالم المستديرة.</small></p>")
    return "\n".join(p)


def publish_preview(f, tbl, st):
    facts = collect(f, tbl)
    data = write(facts)
    nm = names()
    data["home_ar"] = (data.get("home_ar") or nm.get(facts["home"]) or facts["home"]).strip()
    data["away_ar"] = (data.get("away_ar") or nm.get(facts["away"]) or facts["away"]).strip()
    if not data.get("intro"):
        raise ValueError("مخرجات ناقصة")
    H, A = data["home_ar"], data["away_ar"]
    title = f"موعد مباراة {H} و{A} والقنوات الناقلة والتشكيلة المتوقعة"
    body = body_html(facts, data)
    words = len(re.sub(r"<[^>]+>", " ", body).split())
    if words < 300:
        raise ValueError(f"المقال قصير ({words} كلمة)")
    ko = datetime.fromisoformat(facts["kickoff"]).astimezone(ZoneInfo("Asia/Riyadh"))
    slug = sp.slug_words(f'{facts["home"]} vs {facts["away"]} preview lineup prediction', 10)
    name = sp.image_name(slug, f"pre{facts['fid']}")
    img = sp.make_cover("teams", name, title=f"{H} × {A}: الموعد والقنوات والتشكيلة المتوقعة",
                        kicker=facts["league"], date_text=f"{DAYS[ko.weekday()]} {ko.day} {MONTHS[ko.month - 1]} - {hm(ko)}",
                        home_name=H, away_name=A, home_logo=facts["home_logo"], away_logo=facts["away_logo"])
    desc = data.get("description") or data["intro"]
    full = sp.wrap_article(title, desc, img, body, "ما قبل المباريات")
    if img:
        full = full.replace('<div class="post-cover"', '<div class="post-cover" data-ph="1"', 1)
    labels = ["ما قبل المباريات", facts["league"]] + sp.clean_tags([H, A])
    if DRY:
        print("=== DRY ===", title, slug, labels, f"{words} كلمة")
        with open("/tmp/preview_dry.html", "w", encoding="utf-8") as fh:
            fh.write(full)
        st["posts"].append({"fid": facts["fid"], "post_id": None, "kickoff": facts["kickoff"], "dry": True})
        return
    first = slug if (slug and not sp.DRAFT) else title
    post = sb.publish(first, full, labels, draft=sp.DRAFT)
    if first != title:
        for _ in range(3):
            try:
                sb.blogger(f"/posts/{post['id']}", "PATCH", {"title": title})
                break
            except Exception as e:
                print("تعذر تحديث العنوان:", sp.why(e))
                time.sleep(5)
    print("نُشر:", title, post.get("url", ""), flush=True)
    tw = None
    try:
        import x_post
        text = x_post.preview_text(H, A, facts["league"], hm(ko), TV.get(facts["league_id"]), post.get("url", ""))
        today = datetime.now(sb.TZ).strftime("%Y-%m-%d")
        sent = sum(1 for e in st["posts"] if e.get("tweet_id") and (e.get("published") or "").startswith(today))
        if x_post.enabled() and sent < int(os.environ.get("X_DAILY", "3")):
            tw = x_post.tweet(text)
            print("تغريدة نُشرت:", tw, flush=True)
    except Exception as e:
        text = locals().get("text", "")
        print("::warning::تعذر نشر التغريدة:", e, flush=True)
    st["posts"].append({"fid": facts["fid"], "post_id": post["id"], "kickoff": facts["kickoff"],
                        "home_ar": H, "away_ar": A, "players_ar": data.get("players_ar") or {},
                        "published": datetime.now(sb.TZ).isoformat(timespec="seconds"), "official": False,
                        "url": post.get("url", ""), "tweet": text, "tweet_id": tw, "img": img})


def update_official(st):
    """قبل المباراة بساعة تقريبًا: نستبدل التشكيلة المتوقعة بالرسمية"""
    now = datetime.now(sb.TZ)
    for e in st["posts"]:
        if e.get("official") or not e.get("post_id"):
            continue
        ko = datetime.fromisoformat(e["kickoff"])
        mins = (ko - now).total_seconds() / 60
        if mins > 75 or mins < -150:
            if mins < -150:
                e["official"] = "missed"
            continue
        try:
            res = sb.football("fixtures/lineups", fixture=e["fid"])
            if len(res) < 2 or not all(t.get("startXI") for t in res[:2]):
                print("التشكيلة الرسمية لم تُعلن بعد:", e["fid"])
                continue
            pa = e.get("players_ar") or {}
            teams = []
            for t, nm in zip(res[:2], (e["home_ar"], e["away_ar"])):
                teams.append({"name": nm, "formation": t.get("formation"), "coach": (t.get("coach") or {}).get("name"),
                              "xi": [(x.get("player") or {}).get("name") for x in t.get("startXI") or []]})
            block = lineup_block({}, {"home_ar": e["home_ar"], "away_ar": e["away_ar"], "players_ar": pa}, official=teams)
            post = sb.blogger(f"/posts/{e['post_id']}")
            content = post.get("content", "")
            new, n = re.subn(r'<div[^>]*data-lu="1"[^>]*>.*?<div[^>]*data-lu-end="1"[^>]*>\s*</div>\s*</div>',
                             lambda m: block, content, count=1, flags=re.S)
            if not n:
                print("لم أجد قسم التشكيلة في المقال", e["post_id"])
                e["official"] = "nomarker"
                continue
            title = post["title"].replace("والتشكيلة المتوقعة", "والتشكيلة الرسمية")
            if DRY:
                print("=== DRY official ===", title)
            else:
                sb.update(e["post_id"], title, new)
                print("تحدّثت التشكيلة الرسمية:", title, flush=True)
            e["official"] = True
        except Exception as ex:
            sp.check_billing(ex)
            print("فشل تحديث التشكيلة", e["fid"], sp.why(ex))


def tweets_page(st):
    """صفحة خاصة (غير مفهرسة) فيها تغريدات جاهزة: ضغطة وحدة وتنشر"""
    import x_post
    now = datetime.now(sb.TZ)
    items = [e for e in st["posts"] if e.get("tweet")][-30:][::-1]
    cards = []
    for e in items:
        ko = datetime.fromisoformat(e["kickoff"]).astimezone(ZoneInfo("Asia/Riyadh"))
        past = ko < now
        when = f"{DAYS[ko.weekday()]} {ko.day} {MONTHS[ko.month - 1]} - {hm(ko)}"
        badge = '<span class="old">انتهت</span>' if past else '<span class="new">قادمة</span>'
        cards.append(
            f'<div class="c{" past" if past else ""}"><div class="h"><b>{esc(e.get("home_ar", ""))} × {esc(e.get("away_ar", ""))}</b>{badge}</div>'
            f'<div class="t">{esc(when)}</div>'
            + (f'<img src="{esc(e["img"])}" alt="" loading="lazy">' if e.get("img") else "")
            + f'<pre>{esc(e["tweet"])}</pre>'
            + (f'<button class="btn sh" data-img="{esc(e["img"])}" data-text="{esc(e["tweet"])}">📷 انشر مع الصورة</button>' if e.get("img") else "")
            + f'<a class="btn alt" href="{esc(x_post.intent(e["tweet"]))}" target="_blank" rel="noopener">انشر في X (نص فقط)</a>'
            f'<a class="lnk" href="{esc(e.get("url", ""))}" target="_blank" rel="noopener">فتح المقال</a></div>')
    page = ("<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'><meta name='robots' content='noindex,nofollow'>"
            "<title>تغريدات جاهزة - عالم المستديرة</title><style>"
            "body{margin:0;background:#eef2f7;font-family:system-ui,-apple-system,Segoe UI,Tahoma,sans-serif;color:#0f2340}"
            "header{background:#0f2340;color:#fff;padding:18px 16px;font-size:20px;font-weight:800}header small{display:block;font-weight:400;opacity:.8;font-size:13px;margin-top:4px}"
            ".w{max-width:640px;margin:0 auto;padding:12px}.c{background:#fff;border-radius:14px;padding:14px;margin:0 0 12px;box-shadow:0 2px 8px rgba(0,0,0,.06)}"
            ".past{opacity:.55}.h{display:flex;justify-content:space-between;align-items:center;font-size:17px}.t{color:#5b6b80;font-size:13px;margin:4px 0 8px}"
            "pre{white-space:pre-wrap;font-family:inherit;background:#f5f7fa;border-radius:10px;padding:10px;font-size:14px;margin:0 0 10px;direction:rtl}"
            ".btn{display:block;text-align:center;background:#000;color:#fff;text-decoration:none;font-weight:800;padding:12px;border-radius:10px;font-size:16px}"
            ".c img{width:100%;border-radius:10px;margin:0 0 8px;display:block}button.btn{width:100%;border:0;cursor:pointer;margin-bottom:8px;font-family:inherit}"
            ".alt{background:#fff;color:#000;border:2px solid #000}#toast{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);background:#0b6b3a;color:#fff;padding:10px 16px;border-radius:20px;display:none;font-size:14px}"
            ".lnk{display:block;text-align:center;color:#1d5fd1;margin-top:8px;font-size:14px;text-decoration:none}"
            ".new,.old{font-size:12px;padding:3px 8px;border-radius:20px}.new{background:#d9f7e6;color:#0b6b3a}.old{background:#eee;color:#777}"
            "</style></head><body><header>تغريدات جاهزة للمباريات الكبيرة<small>آخر تحديث: "
            + now.strftime("%Y-%m-%d %H:%M") + " بتوقيت السعودية - اضغط «انشر في X» ثم «نشر»</small></header><div class='w'>"
            + ("".join(cards) or "<p>لا توجد تغريدات بعد.</p>") + "</div><div id='toast'>تم نسخ النص - الصقه في التغريدة إذا ما ظهر</div>"
            "<script>document.querySelectorAll('.sh').forEach(function(b){b.onclick=async function(){var t=b.dataset.text;"
            "try{await navigator.clipboard.writeText(t);var o=document.getElementById('toast');o.style.display='block';setTimeout(function(){o.style.display='none'},3500)}catch(e){}"
            "try{var r=await fetch(b.dataset.img);var bl=await r.blob();var f=new File([bl],'match.jpg',{type:'image/jpeg'});"
            "if(navigator.canShare&&navigator.canShare({files:[f]})){await navigator.share({files:[f],text:t});return}}catch(e){if(e.name==='AbortError')return}"
            "window.open(b.dataset.img,'_blank')}})</script></body></html>")
    with open(os.path.join(ROOT, "tweets.html"), "w", encoding="utf-8") as f:
        f.write(page)


def main():
    st = load()
    try:
        update_official(st)
        today = datetime.now(sb.TZ).strftime("%Y-%m-%d")
        n_today = sum(1 for p in st["posts"] if (p.get("published") or "").startswith(today))
        limit = min(int(os.environ.get("MAX_PREVIEWS", "2")), int(os.environ.get("DAILY_PREVIEWS", "6")) - n_today)
        if limit <= 0:
            print("وصلنا الحد اليومي للمقالات التمهيدية")
            return
        cands, tbl = candidates(st)
        made = fails = 0
        for f in cands:
            if made >= limit or fails >= 2:
                break
            try:
                publish_preview(f, tbl, st)
                made += 1
            except Exception as e:
                sp.check_billing(e)
                fails += 1
                print("فشل مقال تمهيدي", f["fixture"]["id"], sp.why(e), flush=True)
        print("مقالات تمهيدية:", made)
    finally:
        if not DRY:
            save(st)
            try:
                tweets_page(st)
            except Exception as e:
                print("تعذر تحديث صفحة التغريدات:", e)


if __name__ == "__main__":
    try:
        sb.blogger_token()
        main()
    except sp.BillingStop as e:
        print("::error::" + str(e), flush=True)
        sys.exit(1)
