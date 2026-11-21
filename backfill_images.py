#!/usr/bin/env python3
"""
يضيف صورة غلاف لكل مقال منشور لا يحتوي على صورة (لا يغير العنوان ولا الرابط).
DRY_RUN=1  يطبع فقط بدون تعديل
LIMIT=0    أقصى عدد مقالات تُعدّل (0 = الكل)
"""
import hashlib
import html
import os
import re
import time

import seo_poster as sp
import sports_bot as sb

DRY = os.environ.get("DRY_RUN", "0") == "1"
LIMIT = int(os.environ.get("LIMIT", "0") or 0)


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


def main():
    done = skipped = 0
    for p in all_posts():
        content = p.get("content") or ""
        if re.search(r"<img\b", content, re.I):
            skipped += 1
            continue
        if LIMIT and done >= LIMIT:
            break
        title = (p.get("title") or "").strip()
        url = p.get("url") or ""
        labels = p.get("labels") or []
        kicker = next((l for l in labels if l not in ("أخبار كرة القدم", "تقارير المباريات")), None) \
            or (labels[0] if labels else "أخبار كرة القدم")
        slug = re.sub(r"\.html$", "", url.rsplit("/", 1)[-1]) or "post"
        date = (p.get("published") or "")[:10]
        name = (date[:7].replace("-", "/") or "old") + f"/{slug[:70]}-{hashlib.md5(p['id'].encode()).hexdigest()[:6]}.jpg"
        if DRY:
            print("DRY", title, "|", kicker, "|", name)
            done += 1
            continue
        img = sp.make_cover("news", name, title=title, kicker=kicker, date_text=date)
        if not img:
            continue
        esc = html.escape
        block = (f'<div class="post-cover" style="margin:0 0 16px"><img src="{esc(img)}" alt="{esc(title)}" '
                 f'title="{esc(title)}" width="1200" height="675" '
                 f'style="width:100%;height:auto;border-radius:12px"/></div>\n')
        try:
            sb.blogger(f"/posts/{p['id']}", "PATCH", {"content": block + content})
            done += 1
            print("أضيفت صورة:", title, url, flush=True)
        except Exception as e:
            print("تعذر تعديل", url, sp.why(e), flush=True)
        time.sleep(1)
    print(f"عُدّل: {done} | فيها صور مسبقًا: {skipped}")


if __name__ == "__main__":
    main()
