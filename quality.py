"""أدوات مشتركة: فلتر السيدات، أهمية الأخبار والمباريات، التدقيق الإملائي، وحصص النشر اليومية."""
import json
import math
import re
from datetime import datetime

import sports_bot as sb

WOMEN_RE = re.compile(r"\bwomen\b|\bwomens\b|\bwomen's\b|\bladies\b|\bfemenin\w*\b|\bfeminin\w*\b|\bfrauen\b|\bwsl\b|\bnwsl\b|"
                      r"\bfemmes\b|\(w\)|\bgirls\b|نساء|سيدات|الستات|للسيدات|النسائ", re.I)
# أندية ومنتخبات ولاعبون ذوو أهمية عالية (بالإنجليزية كما تأتي من الخلاصات)
BIG_EN = ["liverpool", "manchester united", "man utd", "man united", "manchester city", "man city", "arsenal", "chelsea",
          "tottenham", "spurs", "newcastle", "real madrid", "barcelona", "atletico", "atlético", "bayern", "dortmund",
          "leverkusen", "psg", "paris saint-germain", "juventus", "inter milan", "ac milan", "napoli", "roma",
          "al-hilal", "al hilal", "al-nassr", "al nassr", "al-ittihad", "al ittihad", "al-ahli", "al ahli", "saudi pro league",
          "champions league", "world cup", "ronaldo", "messi", "mbappe", "mbappé", "haaland", "salah", "vinicius", "vinícius",
          "bellingham", "yamal", "kane", "neymar", "benzema", "mahrez", "saint-maximin", "amorim", "guardiola", "slot",
          "arteta", "ancelotti", "flick", "mourinho", "klopp", "xabi alonso", "transfer", "sacked", "injury", "ban"]
BIG_TEAMS_API = {"Al-Hilal Saudi FC", "Al-Nassr", "Al-Ittihad FC", "Al-Ahli Jeddah", "Al-Qadisiyah FC", "Real Madrid", "Barcelona",
                 "Atletico Madrid", "Manchester City", "Arsenal", "Liverpool", "Chelsea", "Manchester United", "Tottenham",
                 "Bayern München", "Borussia Dortmund", "Bayer Leverkusen", "Paris Saint Germain", "Inter", "AC Milan",
                 "Juventus", "Napoli", "AS Roma", "Newcastle", "Al Ahly", "Zamalek", "Wydad AC", "Esperance Sportive De Tunis"}
FA = str.maketrans({"چ": "تش", "پ": "ب", "گ": "ج", "ژ": "ج", "ی": "ي", "ک": "ك", "ۆ": "و", "ە": "ه", "ہ": "ه", "ۀ": "ة", "ٹ": "ت"})


def is_women(*texts):
    return any(WOMEN_RE.search(t or "") for t in texts)


def news_score(title, desc=""):
    t = f"{title} {desc}".lower()
    if BANNED_RE.search(t):
        return 0  # مواعيد/قنوات/تشكيلات متوقعة/معاينات: ممنوعة بسياسة 27 نوفمبر
    s = sum(1 for k in BIG_EN if k in t)
    if s and BUZZ_RE.search(t):
        s += 1  # خبر لافت يتكلم عنه الجمهور
    return s


# سياسة 27 نوفمبر: ممنوع مقالات المواعيد والقنوات والتشكيلات المتوقعة والمعاينات
BANNED_RE = re.compile(
    r"predicted line|possible line|probable line|expected line|team news|\bline-?ups?\b|starting xi|confirmed xi|"
    r"how to watch|where to watch|tv channel|live stream|kick-?off time|what time is|\bpreview|\bprediction|"
    r"\bbetting\b|\bodds\b|\btips\b|\blive:|live updates|as it happened|"
    r"موعد مباراة|مواعيد مباريات|مباريات اليوم|القنوات الناقلة|القناة الناقلة|التشكيلة? المتوقع", re.I)
BUZZ_RE = re.compile(
    r"\brecord\b|stunning|comeback|remontada|wonder ?goal|screamer|goal of the|hat-?trick|\bsacked\b|\bfired\b|"
    r"here we go|\bblasts?\b|\bslams?\b|\brow\b|controvers|furious|historic|\bhistory\b|first time|\bshock|"
    r"injury blow|ruled out|red card|\bbanned\b|\bsigns?\b|\bagreed\b", re.I)


