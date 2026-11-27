"""إضافة تغريدة رسمية لمباراة (تضمين فقط). تتحقق من: حساب رسمي + وجود التغريدة فعلاً عبر oEmbed الرسمي."""
import json, os, re, sys, urllib.request, urllib.parse
ROOT = os.path.dirname(os.path.abspath(__file__))
F = os.path.join(ROOT, "data", "embed_tweets.json")
A = os.path.join(ROOT, "data", "official_accounts.json")

def die(msg):
    print("REJECT:", msg); sys.exit(1)

fid = os.environ.get("FID", "").strip()
url = os.environ.get("URL", "").strip().split("?")[0]
minute = os.environ.get("MIN", "").strip()
kind = os.environ.get("KIND", "").strip()
new_acc = os.environ.get("NEW_ACCOUNT", "").strip().lstrip("@")
remove = os.environ.get("REMOVE", "") == "1"
if not fid.isdigit(): die("رقم المباراة غير صحيح")
m = re.match(r"^https://(?:x|twitter|mobile\.twitter)\.com/([A-Za-z0-9_]{1,15})/status/(\d+)$", url)
if not m: die("رابط التغريدة غير صحيح، شكله: https://x.com/اسم_الحساب/status/رقم")
handle, tid = m.group(1), m.group(2)
url = f"https://x.com/{handle}/status/{tid}"
acc = json.load(open(A, encoding="utf-8"))
if new_acc:
    if not re.match(r"^[A-Za-z0-9_]{1,15}$", new_acc): die("اسم الحساب غير صحيح")
    if new_acc.lower() not in [x.lower() for x in acc["accounts"]]:
        acc["accounts"].append(new_acc)
        json.dump(acc, open(A, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
if handle.lower() not in [x.lower() for x in acc["accounts"]]:
    die(f"الحساب @{handle} ليس في قائمة الحسابات الرسمية. إذا كان حساب نادي رسمي أعد التشغيل وضع اسمه في خانة new_account")
data = {}
if os.path.exists(F):
    data = json.load(open(F, encoding="utf-8"))
data = data.get("matches", data)
lst = [x if isinstance(x, dict) else {"u": x} for x in data.get(fid, [])]
if remove:
    lst = [x for x in lst if x["u"] != url]
else:
    # تحقق فعلي من وجود التغريدة وأنها من نفس الحساب
    try:
        req = urllib.request.Request("https://publish.twitter.com/oembed?omit_script=1&url=" + urllib.parse.quote(url, safe=""), headers={"User-Agent": "Mozilla/5.0"})
        j = json.load(urllib.request.urlopen(req, timeout=25))
    except Exception as e:
        die(f"التغريدة غير موجودة أو محذوفة أو محمية ({e})")
    if "pic.twitter.com" not in (j.get("html") or "") and os.environ.get("ALLOW_LINK") != "1":
        die("التغريدة بدون صورة أو فيديو داخل X (رابط فقط لموقع آخر)، فلن يظهر فيها مقطع. اختر تغريدة فيها الفيديو نفسه")
    au = (j.get("author_url") or "").rstrip("/").split("/")[-1]
    if au.lower() != handle.lower(): die("صاحب التغريدة لا يطابق الحساب في الرابط")
    if not any(x["u"] == url for x in lst):
        item = {"u": url, "h": handle}
        if minute.isdigit(): item["m"] = int(minute)
        if kind: item["t"] = kind
        lst.append(item)
data[fid] = lst[:12]
json.dump({"matches": data}, open(F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("OK", fid, url, "minute", minute or "-")

# ---- إضافة/تحديث التغريدات داخل مقال تقرير المباراة (إن وُجد) ----
try:
    st = json.load(open(os.path.join(ROOT, "data", "seo_state.json"), encoding="utf-8"))
    pid = (st.get("report_posts") or {}).get(fid)
except Exception:
    pid = None
if pid and os.environ.get("BLOGGER_BLOG_ID"):
    sys.path.insert(0, ROOT)
    import sports_bot as sb
    try:
        post = sb.blogger(f"/posts/{pid}")
        body = post.get("content", "")
        body = re.sub(r'<div class="tw-embeds">.*?</div><!--tw-->', "", body, flags=re.S)
        body = re.sub(r'<div class="tw-embeds"><h2>مقاطع المباراة</h2>(?:<blockquote class="twitter-tweet".*?</blockquote>)*</div>', "", body, flags=re.S)
        body = re.sub(r'<h2>مقاطع المباراة</h2>(?:<blockquote class="twitter-tweet".*?</blockquote>)+', "", body, flags=re.S)
        acc_l = {x.lower() for x in acc["accounts"]}
        quotes = "".join(f'<blockquote class="twitter-tweet" data-lang="ar" data-dnt="true"><a href="{x["u"]}"></a></blockquote>'
                         for x in data[fid][:6] if x["u"].split("/")[3].lower() in acc_l)
        if quotes:
            block = f'<div class="tw-embeds"><h2>مقاطع المباراة</h2>{quotes}</div><!--tw-->'
            for mark in ("<h2>ملخص المباراة</h2>", "<h2>أرقام المباراة", "<h2>المباريات القادمة"):
                if mark in body:
                    body = body.replace(mark, block + mark, 1); break
            else:
                body += block
        sb.blogger(f"/posts/{pid}", "PATCH", {"content": body})
        print("حُدّث مقال التقرير بالتغريدات", pid)
    except Exception as e:
        print("تعذر تحديث مقال التقرير:", str(e)[:200])
else:
    print("لا يوجد مقال تقرير لهذه المباراة بعد؛ التغريدة تظهر في مركز المباراة، وتُضاف تلقائيًا لأي تقرير يُكتب لاحقًا")
