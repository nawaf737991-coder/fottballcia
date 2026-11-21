#!/usr/bin/env python3
"""
ينقل المقالات الضعيفة إلى المسودات (revert) — قابل للتراجع من لوحة بلوجر.
المعايير: عنوان إنجليزي، أو أقل من MIN_WORDS كلمة، أو مقال "موعد مباراة/القنوات الناقلة" قديم.
DRY_RUN=1 يطبع فقط.
"""
import html
import os
import re
import time
import sports_bot as sb
DRY = os.environ.get("DRY_RUN", "1") == "1"
MIN_WORDS = int(os.environ.get("MIN_WORDS", "250") or 250)
def all_posts():
    token = None
    while True:
        params = {"maxResults": 50, "fetchBodies": "true", "status": "live"}
        if token:
            params["pageToken"] = token
        data = sb.blogger("/posts", **params)
        yield from data.get("items", [])
        token = data.get("nextPageToken")
        if not token:
            break
def words(content):
    c = re.split(r'<h[23][^>]*>\s*اقرأ أيضًا', content or "")[0]
    c = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", c)
    t = html.unescape(re.sub(r"<[^>]+>", " ", c))
    return len(re.findall(r"[\w\u0600-\u06FF]+", t))
def reasons(p):
    t = (p.get("title") or "").strip()
    why = []
    if len(re.findall(r"[A-Za-z]", t)) > len(re.findall(r"[\u0600-\u06FF]", t)):
        why.append("عنوان إنجليزي")
    w = words(p.get("content"))
    if w < MIN_WORDS:
        why.append(f"قصير ({w} كلمة)")
    if re.search(r"موعد مباراة|القنوات الناقلة|موعد المباراة", t):
        why.append("موعد مباراة قديم")
    return why
def main():
    n = kept = 0
    for p in all_posts():
        why = reasons(p)
        if not why:
            kept += 1
            continue
        n += 1
        line = f"{(p.get('published') or '')[:10]} | {p.get('title','').strip()} | {'، '.join(why)} | {p.get('url')}"
        if DRY:
            print("DRY", line, flush=True)
            continue
        try:
            sb.blogger(f"/posts/{p['id']}/revert", "POST")
            print("→ مسودة:", line, flush=True)
        except Exception as e:
            print("تعذر:", line, e, flush=True)
        time.sleep(1)
    print(f"نُقل/مرشح: {n} | باقي منشور: {kept}")
if __name__ == "__main__":
    main()
