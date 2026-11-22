#!/usr/bin/env python3
"""
صفحة دائمة لكل فريق كبير: "مباريات الهلال القادمة ونتائجه الأخيرة" تتحدّث تلقائيًا.
تُنشر كمقالة واحدة لكل فريق (بتاريخ قديم حتى لا تزاحم الأخبار في الرئيسية) ثم تُحدَّث نفس المقالة.
طلبات API: طلبان لكل فريق كل 6 ساعات تقريبًا.
DRY_RUN=1 python team_pages.py -> يكتب HTML في /tmp/team_<slug>.html
"""
import hashlib
import html
import json
import os
import time
from datetime import datetime, timedelta

import sports_bot as sb
import seo_poster as sp
from matches_page import CACHE, NAMES, SITE, load, save

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "data", "team_pages.json")
DRY = os.environ.get("DRY_RUN", "0") == "1"
REFRESH_H = float(os.environ.get("TEAM_REFRESH_H", "6"))
PER_RUN = int(os.environ.get("TEAMS_PER_RUN", "6"))
esc = html.escape

# id: (slug, الاسم بالعربي, رقم الدوري, اسم الترتيب في الجدول)
TEAMS = {
    2932: ("al-hilal", "الهلال", 307, "Al-Hilal Saudi FC"),
    2939: ("al-nassr", "النصر", 307, "Al-Nassr"),
    2938: ("al-ittihad", "الاتحاد", 307, "Al-Ittihad FC"),
    2929: ("al-ahli", "الأهلي", 307, "Al-Ahli Jeddah"),
    2933: ("al-qadsiah", "القادسية", 307, "Al-Qadisiyah FC"),
    2940: ("al-shabab", "الشباب", 307, "Al Shabab"),
    541: ("real-madrid", "ريال مدريد", 140, "Real Madrid"),
    529: ("barcelona", "برشلونة", 140, "Barcelona"),
    530: ("atletico-madrid", "أتلتيكو مدريد", 140, "Atletico Madrid"),
    50: ("manchester-city", "مانشستر سيتي", 39, "Manchester City"),
    42: ("arsenal", "أرسنال", 39, "Arsenal"),
    40: ("liverpool", "ليفربول", 39, "Liverpool"),
    49: ("chelsea", "تشيلسي", 39, "Chelsea"),
    33: ("manchester-united", "مانشستر يونايتد", 39, "Manchester United"),
    157: ("bayern-munich", "بايرن ميونخ", 78, "Bayern München"),
    85: ("psg", "باريس سان جيرمان", 61, "Paris Saint Germain"),
    505: ("inter", "إنتر ميلان", 135, "Inter"),
    489: ("ac-milan", "ميلان", 135, "AC Milan"),
    496: ("juventus", "يوفنتوس", 135, "Juventus"),
}
CUPS = {
    45: "كأس الاتحاد الإنجليزي", 48: "كأس الرابطة الإنجليزية", 528: "الدرع الخيرية", 143: "كأس ملك إسبانيا",
    556: "كأس السوبر الإسباني", 137: "كأس إيطاليا", 547: "كأس السوبر الإيطالي", 81: "كأس ألمانيا",
    529: "كأس السوبر الألماني", 66: "كأس فرنسا", 526: "كأس الأبطال الفرنسي", 504: "كأس خادم الحرمين الشريفين",
    826: "كأس السوبر السعودي", 15: "كأس العالم للأندية", 531: "كأس السوبر الأوروبي", 667: "مباراة ودية",
    10: "مباراة دولية ودية", 16: "دوري أبطال آسيا 2",
}
TABLE_SLUG = {307: "saudi-league-table", 39: "premier-league-table", 140: "laliga-table",
              135: "serie-table", 78: "bundesliga-table", 61: "ligue1-table"}
DAYS = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
TH = "padding:8px 4px;font-size:12.5px;font-weight:700"
TD = "padding:8px 4px;border-bottom:1px solid #e6ebf1;text-align:center;font-size:13.5px"


def tv(lid):
    try:
        import previews
        return "، ".join(previews.TV.get(lid) or []) or "-"
    except Exception:
        return "-"


def league_ar(lg, cache):
    return sp.LEAGUES.get(lg["id"]) or CUPS.get(lg["id"]) or cache.get(lg["name"]) or lg["name"]


def team_ar(t, cache):
    return (next((v[1] for k, v in TEAMS.items() if k == t["id"]), None)
            or NAMES["teams"].get(t["name"]) or cache.get(t["name"]) or t["name"])


def season_label(now):
    y = now.year if now.month >= 7 else now.year - 1
    return f"{y}-{str(y + 1)[2:]}"


def ar_day(d):
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]}"


def table_row(lid, name):
    try:
        for lg in load(os.path.join(ROOT, "data", "tables.json"), {}).get("leagues", []):
            if lg["id"] == lid:
                for r in lg["table"]:
                    if r["t"] == name:
                        return r, len(lg["table"])
    except Exception:
        pass
    return None, 0


