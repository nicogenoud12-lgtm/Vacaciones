"""Paso 2 (stage / prod: ODOO_ENV): crea los empleados del Excel en hr.employee (idempotente por nombre).
Si existe <entorno>_mapeo.local.json ({id del Excel: id de hr.employee}), esas personas NO se crean:
se usa su ficha existente (se le completa la fecha de ingreso y se le suman etiquetas; nombre y empresa no se tocan).
Uso: python3 paso2_empleados.py seed.json"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from o import call, HOST, ENV
print(">>> ESTAS EN:", HOST)
LOG = os.path.join(os.path.dirname(__file__), ENV + "_ids.json")
ids = json.load(open(LOG))
EMP = os.path.join(os.path.dirname(__file__), ENV + "_empleados.local.json")  # nombres: no se sube al repositorio
empleados = json.load(open(EMP)) if os.path.exists(EMP) else {}
T = ids["etiquetas"]
CIA = {"GFI": 1, "AZ": 2}
CTX = {"allowed_company_ids": [1, 2]}
seed = json.load(open(sys.argv[1]))
existentes = {e["name"]: e["id"] for e in call("hr.employee", "search_read", domain=[["category_ids", "in", [T["Importado de Excel vacaciones"]]]],
                                               fields=["name"], context=dict(CTX, active_test=False))}
MAPEO = os.path.join(os.path.dirname(__file__), ENV + "_mapeo.local.json")
mapeo = json.load(open(MAPEO)) if os.path.exists(MAPEO) else {}
ids["reutilizados"] = sorted(set(ids.get("reutilizados", []) + list(mapeo.values())))
nuevos, claves = [], []
for e in seed["empleados"]:
    tags = [T["Importado de Excel vacaciones"], T["Planta"] if e["sector"] == "Planta" else T["Administración"],
            T["Convenio Madera"] if e["convenio"] == "Madera" else T["Convenio Comercio"]]
    if not e["ingreso"]: tags.append(T["Vacaciones: completar ingreso"])
    elif e["revisar"]: tags.append(T["Vacaciones: revisar saldo"])
    if e["id"] in mapeo:
        oid = mapeo[e["id"]]
        actual = call("hr.employee", "read", ids=[oid], fields=["x_fecha_ingreso"], context=CTX)[0]
        vals = {"category_ids": [[4, t] for t in tags]}
        if e["ingreso"] and not actual["x_fecha_ingreso"]: vals["x_fecha_ingreso"] = e["ingreso"]
        call("hr.employee", "write", ids=[oid], vals=vals, context=CTX)
        empleados[e["id"]] = oid
        continue
    if e["nombre"] in existentes:
        empleados[e["id"]] = existentes[e["nombre"]]; continue
    nuevos.append({"name": e["nombre"], "company_id": CIA[e["empresa"]], "resource_calendar_id": 1,
                   "x_fecha_ingreso": e["ingreso"] or False, "category_ids": [[6, 0, tags]]})
    claves.append(e["id"])
for i in range(0, len(nuevos), 20):
    creados = call("hr.employee", "create", vals_list=nuevos[i:i + 20], context=CTX)
    for k, oid in zip(claves[i:i + 20], creados): empleados[k] = oid
    json.dump(empleados, open(EMP, "w"), indent=1, ensure_ascii=False)
json.dump(empleados, open(EMP, "w"), indent=1, ensure_ascii=False)
json.dump(ids, open(LOG, "w"), indent=1, ensure_ascii=False)
print("reutilizadas:", len(mapeo), "| empleados en Odoo:", len(empleados), "creados ahora:", len(nuevos))
