"""تنظيف المقالات القديمة: السيدات + المعاينات والتقارير الأقل أهمية. DRY=1 يعرض فقط."""
import os, sys
import sports_bot as sb
import quality as Q

DRY = os.environ.get("DRY", "1") == "1"
BIG_AR = ["الهلال", "النصر", "الاتحاد", "الأهلي", "الاهلي", "ريال مدريد", "برشلونة", "أتلتيكو", "اتلتيكو", "ليفربول", "مانشستر",
          "أرسنال", "ارسنال", "تشيلسي", "توتنهام", "بايرن", "دورتموند", "ليفركوزن", "باريس", "إنتر", "انتر", "ميلان",
          "يوفنتوس", "نابولي", "روما", "نيوكاسل", "أبطال أوروبا", "كأس العالم", "الزمالك", "الوداد", "الترجي"]
KEEP_LABELS = {"مباريات الفرق"}


def all_posts(status="live"):
    out, tok = [], None
    while True:
        kw = dict(status=status, maxResults=50, fetchBodies="false", fields="items(id,title,labels,url),nextPageToken")
        if tok:
            kw["pageToken"] = tok
        r = sb.blogger("/posts", "GET", None, **kw)
        out += r.get("items", [])
        tok = r.get("nextPageToken")
        if not tok:
            return out


def main():
    posts = all_posts()
    print("عدد المقالات:", len(posts))
    dele = []
    for p in posts:
        t, labels = p.get("title", ""), p.get("labels") or []
        if KEEP_LABELS & set(labels):
            continue
        if Q.is_women(t, " ".join(labels)):
            dele.append((p, "سيدات"))
            continue
        if set(labels) & {"تقارير المباريات", "معاينات المباريات", "معاينة"} or "معاينة" in t or "موعد" in t or "مباراة" in t and "تشكيل" in t:
            if not any(b in t or b in " ".join(labels) for b in BIG_AR):
                dele.append((p, "أقل أهمية"))
    for p, why in dele:
        print(why, "|", p["title"], "|", p.get("labels"), "|", p.get("url"))
    print("للحذف:", len(dele), "من", len(posts))
    if DRY:
        return
    for p, why in dele:
        try:
            sb.blogger(f"/posts/{p['id']}", "DELETE")
            print("حُذف:", p["title"])
        except Exception as e:
            print("تعذر:", p["title"], e)


main()
