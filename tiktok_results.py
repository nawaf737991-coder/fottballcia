#!/usr/bin/env python3
"""فيديو تيك توك بعد المباراة: النتيجة النهائية + لقطة لكل هدف + الهدافون + الأرقام + دعوة لزيارة الموقع.
(رسوم فقط بدون لقطات تلفزيونية حتى لا تُحذف بسبب حقوق البث)
"""
from PIL import ImageDraw

import cover as C
import tiktok as T
from tiktok import VW


def _score_row(img, d, v, y, gh, ga, r=88, size=120):
    T._badge(img, v["home_logo"], VW - 120, y, r)
    T._badge(img, v["away_logo"], 120, y, r)
    f = C._font(C.FONT_BOLD, size)
    gap = int(size * 0.6)
    d.text((VW / 2 + gap, y), str(gh), font=f, fill=C.TEXT, anchor="mm")
    d.text((VW / 2, y), "-", font=f, fill=C.MUTED, anchor="mm")
    d.text((VW / 2 - gap, y), str(ga), font=f, fill=C.TEXT, anchor="mm")


def n_goals(n):
    return "بدون أهداف" if not n else ("هدف واحد" if n == 1 else ("هدفان" if n == 2 else f"{n} أهداف"))


def slide_final(v):
    img = T._bg()
    d = ImageDraw.Draw(img, "RGBA")
    T._pill(d, 250, v["league"], 34, (255, 255, 255, 40), C.TEXT)
    T._center(d, 380, v.get("status_text") or "انتهت المباراة", 62, C.ACCENT)
    _score_row(img, d, v, 600, v["gh"], v["ga"], 100, 130)
    d.text((VW - 120, 760), C.ar(v["home"]), font=C._font(C.FONT_BOLD, 36), fill=C.TEXT, anchor="mm")
    d.text((120, 760), C.ar(v["away"]), font=C._font(C.FONT_BOLD, 36), fill=C.TEXT, anchor="mm")
    if v.get("pens"):
        T._center(d, 850, v["pens"], 38, C.MUTED)
    T._center(d, 990, n_goals(len(v.get("goals") or [])), 44, C.TEXT)
    return img


def slide_goal(v, g):
    img = T._bg()
    d = ImageDraw.Draw(img, "RGBA")
    d.text((VW / 2, 300), "GOAL", font=C._font(C.FONT_BOLD, 130), fill=C.ACCENT, anchor="mm")
    T._pill(d, 440, f"الدقيقة {g['min']}", 44)
    T._center(d, 590, g["player"], 64, C.TEXT, lines=2)
    sub = g.get("kind") or ""
    if g.get("assist"):
        sub = (sub + " - " if sub else "") + "صناعة: " + g["assist"]
    if sub:
        T._center(d, 720, sub, 36, C.MUTED, lines=2)
    T._center(d, 810, g["team"], 40, C.ACCENT)
    _score_row(img, d, v, 1000, g["gh"], g["ga"], 78, 100)
    return img


def slide_scorers(v):
    img = T._bg()
    d = ImageDraw.Draw(img, "RGBA")
    T._center(d, 220, "الهدافون", 60, C.ACCENT)
    _score_row(img, d, v, 400, v["gh"], v["ga"], 72, 96)
    y = 560
    for side, name in (("home", v["home"]), ("away", v["away"])):
        gs = [g for g in v.get("goals") or [] if g["side"] == side]
        d.text((VW - 70, y), C.ar(name), font=C._font(C.FONT_BOLD, 40), fill=C.ACCENT, anchor="rm")
        y += 62
        if not gs:
            d.text((VW - 90, y), "-", font=C._font(C.FONT_MED, 34), fill=C.MUTED, anchor="rm")
            y += 54
        for g in gs[:5]:
            t = f"{g['player']} {g['min']}'"
            if g.get("kind") == "ركلة جزاء":
                t += " (جزاء)"
            elif g.get("kind") == "هدف عكسي":
                t += " (عكسي)"
            d.text((VW - 90, y), C.ar(t), font=C._font(C.FONT_MED, 34), fill=C.TEXT, anchor="rm")
            y += 52
        y += 30
    return img