def previews_map():
    try:
        st = load(os.path.join(ROOT, "data", "previews_state.json"), {"posts": []})
        return {p["fid"]: p["url"] for p in st["posts"] if p.get("url")}
    except Exception:
        return {}


def fetch(tid):
    nxt = sb.football("fixtures", team=tid, next=6, timezone="Asia/Riyadh")
    last = sb.football("fixtures", team=tid, last=6, timezone="Asia/Riyadh")
    slim = lambda f: {"id": f["fixture"]["id"], "date": f["fixture"]["date"], "st": f["fixture"]["status"]["short"],
                      "lg": {"id": f["league"]["id"], "name": f["league"]["name"]},
                      "venue": (f["fixture"].get("venue") or {}).get("name"),
                      "h": {"id": f["teams"]["home"]["id"], "name": f["teams"]["home"]["name"]},
                      "a": {"id": f["teams"]["away"]["id"], "name": f["teams"]["away"]["name"]},
                      "gh": f["goals"]["home"], "ga": f["goals"]["away"]}
    nxt = sorted((slim(f) for f in nxt), key=lambda x: x["date"])
    last = sorted((slim(f) for f in last), key=lambda x: x["date"], reverse=True)
    return nxt, last


def build(tid, nxt, last, cache, now, links):
    slug, name, lid, tname = TEAMS[tid]
    season = season_label(now)
    side = lambda f: "home" if f["h"]["id"] == tid else "away"
    opp = lambda f: team_ar(f["a"] if side(f) == "home" else f["h"], cache)
    # القادمة
    up_rows = []
    for f in nxt:
        d = datetime.fromisoformat(f["date"])
        link = links.get(f["id"])
        o = esc(opp(f))
        o = f"<a href='{esc(link)}'>{o}</a>" if link else o
        up_rows.append(f"<tr><td style='{TD}'>{esc(ar_day(d))}</td><td style='{TD};font-weight:800' dir='ltr'>{d.strftime('%H:%M')}</td>"
                       f"<td style='{TD};font-weight:700'>{o}</td><td style='{TD}'>{'أرضه' if side(f) == 'home' else 'خارج أرضه'}</td>"
                       f"<td style='{TD}'>{esc(league_ar(f['lg'], cache))}</td><td style='{TD}'>{esc(tv(f['lg']['id']))}</td></tr>")
    up_head = "".join(f"<th style='{TH}'>{h}</th>" for h in ["اليوم", "الساعة", "المنافس", "الملعب", "البطولة", "القناة"])
    # النتائج
    res, form = [], ""
    for f in last:
        if f["gh"] is None:
            continue
        d = datetime.fromisoformat(f["date"])
        my, ot = (f["gh"], f["ga"]) if side(f) == "home" else (f["ga"], f["gh"])
        r = "ف" if my > ot else ("ت" if my == ot else "خ")
        form += r
        col = {"ف": "#0b6b3a", "ت": "#8a6d00", "خ": "#b3261e"}[r]
        res.append(f"<tr><td style='{TD}'>{esc(ar_day(d))}</td><td style='{TD};font-weight:700'>{esc(opp(f))}</td>"
                   f"<td style='{TD};font-weight:800' dir='ltr'>{my} - {ot}</td>"
                   f"<td style='{TD};font-weight:800;color:{col}'>{r}</td><td style='{TD}'>{esc(league_ar(f['lg'], cache))}</td></tr>")
    res_head = "".join(f"<th style='{TH}'>{h}</th>" for h in ["التاريخ", "المنافس", "النتيجة", "", "البطولة"])
    tbl = lambda head, rows: ("<div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse;border:1px solid #e6ebf1'>"
                              f"<thead><tr style='background:#153a5b;color:#fff'>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>")
    row, n = table_row(lid, tname)
    lead = f"تعرف على <strong>مواعيد مباريات {name} القادمة</strong> موسم {season} بتوقيت السعودية والقنوات الناقلة، إضافة إلى نتائج آخر مباريات {name}."
    faq = [f"<h2>أسئلة شائعة عن مباريات {name}</h2>"]
    if nxt:
        f = nxt[0]
        d = datetime.fromisoformat(f["date"])
        lead += (f" المباراة القادمة لفريق {name} أمام <strong>{esc(opp(f))}</strong> يوم {ar_day(d)} الساعة {d.strftime('%H:%M')} "
                 f"بتوقيت السعودية في {esc(league_ar(f['lg'], cache))}.")
        faq.append(f"<h3>متى مباراة {name} القادمة؟</h3><p>يلعب {name} مباراته القادمة ضد {esc(opp(f))} يوم {ar_day(d)} "
                   f"الساعة {d.strftime('%H:%M')} بتوقيت مكة المكرمة" + (f" على ملعب {esc(f['venue'])}" if f.get("venue") else "") + ".</p>")
        faq.append(f"<h3>ما القناة الناقلة لمباراة {name} القادمة؟</h3><p>تُنقل المباراة في الشرق الأوسط وشمال أفريقيا عبر: "
                   f"{esc(tv(f['lg']['id']))} (حسب حقوق البث المعلنة للموسم الحالي).</p>")
    if row:
        lead += f" ويحتل {name} المركز {row['r']} في {sp.LEAGUES.get(lid)} برصيد {row['pts']} نقطة من {row['p']} مباراة."
        faq.append(f"<h3>كم ترتيب {name} في {sp.LEAGUES.get(lid)}؟</h3><p>{name} في المركز {row['r']} من أصل {n} فرق برصيد "
                   f"{row['pts']} نقطة (فاز {row['w']} وتعادل {row['d']} وخسر {row['ls']}).</p>")
    if form:
        lead += f" وفي آخر مبارياته ({len(form)}): الفوز في {form.count('ف')} والتعادل في {form.count('ت')} والخسارة في {form.count('خ')}."
    others = " · ".join(f"<a href='{u}'>مباريات {v[1]}</a>" for k, v in TEAMS.items()
                        if k != tid and (u := (load(STATE, {}).get(str(k)) or {}).get("url")))
    body = f"""<div dir="rtl" style="line-height:1.9">
<p>{lead}</p>
<p style="font-size:13px;color:#5b6b7c">آخر تحديث: {now.strftime('%Y-%m-%d %H:%M')} بتوقيت السعودية - تتحدث الصفحة تلقائيًا عدة مرات يوميًا.</p>
<h2>مواعيد مباريات {name} القادمة</h2>
{tbl(up_head, up_rows) if up_rows else '<p>لا توجد مباريات معلنة حاليًا.</p>'}
<h2>نتائج آخر مباريات {name}</h2>
{tbl(res_head, res) if res else '<p>لا توجد نتائج حديثة.</p>'}
{''.join(faq)}
<p>تابع أيضًا: <a href="{SITE}/p/matches-today.html">مباريات اليوم مباشرة</a>""" + (
        f" · <a href='{SITE}/p/{TABLE_SLUG[lid]}.html'>ترتيب {sp.LEAGUES.get(lid)}</a>" if lid in TABLE_SLUG else "") + "</p>" + (
        f"<p style='font-size:14px'>صفحات الفرق: {others}</p>" if others else "") + "</div>"
    title = f"مباريات {name} القادمة {season} والقنوات الناقلة ونتائج آخر المباريات"
    return title, body


