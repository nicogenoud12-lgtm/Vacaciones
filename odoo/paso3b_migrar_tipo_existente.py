"""Paso 3b (solo si ya existía un tipo "Vacaciones" sin asignaciones y con pedidos — caso producción 12/11/2026).
Odoo no deja activar "requiere asignación" en un tipo que ya tiene pedidos. Entonces:
  1) el tipo viejo se renombra "Vacaciones (anterior)" (al final se archiva; no se borra),
  2) se crea el tipo "Vacaciones" nuevo (paso3_tipo_ausencia.py),
  3) cada pedido del tipo viejo se pasa al nuevo con las mismas fechas y estado. Odoo no admite dos pedidos superpuestos
     del mismo empleado, así que primero se quita el original (si estaba aprobado hay que rechazarlo antes) y después se
     crea el nuevo. Los datos del original quedan respaldados en <entorno>_ids.json; si la creación falla se restaura.
Autorizado por el usuario el 12/11/2026 ("Dale, migrá el tipo y los dos pedidos")."""
import json, os, sys, subprocess
sys.path.insert(0, os.path.dirname(__file__))
from o import call, HOST, ENV
print(">>> ESTAS EN:", HOST)
LOG = os.path.join(os.path.dirname(__file__), ENV + "_ids.json")
ids = json.load(open(LOG)); CTX = {"allowed_company_ids": [1, 2]}

# 1) renombrar el tipo viejo
viejo = call("hr.leave.type", "search_read", domain=[["name", "=", "Vacaciones"], ["requires_allocation", "=", False]],
             fields=["name"], context=dict(CTX, active_test=False))
if viejo:
    call("hr.leave.type", "write", ids=[viejo[0]["id"]], vals={"name": "Vacaciones (anterior)"}, context=CTX)
    ids["tipo_anterior"] = viejo[0]["id"]
    json.dump(ids, open(LOG, "w"), indent=1, ensure_ascii=False)
vid = ids["tipo_anterior"]

# 2) tipo nuevo
if ids.get("tipo_vacaciones") in (None, vid):
    ids.pop("tipo_preexistente", None); ids.pop("tipo_vacaciones", None)
    json.dump(ids, open(LOG, "w"), indent=1, ensure_ascii=False)
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "paso3_tipo_ausencia.py")], check=True)
    ids = json.load(open(LOG))
nuevo = ids["tipo_vacaciones"]
assert nuevo != vid, "el tipo nuevo no puede ser el anterior"

# 3) pedidos
ids.setdefault("pedidos_migrados", [])
viejos = call("hr.leave", "search_read", domain=[["holiday_status_id", "=", vid], ["state", "not in", ["cancel", "refuse"]]],
              fields=["employee_id", "request_date_from", "request_date_to", "number_of_days", "state", "name"], context=CTX)
for l in viejos:
    # el tipo nuevo exige días asignados: sin asignación, el pedido queda en el tipo anterior hasta que se le carguen
    if not call("hr.leave.allocation", "search_count", domain=[["employee_id", "=", l["employee_id"][0]], ["holiday_status_id", "=", nuevo], ["state", "=", "validate"]], context=CTX):
        print("queda en el tipo anterior (sin días asignados todavía):", l["employee_id"][1], l["request_date_from"], "->", l["request_date_to"])
        continue
    ids["pedidos_migrados"].append({"original": l, "nuevo": None})
    json.dump(ids, open(LOG, "w"), indent=1, ensure_ascii=False)  # respaldo antes de tocar nada
    if l["state"] in ("validate", "validate1"):
        call("hr.leave", "action_refuse", ids=[l["id"]], context=CTX)
    call("hr.leave", "unlink", ids=[l["id"]], context=CTX)
    datos = {"employee_id": l["employee_id"][0], "request_date_from": l["request_date_from"],
             "request_date_to": l["request_date_to"], "name": l["name"] or False}
    try:
        n = call("hr.leave", "create", vals_list=[dict(datos, holiday_status_id=nuevo)], context=CTX)[0]
    except RuntimeError as e:
        r = call("hr.leave", "create", vals_list=[dict(datos, holiday_status_id=vid)], context=CTX)[0]
        if l["state"] == "validate":
            call("hr.leave", "action_approve", ids=[r], context=CTX)
        raise SystemExit(f"No se pudo crear en el tipo nuevo ({e}); se restauró el original como {r}")
    if l["state"] == "validate":
        call("hr.leave", "action_approve", ids=[n], context=CTX)
    ids["pedidos_migrados"][-1]["nuevo"] = n
    json.dump(ids, open(LOG, "w"), indent=1, ensure_ascii=False)

# 4) archivar el tipo anterior si ya no le quedan pedidos (queda guardado)
if not call("hr.leave", "search_count", domain=[["holiday_status_id", "=", vid], ["state", "not in", ["cancel", "refuse"]]], context=CTX):
    call("hr.leave.type", "write", ids=[vid], vals={"active": False}, context=CTX)
nuevos = [m["nuevo"] for m in ids["pedidos_migrados"] if m["nuevo"]]
print(call("hr.leave", "read", ids=nuevos, fields=["employee_id", "holiday_status_id", "request_date_from", "request_date_to", "number_of_days", "state"], context=CTX))
print(call("hr.leave.type", "search_read", domain=[["name", "like", "Vacaciones"]],
           fields=["name", "active", "requires_allocation", "allows_negative", "max_allowed_negative", "leave_validation_type", "include_public_holidays_in_duration"],
           context={"active_test": False}))
