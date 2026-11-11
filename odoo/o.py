"""Cliente mínimo de la API JSON-2 de Odoo 19 para genoud-stage (la clave la inyecta el proxy)."""
import json, sys, urllib.request, urllib.error
HOST = "https://genoud-stage.odoo.com"
DB = None
def call(model, method, **kw):
    h = {"Content-Type": "application/json", "Authorization": "bearer proxy-injected"}
    if DB: h["X-Odoo-Database"] = DB
    req = urllib.request.Request(f"{HOST}/json/2/{model}/{method}", data=json.dumps(kw).encode(), headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try: body = json.loads(body).get("message", body)
        except Exception: pass
        raise RuntimeError(f"{e.code} {model}.{method}: {body[:600]}")
if __name__ == "__main__":
    print(call("res.users", "context_get"))
