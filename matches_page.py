#!/usr/bin/env python3
"""
صفحة ثابتة «مباريات اليوم» على بلوقر يحدّثها البوت تلقائيًا بجدول نصي
(قابل للأرشفة في جوجل) لمباريات اليوم والغد في البطولات المهمة.
python matches_page.py          -> ينشئ الصفحة أول مرة ثم يحدّثها
DRY_RUN=1 python matches_page.py -> يكتب HTML في /tmp/matches_page.html فقط
"""
import html
import json
import os
import sys
import urllib.parse
from datetime import datetime, timedelta

import sports_bot as sb

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "data", "pages.json")
NAMES = json.load(open(os.path.join(ROOT, "names_ar.json"), encoding="utf-8"))
CACHE = os.path.join(ROOT, "data", "names_cache.json")
DRY = os.environ.get("DRY_RUN", "0") == "1"
SLUG = "matches-today"
TITLE = "مباريات اليوم ونتائجها مباشرة"
SITE = "https://www.fottballcia.com"

# ترتيب الظهور = الأهمية
LEAGUES = [
    (307, "الدوري السعودي للمحترفين"), (308, "دوري يلو الدرجة الأولى السعودي"),
    (504, "كأس الملك السعودي"), (2, "دوري أبطال أوروبا"), (17, "دوري أبطال آسيا للنخبة"),
    (18, "دوري أبطال آسيا 2"), (39, "الدوري الإنجليزي الممتاز"), (140, "الدوري الإسباني"),
    (135, "الدوري الإيطالي"), (78, "الدوري الألماني"), (61, "الدوري الفرنسي"),
    (3, "الدوري الأوروبي"), (848, "دوري المؤتمر الأوروبي"), (1, "كأس العالم"),
    (860, "كأس العرب"), (6, "كأس أمم أفريقيا"), (7, "كأس آسيا"),
    (32, "تصفيات كأس العالم - أوروبا"), (30, "تصفيات كأس العالم - آسيا"),
    (29, "تصفيات كأس العالم - أفريقيا"), (5, "دوري الأمم الأوروبية"), (10, "مباريات ودية دولية"),
    (12, "دوري أبطال أفريقيا"), (233, "الدوري المصري الممتاز"), (305, "دوري نجوم قطر"),
    (301, "دوري أدنوك للمحترفين الإماراتي"), (200, "الدوري المغربي الاحترافي"),
    (143, "كأس ملك إسبانيا"), (45, "كأس الاتحاد الإنجليزي"), (48, "كأس الرابطة الإنجليزية"),
    (137, "كأس إيطاليا"), (81, "كأس ألمانيا"), (66, "كأس فرنسا"),
    (94, "الدوري البرتغالي"), (88, "الدوري الهولندي"), (203, "الدوري التركي"),
]
ORDER = {lid: i for i, (lid, _) in enumerate(LEAGUES)}
LNAME = dict(LEAGUES)
DAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس",
          "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
LIVE = {"1H", "2H", "HT", "ET", "BT", "P", "LIVE", "INT"}
DONE = {"FT", "AET", "PEN"}
OFF = {"PST": "مؤجلة", "CANC": "ملغاة", "ABD": "متوقفة", "SUSP": "معلقة", "AWD": "قرار إداري", "WO": "انسحاب"}


def load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def save(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def ar_date(d):
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]} {d.year}"


def fetch(day):
    fx = sb.football("fixtures", date=day.strftime("%Y-%m-%d"), timezone="Asia/Riyadh")
    return sorted([f for f in fx if f["league"]["id"] in ORDER],
                  key=lambda f: (ORDER[f["league"]["id"]], f["fixture"]["timestamp"]))


def translate_missing(names, cache):
    """يترجم أسماء الفرق غير الموجودة في القاموس مرة واحدة ويحفظها"""
    missing = sorted({n for n in names if n not in NAMES["teams"] and n not in NAMES["countries"]
                      and n not in cache})
    if not missing or not os.environ.get("GEMINI_API_KEY", "").strip():
        return
    prompt = ("ترجم أسماء فرق كرة القدم التالية إلى الاسم العربي الشائع في الإعلام الرياضي العربي. "
              "أعد JSON فقط بالشكل {\"English\": \"عربي\"} بدون أي شرح.\n" + "\n".join(missing[:120]))
    try:
        txt = sb.gemini(prompt, 3000, os.environ["GEMINI_API_KEY"].strip())
        txt = txt[txt.find("{"): txt.rfind("}") + 1]
        for k, v in json.loads(txt).items():
            if k in missing and isinstance(v, str) and 0 < len(v) < 40:
                cache[k] = v.strip()
    except Exception as e:
        print("تعذرت ترجمة الأسماء:", str(e)[:200])


