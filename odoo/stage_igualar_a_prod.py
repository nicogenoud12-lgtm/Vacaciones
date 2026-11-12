"""Deja las vacaciones de STAGE iguales a las de producción (12/11/2026), repitiendo los mismos pasos.

1) Borra de stage los datos de prueba creados el 11/11 (pedidos y asignaciones del tipo Vacaciones, y las fichas
   creadas por el paso 2 de ese día). Las herramientas (campos, vistas, acción, nota, menús) se conservan.
2) Vuelve a cargar con las decisiones de producción: fichas preexistentes reutilizadas, planilla GFI + planilla Arazá,
   4 personas pasadas a Arazá, Bonet en "Martin", Lira y Caliva, ajuste de Wasskiewich Fausto.
3) Copia los 2 pedidos reales de producción y saca el puente del 7/12 de Genoud (como está en producción).
4) Compara empleado por empleado contra producción.
Uso: python3 stage_igualar_a_prod.py seed_gfi.json seed_az.json"""
import json, os, subprocess, sys
D = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, D)
os.environ["ODOO_ENV"] = "stage"
import o
from o import call
assert o.ENV == "stage" and "genoud-stage" in o.HOST
print(">>> ESTAS EN:", o.HOST)
CTX = {"allowed_company_ids": [1, 2]}
SEED_GFI, SEED_AZ = sys.argv[1], sys.argv[2]
LOG = os.path.join(D, "stage_ids.json"); EMPF = os.path.join(D, "stage_empleados.local.json"); MAPF = os.path.join(D, "stage_mapeo.local.json")
ids = json.load(open(LOG)); T = ids["tipo_vacaciones"]; TAG = ids["etiquetas"]

def paso(script, *args):
    subprocess.run([sys.executable, os.path.join(D, script), *args], check=True, env=dict(os.environ, ODOO_ENV="stage"), stdout=subprocess.DEVNULL)

def en_prod(model, method, **kw):
    o.HOST = "https://genoud.odoo.com"
    try: return call(model, method, **kw)
    finally: o.HOST = "https://genoud-stage.odoo.com"

# 1) limpieza de los datos de prueba del 11/11
for m in ("hr.leave", "hr.leave.allocation"):
    r = call(m, "search", domain=[["holiday_status_id", "=", T]], context=dict(CTX, active_test=False))
    ap = call(m, "search", domain=[["id", "in", r], ["state", "in", ["validate", "validate1"]]], context=CTX) if r else []
    if ap: call(m, "action_refuse", ids=ap, context=CTX)
    if r: call(m, "unlink", ids=r, context=CTX)
viejas = list(json.load(open(EMPF)).values()) if os.path.exists(EMPF) else []
if viejas:
    info = call("hr.employee", "read", ids=viejas, fields=["create_date", "user_id"], context=dict(CTX, active_test=False))
    assert all(e["create_date"] >= "2026-11-11" and not e["user_id"] for e in info), "solo se borran fichas creadas por el paso 2 del 11/11"
    call("hr.employee", "unlink", ids=viejas, context=CTX)
print("1) limpieza: pedidos, asignaciones y", len(viejas), "fichas de prueba borradas")
json.dump({}, open(EMPF, "w"))

# 2) mapeo de stage: solo fichas preexistentes (mismos IDs en las dos bases, verificado)
pm = json.load(open(os.path.join(D, "prod_mapeo.local.json")))
mapeo = {k: v for k, v in pm.items() if v <= 48}
json.dump(mapeo, open(MAPF, "w"), indent=1)
ids["reutilizados"] = sorted(set(mapeo.values())); json.dump(ids, open(LOG, "w"), indent=1, ensure_ascii=False)
paso("paso2_empleados.py", SEED_GFI)
emp = json.load(open(EMPF))
# personas de las dos planillas: en producción quedaron en la ficha creada desde la planilla GFI
pemp = json.load(open(os.path.join(D, "prod_empleados.local.json")))
inv_prod = {}
for k, v in pemp.items(): inv_prod.setdefault(v, k)
gfi_keys = {e["id"] for e in json.load(open(SEED_GFI))["empleados"]}
for k, v in pm.items():
    if v > 48 and k not in gfi_keys:  # clave de la planilla Arazá que en prod apunta a una ficha creada desde la planilla GFI
        clave_gfi = [kk for kk, vv in pemp.items() if vv == v and kk in gfi_keys]
        if clave_gfi: mapeo[k] = emp[clave_gfi[0]]
json.dump(mapeo, open(MAPF, "w"), indent=1)
pids = json.load(open(os.path.join(D, "prod_ids.json")))
mover = [emp[k] for k in emp if pemp.get(k) in [x["id"] for x in pids["cambio_empresa_a_araza"]]]
call("hr.employee", "write", ids=mover, vals={"company_id": 2}, context=CTX)
paso("paso2_empleados.py", SEED_AZ)
emp = json.load(open(EMPF))
for e in json.load(open(SEED_AZ))["empleados"]:
    sec, otro = ("Planta", "Administración") if e["sector"] == "Planta" else ("Administración", "Planta")
    conv, otroc = ("Convenio Madera", "Convenio Comercio") if e["convenio"] == "Madera" else ("Convenio Comercio", "Convenio Madera")
    ops = [[4, TAG[sec]], [3, TAG[otro]], [4, TAG[conv]], [3, TAG[otroc]], [3, TAG["Vacaciones: completar ingreso"]],
           [4, TAG["Vacaciones: revisar saldo"]] if e["inicio"]["arrastre"] else [3, TAG["Vacaciones: revisar saldo"]]]
    call("hr.employee", "write", ids=[emp[e["id"]]], vals={"category_ids": ops, "x_fecha_ingreso": e["ingreso"]}, context=CTX)
