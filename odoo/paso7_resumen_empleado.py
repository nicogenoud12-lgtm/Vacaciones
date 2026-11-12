"""Paso 7 (stage / prod: ODOO_ENV): "Resumen de vacaciones" por empleado, al tocar una fila de Vacaciones → Reportes → Saldo de vacaciones.
Muestra el saldo actual, los días que le correspondieron (asignaciones) y cada pedido con el saldo que le quedó después.

Período de un pedido: octubre a diciembre = período del año; enero a septiembre = período del año anterior
(misma regla que la nota PDF: las vacaciones del período 2026 se toman de octubre 2026 a septiembre 2027).
"Le quedaban" después de un pedido = asignaciones de ese período y anteriores − pedidos acumulados hasta ese."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from o import call, HOST, ENV
print(">>> ESTAS EN:", HOST)

def _modelo(nombre):
    return call("ir.model", "search", domain=[["model", "=", nombre]], limit=1)[0]
LOG = os.path.join(os.path.dirname(__file__), ENV + "_ids.json")
ids = json.load(open(LOG))
M_EMP, M_LEAVE = _modelo("hr.employee"), _modelo("hr.leave")


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

# 2b. Desglose de cada pedido: días de fin de semana y feriados (lunes a viernes) dentro del rango; período como texto
ids["campo_x_periodo_txt"] = campo(M_LEAVE, "hr.leave", "x_periodo_txt", {
    "ttype": "char", "field_description": "Período (texto)", "store": False, "readonly": True, "depends": "request_date_from",
    "compute": """
for rec in self:
    d = rec.request_date_from
    rec['x_periodo_txt'] = str(d.year if d.month >= 10 else d.year - 1) if d else ''
""",
})
ids["campo_x_dias_finde"] = campo(M_LEAVE, "hr.leave", "x_dias_finde", {
    "ttype": "integer", "field_description": "Días de fin de semana", "store": False, "readonly": True,
    "depends": "request_date_from,request_date_to",
    "compute": """
for rec in self:
    n = 0
    if rec.request_date_from and rec.request_date_to:
        d = rec.request_date_from
        while d <= rec.request_date_to:
            if d.weekday() >= 5:
                n = n + 1
            d = d + datetime.timedelta(days=1)
    rec['x_dias_finde'] = n
""",
})
ids["campo_x_dias_feriado"] = campo(M_LEAVE, "hr.leave", "x_dias_feriado", {
    "ttype": "integer", "field_description": "Feriados (lunes a viernes)", "store": False, "readonly": True,
    "depends": "request_date_from,request_date_to,employee_id",
    "compute": """
for rec in self:
    n = 0
    if rec.request_date_from and rec.request_date_to and rec.employee_id:
        cia = rec.employee_id.company_id.id
        d = rec.request_date_from
        while d <= rec.request_date_to:
            if d.weekday() < 5:
                mediodia = datetime.datetime(d.year, d.month, d.day, 15, 0, 0)
                if self.env['resource.calendar.leaves'].sudo().search_count([
                        ('resource_id', '=', False), ('company_id', 'in', [cia, False]),
                        ('date_from', '<=', mediodia), ('date_to', '>=', mediodia)]):
                    n = n + 1
            d = d + datetime.timedelta(days=1)
    rec['x_dias_feriado'] = n
""",
})

ids["campo_x_finde_cobrado"] = campo(M_LEAVE, "hr.leave", "x_finde_cobrado", {
    "ttype": "integer", "field_description": "Fin de semana cobrado (días)", "store": False, "readonly": True, "depends": "",
    # días de fin de semana que se cobran con este pedido = corridos que baja el saldo − hábiles del pedido
    # (cada vez que se completan 5 hábiles se cobran 2 días de fin de semana)
    "compute": CALCULO % {"campo": "x_finde_cobrado", "final": """    t = int(round(total))
    antes = int(round(usado - rec.number_of_days))
    ahora = int(round(usado))
    if antes <= t:
        c_antes = (t + 2 * (t // 5)) - (antes + 2 * (antes // 5))
    else:
        c_antes = -((antes - t) + 2 * ((antes - t) // 5))
    if ahora <= t:
        c_ahora = (t + 2 * (t // 5)) - (ahora + 2 * (ahora // 5))
    else:
        c_ahora = -((ahora - t) + 2 * ((ahora - t) // 5))
    rec['x_finde_cobrado'] = (c_antes - c_ahora) - int(round(rec.number_of_days))"""},
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
        <field name="x_vac_asignado" string="Le corresponden (háb)" widget="integer"/>
        <field name="x_vac_tomado" string="Tomados + por aprobar (háb)" widget="integer"/>
        <field name="x_vac_saldo" string="Le quedan (háb)" widget="integer" decoration-danger="x_vac_saldo &lt; 0" decoration-success="x_vac_saldo &gt; 0" decoration-bf="1"/>
        <field name="x_vac_saldo_corridos" string="Le quedan (corridos)" decoration-danger="x_vac_saldo_corridos &lt; 0" decoration-bf="1"/>
      </group>
    </group>
    <separator string="Días que le corresponden"/>
    <field name="x_vac_asignaciones_ids" readonly="1" nolabel="1">
      <list>
        <field name="date_from" string="Desde"/>
        <field name="name" string="Concepto"/>
        <field name="number_of_days" string="Días (háb)" sum="Total" widget="integer"/>
        <field name="notes" string="Detalle"/>
      </list>
    </field>
    <separator string="Cómo se las tomó"/>
    <field name="x_vac_ausencias_ids" readonly="1" nolabel="1">
      <list default_order="request_date_from, id">
        <field name="x_periodo_txt" string="Período"/>
        <field name="request_date_from" string="Desde"/>
        <field name="request_date_to" string="Hasta"/>
        <field name="x_dias_corridos" string="Corridos" sum="Total"/>
        <field name="number_of_days" string="Hábiles (descuenta)" sum="Total" widget="integer"/>
        <field name="x_dias_finde" string="Fin de semana" sum="Total"/>
        <field name="x_dias_feriado" string="Feriados" sum="Total"/>
        <field name="x_retoma" string="Retomó"/>
        <field name="state" string="Estado" widget="badge" decoration-success="state == 'validate'" decoration-warning="state in ('confirm', 'validate1')"/>
        <field name="x_saldo_despues" string="Le quedaron (háb)" widget="integer" decoration-danger="x_saldo_despues &lt; 0"/>
        <field name="x_finde_cobrado" string="Finde cobrado" sum="Total" decoration-warning="x_finde_cobrado &gt; 0"/>
        <field name="x_saldo_despues_corr" string="Le quedaron (corr.)" decoration-danger="x_saldo_despues_corr &lt; 0"/>
        <field name="name" string="Descripción" optional="show"/>
      </list>
    </field>
  </sheet>
  <chatter/>
</form>""",
})

# 4. La acción "Saldo de vacaciones" abre este formulario al tocar una fila
acc = ids["accion_saldo_vacaciones"]
call("ir.actions.act_window", "write", ids=[acc], vals={"view_mode": "list,form", "view_ids": [[5, 0, 0],
    [0, 0, {"sequence": 1, "view_mode": "list", "view_id": ids["vista_saldo_vacaciones"]}],
    [0, 0, {"sequence": 2, "view_mode": "form", "view_id": ids["vista_resumen_vacaciones"]}]]})
json.dump(ids, open(LOG, "w"), indent=1, ensure_ascii=False)
print({k: ids[k] for k in ids if k.startswith(("campo_x_vac_a", "campo_x_periodo", "campo_x_saldo_d", "vista_resumen"))})
