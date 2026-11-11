"""Paso 3 (stage): tipo de ausencia Vacaciones. Requiere el grupo Ausencias / Administrador.
Idempotente: si algo ya existe, lo reutiliza. Registra los IDs en odoo/stage_ids.json."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from o import call, HOST
assert "genoud-stage" in HOST, "Este script es solo para stage"
LOG = os.path.join(os.path.dirname(__file__), "stage_ids.json")
ids = json.load(open(LOG)) if os.path.exists(LOG) else {}
CTX = {"allowed_company_ids": [1, 2]}

def uno(model, domain):
    r = call(model, "search", domain=domain, limit=1, context=dict(CTX, active_test=False))
    return r[0] if r else None

# 3. Tipo de ausencia Vacaciones
lt = uno("hr.leave.type", [["name", "=", "Vacaciones"]])
vals = {
    "name": "Vacaciones", "company_id": False, "request_unit": "day", "requires_allocation": True,
    "allows_negative": True, "max_allowed_negative": 35, "include_public_holidays_in_duration": False,
    "leave_validation_type": "hr", "allocation_validation_type": "no_validation", "employee_requests": False,
    "time_type": "leave",
}
if lt: call("hr.leave.type", "write", ids=[lt], vals=vals)
else: lt = call("hr.leave.type", "create", vals_list=[vals])[0]
ids["tipo_vacaciones"] = lt

json.dump(ids, open(LOG, "w"), indent=1, ensure_ascii=False)
print("tipo_vacaciones", lt)
