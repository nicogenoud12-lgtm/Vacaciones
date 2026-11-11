"""Paso 2 (stage): crea los empleados del Excel en hr.employee (idempotente por nombre).
Uso: python3 paso2_empleados.py seed.json"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from o import call, HOST
assert "genoud-stage" in HOST, "Este script es solo para stage"
LOG = os.path.join(os.path.dirname(__file__), "stage_ids.json")
ids = json.load(open(LOG))
EMP = os.path.join(os.path.dirname(__file__), "stage_empleados.local.json")  # nombres: no se sube al repositorio
empleados = json.load(open(EMP)) if os.path.exists(EMP) else {}
T = ids["etiquetas"]
CIA = {"GFI": 1, "AZ": 2}
CTX = {"allowed_company_ids": [1, 2]}
seed = json.load(open(sys.argv[1]))
existentes = {e["name"]: e["id"] for e in call("hr.employee", "search_read", domain=[["category_ids", "in", [T["Importado de Excel vacaciones"]]]],
                                               fields=["name"], context=dict(CTX, active_test=False))}
nuevos, claves = [], []
for e in seed["empleados"]:
    if e["nombre"] in existentes:
        empleados[e["id"]] = existentes[e["nombre"]]; continue
    tags = [T["Importado de Excel vacaciones"], T["Planta"] if e["sector"] == "Planta" else T["Administración"],
            T["Convenio Madera"] if e["convenio"] == "Madera" else T["Convenio Comercio"]]
    if not e["ingreso"]: tags.append(T["Vacaciones: completar ingreso"])
    elif e["revisar"]: tags.append(T["Vacaciones: revisar saldo"])
    nuevos.append({"name": e["nombre"], "company_id": CIA[e["empresa"]], "resource_calendar_id": 1,
                   "x_fecha_ingreso": e["ingreso"] or False, "category_ids": [[6, 0, tags]]})
    claves.append(e["id"])
for i in range(0, len(nuevos), 20):
    creados = call("hr.employee", "create", vals_list=nuevos[i:i + 20], context=CTX)
    for k, oid in zip(claves[i:i + 20], creados): empleados[k] = oid
    json.dump(empleados, open(EMP, "w"), indent=1, ensure_ascii=False)
json.dump(empleados, open(EMP, "w"), indent=1, ensure_ascii=False)
print("empleados en Odoo:", len(empleados), "creados ahora:", len(nuevos))
