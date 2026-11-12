"""Paso 6 (stage / prod: ODOO_ENV): vista "Saldo de vacaciones" con el saldo real por empleado (incluye anticipos/negativos).
El reporte Balance de Odoo nunca muestra negativos: calcula "Restante" por asignación y lo deja en 0.
Agrega campos calculados (no almacenados) en hr.employee, una lista, una acción y un menú en Vacaciones → Reportes."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from o import call, HOST, ENV
print(">>> ESTAS EN:", HOST)

def _modelo(nombre):
    return call("ir.model", "search", domain=[["model", "=", nombre]], limit=1)[0]
LOG = os.path.join(os.path.dirname(__file__), ENV + "_ids.json")
ids = json.load(open(LOG))
M_EMP = _modelo("hr.employee")

def upsert(model, domain, vals):
    r = call(model, "search", domain=domain, limit=1, context={"active_test": False})
    if r:
        call(model, "write", ids=r, vals=vals); return r[0]
    return call(model, "create", vals_list=[vals])[0]

def campo(name, ttype, desc, compute, digits=None):
    vals = {"model_id": M_EMP, "model": "hr.employee", "name": name, "ttype": ttype, "state": "manual",
            "field_description": desc, "store": False, "readonly": True, "depends": "", "compute": compute}
    return upsert("ir.model.fields", [["model", "=", "hr.employee"], ["name", "=", name]], vals)

# En serie (cada campo recarga el registry). El saldo depende de los dos primeros: se crea después.
ids["campo_x_vac_asignado"] = campo("x_vac_asignado", "float", "Vacaciones: asignados (háb)", """
tipo = self.env['hr.leave.type'].sudo().search([('name', '=', 'Vacaciones')], limit=1)
for rec in self:
    al = self.env['hr.leave.allocation'].sudo().search([('employee_id', '=', rec.id), ('holiday_status_id', '=', tipo.id), ('state', '=', 'validate')])
    rec['x_vac_asignado'] = sum(al.mapped('number_of_days'))
""")
ids["campo_x_vac_tomado"] = campo("x_vac_tomado", "float", "Vacaciones: tomados y por aprobar (háb)", """
tipo = self.env['hr.leave.type'].sudo().search([('name', '=', 'Vacaciones')], limit=1)
for rec in self:
    lv = self.env['hr.leave'].sudo().search([('employee_id', '=', rec.id), ('holiday_status_id', '=', tipo.id), ('state', 'in', ['confirm', 'validate1', 'validate'])])
    rec['x_vac_tomado'] = sum(lv.mapped('number_of_days'))
""")
ids["campo_x_vac_saldo"] = campo("x_vac_saldo", "float", "Vacaciones: saldo (háb)", """
for rec in self:
    rec['x_vac_saldo'] = rec.x_vac_asignado - rec.x_vac_tomado
""")
# Corridos con la regla de la app: cada 5 hábiles se cobra un fin de semana.
ids["campo_x_vac_saldo_corridos"] = campo("x_vac_saldo_corridos", "integer", "Vacaciones: saldo (corridos)", """
for rec in self:
    t = int(round(rec.x_vac_asignado))
    u = int(round(rec.x_vac_tomado))
    if u <= t:
        c = (t + 2 * (t // 5)) - (u + 2 * (u // 5))
    else:
        d = u - t
        c = -(d + 2 * (d // 5))
    rec['x_vac_saldo_corridos'] = c
""")

ids["vista_saldo_vacaciones"] = upsert("ir.ui.view", [["key", "=", "genoud.hr_employee_saldo_vacaciones"]], {
    "name": "hr.employee.list · saldo de vacaciones", "key": "genoud.hr_employee_saldo_vacaciones",
    "model": "hr.employee", "type": "list", "mode": "primary", "priority": 99,
    "arch": """<list string="Saldo de vacaciones" create="0" delete="0" default_order="name">
  <field name="name"/>
  <field name="company_id" optional="show"/>
  <field name="x_fecha_ingreso" optional="show"/>
  <field name="x_vac_asignado" string="Asignados (háb)"/>
  <field name="x_vac_tomado" string="Tomados + por aprobar (háb)"/>
  <field name="x_vac_saldo" string="Saldo (háb)" decoration-danger="x_vac_saldo &lt; 0" decoration-success="x_vac_saldo &gt; 0" decoration-bf="1"/>
  <field name="x_vac_saldo_corridos" string="Saldo (corridos)" decoration-danger="x_vac_saldo_corridos &lt; 0"/>
  <field name="category_ids" widget="many2many_tags" optional="hide"/>
</list>""",
})
grupo = call("ir.model.data", "search_read", domain=[["module", "=", "hr_holidays"], ["name", "=", "group_hr_holidays_user"]], fields=["res_id"])[0]["res_id"]
ids["accion_saldo_vacaciones"] = upsert("ir.actions.act_window", [["name", "=", "Saldo de vacaciones"], ["res_model", "=", "hr.employee"]], {
    "name": "Saldo de vacaciones", "res_model": "hr.employee", "view_mode": "list,form",
    "view_id": ids["vista_saldo_vacaciones"],
    "domain": "['|', ('x_fecha_ingreso', '!=', False), ('category_ids.name', '=', 'Importado de Excel vacaciones')]",
    "help": "<p>Saldo real de vacaciones por empleado, en días hábiles y corridos. En rojo: anticipo (saldo negativo).</p>",
})
# Menú hermano de Reportes → Balance
bal = call("ir.model.data", "search_read", domain=[["module", "=", "hr_holidays"], ["model", "=", "ir.ui.menu"]], fields=["res_id"])
menus = call("ir.ui.menu", "read", ids=[b["res_id"] for b in bal], fields=["name", "parent_id", "sequence"], context={"lang": "en_US"})
padre = [m for m in menus if m["name"] in ("Balance",)][0]["parent_id"][0]
ids["menu_saldo_vacaciones"] = upsert("ir.ui.menu", [["name", "=", "Saldo de vacaciones"], ["parent_id", "=", padre]], {
    "name": "Saldo de vacaciones", "parent_id": padre, "sequence": 1,
    "action": f"ir.actions.act_window,{ids['accion_saldo_vacaciones']}", "group_ids": [[6, 0, [grupo]]],
})
json.dump(ids, open(LOG, "w"), indent=1, ensure_ascii=False)
print({k: ids[k] for k in ids if "saldo" in k or "x_vac" in k})
