"""Deshace (stage / prod según ODOO_ENV) lo creado por los pasos 1 a 5, usando <entorno>_ids.json. NO correr sin confirmarlo."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from o import call, HOST, ENV
print(">>> ESTAS EN:", HOST)
ids = json.load(open(os.path.join(os.path.dirname(__file__), ENV + "_ids.json")))
CTX = {"allowed_company_ids": [1, 2], "active_test": False}
_f = os.path.join(os.path.dirname(__file__), ENV + "_empleados.local.json")
emp = list(json.load(open(_f)).values()) if os.path.exists(_f) else []
# Las fichas que ya existían (reutilizadas) NUNCA se borran: solo se les quitan asignaciones y pedidos creados acá.
reutilizados = set(ids.get("reutilizados", []))
if emp:
    # Odoo no deja borrar ausencias ni asignaciones aprobadas: primero se rechazan
    for m in ("hr.leave", "hr.leave.allocation"):
        # solo lo creado desde el despliegue: nunca pedidos o asignaciones que ya existían
        r = call(m, "search", domain=[["employee_id", "in", emp], ["create_date", ">=", ids.get("inicio_despliegue", "1900-01-01 00:00:00")]], context=CTX)
        ap = call(m, "search", domain=[["id", "in", r], ["state", "in", ["validate", "validate1"]]], context=CTX) if r else []
        if ap: call(m, "action_refuse", ids=ap, context=CTX)
        if r: call(m, "unlink", ids=r, context=CTX)
    borrar = [e for e in emp if e not in reutilizados]
    if borrar: call("hr.employee", "unlink", ids=borrar, context=CTX)
for k, m in [("vista_resumen_vacaciones", "ir.ui.view"), ("campo_x_periodo_txt", "ir.model.fields"), ("campo_x_dias_finde", "ir.model.fields"), ("campo_x_dias_feriado", "ir.model.fields"), ("campo_x_saldo_despues_corr", "ir.model.fields"), ("campo_x_saldo_despues", "ir.model.fields"),
             ("campo_x_periodo", "ir.model.fields"), ("campo_x_vac_ausencias_ids", "ir.model.fields"), ("campo_x_vac_asignaciones_ids", "ir.model.fields"),
             ("menu_saldo_vacaciones", "ir.ui.menu"), ("accion_saldo_vacaciones", "ir.actions.act_window"), ("vista_saldo_vacaciones", "ir.ui.view"),
             ("campo_x_vac_saldo_corridos", "ir.model.fields"), ("campo_x_vac_saldo", "ir.model.fields"), ("campo_x_vac_tomado", "ir.model.fields"), ("campo_x_vac_asignado", "ir.model.fields"),
             ("reporte_nota_vacaciones", "ir.actions.report"), ("vista_nota_vacaciones", "ir.ui.view"), ("accion_generar_vacaciones", "ir.actions.server"),
             ("vista_ficha_empleado", "ir.ui.view"), ("campo_x_retoma", "ir.model.fields"), ("campo_x_dias_corridos", "ir.model.fields"),
             ("campo_x_fecha_ingreso", "ir.model.fields")] + ([] if ids.get("tipo_preexistente") else [("tipo_vacaciones", "hr.leave.type")]):
    if ids.get(k): call(m, "unlink", ids=[ids[k]], context=CTX)
fer = ids.get("feriados", []) + ids.get("feriados_araza", [])
if fer: call("resource.calendar.leaves", "unlink", ids=fer, context=CTX)
if ids.get("paperformat_vacaciones"): call("report.paperformat", "unlink", ids=[ids["paperformat_vacaciones"]], context=CTX)
if ids.get("etiquetas"): call("hr.employee.category", "unlink", ids=list(ids["etiquetas"].values()), context=CTX)
print("Listo")
