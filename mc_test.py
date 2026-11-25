import json, os, sys, urllib.parse, urllib.request
sys.path.insert(0, "server")
import match_center as M
KEY = os.environ["API_FOOTBALL_KEY"]
def api(path, **params):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"https://v3.football.api-sports.io/{path}?{q}", headers={"x-apisports-key": KEY})
    with urllib.request.urlopen(req, timeout=25) as r:
        b = json.load(r)
    if b.get("errors"):
        raise RuntimeError(str(b["errors"]))
    return b.get("response", [])
st = json.load(open("data/previews_state.json"))
done = [p for p in st["posts"] if p.get("result_done") or p.get("result")]
ids = [str(done[-1]["fid"])] if done else []
ids += [str(p["fid"]) for p in st["posts"] if str(p["fid"]) not in ids][-1:]
os.makedirs("data/match_sample", exist_ok=True)
for fid in ids:
    code, d = M.handle(api, "/tmp/mcdata", fid)
    print(fid, code, len(json.dumps(d)))
    json.dump(d, open(f"data/match_sample/{fid}.json", "w"), ensure_ascii=False)
