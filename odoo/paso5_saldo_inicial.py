"""Paso 5 (stage): saldo inicial del Excel. Pendiente (+) = asignación "Saldo inicial 2025 (Excel)";
anticipo (-) = se descuenta de "Vacaciones 2026". Idempotente. Uso: python3 paso5_saldo_inicial.py seed.json"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from o import call, HOST
assert "genoud-stage" in HOST
LOG = os.path.join(os.path.dirname(__file__), "stage_ids.json")
ids = json.load(open(LOG)); CTX = {"allowed_company_ids": [1, 2]}
seed = json.load(open(sys.argv[1])); T = ids["tipo_vacaciones"]
EMP = json.load(open(os.path.join(os.path.dirname(__file__), "stage_empleados.local.json")))
hechos = []
for e in seed["empleados"]:
    arr = e["inicio"]["arrastre"]; oid = EMP[e["id"]]
    if not arr: continue
    if arr > 0:
        if call("hr.leave.allocation", "search_count", domain=[["employee_id", "=", oid], ["name", "=", "Saldo inicial 2025 (Excel)"]], context=CTX): continue
        call("hr.leave.allocation", "create", vals_list=[{"name": "Saldo inicial 2025 (Excel)", "holiday_status_id": T, "employee_id": oid,
             "allocation_type": "regular", "number_of_days": arr, "date_from": "2026-01-01", "date_to": False, "notes": e["inicio"]["origen"]}], context=CTX)
    else:
        a = call("hr.leave.allocation", "search_read", domain=[["employee_id", "=", oid], ["name", "=", "Vacaciones 2026"], ["holiday_status_id", "=", T]],
                 fields=["number_of_days", "notes"], context=CTX)[0]
        if "anticipo" in (a["notes"] or "").lower(): continue
        nuevo = a["number_of_days"] + arr
        nota = (a["notes"] or "") + f" Menos {-arr} de anticipo ya tomado ({e['inicio']['origen']})."
        call("hr.leave.allocation", "write", ids=[a["id"]], vals={"number_of_days": nuevo, "notes": nota, "name": "Vacaciones 2026"}, context=CTX)  # se reescribe el nombre: Odoo lo cambia al editar los días
    hechos.append((e["nombre"], arr))
print(len(hechos), hechos)
