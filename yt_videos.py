"""ملخصات رسمية من يوتيوب للمباريات القوية (تضمين فقط، بلا تحميل ولا رفع).
- يقرأ آخر فيديوهات القنوات الرسمية فقط (playlistItems = وحدة حصة لكل قناة).
- يطابق عنوان الفيديو مع اسمي الفريقين، ويشترط: نُشر بعد المباراة، عنوانه ملخص/أهداف، قابل للتضمين، عام، ليس نسائيًا.
- يكتب data/embed_videos.json (يقرأه match.js) ويضيف الفيديو لمقال التقرير إن وُجد."""
import glob, json, os, re, sys, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
ROOT = os.path.dirname(os.path.abspath(__file__))
D = lambda *p: os.path.join(ROOT, "data", *p)
KEY = os.environ.get("YOUTUBE_API_KEY", "")
if not KEY:
    print("YOUTUBE_API_KEY غير موجود"); sys.exit(0)
API = "https://www.googleapis.com/youtube/v3/"
# (handle, نص يجب أن يظهر في اسم القناة) - لا يُقبل إلا إذا تطابق الاسم وعدد المشتركين >= 100 ألف
CHANNELS = [("beINSPORTS", "bein"), ("beINSPORTSArabia", "bein"), ("beINSPORTSEN", "bein"), ("SPL", "saudi"), ("SaudiProLeague", "saudi"),
            ("ChampionsLeague", "champions league"), ("UEFA", "uefa"), ("LaLiga", "laliga"), ("premierleague", "premier league"),
            ("SerieA", "serie a"), ("bundesliga", "bundesliga"), ("AFCChampionsLeague", "afc"), ("CAFOnline", "caf"), ("fifa", "fifa")]
GOOD = re.compile(r"highlight|goals|all goals|extended|summary|ملخص|أهداف|اهداف|الأهداف", re.I)
BAD = re.compile(r"press conference|preview|reaction|interview|predict|women|femin|مؤتمر|تصريحات|نسائ|سيدات|live\b|بث مباشر", re.I)
STOP = {"fc", "cf", "club", "afc", "sc", "ac", "al", "de", "the", "city", "united", "real", "manchester", "sporting", "saint", "borussia", "olympique", "athletic", "atletico", "inter", "san", "st"}
ALIAS = {"manchester united": ["man united", "man utd"], "manchester city": ["man city"], "tottenham": ["spurs"], "paris saint germain": ["psg", "paris sg"],
         "atletico madrid": ["atletico", "atleti"], "inter": ["inter milan", "internazionale"], "bayern munich": ["bayern"], "newcastle": ["newcastle"],
         "real madrid": ["real madrid"], "borussia dortmund": ["dortmund"], "al nassr": ["nassr"], "al hilal": ["hilal"], "al ittihad": ["ittihad"], "al ahli": ["ahli"]}

def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9\u0600-\u06ff ]+", " ", s).strip()

def api(path, **p):
    p["key"] = KEY
    with urllib.request.urlopen(API + path + "?" + urllib.parse.urlencode(p), timeout=30) as r:
        return json.load(r)

try:
    ar_names = json.load(open(D("names_cache.json"), encoding="utf-8"))
except Exception:
    ar_names = {}

def keys(team):
    n = norm(team)
    out = {n} | set(ALIAS.get(n, []))
    toks = [t for t in n.split() if t not in STOP and len(t) >= 4]
    out |= set(toks)
    ar = ar_names.get(team)
    if ar: out.add(norm(ar)); out |= {t for t in norm(ar).split() if len(t) >= 4 and t not in ("الاتحاد", "نادي")}
    return {k for k in out if k}

def has(title, team):
    t = " " + norm(title) + " "
    return any(" " + k + " " in t for k in keys(team))

# ---- المباريات المرشحة: تقارير ومعاينات (مباريات قوية فقط) ----
st = json.load(open(D("seo_state.json"), encoding="utf-8"))
cand = {str(x) for x in st.get("reports", [])[-40:]}
try:
    cand |= {str(p["fid"]) for p in json.load(open(D("previews_state.json"), encoding="utf-8")).get("posts", [])[-40:]}
except Exception:
    pass
matches = {}
def walk(o):
    if isinstance(o, dict):
        if "id" in o and "home" in o and "away" in o and "time" in o: matches[str(o["id"])] = o
        for v in o.values(): walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
