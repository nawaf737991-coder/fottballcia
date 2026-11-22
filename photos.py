#!/usr/bin/env python3
"""
صور حقيقية لمقالات الأخبار بشكل قانوني:
- صورة اللاعب/المدرب/النادي من ويكيميديا كومنز (رخص حرة فقط CC/Public domain) مع نسب الصورة لصاحبها.
- شعارات الأندية من API-Football عند وجود فريقين في الخبر.
"""
import json
import re
import urllib.parse
import urllib.request

UA = {"User-Agent": "fottballcia-bot/1.0 (https://www.fottballcia.com; bot@users.noreply.github.com)"}
FREE = re.compile(r"^(cc[- ]?by|cc0|public domain|pd|attribution|gfdl|cc-by-sa|cc by-sa)", re.I)


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _api(base, **params):
    params.update(format="json", formatversion="2")
    return json.loads(_get(base + "?" + urllib.parse.urlencode(params)))


def _strip(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()


def wiki_photo(title, lang="en", min_w=300):
    """يرجع dict(bytes, credit, license, page) لصورة حرة للموضوع أو None"""
    if not title:
        return None
    try:
        q = _api(f"https://{lang}.wikipedia.org/w/api.php", action="query", titles=title,
                 prop="pageimages", piprop="name", redirects=1)
        pages = q.get("query", {}).get("pages", [])
        if not pages or pages[0].get("missing") or not pages[0].get("pageimage"):
            return None
        fname = pages[0]["pageimage"]
        if fname.lower().endswith((".svg", ".gif")):
            return None
        # الصورة لازم تكون على كومنز (الصور غير الحرة تكون محلية في ويكيبيديا فقط)
        c = _api("https://commons.wikimedia.org/w/api.php", action="query", titles="File:" + fname,
                 prop="imageinfo", iiprop="url|extmetadata|size", iiurlwidth=1280)
        cp = c.get("query", {}).get("pages", [])
        if not cp or cp[0].get("missing") or not cp[0].get("imageinfo"):
            return None
        ii = cp[0]["imageinfo"][0]
        meta = ii.get("extmetadata", {})
        lic = _strip(meta.get("LicenseShortName", {}).get("value"))
        if not FREE.match(lic or ""):
            return None
        if (ii.get("width") or 0) < min_w:
            return None
        artist = _strip(meta.get("Artist", {}).get("value")) or "Wikimedia Commons"
        data = _get(ii.get("thumburl") or ii["url"], timeout=40)
        return {"bytes": data, "credit": artist[:80], "license": lic,
                "page": ii.get("descriptionurl", "")}
    except Exception as e:
        print("تعذر جلب صورة ويكيميديا:", title, e, flush=True)
        return None


_LOGOS = None


def _norm(n):
    return re.sub(r"[^a-z0-9]", "", (n or "").lower().replace("fc", "").replace("afc", ""))


def _local_logos():
    """فهرس الأسماء -> الشعارات من ملفات البيانات (مباريات الأيام والنتائج)"""
    global _LOGOS
    if _LOGOS is not None:
        return _LOGOS
    import glob
    import os
    _LOGOS = {}
    root = os.path.dirname(os.path.abspath(__file__))
    def walk(o):
        if isinstance(o, dict):
            for nk, lk in (("home", "hl"), ("away", "al")):
                if isinstance(o.get(nk), str) and isinstance(o.get(lk), str):
                    _LOGOS.setdefault(_norm(o[nk]), o[lk])
            t = o.get("team")
            if isinstance(t, dict) and t.get("name") and t.get("logo"):
                _LOGOS.setdefault(_norm(t["name"]), t["logo"])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    for f in glob.glob(os.path.join(root, "data", "*.json")) + glob.glob(os.path.join(root, "data", "days", "*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                walk(json.load(fh))
        except Exception:
            pass
    return _LOGOS


def team_logo(name, football):
    """رابط شعار الفريق: من البيانات المحلية أولًا ثم بحث API-Football"""
    if not name:
        return None
    loc = _local_logos()
    k = _norm(name)
    if k in loc:
        return loc[k]
    for kk, v in loc.items():
        if k and len(k) > 4 and (k in kk or kk in k):
            return v
    try:
        res = football("teams", search=re.sub(r"[^A-Za-z0-9 ]", " ", name).strip()[:40])
        for r in res:
            t = r.get("team", {})
            if t.get("logo"):
                return t["logo"]
        return None
    except Exception as e:
        print("تعذر جلب الشعار:", name, e, flush=True)
        return None


if __name__ == "__main__":
    import sys
    for t in sys.argv[1:] or ["Erling Haaland", "Cristiano Ronaldo", "José Mourinho", "Al Hilal SFC"]:
        p = wiki_photo(t)
        print(t, "->", (p["license"], p["credit"], len(p["bytes"])) if p else None)