def tn(name, cache):
    return NAMES["teams"].get(name) or cache.get(name) or NAMES["countries"].get(name) or name


def cell_status(f):
    st = f["fixture"]["status"]
    gh, ga = f["goals"]["home"], f["goals"]["away"]
    t = datetime.fromtimestamp(f["fixture"]["timestamp"], sb.TZ).strftime("%H:%M")
    if st["short"] in DONE:
        return f"{gh} - {ga}", "انتهت" + (" (ركلات ترجيح)" if st["short"] == "PEN" else "")
    if st["short"] in LIVE:
        return f"{gh} - {ga}", "استراحة" if st["short"] == "HT" else f"مباشر {st.get('elapsed') or ''}'"
    if st["short"] in OFF:
        return t, OFF[st["short"]]
    return t, "لم تبدأ"


TD = "padding:9px 6px;border-bottom:1px solid #e6ebf1;text-align:center;font-size:15px"


def league_block(lid, items, cache):
    f0 = items[0]
    rnd = html.escape(f0["league"].get("round") or "").replace("Regular Season - ", "الجولة ")
    rows = []
    for f in items:
        a, b = cell_status(f)
        home, away = html.escape(tn(f["teams"]["home"]["name"], cache)), html.escape(tn(f["teams"]["away"]["name"], cache))
        venue = html.escape((f["fixture"].get("venue") or {}).get("name") or "")
        rows.append(
            f"<tr><td style='{TD};font-weight:700'><a href='{SITE}/p/match.html?id={f['fixture']['id']}' style='color:inherit;text-decoration:none'>{home}</a></td>"
            f"<td style='{TD};font-weight:800;color:#153a5b;white-space:nowrap'><a href='{SITE}/p/match.html?id={f['fixture']['id']}' style='color:inherit;text-decoration:none'>{a}</a></td>"
            f"<td style='{TD};font-weight:700'><a href='{SITE}/p/match.html?id={f['fixture']['id']}' style='color:inherit;text-decoration:none'>{away}</a></td>"
            f"<td style='{TD};color:#5b6b7c;font-size:13px'>{b}<br><a href='{SITE}/p/match.html?id={f['fixture']['id']}' style='font-weight:700;color:#153a5b'>تفاصيل المباراة</a></td></tr>"
            + (f"<tr><td colspan='4' style='padding:0 6px 8px;text-align:center;font-size:12px;color:#8a97a6;border-bottom:1px solid #e6ebf1'>الملعب: {venue}</td></tr>" if venue else "")
        )
    return (f"<h3 style='margin:22px 0 8px;font-size:19px'>{html.escape(LNAME[lid])}"
            + (f" <small style='color:#8a97a6;font-weight:400'>({rnd})</small>" if rnd else "") + "</h3>"
            "<table style='width:100%;border-collapse:collapse;background:#fff;border:1px solid #e6ebf1;border-radius:10px'>"
            f"<thead><tr style='background:#153a5b;color:#fff'><th style='padding:8px'>صاحب الأرض</th>"
            f"<th style='padding:8px'>النتيجة / التوقيت</th><th style='padding:8px'>الضيف</th>"
            f"<th style='padding:8px'>الحالة</th></tr></thead><tbody>{''.join(rows)}</tbody></table>")


def day_section(title, fx, cache):
    if not fx:
        return f"<h2>{title}</h2><p>لا توجد مباريات في البطولات الكبرى والعربية المتابعة في هذا اليوم.</p>"
    groups = {}
    for f in fx:
        groups.setdefault(f["league"]["id"], []).append(f)
    return f"<h2>{title}</h2>" + "".join(league_block(l, it, cache) for l, it in groups.items())


def summary(fx):
    if not fx:
        return "لا توجد اليوم مباريات في البطولات الكبرى، ويمكنك متابعة مباريات الغد في الأسفل."
    leagues = list(dict.fromkeys(LNAME[f["league"]["id"]] for f in fx))
    live = sum(f["fixture"]["status"]["short"] in LIVE for f in fx)
    done = sum(f["fixture"]["status"]["short"] in DONE for f in fx)
    s = f"تقام اليوم {len(fx)} مباراة في {len(leagues)} بطولة، أبرزها {('، '.join(leagues[:4]))}."
    if live:
        s += f" تُلعب الآن {live} مباراة بشكل مباشر."
    if done:
        s += f" وانتهت {done} مباراة حتى الآن."
    return s