# Ariel Lira (48) y Caliva, como en producción
lira_tags = [[4, TAG[t]] for t in ("Importado de Excel vacaciones", "Planta", "Convenio Madera", "Vacaciones: revisar saldo")]
call("hr.employee", "write", ids=[48], vals={"x_fecha_ingreso": "2003-10-01", "category_ids": lira_tags}, context=CTX)
cal = call("hr.employee", "search", domain=[["name", "=", "Caliva, Vicente Oscar"]], context=CTX)
caliva = cal[0] if cal else call("hr.employee", "create", vals_list=[{"name": "Caliva, Vicente Oscar", "company_id": 2, "resource_calendar_id": 1,
    "x_fecha_ingreso": "2003-09-01", "category_ids": [[6, 0, [TAG[t] for t in ("Importado de Excel vacaciones", "Planta", "Convenio Madera", "Vacaciones: revisar saldo")]]]}], context=CTX)[0]
emp["lira-ariel"] = 48; emp["caliva-vicente"] = caliva; json.dump(emp, open(EMPF, "w"), indent=1, ensure_ascii=False)
todos = sorted(set(emp.values()))
r = call("ir.actions.server", "run", ids=[ids["accion_generar_vacaciones"]],
         context={"active_model": "hr.employee", "active_ids": todos, "active_id": todos[0], "vac_anio": 2026, **CTX})
print("2) asignaciones:", r["params"]["message"][:60])
paso("paso5_saldo_inicial.py", SEED_GFI)
paso("paso5_saldo_inicial.py", SEED_AZ)
f = emp["wasskiewich-fausto-luciano"]
if not call("hr.leave.allocation", "search_count", domain=[["employee_id", "=", f], ["name", "like", "Ajuste"]], context=CTX):
    call("hr.leave.allocation", "create", vals_list=[{"name": "Ajuste: igualar planilla Arazá 2026", "holiday_status_id": T, "employee_id": f,
        "allocation_type": "regular", "number_of_days": 5, "date_from": "2026-01-01",
        "notes": "La planilla Arazá 2026 le da 14 días corridos (10 hábiles). Por ley (art. 153, ingresó el 02/08/2026) le corresponden 5 hábiles; se suman 5 para igualar la planilla. Revisar."}], context=CTX)

# 3) feriados y pedidos como en producción
pf = en_prod("resource.calendar.leaves", "search_read", domain=[["resource_id", "=", False]], fields=["date_from", "company_id"], context=CTX)
en_prod_set = {(x["date_from"], x["company_id"][0]) for x in pf if x["company_id"]}
sf = call("resource.calendar.leaves", "search_read", domain=[["resource_id", "=", False]], fields=["date_from", "company_id"], context=CTX)
sobran = [x["id"] for x in sf if x["company_id"] and (x["date_from"], x["company_id"][0]) not in en_prod_set]
if sobran: call("resource.calendar.leaves", "unlink", ids=sobran, context=CTX)
for l in en_prod("hr.leave", "search_read", domain=[["state", "not in", ["cancel", "refuse"]]],
                 fields=["employee_id", "request_date_from", "request_date_to", "state", "name"], context=CTX):
    n = call("hr.leave", "create", vals_list=[{"holiday_status_id": T, "employee_id": l["employee_id"][0], "request_date_from": l["request_date_from"],
             "request_date_to": l["request_date_to"], "name": l["name"] or False}], context=CTX)[0]
    if l["state"] == "validate": call("hr.leave", "action_approve", ids=[n], context=CTX)
print("3) feriados quitados para igualar:", len(sobran), "| pedidos copiados de producción")

# 4) comparación empleado por empleado
campos = ["name", "company_id", "x_fecha_ingreso", "x_vac_asignado", "x_vac_tomado", "x_vac_saldo"]
dom = [["category_ids.name", "=", "Importado de Excel vacaciones"]]
a = {(e["name"], e["company_id"][0]): e for e in call("hr.employee", "search_read", domain=dom, fields=campos, context=CTX)}
b = {(e["name"], e["company_id"][0]): e for e in en_prod("hr.employee", "search_read", domain=dom, fields=campos, context=CTX)}
dif = [(k, {c: (a.get(k, {}).get(c), b[k][c]) for c in campos[2:] if a.get(k, {}).get(c) != b[k][c]}) for k in b if a.get(k) != b[k] and
       any(a.get(k, {}).get(c) != b[k][c] for c in campos[2:])]
print("4) empleados stage:", len(a), "| prod:", len(b), "| solo en stage:", [k for k in a if k not in b], "| diferencias:", dif)
