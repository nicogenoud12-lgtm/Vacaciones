"""Paso 7 (stage): "Resumen de vacaciones" por empleado, al tocar una fila de Vacaciones → Reportes → Saldo de vacaciones.
Muestra el saldo actual, los días que le correspondieron (asignaciones) y cada pedido con el saldo que le quedó después.

Período de un pedido: octubre a diciembre = período del año; enero a septiembre = período del año anterior
(misma regla que la nota PDF: las vacaciones del período 2026 se toman de octubre 2026 a septiembre 2027).
"Le quedaban" después de un pedido = asignaciones de ese período y anteriores − pedidos acumulados hasta ese."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from o import call, HOST
assert "genoud-stage" in HOST
LOG = os.path.join(os.path.dirname(__file__), "stage_ids.json")
ids = json.load(open(LOG))
M_EMP, M_LEAVE = 947, 1352


def upsert(model, domain, vals):
    r = call(model, "search", domain=domain, limit=1, context={"active_test": False})
    if r:
        call(model, "write", ids=r, vals=vals); return r[0]
    return call(model, "create", vals_list=[vals])[0]


def campo(model_id, model, name, vals):
    base = {"model_id": model_id, "model": model, "name": name, "state": "manual"}
    base.update(vals)
    return upsert("ir.model.fields", [["model", "=", model], ["name", "=", name]], base)


# 1. Relaciones del empleado con sus asignaciones y pedidos de Vacaciones (solo lectura)
ids["campo_x_vac_asignaciones_ids"] = campo(M_EMP, "hr.employee", "x_vac_asignaciones_ids", {
    "ttype": "one2many", "relation": "hr.leave.allocation", "relation_field": "employee_id",
    "field_description": "Vacaciones: días asignados",
    "domain": "[('holiday_status_id.name', '=', 'Vacaciones'), ('state', '=', 'validate')]",
})
ids["campo_x_vac_ausencias_ids"] = campo(M_EMP, "hr.employee", "x_vac_ausencias_ids", {
    "ttype": "one2many", "relation": "hr.leave", "relation_field": "employee_id",
    "field_description": "Vacaciones: pedidos",
    "domain": "[('holiday_status_id.name', '=', 'Vacaciones'), ('state', 'in', ['confirm', 'validate1', 'validate'])]",
})

# 2. En cada pedido: período y saldo que le quedó después (no almacenados)
CALCULO = """
for rec in self:
    d = rec.request_date_from
    if not rec.employee_id or not d or not rec.holiday_status_id:
        rec['%(campo)s'] = 0
        continue
    per = d.year if d.month >= 10 else d.year - 1
    total = 0
    for a in self.env['hr.leave.allocation'].sudo().search([('employee_id', '=', rec.employee_id.id), ('holiday_status_id', '=', rec.holiday_status_id.id), ('state', '=', 'validate')]):
        if a.date_from and a.date_from.year <= per:
            total = total + a.number_of_days
    rid = rec._origin.id or 999999999
    usado = 0
    for l in self.env['hr.leave'].sudo().search([('employee_id', '=', rec.employee_id.id), ('holiday_status_id', '=', rec.holiday_status_id.id), ('state', 'in', ['confirm', 'validate1', 'validate']), ('request_date_from', '<=', d)]):
        if l.request_date_from < d or l.id <= rid:
            usado = usado + l.number_of_days
%(final)s
"""
ids["campo_x_periodo"] = campo(M_LEAVE, "hr.leave", "x_periodo", {
    "ttype": "integer", "field_description": "Período", "store": False, "readonly": True, "depends": "request_date_from",
    "compute": """
for rec in self:
    d = rec.request_date_from
    rec['x_periodo'] = (d.year if d.month >= 10 else d.year - 1) if d else 0
