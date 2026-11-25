#!/usr/bin/env python3
"""
صفحات ثابتة لترتيب الدوريات الكبرى والهدافين يحدّثها البوت من data/tables.json
(الملف يحدّثه site_bot.py كل 3 ساعات). تُحدَّث الصفحة فقط إذا تغيّرت البيانات.
DRY_RUN=1 python tables_pages.py -> يكتب HTML في /tmp/table_<slug>.html
"""
import hashlib
import html
import json
import os
from datetime import datetime

import sports_bot as sb
from matches_page import CACHE, NAMES, SITE, STATE, load, save

DRY = os.environ.get("DRY_RUN", "0") == "1"
ROOT = os.path.dirname(os.path.abspath(__file__))

# id: (slug, الاسم الكامل, اسم مختصر)
PAGES = {
    307: ("saudi-league-table", "الدوري السعودي للمحترفين", "دوري روشن"),
    39: ("premier-league-table", "الدوري الإنجليزي الممتاز", "البريميرليغ"),
    140: ("laliga-table", "الدوري الإسباني", "الليغا"),
    135: ("serie-table", "الدوري الإيطالي", "الكالتشيو"),
    78: ("bundesliga-table", "الدوري الألماني", "البوندسليغا"),
    61: ("ligue1-table", "الدوري الفرنسي", "الليغ 1"),
    2: ("champions-league-table", "دوري أبطال أوروبا", "دوري الأبطال"),
    12: ("caf-champions-league-table", "دوري أبطال أفريقيا", "أبطال أفريقيا"),
    17: ("afc-champions-league-table", "دوري أبطال آسيا للنخبة", "أبطال آسيا"),
}
FORM = {"W": "ف", "D": "ت", "L": "خ"}


def translate(names, cache):
    missing = sorted({n for n in names if n and n not in NAMES["teams"] and n not in NAMES["countries"]
                      and n not in cache})
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not missing or not key:
        return
    prompt = ("ترجم أسماء فرق ولاعبي كرة القدم التالية إلى الكتابة العربية الشائعة في الإعلام الرياضي العربي "
              "(للاعب اكتب الاسم الأخير المعروف فقط إذا جاء بحرف أول مختصر مثل E. Haaland -> هالاند). "
              "أعد JSON فقط بالشكل {\"English\": \"عربي\"} بدون أي شرح.\n" + "\n".join(missing[:150]))
    try:
        txt = sb.gemini(prompt, 4000, key)
        txt = txt[txt.find("{"): txt.rfind("}") + 1]
        for k, v in json.loads(txt).items():
            if k in missing and isinstance(v, str) and 0 < len(v) < 40:
                cache[k] = v.strip()
    except Exception as e:
        print("تعذرت ترجمة الأسماء:", str(e)[:200])


def ar(name, cache):
    return html.escape(NAMES["teams"].get(name) or cache.get(name) or NAMES["countries"].get(name) or name or "")


TH = "padding:8px 3px;font-size:12.5px;font-weight:700"
TD = "padding:8px 3px;border-bottom:1px solid #e6ebf1;text-align:center;font-size:13.5px"


def standings_table(rows, cache, lid=0):
    n = len(rows)
    out = []
    last_g = None
    cup = lid in (2, 12, 17)
    for r in rows:
        if r.get("g") and r.get("g") != last_g:
            out.append(f"<tr><td colspan='8' style='{TD};background:#153a5b;color:#fff;font-weight:800'>{html.escape(r['g'])}</td></tr>")
        last_g = r.get("g")
        if lid == 2:
            bg = "#eafaf0" if r["r"] <= 8 else ("#fff7e0" if r["r"] <= 24 else "#fdecec")
        elif cup:
            bg = "#eafaf0" if r["r"] <= 2 else "#fff"
        else:
            bg = "#eafaf0" if r["r"] <= 4 else ("#fdecec" if r["r"] > n - 3 else "#fff")
        form = "".join(FORM.get(c, "") for c in (r.get("f") or "")[-5:])
        gd = r.get("gd") or 0
        out.append(
            f"<tr style='background:{bg}'><td style='{TD};font-weight:800'>{r['r']}</td>"
            f"<td style='{TD};text-align:right;font-weight:700'>{ar(r['t'], cache)}</td>"
            f"<td style='{TD};font-weight:800;color:#153a5b;background:rgba(21,58,91,.06)'>{r['pts']}</td>"
            f"<td style='{TD}'>{r['p']}</td><td style='{TD}'>{r['w']}</td><td style='{TD}'>{r['d']}</td>"
            f"<td style='{TD}'>{r['ls']}</td><td style='{TD}' dir='ltr'>{'+' if gd > 0 else ''}{gd}</td></tr>")
    head = "".join(f"<th style='{TH}'>{h}</th>" for h in ["#", "الفريق", "نقاط", "لعب", "فوز", "تعادل", "خسارة", "+/-"])
    return ("<div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse;border:1px solid #e6ebf1;table-layout:auto'>"
            f"<thead><tr style='background:#153a5b;color:#fff'>{head}</tr></thead><tbody>{''.join(out)}</tbody></table></div>"
            "<p style='font-size:13px;color:#5b6b7c'>"
            + ("الأخضر: التأهل المباشر لدور الـ16 (أول 8) · الأصفر: الملحق (من 9 إلى 24) · الأحمر: خارج المنافسة." if lid == 2 else
               ("الأخضر: مراكز التأهل للأدوار الإقصائية." if lid in (12, 17) else
                "الأخضر: مراكز المقدمة الأربعة · الأحمر: آخر ثلاثة مراكز (منطقة الخطر)."))
            + "</p>")