def report_notable(full, events=None):
    """هل المباراة فيها شيء مميز يستحق تقريرًا؟ يرجع قائمة الأسباب (فارغة = مباراة عادية لا نكتب عنها)"""
    why = []
    th, ta = full["teams"]["home"], full["teams"]["away"]
    gh, ga = full["goals"].get("home") or 0, full["goals"].get("away") or 0
    big = [s for s in ("home", "away") if full["teams"][s]["name"] in BIG_TEAMS_API]
    status = full["fixture"]["status"]["short"]
    rnd = (full["league"].get("round") or "").lower()
    if len(big) == 2:
        why.append("قمة بين كبيرين")
    if gh + ga >= 4:
        why.append("مباراة غزيرة الأهداف")
    if status in ("PEN", "AET"):
        why.append("وقت إضافي أو ركلات ترجيح")
    if len(big) == 1:
        bg, og = (gh, ga) if big[0] == "home" else (ga, gh)
        if bg < og:
            why.append("خسارة مفاجئة لفريق كبير")
        elif bg == og:
            why.append("تعثر فريق كبير")
    if full["league"]["id"] in (1, 2, 12, 17) and rnd and not any(k in rnd for k in ("league stage", "group", "regular")):
        why.append("دور إقصائي")
    ev = events if events is not None else (full.get("events") or [])
    scorers = {}
    run_h = run_a = 0
    trailed = {"home": False, "away": False}
    for e in ev:
        det = e.get("detail") or ""
        if e.get("type") == "Card" and "Red" in det:
            why.append("بطاقة حمراء")
        if e.get("type") != "Goal" or "Missed" in det:
            continue
        p = e.get("player")
        p = p.get("name") if isinstance(p, dict) else p
        if p and det != "Own Goal":
            scorers[p] = scorers.get(p, 0) + 1
        tm = e.get("team")
        tid = tm.get("id") if isinstance(tm, dict) else None
        tname = tm.get("name") if isinstance(tm, dict) else tm
        side = "home" if (tid is not None and tid == th.get("id")) or tname == th.get("name") else "away"
        if side == "home":
            run_h += 1
        else:
            run_a += 1
        if run_h < run_a:
            trailed["home"] = True
        if run_a < run_h:
            trailed["away"] = True
    if any(n >= 3 for n in scorers.values()):
        why.append("هاتريك")
    if (gh > ga and trailed["home"]) or (ga > gh and trailed["away"]):
        why.append("عودة في النتيجة")
    return list(dict.fromkeys(why))


def team_big(f):
    return sum(1 for s in ("home", "away") if f["teams"][s]["name"] in BIG_TEAMS_API)


def fix_ar(s):
    """تنظيف إملائي آلي بسيط (يعمل بدون الذكاء الاصطناعي)"""
    if not isinstance(s, str):
        return s
    s = s.translate(FA).replace("ـ", "")
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"\s+([،؛:!؟\.,])", r"\1", s)
    s = re.sub(r"([،؛])(?=[^\s\d])", r"\1 ", s)
    s = re.sub(r"([!؟\.]){3,}", r"\1", s)
    s = re.sub(r"،{2,}", "،", s)
    s = s.replace(" ,", "،").replace("؟?", "؟")
    L = "\u0621-\u064A"
    for a, b in (("إنشاء الله", "إن شاء الله"), ("لاكن", "لكن"), ("هاذا", "هذا"), ("هاذه", "هذه"), ("اللذي", "الذي"),
                 ("إذاً", "إذًا"), ("الان", "الآن"), ("اكثر", "أكثر"), ("افضل", "أفضل"), ("اغلب", "أغلب"),
                 ("الاول", "الأول"), ("الاخير", "الأخير"), ("الاهداف", "الأهداف"), ("الاندية", "الأندية")):
        s = re.sub(f"(?<![{L}]){a}(?![{L}])", b, s)
    return s.strip()


def _walk(o, fn):
    if isinstance(o, str):
        return fn(o)
    if isinstance(o, list):
        return [_walk(x, fn) for x in o]
    if isinstance(o, dict):
        return {k: _walk(v, fn) for k, v in o.items()}
    return o