def main():
    st = load(STATE, {})
    cache = load(CACHE, {})
    now = datetime.now(sb.TZ)
    links = previews_map()
    due = sorted(TEAMS, key=lambda t: (st.get(str(t)) or {}).get("fetched", ""))
    done = 0
    for tid in due:
        rec = st.get(str(tid)) or {}
        if rec.get("fetched") and (now - datetime.fromisoformat(rec["fetched"])) < timedelta(hours=REFRESH_H) and not DRY:
            continue
        if done >= PER_RUN:
            break
        done += 1
        slug, name, lid, _ = TEAMS[tid]
        try:
            nxt, last = fetch(tid)
            title, body = build(tid, nxt, last, cache, now, links)
            if DRY:
                open(f"/tmp/team_{slug}.html", "w", encoding="utf-8").write(body)
                print("DRY:", title, len(nxt), len(last))
                if done >= 2:
                    break
                continue
            sig = hashlib.md5(json.dumps([nxt, last, links.get(nxt[0]["id"]) if nxt else None], sort_keys=True).encode()).hexdigest()
            rec["fetched"] = now.isoformat(timespec="seconds")
            if not rec.get("id"):
                post = sb.blogger("/posts/", "POST", {"title": f"{slug} fixtures results", "content": body,
                                                     "labels": ["مباريات الفرق", name],
                                                     "published": "2026-08-01T12:00:00+03:00"})
                rec.update({"id": post["id"], "url": post.get("url", "")})
                time.sleep(3)
                sb.update(post["id"], title, body)
                rec["sig"] = sig
                print("أُنشئت صفحة:", name, rec["url"], flush=True)
            elif rec.get("sig") != sig or rec.get("day") != now.strftime("%Y-%m-%d"):
                sb.update(rec["id"], title, body)
                rec["sig"] = sig
                print("تحدّثت صفحة:", name, flush=True)
            rec["day"] = now.strftime("%Y-%m-%d")
            st[str(tid)] = rec
            save(STATE, st)
            time.sleep(3)
        except Exception as e:
            sp.check_billing(e)
            print("::warning::فشل صفحة الفريق", name, sp.why(e), flush=True)


if __name__ == "__main__":
    sb.blogger_token() if not DRY else None
    main()
