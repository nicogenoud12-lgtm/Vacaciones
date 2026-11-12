"""Paso 1 (stage / prod: ODOO_ENV): campo Fecha de ingreso, etiquetas y feriados.
Idempotente: si algo ya existe, lo reutiliza. Registra los IDs en odoo/<entorno>_ids.json."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from o import call, HOST, ENV
print(">>> ESTAS EN:", HOST)

def _modelo(nombre):
    return call("ir.model", "search", domain=[["model", "=", nombre]], limit=1)[0]
LOG = os.path.join(os.path.dirname(__file__), ENV + "_ids.json")
ids = json.load(open(LOG)) if os.path.exists(LOG) else {}
CTX = {"allowed_company_ids": [1, 2]}

def uno(model, domain):
    r = call(model, "search", domain=domain, limit=1, context=dict(CTX, active_test=False))
    return r[0] if r else None

# 1. Campo de fecha de ingreso (antigüedad)
fid = uno("ir.model.fields", [["model", "=", "hr.employee"], ["name", "=", "x_fecha_ingreso"]])
if not fid:
    fid = call("ir.model.fields", "create", vals_list=[{
        "model_id": _modelo("hr.employee"), "model": "hr.employee", "name": "x_fecha_ingreso", "ttype": "date", "state": "manual",
        "field_description": "Fecha de ingreso (antigüedad)",
        "help": "Fecha desde la que se cuenta la antigüedad para las vacaciones (LCT art. 150).",
    }])[0]
ids["campo_x_fecha_ingreso"] = fid

# 2. Etiquetas de empleado
ids.setdefault("etiquetas", {})
for nombre in ["Planta", "Administración", "Convenio Madera", "Convenio Comercio", "Vacaciones: revisar saldo", "Vacaciones: completar ingreso", "Importado de Excel vacaciones"]:
    t = uno("hr.employee.category", [["name", "=", nombre]]) or call("hr.employee.category", "create", vals_list=[{"name": nombre}])[0]
    ids["etiquetas"][nombre] = t

# 4. Feriados: Odoo les pone siempre una compañía (la activa), así que se crean una vez por compañía,
#    cada vez con esa compañía como activa. Día completo en hora argentina (UTC-3).
import datetime as dt
seed = json.load(open(sys.argv[1]))
for cia, clave in ((1, "feriados"), (2, "feriados_araza")):
    ids.setdefault(clave, [])
    ya = {f["date_from"][:10] for f in call("resource.calendar.leaves", "search_read",
          domain=[["resource_id", "=", False], ["company_id", "=", cia], ["date_from", ">=", "2026-01-01 00:00:00"]],
          fields=["date_from"], context={"allowed_company_ids": [cia]})}
    nuevos = []
    for f in seed["config"]["feriados"]:
        d = dt.date.fromisoformat(f["fecha"])
        if d.isoformat() in ya: continue
        nuevos.append({"name": f["nombre"], "company_id": cia, "calendar_id": False, "resource_id": False, "time_type": "leave",
                       "date_from": f"{d.isoformat()} 03:00:00", "date_to": f"{(d + dt.timedelta(days=1)).isoformat()} 02:59:59"})
    if nuevos:
        ids[clave] += call("resource.calendar.leaves", "create", vals_list=nuevos, context={"allowed_company_ids": [cia]})
json.dump(ids, open(LOG, "w"), indent=1, ensure_ascii=False)
print(json.dumps({k: (len(v) if k in ("feriados", "feriados_araza") else v) for k, v in ids.items()}, ensure_ascii=False, indent=1))