def _shape(o):
    if isinstance(o, dict):
        return {k: _shape(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_shape(o[0])] if o else []
    return type(o).__name__


SKIP_KEYS = ("star_en", "venue_en", "photo_subject_en", "teams_en", "teams_ar", "tags", "home_ar", "away_ar", "players_ar", "slug")


def proofread(data):
    """تدقيق إملائي ونحوي للنص: مرحلة آلية ثم مراجعة Gemini. عند أي خلل نرجع النسخة الآلية."""
    data = _walk(data, fix_ar)
    keep = {k: data.pop(k) for k in list(data) if k in SKIP_KEYS}
    try:
        raw = sb.claude(
            "أنت مدقق لغوي عربي محترف. صحّح الأخطاء الإملائية والنحوية وعلامات الترقيم والهمزات في قيم النصوص داخل JSON التالي، "
            "وأصلح الجمل الركيكة أو المكررة بأقل تعديل ممكن، ولا تغيّر المعنى ولا الأرقام ولا الأسماء ولا مفاتيح JSON ولا ترتيبها "
            "ولا عدد عناصر القوائم. أعد JSON فقط بنفس البنية تمامًا بدون أي شرح.\n"
            + json.dumps(data, ensure_ascii=False), 6000)
        from seo_poster import parse_json
        new = parse_json(raw)
        if _shape(new) == _shape(data):
            old_len = len(json.dumps(data, ensure_ascii=False))
            new_len = len(json.dumps(new, ensure_ascii=False))
            if 0.85 <= new_len / max(old_len, 1) <= 1.15:
                data = _walk(new, fix_ar)
    except Exception as e:
        print("تعذر التدقيق بالذكاء الاصطناعي:", str(e)[:150], flush=True)
    data.update(keep)
    return data


# ---------- حصص النشر اليومية (تُحفظ داخل حالة كل بوت) ----------
def today():
    return datetime.now(sb.TZ).strftime("%Y-%m-%d")


def day_counts(st):
    d = st.setdefault("daily", {})
    for k in sorted(d)[:-5]:
        del d[k]
    return d.setdefault(today(), {"pub": 0, "draft": 0, "rep": 0})


def spread_allowed(cap):
    """توزيع الحصة على اليوم: لا نستهلك كل شيء في أول ساعات"""
    h = datetime.now(sb.TZ).hour
    return min(cap, math.ceil(cap * (h + 1) / 20))


# ---------- منع تكرار نفس الخبر بروابط مختلفة ----------
_STOP = set("the a an of to in on for and at is with as by from after over into his her their its be has have will are was were "
            "that this it vs v not but new says say could would out up down more than who what when how why".split())


def norm_link(u):
    u = (u or "").split("#")[0].split("?")[0].lower().rstrip("/")
    return re.sub(r"^https?://(www\.|m\.)?", "", u)


def title_words(t):
    ws = re.findall(r"[a-z0-9]+", (t or "").lower())
    return {w for w in ws if w not in _STOP and len(w) > 2}


def same_story(a, b):
    """true إذا العنوانان لنفس الخبر تقريبًا (تقاطع كلمات مرتفع)"""
    wa, wb = title_words(a), title_words(b)
    if len(wa) < 3 or len(wb) < 3:
        return False
    inter = len(wa & wb)
    return inter >= 4 and inter / min(len(wa), len(wb)) >= 0.6 or inter / len(wa | wb) >= 0.55


def is_dup(title, recent):
    return any(same_story(title, r) for r in recent)


GENERIC_AR = set("""دوري أبطال أوروبا آسيا أفريقيا مباراة المباراة التعادل تعادل فوز يفوز يهزم أمام ضد على في من مع بعد قبل
الدوري الممتاز الإنجليزي الإسباني الإيطالي الألماني الفرنسي السعودي للمحترفين اليوم والقنوات الناقلة والتشكيلة المتوقعة موعد
نتيجة هدف هدفين بثلاثية برباعية بخماسية بهدف ثمينة نقطة الأبطال قمة يتعادل يتجاوز يكتسح سقوط فخ""".split())
def _sig(t):
    import re as _re
    w = _re.findall(r"[\u0600-\u06ff]{3,}", t or "")
    return {x for x in w if x not in GENERIC_AR}
def dup_site(ar_title, site_titles):
    """نفس الخبر منشور في الموقع؟ (3 كلمات مميزة مشتركة أو أكثر)"""
    a = _sig(ar_title)
    return any(len(a & _sig(t)) >= 3 for t in site_titles)
def site_titles(days=3):
    import json as _j, urllib.request as _u
    from datetime import datetime as _d, timedelta as _t, timezone as _z
    out = []
    try:
        for kind in ("default", "summary"):
            pass
        d = _j.load(_u.urlopen("https://www.fottballcia.com/feeds/posts/summary?alt=json&max-results=60", timeout=30))
        lim = _d.now(_z.utc) - _t(days=days)
        for e in d["feed"].get("entry", []):
            if _d.fromisoformat(e["published"]["$t"]) >= lim:
                out.append(e["title"]["$t"])
    except Exception as ex:
        print("تعذر قراءة عناوين الموقع", ex)
    return out