def scorers_table(sc, cache):
    if not sc:
        return "<p>قائمة الهدافين غير متاحة حاليًا وستظهر مع تقدم الموسم.</p>"
    rows = "".join(
        f"<tr><td style='{TD};font-weight:800'>{i}</td><td style='{TD};text-align:right;font-weight:700'>{ar(x['n'], cache)}</td>"
        f"<td style='{TD}'>{ar(x['t'], cache)}</td><td style='{TD};font-weight:800;color:#153a5b'>{x['g']}</td>"
        f"<td style='{TD}'>{x['a']}</td><td style='{TD}'>{x['pen']}</td></tr>"
        for i, x in enumerate(sc, 1))
    head = "".join(f"<th style='{TH}'>{h}</th>" for h in ["#", "اللاعب", "الفريق", "أهداف", "صناعة", "جزاء"])
    return ("<div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse;border:1px solid #e6ebf1'>"
            f"<thead><tr style='background:#153a5b;color:#fff'>{head}</tr></thead><tbody>{rows}</tbody></table></div>")


def cnt(n, one, two, few, many):
    if n == 1:
        return one
    if n == 2:
        return two
    return f"{n} {few if 3 <= n % 100 <= 10 else many}"


def pts(n):
    return f"{n} نقطة" if n == 0 else cnt(n, "نقطة واحدة", "نقطتين", "نقاط", "نقطة")


def goals(n):
    return cnt(n, "هدف واحد", "هدفين", "أهداف", "هدفًا")


def season_label(s):
    return f"{s}-{s + 1}"


def title_of(lid, season):
    return f"ترتيب {PAGES[lid][1]} {season_label(season)} وقائمة الهدافين"


