import json, os
import sports_bot as sb
CONTENT = ('<div id="mc-root" dir="rtl">جاري تحميل مركز المباراة...</div>\n'
           '<noscript>يحتاج مركز المباراة إلى تفعيل جافاسكربت.</noscript>\n'
           '<script src="https://nawaf737991-coder.github.io/fottballcia/match.js?v=1"></script>')
pages = sb.blogger("/pages", "GET", None, status="live", maxResults=50).get("items", [])
for p in pages:
    if p.get("url", "").endswith("/p/match.html"):
        sb.blogger(f"/pages/{p['id']}", "PATCH", {"content": CONTENT})
        print("تم تحديث:", p["url"]); break
else:
    p = sb.blogger("/pages", "POST", {"title": "match", "content": CONTENT})
    sb.blogger(f"/pages/{p['id']}", "PATCH", {"title": "مركز المباراة"})
    print("أُنشئت:", p.get("url"))
