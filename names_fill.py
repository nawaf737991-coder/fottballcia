"""يترجم أسماء الفرق الناقصة (من مباريات الأيام والجداول) إلى data/names_cache.json ليستخدمها مركز المباراة."""
import glob, json, os
import tables_pages as T
from matches_page import CACHE, load, save
names = set()
for f in glob.glob("data/days/*.json") + ["data/today.json"]:
    d = load(f, {})
    for m in (d.get("matches") if isinstance(d, dict) else d) or []:
        names.update([m.get("home"), m.get("away")])
for l in load("data/tables.json", {}).get("leagues", []):
    names.update(r["t"] for r in l.get("table", []))
cache = load(CACHE, {})
before = len(cache)
for i in range(3):
    T.translate(sorted(n for n in names if n), cache)
if len(cache) != before:
    save(CACHE, cache)
print("أسماء جديدة:", len(cache) - before)
