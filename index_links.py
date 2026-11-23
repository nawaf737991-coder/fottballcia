#!/usr/bin/env python3
"""صفحة index.html خاصة (غير مفهرسة): 10 روابط يوميًا لطلب فهرستها من Google Search Console.
تختار الأهم أولًا (ما قبل المباريات، صفحات الفرق، التقارير) ولا تكرر رابطًا سبق اقتراحه.
"""
import html
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "data", "index_links.json")
OUT = os.path.join(ROOT, "index-links.html")
SITE = "https://www.fottballcia.com"
TZ = timezone(timedelta(hours=3))
PER_DAY = 10
esc = html.escape
PAGES = {"/p/matches-today.html": "صفحة مباريات اليوم", "/p/saudi-league-table.html": "ترتيب الدوري السعودي",
         "/p/premier-league-table.html": "ترتيب الدوري الإنجليزي", "/p/laliga-table.html": "ترتيب الدوري الإسباني",
         "/p/serie-table.html": "ترتيب الدوري الإيطالي", "/p/bundesliga-table.html": "ترتيب الدوري الألماني",
         "/p/ligue1-table.html": "ترتيب الدوري الفرنسي"}


def feed(n=150):
    url = f"{SITE}/feeds/posts/summary?alt=json&max-results={n}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r:
        d = json.load(r)
    out = []
    for e in d["feed"].get("entry", []):
        link = next((l for l in e["link"] if l["rel"] == "alternate"), None)
        if not link:
            continue
        labels = [c["term"] for c in e.get("category", [])]
        out.append({"url": link["href"], "title": link.get("title") or e["title"]["$t"],
                    "pub": e["published"]["$t"], "labels": labels})
    return out


def score(p, now):
    s = 0
    L = p["labels"]
    if "ما قبل المباريات" in L:
        s += 100
    if "مباريات الفرق" in L:
        s += 80
    if any(x in L for x in ("تقارير المباريات", "نتائج المباريات")) or " يفوز " in p["title"] or "يكتسح" in p["title"]:
        s += 40
    big = ("الهلال", "النصر", "الاتحاد", "الأهلي", "ريال مدريد", "برشلونة", "ليفربول", "مانشستر", "أرسنال", "تشيلسي",
           "بايرن", "باريس", "يوفنتوس", "ميلان", "إنتر", "رونالدو", "ميسي", "صلاح")
    s += 25 * sum(1 for b in big if b in p["title"])
    try:
        age = (now - datetime.fromisoformat(p["pub"])).total_seconds() / 86400
        s += max(0, 30 - age * 10)  # الأحدث أولًا
    except Exception:
        pass
    return s


def inspect_link(u):
    return ("https://search.google.com/search-console/inspect?resource_id=" + urllib.parse.quote(SITE + "/", safe="")
            + "&id=" + urllib.parse.quote(u, safe=""))


def main():
    now = datetime.now(TZ)
    today = now.strftime("%Y-%m-%d")
    try:
        st = json.load(open(STATE, encoding="utf-8"))
    except Exception:
        st = {"days": {}}
    days = st.setdefault("days", {})
    if today not in days:
        used = {u for v in days.values() for u in (x["url"] for x in v)}
        posts = [p for p in feed() if p["url"] not in used and "?m=" not in p["url"]]
        # صفحات ثابتة مرة واحدة في البداية
        fixed = [{"url": SITE + p, "title": PAGES[p]} for p in PAGES if SITE + p not in used]
        posts.sort(key=lambda p: -score(p, now))
        pick = fixed[:3] + [{"url": p["url"], "title": p["title"]} for p in posts]
        days[today] = pick[:PER_DAY]
        for k in sorted(days)[:-14]:
            del days[k]
        json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rows = []
    for i, x in enumerate(days[today], 1):
        rows.append(f'<div class="c"><div class="n">{i}</div><div class="b"><div class="t">{esc(x["title"])}</div>'
                    f'<div class="u" dir="ltr">{esc(x["url"])}</div>'
                    f'<div class="a"><button class="btn cp" data-u="{esc(x["url"])}">📋 نسخ الرابط</button>'
                    f'<a class="btn go" href="{esc(inspect_link(x["url"]))}" target="_blank" rel="noopener">🔎 افتح في سيرش كونسول</a>'
                    f'<button class="btn ok" data-k="{esc(today)}-{i}">✅ تم</button></div></div></div>')
    page = ("<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'><meta name='robots' content='noindex,nofollow'>"
            "<title>روابط الفهرسة اليومية - عالم المستديرة</title><style>"
            "body{margin:0;background:#eef2f7;font-family:system-ui,-apple-system,Segoe UI,Tahoma,sans-serif;color:#0f2340}"
            "header{background:#0f2340;color:#fff;padding:18px 16px;font-size:20px;font-weight:800}header small{display:block;font-weight:400;opacity:.85;font-size:13px;margin-top:6px;line-height:1.7}"
            ".w{max-width:640px;margin:0 auto;padding:12px}.c{display:flex;gap:10px;background:#fff;border-radius:14px;padding:12px;margin:0 0 10px;box-shadow:0 2px 8px rgba(0,0,0,.06)}"
            ".n{min-width:30px;height:30px;border-radius:50%;background:#1d5fd1;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:800}"
            ".b{flex:1;min-width:0}.t{font-weight:700;font-size:15px;margin-bottom:4px}.u{font-size:11.5px;color:#5b6b80;word-break:break-all;margin-bottom:8px}"
            ".a{display:flex;gap:6px;flex-wrap:wrap}.btn{border:0;border-radius:9px;padding:9px 10px;font-size:13.5px;font-weight:700;font-family:inherit;text-decoration:none;cursor:pointer}"
            ".cp{background:#eef2f7;color:#0f2340}.go{background:#1d5fd1;color:#fff}.ok{background:#e8f7ee;color:#0b6b3a}"
            ".done{opacity:.45}.done .ok{background:#0b6b3a;color:#fff}"
            "#toast{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);background:#0b6b3a;color:#fff;padding:10px 16px;border-radius:20px;display:none;font-size:14px}"
            "</style></head><body><header>روابط اليوم للفهرسة (" + esc(today) + ")<small>"
            "1) اضغط «افتح في سيرش كونسول» ← انتظر الفحص ← «طلب الفهرسة».<br>"
            "2) لو ما فتح الرابط مباشرة: «نسخ الرابط» ثم الصقه في خانة البحث أعلى سيرش كونسول.<br>"
            "3) اضغط «تم» بعد كل رابط. قوقل يسمح بحوالي 10 طلبات يوميًا، والقائمة تتجدد كل يوم تلقائيًا.</small></header><div class='w'>"
            + "".join(rows) + "</div><div id='toast'>تم النسخ</div><script>"
            "document.querySelectorAll('.cp').forEach(function(b){b.onclick=async function(){try{await navigator.clipboard.writeText(b.dataset.u);"
            "var t=document.getElementById('toast');t.style.display='block';setTimeout(function(){t.style.display='none'},2000)}catch(e){prompt('انسخ الرابط',b.dataset.u)}}});"
            "document.querySelectorAll('.ok').forEach(function(b){var c=b.closest('.c');if(localStorage.getItem(b.dataset.k))c.classList.add('done');"
            "b.onclick=function(){c.classList.toggle('done');c.classList.contains('done')?localStorage.setItem(b.dataset.k,1):localStorage.removeItem(b.dataset.k)}});"
            "</script></body></html>")
    open(OUT, "w", encoding="utf-8").write(page)
    print("روابط اليوم:", len(days[today]))


if __name__ == "__main__":
    main()
