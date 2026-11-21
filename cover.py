#!/usr/bin/env python3
"""
مولد صور الغلاف لمقالات عالم المستديرة (1200x675 JPEG).
- تقارير المباريات: شعارا الفريقين والنتيجة واسم البطولة والعنوان.
- الأخبار: تصميم الموقع مع العنوان والتصنيف.
يحتاج: pillow, arabic-reshaper, python-bidi
"""
import io
import os
import urllib.request

from PIL import Image, ImageDraw, ImageFilter, ImageFont, features

RAQM = features.check("raqm")
if not RAQM:
    import arabic_reshaper
    from bidi.algorithm import get_display

ROOT = os.path.dirname(os.path.abspath(__file__))
FONT_BOLD = os.path.join(ROOT, "assets", "fonts", "Tajawal-Bold.ttf")
FONT_MED = os.path.join(ROOT, "assets", "fonts", "Tajawal-Medium.ttf")
W, H = 1200, 675
BG1, BG2 = (8, 20, 14), (22, 48, 33)
ACCENT = (46, 226, 122)
INK = (6, 35, 20)
TEXT = (240, 247, 243)
MUTED = (160, 186, 172)
BRAND = "عالم المستديرة"
SITE = "fottballcia.com"


def _font(path, size):
    eng = ImageFont.Layout.RAQM if RAQM else ImageFont.Layout.BASIC
    return ImageFont.truetype(path, size, layout_engine=eng)


def ar(text):
    """مع raqm يتولى المحرك التشكيل والاتجاه، وإلا نشكل الحروف يدويًا"""
    if RAQM:
        return text or ""
    return get_display(arabic_reshaper.reshape(text or ""))


_draw_text = ImageDraw.ImageDraw.text
_draw_len = ImageDraw.ImageDraw.textlength


def _is_ar(t):
    return any("\u0600" <= c <= "\u06ff" for c in str(t))


def _text(self, xy, text, *a, **k):
    if RAQM and _is_ar(text):
        k.setdefault("direction", "rtl")
        k.setdefault("language", "ar")
    return _draw_text(self, xy, text, *a, **k)


def _len(self, text, *a, **k):
    if RAQM and _is_ar(text):
        k.setdefault("direction", "rtl")
        k.setdefault("language", "ar")
    return _draw_len(self, text, *a, **k)


ImageDraw.ImageDraw.text = _text
ImageDraw.ImageDraw.textlength = _len


def _wrap(draw, text, font, max_w, max_lines):
    words = (text or "").split()
    lines, cur = [], []
    for w in words:
        trial = " ".join(cur + [w])
        if cur and draw.textlength(ar(trial), font=font) > max_w:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and draw.textlength(ar(last + "…"), font=font) > max_w:
            last = " ".join(last.split()[:-1])
        lines[-1] = last + "…"
    return lines


def _background():
    img = Image.new("RGB", (W, H), BG1)
    px = img.load()
    for y in range(H):
        for x in range(0, W, 4):
            t = (x / W) * 0.55 + (y / H) * 0.45
            c = tuple(int(BG1[i] + (BG2[i] - BG1[i]) * t) for i in range(3))
            for dx in range(4):
                if x + dx < W:
                    px[x + dx, y] = c
    d = ImageDraw.Draw(img, "RGBA")
    # خطوط ملعب خفيفة
    line = (255, 255, 255, 18)
    d.ellipse((W / 2 - 170, H / 2 - 170, W / 2 + 170, H / 2 + 170), outline=line, width=4)
    d.line((W / 2, 0, W / 2, H), fill=line, width=4)
    d.rectangle((-4, H / 2 - 190, 150, H / 2 + 190), outline=line, width=4)
    d.rectangle((W - 150, H / 2 - 190, W + 4, H / 2 + 190), outline=line, width=4)
    # شريط سفلي للعنوان
    d.rectangle((0, H - 250, W, H), fill=(0, 0, 0, 120))
    d.rectangle((0, H - 254, W, H - 250), fill=ACCENT + (255,))
    return img


def _header(img, kicker, date_text):
    d = ImageDraw.Draw(img, "RGBA")
    f = _font(FONT_BOLD, 34)
    label = ar(BRAND)
    tw = d.textlength(label, font=f)
    d.rounded_rectangle((W - 48 - tw - 44, 34, W - 48, 94), radius=30, fill=ACCENT)
    d.text((W - 48 - 22, 64), label, font=f, fill=INK, anchor="rm")
    fk = _font(FONT_MED, 30)
    if kicker:
        d.text((48, 52), ar(kicker), font=fk, fill=TEXT, anchor="lm")
    if date_text:
        d.text((48, 90), date_text, font=_font(FONT_MED, 24), fill=MUTED, anchor="lm")