""",
})
ids["campo_x_saldo_despues"] = campo(M_LEAVE, "hr.leave", "x_saldo_despues", {
    "ttype": "float", "field_description": "Le quedaban (háb)", "store": False, "readonly": True, "depends": "",
    "compute": CALCULO % {"campo": "x_saldo_despues", "final": "    rec['x_saldo_despues'] = total - usado"},
})
ids["campo_x_saldo_despues_corr"] = campo(M_LEAVE, "hr.leave", "x_saldo_despues_corr", {
    "ttype": "integer", "field_description": "Le quedaban (corridos)", "store": False, "readonly": True, "depends": "",
    "compute": CALCULO % {"campo": "x_saldo_despues_corr", "final": """    t = int(round(total))
    u = int(round(usado))
    if u <= t:
        rec['x_saldo_despues_corr'] = (t + 2 * (t // 5)) - (u + 2 * (u // 5))
    else:
        rec['x_saldo_despues_corr'] = -((u - t) + 2 * ((u - t) // 5))"""},
})

# 3. Formulario de resumen (solo para la acción "Saldo de vacaciones")
ids["vista_resumen_vacaciones"] = upsert("ir.ui.view", [["key", "=", "genoud.hr_employee_resumen_vacaciones"]], {
    "name": "hr.employee.form · resumen de vacaciones", "key": "genoud.hr_employee_resumen_vacaciones",
    "model": "hr.employee", "type": "form", "mode": "primary", "priority": 99,
    "arch": """<form string="Resumen de vacaciones" create="0" edit="0" delete="0">
  <sheet>
    <div class="oe_title"><h1><field name="name" readonly="1"/></h1></div>
    <group>
      <group string="Empleado">
        <field name="company_id" readonly="1"/>
        <field name="x_fecha_ingreso" readonly="1"/>
      </group>
      <group string="Hoy">
        <field name="x_vac_asignado" string="Le corresponden (háb)"/>
        <field name="x_vac_tomado" string="Tomados + por aprobar (háb)"/>
        <field name="x_vac_saldo" string="Le quedan (háb)" decoration-danger="x_vac_saldo &lt; 0" decoration-success="x_vac_saldo &gt; 0" decoration-bf="1"/>
        <field name="x_vac_saldo_corridos" string="Le quedan (corridos)" decoration-danger="x_vac_saldo_corridos &lt; 0" decoration-bf="1"/>
      </group>
    </group>
    <separator string="Días que le corresponden"/>
    <field name="x_vac_asignaciones_ids" readonly="1" nolabel="1">
      <list>
        <field name="date_from" string="Desde"/>
        <field name="name" string="Concepto"/>
        <field name="number_of_days" string="Días (háb)" sum="Total"/>
        <field name="notes" string="Detalle"/>
      </list>
    </field>
    <separator string="Cómo se las tomó"/>
    <field name="x_vac_ausencias_ids" readonly="1" nolabel="1">
      <list default_order="request_date_from, id">
        <field name="x_periodo" string="Período"/>
        <field name="request_date_from" string="Desde"/>
        <field name="request_date_to" string="Hasta"/>
        <field name="x_dias_corridos" string="Corridos" sum="Total"/>
        <field name="number_of_days" string="Hábiles" sum="Total"/>
        <field name="x_retoma" string="Retomó"/>
        <field name="state" string="Estado" widget="badge" decoration-success="state == 'validate'" decoration-warning="state in ('confirm', 'validate1')"/>
        <field name="x_saldo_despues" string="Le quedaron (háb)" decoration-danger="x_saldo_despues &lt; 0"/>
        <field name="x_saldo_despues_corr" string="Le quedaron (corr.)" decoration-danger="x_saldo_despues_corr &lt; 0"/>
        <field name="name" string="Descripción" optional="show"/>
      </list>
    </field>
  </sheet>
</form>""",
})

# 4. La acción "Saldo de vacaciones" abre este formulario al tocar una fila
acc = ids["accion_saldo_vacaciones"]
call("ir.actions.act_window", "write", ids=[acc], vals={"view_mode": "list,form", "view_ids": [[5, 0, 0],
    [0, 0, {"sequence": 1, "view_mode": "list", "view_id": ids["vista_saldo_vacaciones"]}],
    [0, 0, {"sequence": 2, "view_mode": "form", "view_id": ids["vista_resumen_vacaciones"]}]]})
json.dump(ids, open(LOG, "w"), indent=1, ensure_ascii=False)
print({k: ids[k] for k in ids if k.startswith(("campo_x_vac_a", "campo_x_periodo", "campo_x_saldo_d", "vista_resumen"))})