def build(today_fx, tomorrow_fx, now, cache):
    tomorrow = now + timedelta(days=1)
    links = [("ترتيب الدوري السعودي", "/p/saudi-league-table.html"),
             ("ترتيب الدوري الإنجليزي", "/p/premier-league-table.html"),
             ("ترتيب الدوري الإسباني", "/p/laliga-table.html"),
             ("أخبار الدوري السعودي", "/search/label/" + urllib.parse.quote("الدوري السعودي للمحترفين")),
             ("أخبار كرة القدم", "/search/label/" + urllib.parse.quote("أخبار كرة القدم")),
             ("تقارير المباريات", "/search/label/" + urllib.parse.quote("تقارير المباريات"))]
    rel = " · ".join(f"<a href='{SITE}{html.escape(u)}'>{t}</a>" for t, u in links)
    return f"""<div dir="rtl" style="line-height:1.9">
<p><strong>مباريات اليوم {ar_date(now)}</strong>: جدول كامل بمواعيد ونتائج مباريات اليوم في الدوري السعودي والدوريات الأوروبية الكبرى ودوري أبطال أوروبا وآسيا والبطولات العربية، مع النتيجة المباشرة لكل مباراة. {summary(today_fx)}</p>
<p style="font-size:13px;color:#5b6b7c">جميع المواعيد بتوقيت مكة المكرمة (السعودية). آخر تحديث: {now.strftime('%H:%M')} - يتم تحديث الصفحة تلقائيًا خلال اليوم.</p>
{day_section('جدول مباريات اليوم ' + ar_date(now), today_fx, cache)}
{day_section('مباريات الغد ' + ar_date(tomorrow), tomorrow_fx, cache)}
<h2>أسئلة شائعة عن مباريات اليوم</h2>
<h3>ما توقيت مباريات اليوم في الجدول؟</h3>
<p>كل المواعيد المذكورة بتوقيت السعودية (GMT+3)، ويمكنك إضافة أو طرح الفرق حسب توقيت بلدك؛ فمصر متأخرة ساعة عن السعودية، والإمارات متقدمة ساعة.</p>
<h3>كم مرة تُحدَّث الصفحة؟</h3>
<p>تُحدَّث نتائج مباريات اليوم تلقائيًا عدة مرات في الساعة من مصادر بيانات رياضية موثوقة، وللمتابعة الدقيقة لحظة بلحظة افتح الصفحة الرئيسية لموقع عالم المستديرة حيث تظهر الأهداف والبطاقات مباشرة.</p>
<h3>أين أجد تفاصيل المباراة بعد نهايتها؟</h3>
<p>ننشر تقارير مفصلة لأهم المباريات تتضمن الأهداف والإحصائيات والتشكيلات في قسم تقارير المباريات.</p>
<p>روابط مفيدة: {rel}</p>
</div>"""


def find_page(st):
    if st.get("matches_page_id"):
        return st["matches_page_id"]
    for p in sb.blogger("/pages", status="live").get("items", []) or []:
        if p.get("url", "").rstrip("/").endswith(f"/p/{SLUG}.html"):
            return p["id"]
    return None


def main():
    now = datetime.now(sb.TZ)
    cache = load(CACHE, {})
    today_fx = fetch(now)
    tomorrow_fx = fetch(now + timedelta(days=1))
    names = [f["teams"][s]["name"] for f in today_fx + tomorrow_fx for s in ("home", "away")]
    before = len(cache)
    translate_missing(names, cache)
    if len(cache) != before:
        save(CACHE, cache)
    content = build(today_fx, tomorrow_fx, now, cache)
    print(f"اليوم: {len(today_fx)} مباراة | الغد: {len(tomorrow_fx)} مباراة")
    if DRY:
        open("/tmp/matches_page.html", "w", encoding="utf-8").write(content)
        print("DRY: /tmp/matches_page.html")
        return
    st = load(STATE, {})
    pid = find_page(st)
    if not pid:
        # إنشاء بعنوان إنجليزي ليصبح الرابط /p/matches-today.html ثم إرجاع العنوان العربي
        page = sb.blogger("/pages", "POST", {"title": "matches today", "content": content})
        pid = page["id"]
        print("أُنشئت الصفحة:", page.get("url"))
    sb.blogger(f"/pages/{pid}", "PATCH", {"title": TITLE, "content": content})
    st["matches_page_id"] = pid
    st["matches_updated"] = now.isoformat(timespec="seconds")
    save(STATE, st)
    print("تم تحديث صفحة مباريات اليوم", pid)


if __name__ == "__main__":
    sys.exit(main())
