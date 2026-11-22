#!/usr/bin/env python3
"""
يبدّل صور الأغلفة التصميمية في مقالات الأخبار القديمة بصورة حقيقية للاعب/المدرب (ويكيميديا كومنز)
أو بشعاري الفريقين. لا يغير العنوان ولا الرابط. تقارير المباريات تبقى كما هي (فيها الشعارات والنتيجة).
DRY_RUN=1 يطبع فقط | LIMIT=0 الكل
"""
import hashlib
import html
import json
import os
import re
import time
from datetime import datetime
import seo_poster as sp
import sports_bot as sb

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "data", "photo_backfill.json")
DRY = os.environ.get("DRY_RUN", "0") == "1"
LIMIT = int(os.environ.get("LIMIT", "0") or 0)


def load():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=0)


def all_posts():
    token = None
    while True:
        params = {"maxResults": 50, "fetchBodies": "true", "status": "live"}
        if token:
            params["pageToken"] = token
        data = sb.blogger("/posts", **params)
        for p in data.get("items", []):
            yield p
        token = data.get("nextPageToken")
        if not token:
            break


def ask_subject(title, text):
    raw = sb.claude(
        "اقرأ عنوان ونص مقال كرة قدم وحدد الصورة المناسبة له. أعد JSON فقط:\n"
        '{"photo_subject_en": "عنوان صفحة ويكيبيديا الإنجليزية بالضبط للاعب أو المدرب الأبرز في المقال مثل Erling Haaland، أو فارغ إذا لا يوجد شخص بارز",'
        ' "teams_en": ["الاسم الإنجليزي للناديين أو المنتخبين إذا كان المقال عن مواجهة بينهما، وإلا قائمة فارغة"],'
        ' "teams_ar": ["نفس الفرق بالعربي وبنفس الترتيب"]}\n\n'
        f"العنوان: {title}\nالنص: {text[:1800]}",
        max_tokens=300,
    )
    return sp.parse_json(raw)


def main():
    st = load()
    done = 0
    for p in all_posts():
        if LIMIT and done >= LIMIT:
            break
        pid = p["id"]
        labels = p.get("labels") or []
        content = p.get("content") or ""
        if pid in st or "تقارير المباريات" in labels or 'data-ph="1"' in content:
            continue
        m = re.search(r'<div class="post-cover"[^>]*>\s*<img src="([^"]+)"', content)
        if not m or sp.IMG_BASE not in m.group(1):
            st[pid] = "skip"
            continue
        old_url = m.group(1)
        title = (p.get("title") or "").strip()
        text = re.sub(r"\s+", " ", re.sub(r"<script.*?</script>|<[^>]+>", " ", content, flags=re.S))
        try:
            data = ask_subject(title, text)
        except Exception as e:
            print("تعذر التحليل:", title, sp.why(e), flush=True)
            continue
        kicker = next((l for l in labels if l != "أخبار كرة القدم"), "أخبار كرة القدم")
        slug = re.sub(r"\.html$", "", (p.get("url") or "").rsplit("/", 1)[-1]) or "post"
        key = pid + "-ph"
        if DRY:
            print("DRY", title, "|", data, flush=True)
            done += 1
            continue
        img, credit = sp.news_image(data, slug, key, title, [kicker])
        if not img or sp.LAST_IMAGE_KIND == "news":
            st[pid] = "none"
            _rm(img)
            print("لا توجد صورة مناسبة:", title, flush=True)
            continue
        new = content.replace(old_url, img)
        new = new.replace('<div class="post-cover"', '<div class="post-cover" data-ph="1"', 1)
        if credit:
            new = re.sub(r'(<div class="post-cover" data-ph="1"[^>]*>\s*<img [^>]*/?>)',
                         lambda mm: mm.group(1) + f'<div style="font-size:12px;color:#7a8a82;margin-top:4px">{credit}</div>',
                         new, count=1)
        try:
            sb.blogger(f"/posts/{pid}", "PATCH", {"content": new})
            st[pid] = sp.LAST_IMAGE_KIND
            done += 1
            print("تم:", st[pid], title, p.get("url"), flush=True)
        except Exception as e:
            print("تعذر تعديل", p.get("url"), sp.why(e), flush=True)
        save(st)
        time.sleep(1.5)
    save(st)
    print(f"عُدّل: {done}")


def _rm(url):
    try:
        if url and url.startswith(sp.IMG_BASE):
            os.remove(os.path.join(ROOT, "img", url[len(sp.IMG_BASE):]))
    except Exception:
        pass


if __name__ == "__main__":
    main()
