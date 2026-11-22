#!/usr/bin/env python3
"""فيديو عمودي قصير (720x1280) لتيك توك قبل المباريات الكبيرة: 4 لقطات مع انتقال ناعم.
يحتاج: pillow, arabic-reshaper, python-bidi, ffmpeg
"""
import os
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFilter

import cover as C

VW, VH = 720, 1280
SEC = 3.6   # مدة كل لقطة
FADE = 0.5


def _bg():
    img = Image.new("RGB", (VW, VH), C.BG1)
    d = ImageDraw.Draw(img, "RGBA")
    for y in range(0, VH, 4):
        t = y / VH
        c = tuple(int(C.BG1[i] + (C.BG2[i] - C.BG1[i]) * t) for i in range(3))
        d.rectangle((0, y, VW, y + 4), fill=c)
    line = (255, 255, 255, 16)
    d.ellipse((VW / 2 - 200, VH / 2 - 200, VW / 2 + 200, VH / 2 + 200), outline=line, width=4)
    d.line((0, VH / 2, VW, VH / 2), fill=line, width=4)
    d.rectangle((VW / 2 - 220, -4, VW / 2 + 220, 170), outline=line, width=4)
    d.rectangle((VW / 2 - 220, VH - 170, VW / 2 + 220, VH + 4), outline=line, width=4)
    # الشعار والموقع
    f = C._font(C.FONT_BOLD, 34)
    lab = C.ar(C.BRAND)
    tw = d.textlength(lab, font=f)
    d.rounded_rectangle((VW / 2 - tw / 2 - 26, 60, VW / 2 + tw / 2 + 26, 120), radius=30, fill=C.ACCENT)
    d.text((VW / 2, 90), lab, font=f, fill=C.INK, anchor="mm")
    d.text((VW / 2, VH - 70), "fottballcia.com", font=C._font(C.FONT_BOLD, 34), fill=C.TEXT, anchor="mm")
    return img