def build(lg, cache, now, others):
    lid, rows, sc = lg["id"], lg["table"], lg.get("scorers") or []
    slug, full, short = PAGES[lid]
    g0 = rows[0].get("g") if rows else ""
    top_rows = [r for r in rows if r.get("g") == g0] or rows
    season = season_label(lg["season"])
    first, second = top_rows[0], top_rows[1] if len(top_rows) > 1 else None
    gap = first["pts"] - second["pts"] if second else 0
    lead = (f"يتصدر <strong>{ar(first['t'], cache)}</strong> ترتيب {full} برصيد {pts(first['pts'])} بعد {cnt(first['p'], 'مباراة واحدة', 'مباراتين', 'مباريات', 'مباراة')}"
            + (f"، بفارق {pts(gap)} عن {ar(second['t'], cache)} صاحب المركز الثاني" if second and gap else
               (f"، ويتساوى بالنقاط مع {ar(second['t'], cache)}" if second else "")) + ".")
    bottom = top_rows[-1]
    lead += f" وفي ذيل الترتيب يأتي {ar(bottom['t'], cache)} برصيد {pts(bottom['pts'])}."
    top_sc = sc[0] if sc else None
    if top_sc:
        lead += f" أما في صراع الهدافين فيتقدم {ar(top_sc['n'], cache)} لاعب {ar(top_sc['t'], cache)} برصيد {goals(top_sc['g'])}."
    rel = " · ".join(f"<a href='{SITE}/p/{PAGES[o][0]}.html'>ترتيب {PAGES[o][1]}</a>" for o in others if o != lid)
    faq = f"""<h2>أسئلة شائعة عن ترتيب {full}</h2>
<h3>من متصدر {full} موسم {season}؟</h3>
<p>المتصدر حاليًا هو {ar(first['t'], cache)} برصيد {pts(first['pts'])}، حيث فاز في {first['w']} وتعادل في {first['d']} وخسر {first['ls']} من مبارياته.</p>"""
    if top_sc:
        faq += f"""
<h3>من هداف {full} حتى الآن؟</h3>
<p>هداف {short} حاليًا هو {ar(top_sc['n'], cache)} برصيد {goals(top_sc['g'])}""" + (
            f"، يليه {ar(sc[1]['n'], cache)} برصيد {goals(sc[1]['g'])}" if len(sc) > 1 else "") + ".</p>"
    faq += f"""
<h3>متى يتم تحديث جدول الترتيب؟</h3>
<p>يُحدَّث جدول ترتيب {full} وقائمة الهدافين تلقائيًا عدة مرات يوميًا بعد نهاية المباريات، اعتمادًا على مصادر بيانات رياضية موثوقة.</p>"""
    return f"""<div dir="rtl" style="line-height:1.9">
<p style="text-align:center"><img src="https://media.api-sports.io/football/leagues/{lid}.png" alt="ترتيب {full} {season}" width="120" height="120" style="width:120px;height:auto;background:#fff;border-radius:12px;padding:6px"></p>
<p><strong>ترتيب {full} {season}</strong>: جدول ترتيب {short} كاملًا بعد آخر المباريات، مع عدد المباريات والانتصارات والتعادلات والهزائم وفارق الأهداف والنقاط، إضافة إلى قائمة هدافي الدوري. {lead}</p>
<p style="font-size:13px;color:#5b6b7c">آخر تحديث: {now.strftime('%Y-%m-%d %H:%M')} بتوقيت السعودية.</p>
<h2>جدول ترتيب {full} {season}</h2>
{standings_table(rows, cache, lid)}
<h2>ترتيب هدافي {full} {season}</h2>
{scorers_table(sc, cache)}
{faq}
<p>تابع أيضًا: <a href="{SITE}/p/matches-today.html">مباريات اليوم ونتائجها مباشرة</a> · {rel}</p>
</div>"""


def api(path, method="GET", data=None, **kw):
    import time
    for wait in (0, 20, 60, 120):
        if wait:
            time.sleep(wait)
        try:
            return sb.blogger(path, method, data, **kw)
        except Exception as e:
            if "429" not in str(e) or wait == 120:
                raise
            print("ضغط على Blogger API، انتظار...", flush=True)


def find_page(slug, cache_pages):
    for p in cache_pages:
        if p.get("url", "").rstrip("/").endswith(f"/p/{slug}.html"):
            return p["id"]
    return None


def main():
    data = load(os.path.join(ROOT, "data", "tables.json"), {})
    leagues = [l for l in data.get("leagues", []) if l.get("id") in PAGES and l.get("table")]
    if not leagues:
        print("لا توجد بيانات ترتيب")
        return
    cache = load(CACHE, {})
    names = [r["t"] for l in leagues for r in l["table"]] + [x[k] for l in leagues for x in l.get("scorers") or [] for k in ("n", "t")]
    before = len(cache)
    translate(names, cache)
    if len(cache) != before:
        save(CACHE, cache)
    st = load(STATE, {})
    ids = st.setdefault("tables", {})
    now = datetime.now(sb.TZ)
    others = [l["id"] for l in leagues]
    existing = None
    for lg in leagues:
        slug = PAGES[lg["id"]][0]
        content = build(lg, cache, now, others)
        sig = hashlib.md5(json.dumps([lg["table"], lg.get("scorers"), sorted(others)], ensure_ascii=False).encode()
                          + str(len(cache)).encode() + b"v5").hexdigest()
        if DRY:
            open(f"/tmp/table_{slug}.html", "w", encoding="utf-8").write(content)
            print("DRY:", slug)
            continue
        rec = ids.get(slug) or {}
        if rec.get("sig") == sig:
            continue
        pid = rec.get("id")
        if not pid:
            if existing is None:
                existing = api("/pages", status="live").get("items", []) or []
            pid = find_page(slug, existing)
        if not pid:
            page = api("/pages", "POST", {"title": slug.replace("-", " "), "content": content})
            pid = page["id"]
            print("أُنشئت:", page.get("url"))
        api(f"/pages/{pid}", "PATCH", {"title": title_of(lg["id"], lg["season"]), "content": content})
        ids[slug] = {"id": pid, "sig": sig}
        save(STATE, st)
        print("حُدّثت:", slug)
        __import__("time").sleep(4)


if __name__ == "__main__":
    main()