for f in glob.glob(D("days", "2026-*.json")) + [D("results.json")]:
    try: walk(json.load(open(f, encoding="utf-8")))
    except Exception: pass
now = datetime.now(timezone.utc)
todo = []
for fid in cand:
    m = matches.get(fid)
    if not m or m.get("status") not in ("FT", "AET", "PEN"): continue
    ko = datetime.fromisoformat(m["time"]).astimezone(timezone.utc)
    if now - ko > timedelta(days=4): continue
    todo.append((fid, m, ko))
out_path = D("embed_videos.json")
store = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {"matches": {}, "posted": []}
todo = [t for t in todo if t[0] not in store["matches"]]
print("مباريات تنتظر فيديو:", len(todo))
if not todo and not store["matches"]:
    print("لا شيء"); 

# ---- القنوات الرسمية ----
videos = []
if todo:
    for handle, must in CHANNELS:
        try:
            c = api("channels", part="snippet,statistics,contentDetails", forHandle="@" + handle).get("items") or []
            if not c: continue
            c = c[0]; title = c["snippet"]["title"]; subs = int(c["statistics"].get("subscriberCount", 0))
            if must not in title.lower() or subs < 100000:
                print("تجاهل قناة غير مؤكدة:", handle, title, subs); continue
            up = c["contentDetails"]["relatedPlaylists"]["uploads"]
            items = api("playlistItems", part="snippet", playlistId=up, maxResults=50).get("items", [])
            for it in items:
                s = it["snippet"]
                videos.append({"v": s["resourceId"]["videoId"], "t": s["title"], "c": title, "p": s["publishedAt"]})
            print("قناة معتمدة:", title, subs, len(items))
        except Exception as e:
            print("خطأ قناة", handle, str(e)[:120])
changed = False
for fid, m, ko in todo:
    hits = []
    for v in videos:
        if not (GOOD.search(v["t"]) and not BAD.search(v["t"])): continue
        pub = datetime.fromisoformat(v["p"].replace("Z", "+00:00"))
        if pub < ko + timedelta(minutes=100): continue
        if has(v["t"], m["home"]) and has(v["t"], m["away"]): hits.append(v)
    if not hits: continue
    ids = [h["v"] for h in hits][:5]
    ok = {i["id"] for i in api("videos", part="status", id=",".join(ids)).get("items", [])
          if i["status"].get("embeddable") and i["status"].get("privacyStatus") == "public"}
    good = [h for h in hits if h["v"] in ok][:2]
    if good:
        store["matches"][fid] = good; changed = True
        print("فيديو للمباراة", fid, m["home"], m["away"], [g["t"] for g in good])
if changed:
    json.dump(store, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---- إضافة الفيديو لمقال التقرير ----
posts = st.get("report_posts", {})
sys.path.insert(0, ROOT)
if any(f in posts and f not in store["posted"] for f in store["matches"]):
    import sports_bot as sb
    for fid, vids in store["matches"].items():
        pid = posts.get(fid)
        if not pid or fid in store["posted"]: continue
        try:
            post = sb.blogger(f"/posts/{pid}")
            body = post.get("content", "")
            if "yt-embed" not in body:
                v = vids[0]
                block = (f'<div class="yt-embed" style="margin:16px 0"><h2>ملخص المباراة بالفيديو</h2>'
                         f'<div style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden"><iframe src="https://www.youtube.com/embed/{v["v"]}" '
                         f'style="position:absolute;top:0;left:0;width:100%;height:100%;border:0" allowfullscreen loading="lazy" title="ملخص المباراة"></iframe></div>'
                         f'<p style="font-size:12px;color:#6b7a89">المصدر: قناة {v["c"]} الرسمية على يوتيوب.</p></div>')
                for mark in ("<h2>أرقام المباراة", "<h2>المباريات القادمة"):
                    if mark in body:
                        body = body.replace(mark, block + mark, 1); break
                else:
                    body += block
                sb.blogger(f"/posts/{pid}", "PATCH", {"content": body})
                print("أُضيف الفيديو لمقال", pid)
            store["posted"].append(fid); changed = True
        except Exception as e:
            print("تعذر تحديث المقال", pid, str(e)[:150])
    json.dump(store, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
