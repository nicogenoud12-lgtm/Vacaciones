"""Deshace en stage lo creado por los pasos 1 a 5, usando stage_ids.json. NO correr sin confirmarlo."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from o import call, HOST
assert "genoud-stage" in HOST
ids = json.load(open(os.path.join(os.path.dirname(__file__), "stage_ids.json")))
CTX = {"allowed_company_ids": [1, 2], "active_test": False}
emp = list(ids.get("empleados", {}).values())
if emp:
    for m in ("hr.leave", "hr.leave.allocation"):
        r = call(m, "search", domain=[["employee_id", "in", emp]], context=CTX)
        if r: call(m, "unlink", ids=r, context=CTX)
    call("hr.employee", "unlink", ids=emp, context=CTX)
for k, m in [("reporte_nota_vacaciones", "ir.actions.report"), ("vista_nota_vacaciones", "ir.ui.view"), ("accion_generar_vacaciones", "ir.actions.server"),
             ("vista_ficha_empleado", "ir.ui.view"), ("campo_x_retoma", "ir.model.fields"), ("campo_x_dias_corridos", "ir.model.fields"),
             ("campo_x_fecha_ingreso", "ir.model.fields"), ("tipo_vacaciones", "hr.leave.type")]:
    if ids.get(k): call(m, "unlink", ids=[ids[k]], context=CTX)
if ids.get("feriados"): call("resource.calendar.leaves", "unlink", ids=ids["feriados"], context=CTX)
if ids.get("etiquetas"): call("hr.employee.category", "unlink", ids=list(ids["etiquetas"].values()), context=CTX)
print("Listo")