def slide_stats(v):
    img = T._bg()
    d = ImageDraw.Draw(img, "RGBA")
    T._center(d, 230, "أرقام المباراة", 60, C.ACCENT)
    T._badge(img, v["home_logo"], VW - 120, 400, 70)
    T._badge(img, v["away_logo"], 120, 400, 70)
    y = 560
    for k, (a, b) in list((v.get("stats") or {}).items())[:6]:
        d.text((VW / 2, y), C.ar(k), font=C._font(C.FONT_MED, 34), fill=C.MUTED, anchor="mm")
        d.text((VW - 90, y), str(a), font=C._font(C.FONT_BOLD, 44), fill=C.TEXT, anchor="rm")
        d.text((90, y), str(b), font=C._font(C.FONT_BOLD, 44), fill=C.TEXT, anchor="lm")
        y += 95
    return img


def slide_cta(v):
    img = T._bg()
    d = ImageDraw.Draw(img, "RGBA")
    _score_row(img, d, v, 450, v["gh"], v["ga"], 95, 120)
    T._center(d, 680, "التقرير الكامل والإحصائيات", 52, C.TEXT)
    T._pill(d, 820, "على موقع عالم المستديرة", 40)
    T._center(d, 950, "ابحث في قوقل: عالم المستديرة", 40, C.ACCENT)
    T._center(d, 1060, "وش رأيك في النتيجة؟ اكتبه في التعليقات", 36, C.TEXT)
    return img


def slides(v):
    out = [(slide_final(v), 3.4)]
    for g in (v.get("goals") or [])[:8]:
        out.append((slide_goal(v, g), 2.6))
    if v.get("goals"):
        out.append((slide_scorers(v), 3.4))
    if v.get("stats"):
        out.append((slide_stats(v), 3.4))
    out.append((slide_cta(v), 3.0))
    return out


def make_result_video(path, v):
    return T.make_video(path, v, slides(v))


def caption(v):
    tags = " ".join(t for t in (T._tag(v["home"]), T._tag(v["away"]), T._tag(v["league"]),
                                "#كرة_القدم", "#عالم_المستديرة", "#اكسبلور") if t)
    sc = "، ".join(dict.fromkeys(g["player"] for g in v.get("goals") or [] if g.get("kind") != "هدف عكسي" and g.get("player")))
    return (f"{v['home']} {v['gh']}-{v['ga']} {v['away']} ⚽\n{v['league']}\n"
            + (f"الأهداف: {sc}\n" if sc else "")
            + "وش رأيك في النتيجة؟ 👇\nالتقرير الكامل على موقع عالم المستديرة - ابحث في قوقل: عالم المستديرة أو fottballcia.com\n" + tags)


if __name__ == "__main__":
    v = {"home": "ليفربول", "away": "مانشستر يونايتد", "league": "الدوري الإنجليزي الممتاز",
         "home_logo": "https://media.api-sports.io/football/teams/40.png",
         "away_logo": "https://media.api-sports.io/football/teams/33.png", "gh": 2, "ga": 1,
         "goals": [
             {"min": 23, "player": "محمد صلاح", "assist": "فلوريان فيرتز", "team": "ليفربول", "side": "home", "gh": 1, "ga": 0},
             {"min": 51, "player": "برونو فيرنانديز", "kind": "ركلة جزاء", "team": "مانشستر يونايتد", "side": "away", "gh": 1, "ga": 1},
             {"min": 88, "player": "ألكسندر إيساك", "assist": "دومينيك سوبوسلاي", "team": "ليفربول", "side": "home", "gh": 2, "ga": 1}],
         "stats": {"الاستحواذ": ["58%", "42%"], "التسديدات": [15, 9], "على المرمى": [6, 3], "الركنيات": [7, 2],
                   "الأهداف المتوقعة (xG)": ["1.9", "0.8"]}}
    for i, (im, _) in enumerate(slides(v)):
        im.save(f"/tmp/rs{i}.png")
    make_result_video("/tmp/rs.mp4", v)
    print(caption(v))