def _badge(img, url, cx, cy, r, name=None):
    d = ImageDraw.Draw(img, "RGBA")
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((cx - r, cy - r + 10, cx + r, cy + r + 10), fill=(0, 0, 0, 120))
    sh = sh.filter(ImageFilter.GaussianBlur(12))
    img.paste(sh, (0, 0), sh)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(250, 252, 250), outline=C.ACCENT, width=5)
    lg = C._logo(url, int(r * 1.35)) if url else None
    if lg:
        img.paste(lg, (cx - lg.width // 2, cy - lg.height // 2), lg)
    if name:
        f = C._font(C.FONT_BOLD, 40)
        ln = C._wrap(d, name, f, 330, 1)
        d.text((cx, cy + r + 46), C.ar(ln[0] if ln else name), font=f, fill=C.TEXT, anchor="mm")


def _center(d, y, text, size, fill=None, font=None, max_w=640, lines=2, gap=1.25):
    f = C._font(font or C.FONT_BOLD, size)
    for i, ln in enumerate(C._wrap(d, text, f, max_w, lines)):
        d.text((VW / 2, y + i * size * gap), C.ar(ln), font=f, fill=fill or C.TEXT, anchor="mm")
    return y + len(C._wrap(d, text, f, max_w, lines)) * size * gap


def _pill(d, y, text, size=36, fill=C.ACCENT, ink=C.INK):
    f = C._font(C.FONT_BOLD, size)
    tw = d.textlength(C.ar(text), font=f)
    d.rounded_rectangle((VW / 2 - tw / 2 - 30, y - size * 0.85, VW / 2 + tw / 2 + 30, y + size * 0.85), radius=40, fill=fill)
    d.text((VW / 2, y), C.ar(text), font=f, fill=ink, anchor="mm")


def slide_intro(v):
    img = _bg()
    d = ImageDraw.Draw(img, "RGBA")
    _pill(d, 250, v["league"], 34, (255, 255, 255, 40), C.TEXT)
    _badge(img, v["home_logo"], VW // 2, 430, 110, v["home"])
    d.text((VW / 2, 705), "VS", font=C._font(C.FONT_BOLD, 96), fill=C.ACCENT, anchor="mm")
    _badge(img, v["away_logo"], VW // 2, 880, 110, v["away"])
    _center(d, 1135, v["when"], 40, C.ACCENT)
    return img


def slide_tv(v):
    img = _bg()
    d = ImageDraw.Draw(img, "RGBA")
    _center(d, 240, "القنوات الناقلة", 58, C.ACCENT)
    y = 360
    for ch in (v.get("channels") or ["تتابعها مباشرة على عالم المستديرة"])[:3]:
        d.rounded_rectangle((90, y - 50, VW - 90, y + 50), radius=26, fill=(255, 255, 255, 30), outline=(255, 255, 255, 60), width=2)
        d.text((VW / 2, y), C.ar(ch), font=C._font(C.FONT_BOLD, 44), fill=C.TEXT, anchor="mm")
        y += 128
    y = max(y + 60, 800)
    _center(d, y, "موعد المباراة", 50, C.ACCENT)
    y += 90
    for country, t in v["times"]:
        d.text((VW - 130, y), C.ar(country), font=C._font(C.FONT_MED, 42), fill=C.MUTED, anchor="rm")
        d.text((130, y), t, font=C._font(C.FONT_BOLD, 46), fill=C.TEXT, anchor="lm")
        y += 70
    return img


def slide_xi(v):
    img = _bg()
    d = ImageDraw.Draw(img, "RGBA")
    _center(d, 200, v.get("xi_title") or "التشكيلة المتوقعة", 56, C.ACCENT)
    y = 280
    for side in ("home", "away"):
        xi = v.get(f"xi_{side}") or []
        d.rounded_rectangle((50, y, VW - 50, y + 58), radius=20, fill=(255, 255, 255, 34))
        d.text((VW - 80, y + 29), C.ar(v[side]), font=C._font(C.FONT_BOLD, 38), fill=C.TEXT, anchor="rm")
        if v.get(f"form_{side}"):
            d.text((80, y + 29), v[f"form_{side}"], font=C._font(C.FONT_BOLD, 36), fill=C.ACCENT, anchor="lm")
        y += 82
        if not xi:
            _center(d, y + 20, "تُعلن قبل المباراة بساعة", 34, C.MUTED)
            y += 90
            continue
        def fit(name, max_w=275):
            for sz in (31, 28, 25, 22):
                f = C._font(C.FONT_MED, sz)
                if d.textlength(C.ar(name), font=f) <= max_w:
                    return f
            return f
        for i in range(0, len(xi), 2):
            pair = xi[i:i + 2]
            d.text((VW - 75, y), C.ar(pair[0]), font=fit(pair[0]), fill=C.TEXT, anchor="rm")
            if len(pair) > 1:
                d.text((VW / 2 - 15, y), C.ar(pair[1]), font=fit(pair[1]), fill=C.TEXT, anchor="rm")
            y += 44
        y += 34
    return img


def slide_pred(v):
    img = _bg()
    d = ImageDraw.Draw(img, "RGBA")
    _center(d, 300, "توقعنا للمباراة", 60, C.ACCENT)
    _badge(img, v["home_logo"], VW - 115, 560, 78)
    _badge(img, v["away_logo"], 115, 560, 78)
    sc = (v.get("pred") or "?-?").replace(" ", "")
    try:
        a, b = sc.split("-")[:2]
        sc = f"{b} - {a}"   # الضيف يسار والمضيف يمين
    except Exception:
        pass
    d.text((VW / 2, 560), sc, font=C._font(C.FONT_BOLD, 110), fill=C.TEXT, anchor="mm")
    _center(d, 760, "وش توقعك أنت؟ اكتبه في التعليقات", 40, C.TEXT)
    _pill(d, 930, "التفاصيل كاملة على عالم المستديرة", 36)
    _center(d, 1040, "الرابط في البايو", 40, C.ACCENT)
    return img


def make_video(path, v):
    slides = [slide_intro(v), slide_tv(v), slide_xi(v), slide_pred(v)]
    with tempfile.TemporaryDirectory() as tmp:
        files = []
        for i, s in enumerate(slides):
            p = os.path.join(tmp, f"s{i}.png")
            s.save(p)
            files.append(p)
        import shutil
        exe = shutil.which("ffmpeg")
        if not exe:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [exe, "-y", "-loglevel", "error"]
        for p in files:
            cmd += ["-loop", "1", "-t", str(SEC), "-framerate", "25", "-i", p]
        # صوت صامت حتى يقبل تيك توك الفيديو ويضيف المستخدم صوتًا من التطبيق
        cmd += ["-f", "lavfi", "-t", str(len(files) * SEC), "-i", "anullsrc=r=44100:cl=stereo"]
        chain, last = [], "[0:v]"
        for i in range(1, len(files)):
            off = round(i * (SEC - FADE), 2)
            out = f"[x{i}]"
            chain.append(f"{last}[{i}:v]xfade=transition=fade:duration={FADE}:offset={off}{out}")
            last = out
        chain.append(f"{last}format=yuv420p[v]")
        cmd += ["-filter_complex", ";".join(chain), "-map", "[v]", "-map", f"{len(files)}:a",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-r", "25",
                "-c:a", "aac", "-b:a", "64k", "-shortest", "-movflags", "+faststart", path]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        subprocess.run(cmd, check=True)
    return path


def caption(v):
    tags = " ".join(t for t in (_tag(v["home"]), _tag(v["away"]), _tag(v["league"]), "#كرة_القدم", "#عالم_المستديرة", "#اكسبلور") if t)
    return (f"{v['home']} × {v['away']} 🔥\n{v['league']} - {v['when']}\n"
            "القنوات الناقلة والتشكيلة المتوقعة وتوقعنا 👆 وش توقعك؟\n"
            "التفاصيل كاملة على موقع عالم المستديرة (الرابط في البايو)\n" + tags)


def _tag(s):
    import re
    s = re.sub(r"[^\w\u0600-\u06FF]+", "_", s or "").strip("_")
    return "#" + s if s else ""


if __name__ == "__main__":
    v = {"home": "ليفربول", "away": "مانشستر يونايتد", "league": "الدوري الإنجليزي الممتاز",
         "when": "الأحد 22 نوفمبر - 19:30", "home_logo": "https://media.api-sports.io/football/teams/40.png",
         "away_logo": "https://media.api-sports.io/football/teams/33.png", "channels": ["beIN SPORTS"],
         "times": [("السعودية", "19:30"), ("الإمارات", "20:30"), ("مصر", "18:30"), ("المغرب", "16:30")],
         "xi_home": ["أليسون بيكر", "رونالد أراوخو", "جوان جاكيه", "فيرجيل فان دايك", "ميلوس كيركيز", "دومينيك سوبوسلاي",
                     "أليكسيس ماك أليستر", "كودي جاكبو", "فلوريان فيرتز", "برادلي باركولا", "ألكسندر إيساك"],
         "xi_away": ["سيني لامينز", "نصير مزراوي", "ليني يورو", "هاري ماغواير", "ديوغو دالوت", "يوري تيليمانس",
                     "كوبي ماينو", "أماد ديالو", "برونو فيرنانديز", "ماتيوس كونيا", "برايان مبومو"],
         "form_home": "4-2-3-1", "form_away": "4-2-3-1", "pred": "2-1"}
    for i, s in enumerate([slide_intro(v), slide_tv(v), slide_xi(v), slide_pred(v)]):
        s.save(f"/tmp/tk{i}.png")
    make_video("/tmp/tk.mp4", v)
    print(caption(v))
