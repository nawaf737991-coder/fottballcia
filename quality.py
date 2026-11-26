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
    return sum(1 for k in BIG_EN if k in t)


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
