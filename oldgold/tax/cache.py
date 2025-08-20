import json, time, os
PATH = "out/tax_cache.json"

def load():
    try:
        return json.load(open(PATH))
    except Exception:
        return {}

def save(d):
    os.makedirs("out", exist_ok=True)
    json.dump(d, open(PATH, "w"), indent=2)

def get(chain, token, router, ttl_sec=86400):
    d = load(); k = f"{chain}:{token.lower()}:{router.lower()}"; v = d.get(k)
    if v and time.time() - v.get("ts", 0) < ttl_sec:
        return v

def put(chain, token, router, payload):
    d = load(); k = f"{chain}:{token.lower()}:{router.lower()}"; payload = dict(payload); payload["ts"] = time.time(); d[k] = payload; save(d)