def _title(img, title, size, max_lines):
    d = ImageDraw.Draw(img)
    f = _font(FONT_BOLD, size)
    lines = _wrap(d, title, f, W - 120, max_lines)
    lh = int(size * 1.35)
    top = H - 250 + (250 - 40 - lh * len(lines)) // 2 + 6
    for i, ln in enumerate(lines):
        d.text((W - 60, top + i * lh + lh // 2), ar(ln), font=f, fill=TEXT, anchor="rm")
    d.text((60, H - 26), SITE, font=_font(FONT_MED, 22), fill=MUTED, anchor="ls")


def _logo(url, size):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            im = Image.open(io.BytesIO(r.read())).convert("RGBA")
        im.thumbnail((size, size), Image.LANCZOS)
        return im
    except Exception:
        return None


def _badge(img, url, cx, cy, name):
    r = 105
    d = ImageDraw.Draw(img, "RGBA")
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse((cx - r, cy - r + 10, cx + r, cy + r + 10), fill=(0, 0, 0, 110))
    img.paste(shadow.filter(ImageFilter.GaussianBlur(12)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(12)))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(250, 252, 250), outline=ACCENT, width=5)
    lg = _logo(url, 140) if url else None
    if lg:
        img.paste(lg, (cx - lg.width // 2, cy - lg.height // 2), lg)
    if name:
        f = _font(FONT_BOLD, 30)
        lines = _wrap(d, name, f, 300, 1)
        d.text((cx, cy + r + 34), ar(lines[0] if lines else name), font=f, fill=TEXT, anchor="mm")


def match_cover(path, title, league, date_text, home_name, away_name, home_logo, away_logo,
                home_goals, away_goals):
    img = _background()
    _header(img, league, date_text)
    cy = 235
    # صاحب الأرض يمين (اتجاه القراءة العربي)
    _badge(img, home_logo, W - 260, cy, home_name)
    _badge(img, away_logo, 260, cy, away_name)
    d = ImageDraw.Draw(img, "RGBA")
    fs = _font(FONT_BOLD, 120)
    d.rounded_rectangle((W / 2 - 160, cy - 80, W / 2 + 160, cy + 80), radius=28, fill=(0, 0, 0, 90))
    # الرقم الأيمن لصاحب الأرض
    d.text((W / 2 + 80, cy + 8), str(home_goals), font=fs, fill=TEXT, anchor="mm")
    d.text((W / 2, cy + 4), "-", font=fs, fill=ACCENT, anchor="mm")
    d.text((W / 2 - 80, cy + 8), str(away_goals), font=fs, fill=TEXT, anchor="mm")
    _title(img, title, 50, 2)
    _save(img, path)


def news_cover(path, title, kicker, date_text):
    img = _background()
    _header(img, "", date_text)
    d = ImageDraw.Draw(img, "RGBA")
    # عنوان كبير في منتصف الصورة
    f = _font(FONT_BOLD, 68)
    lines = _wrap(d, title, f, W - 160, 3)
    lh = 96
    top = 120 + (300 - lh * len(lines)) // 2
    for i, ln in enumerate(lines):
        d.text((W / 2, top + i * lh + lh // 2), ar(ln), font=f, fill=TEXT, anchor="mm")
    fk = _font(FONT_BOLD, 40)
    d.text((W - 60, H - 150), ar(kicker or "أخبار كرة القدم"), font=fk, fill=ACCENT, anchor="rm")
    d.text((W - 60, H - 90), ar("تابع آخر الأخبار والنتائج على عالم المستديرة"), font=_font(FONT_MED, 30),
           fill=MUTED, anchor="rm")
    d.text((60, H - 26), SITE, font=_font(FONT_MED, 22), fill=MUTED, anchor="ls")
    _save(img, path)


def _save(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, "JPEG", quality=82, optimize=True, progressive=True)


if __name__ == "__main__":
    match_cover("/tmp/cover_match.jpg", "الأهلي يفوز على النصر 3-1 في الدوري السعودي للمحترفين",
                "الدوري السعودي للمحترفين", "2026-11-21", "الأهلي", "النصر",
                "https://media.api-sports.io/football/teams/2929.png",
                "https://media.api-sports.io/football/teams/2939.png", 3, 1)
    news_cover("/tmp/cover_news.jpg", "أزمة خط وسط مانشستر سيتي بعد إنفاق 327 مليون إسترليني على الصفقات",
               "أخبار كرة القدم", "2026-11-21")
    print("ok")
