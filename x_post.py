#!/usr/bin/env python3
"""نشر تغريدة في حساب X (OAuth 1.0a بدون مكتبات خارجية).
المتغيرات: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
اختياري: X_DAILY (الافتراضي 3 تغريدات في اليوم)
"""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import urllib.parse
import urllib.request

URL = "https://api.x.com/2/tweets"
KEYS = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")


def enabled():
    return all(os.environ.get(k, "").strip() for k in KEYS)


def _q(s):
    return urllib.parse.quote(str(s), safe="~")


def _auth_header(method, url):
    ck, cs, tk, ts = (os.environ[k].strip() for k in KEYS)
    oauth = {
        "oauth_consumer_key": ck, "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1", "oauth_timestamp": str(int(time.time())),
        "oauth_token": tk, "oauth_version": "1.0",
    }
    params = "&".join(f"{_q(k)}={_q(v)}" for k, v in sorted(oauth.items()))
    base = "&".join([method, _q(url), _q(params)])
    key = f"{_q(cs)}&{_q(ts)}".encode()
    oauth["oauth_signature"] = base64.b64encode(hmac.new(key, base.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join(f'{_q(k)}="{_q(v)}"' for k, v in sorted(oauth.items()))


def tweet(text):
    req = urllib.request.Request(URL, data=json.dumps({"text": text}).encode(), method="POST", headers={
        "Authorization": _auth_header("POST", URL), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())["data"]["id"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"X HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")


def tag(s):
    s = re.sub(r"[^\w\u0600-\u06FF]+", "_", s or "").strip("_")
    return "#" + s if s else ""


def preview_text(home, away, league, kickoff_hm, channels, url):
    lines = [f"🔥 {home} × {away}", f"🏆 {league}", f"⏰ {kickoff_hm} بتوقيت السعودية"]
    if channels:
        lines.append("📺 " + "، ".join(channels))
    lines += ["", "الموعد والتشكيلة المتوقعة والغيابات وتوقعنا للنتيجة 👇", url, "",
              " ".join(t for t in (tag(home), tag(away), tag(league)) if t)]
    return "\n".join(lines)


def intent(text):
    return "https://x.com/intent/tweet?text=" + urllib.parse.quote(text)
