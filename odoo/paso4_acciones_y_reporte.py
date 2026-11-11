"""Paso 4 (stage): fecha de ingreso visible en la ficha, acción "Generar vacaciones del período",
campos calculados en la ausencia (días corridos y retoma) y la nota de notificación en PDF.
Solo necesita permisos de administrador del sistema. Idempotente (actualiza si ya existe)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from o import call, HOST
assert "genoud-stage" in HOST, "Este script es solo para stage"
LOG = os.path.join(os.path.dirname(__file__), "stage_ids.json")
ids = json.load(open(LOG))
M_EMP, M_LEAVE = 947, 1352


def upsert(model, domain, vals):
    r = call(model, "search", domain=domain, limit=1, context={"active_test": False})
    if r:
        call(model, "write", ids=r, vals=vals)
        return r[0]
    return call(model, "create", vals_list=[vals])[0]


# 1. Fecha de ingreso en la ficha del empleado (pestaña Configuración de RRHH / datos de empleo)
ids["vista_ficha_empleado"] = upsert("ir.ui.view", [["key", "=", "genoud.hr_employee_fecha_ingreso"]], {
    "name": "hr.employee.form · fecha de ingreso (vacaciones)", "key": "genoud.hr_employee_fecha_ingreso",
    "model": "hr.employee", "type": "form", "inherit_id": 3156, "mode": "extension",
    "arch": """<xpath expr="(//field[@name='employee_type'])[1]" position="before">
  <field name="x_fecha_ingreso"/>
</xpath>""",
})

# 2. Acción: generar la asignación de vacaciones del período para los empleados seleccionados
CODIGO = r'''
# Genera la asignacion "Vacaciones AAAA" de cada empleado seleccionado.
# LCT art. 150: antiguedad al 31/12 -> 14/21/28/35 dias corridos = 10/15/20/25 habiles.
# Art. 153: si ingreso en el anio y no trabajo la mitad de los habiles, 1 dia cada 20 habiles trabajados.
# Periodo: desde octubre se genera el del anio en curso; antes, el del anio anterior.
hoy = datetime.date.today()
anio = env.context.get('vac_anio') or (hoy.year if hoy.month >= 10 else hoy.year - 1)
tipo = env['hr.leave.type'].search([('name', '=', 'Vacaciones')], limit=1)
if not tipo:
    raise UserError('No existe el tipo de ausencia "Vacaciones".')
ini = datetime.date(anio, 1, 1)
fin = datetime.date(anio, 12, 31)
habiles_anio = 0
d = ini
while d <= fin:
    if d.weekday() < 5:
        habiles_anio = habiles_anio + 1
    d = d + datetime.timedelta(days=1)
nombre = 'Vacaciones ' + str(anio)
creadas = 0
avisos = []
for emp in records:
    ing = emp.x_fecha_ingreso
    if not ing:
        avisos.append(emp.name + ': falta la fecha de ingreso')
        continue
    if ing > fin:
        continue
    if env['hr.leave.allocation'].search_count([('employee_id', '=', emp.id), ('holiday_status_id', '=', tipo.id), ('name', '=', nombre)]):
        avisos.append(emp.name + ': ya tenia ' + nombre)
        continue
    dias = 0
    detalle = ''
    if ing >= ini:
        trab = 0
        d = ing
        while d <= fin:
            if d.weekday() < 5:
                trab = trab + 1
            d = d + datetime.timedelta(days=1)
        if trab * 2 < habiles_anio:
            dias = int(trab / 20.0 + 0.5)
            detalle = 'Proporcional (art. 153): ' + str(trab) + ' habiles trabajados / 20 = ' + str(dias) + ' dias.'
    if not detalle:
        rd = dateutil.relativedelta.relativedelta
        if fin > ing + rd(years=20):
            corr = 35
        elif fin > ing + rd(years=10):
            corr = 28
        elif fin > ing + rd(years=5):
            corr = 21
        else:
            corr = 14
        dias = corr * 5 // 7
        detalle = 'Antiguedad al 31/12/' + str(anio) + ': ' + str(anio - ing.year) + ' anios -> ' + str(corr) + ' dias corridos = ' + str(dias) + ' habiles.'
    if dias <= 0:
        continue
    env['hr.leave.allocation'].create({
        'name': nombre, 'holiday_status_id': tipo.id, 'employee_id': emp.id, 'allocation_type': 'regular',
        'number_of_days': dias, 'date_from': ini, 'date_to': False, 'notes': detalle,
    })
    creadas = creadas + 1
mensaje = 'Se crearon ' + str(creadas) + ' asignaciones de ' + nombre + '.'
if avisos:
    mensaje = mensaje + ' Sin crear: ' + '; '.join(avisos)
action = {'type': 'ir.actions.client', 'tag': 'display_notification',
          'params': {'title': nombre, 'message': mensaje, 'sticky': True, 'type': 'success' if creadas else 'warning'}}
'''
grupo_ausencias = call("ir.model.data", "search_read", domain=[["module", "=", "hr_holidays"], ["name", "=", "group_hr_holidays_user"]], fields=["res_id"])[0]["res_id"]
ids["accion_generar_vacaciones"] = upsert("ir.actions.server", [["name", "=", "Generar vacaciones del período"], ["model_id", "=", M_EMP]], {
    "name": "Generar vacaciones del período", "model_id": M_EMP, "state": "code", "code": CODIGO,
    "binding_model_id": M_EMP, "binding_type": "action", "binding_view_types": "list,form",
    "group_ids": [[6, 0, [grupo_ausencias]]],
})

# 3. Campos calculados en la ausencia (no almacenados)
def campo(name, ttype, desc, depends, compute):
    return upsert("ir.model.fields", [["model", "=", "hr.leave"], ["name", "=", name]], {
        "model_id": M_LEAVE, "model": "hr.leave", "name": name, "ttype": ttype, "state": "manual",
        "field_description": desc, "store": False, "readonly": True, "depends": depends, "compute": compute,
    })

ids["campo_x_dias_corridos"] = campo("x_dias_corridos", "integer", "Días corridos", "request_date_from,request_date_to", """
for rec in self:
    if rec.request_date_from and rec.request_date_to:
        rec['x_dias_corridos'] = (rec.request_date_to - rec.request_date_from).days + 1
    else:
        rec['x_dias_corridos'] = 0
""")
ids["campo_x_retoma"] = campo("x_retoma", "date", "Retoma tareas", "request_date_to", """
for rec in self:
    if not rec.request_date_to:
        rec['x_retoma'] = False
        continue
    d = rec.request_date_to + datetime.timedelta(days=1)
    n = 0
    while n < 40:
        n = n + 1
        if d.weekday() >= 5:
            d = d + datetime.timedelta(days=1)
            continue
        mediodia = datetime.datetime(d.year, d.month, d.day, 15, 0, 0)
        feriado = self.env['resource.calendar.leaves'].sudo().search_count([
            ('resource_id', '=', False), ('date_from', '<=', mediodia), ('date_to', '>=', mediodia)])
        if feriado:
            d = d + datetime.timedelta(days=1)
            continue
        break
    rec['x_retoma'] = d
""")

# 4. Nota de notificación (dos copias por hoja A4)
KEY = "genoud.report_vacaciones_notificacion"
ARCH = """<t t-name="genoud.report_vacaciones_notificacion">
<t t-call="web.html_container">
<t t-set="letras" t-value="['CERO','UNO','DOS','TRES','CUATRO','CINCO','SEIS','SIETE','OCHO','NUEVE','DIEZ','ONCE','DOCE','TRECE','CATORCE','QUINCE','DIECISÉIS','DIECISIETE','DIECIOCHO','DIECINUEVE','VEINTE','VEINTIUNO','VEINTIDÓS','VEINTITRÉS','VEINTICUATRO','VEINTICINCO','VEINTISÉIS','VEINTISIETE','VEINTIOCHO','VEINTINUEVE']"/>
<t t-set="decenas" t-value="['','','','TREINTA','CUARENTA','CINCUENTA','SESENTA','SETENTA','OCHENTA','NOVENTA']"/>
<t t-set="dias_semana" t-value="['lunes','martes','miércoles','jueves','viernes','sábado','domingo']"/>
<t t-set="meses" t-value="['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']"/>
<t t-foreach="docs" t-as="o">
<div class="article" t-att-data-oe-model="o._name" t-att-data-oe-id="o.id" t-attf-style="font-family: Arial, Helvetica, sans-serif; font-size: 11pt; color: #000; {{ 'page-break-before: always;' if o_index else '' }}">
<t t-set="n" t-value="o.x_dias_corridos"/>
<t t-set="n_letras" t-value="letras[n] if n &lt; 30 else (decenas[n // 10] + ((' Y ' + letras[n % 10]) if n % 10 else ''))"/>
<t t-set="periodo" t-value="o.request_date_from.year if o.request_date_from.month &gt;= 10 else o.request_date_from.year - 1"/>
<t t-foreach="[1, 2]" t-as="copia">
<div t-attf-style="height: 132mm; overflow: hidden; {{ 'border-top: 1px dashed #888; padding-top: 8mm;' if copia == 2 else '' }}">
  <div style="font-size: 9pt;" t-esc="o.employee_id.company_id.name"/>
  <div style="text-align: center; font-weight: bold; font-size: 13pt; margin-top: 4mm;">PERÍODO DE DESCANSO ANUAL</div>
  <div style="text-align: center; font-size: 10pt;">(Artículo 154 - Ley 20.744)</div>
  <div style="text-align: right; margin-top: 6mm;">Pergamino, <t t-esc="int(time.strftime('%d'))"/> de <t t-esc="meses[int(time.strftime('%m')) - 1]"/> de <t t-esc="time.strftime('%Y')"/></div>
  <div style="margin-top: 5mm;">Señor/a: <b t-esc="o.employee_id.name"/></div>
  <p style="margin-top: 4mm; text-align: justify;">Notificámosle que en cumplimiento a lo dispuesto por el artículo 154 de la Ley 20.744 comenzará el período de descanso anual que le corresponde, según se detalla a continuación.</p>
  <table style="margin-left: 6mm; border-collapse: collapse;">
    <tr><td style="font-weight: bold; padding: 1mm 6mm 1mm 0;">CORRESPONDEN AL AÑO:</td><td t-esc="periodo"/></tr>
    <tr><td style="font-weight: bold; padding: 1mm 6mm 1mm 0;">PERÍODO DE:</td><td><t t-esc="n"/> (<t t-esc="n_letras"/>) DÍAS</td></tr>
    <tr><td style="font-weight: bold; padding: 1mm 6mm 1mm 0;">DESDE:</td><td><t t-esc="dias_semana[o.request_date_from.weekday()]"/> <t t-esc="o.request_date_from.strftime('%d/%m/%Y')"/> &#160;&#160; <b>HASTA:</b> <t t-esc="dias_semana[o.request_date_to.weekday()]"/> <t t-esc="o.request_date_to.strftime('%d/%m/%Y')"/> (inclusive)</td></tr>
    <tr><td style="font-weight: bold; padding: 1mm 6mm 1mm 0;">RETOMA TAREAS EL:</td><td><t t-if="o.x_retoma"><t t-esc="dias_semana[o.x_retoma.weekday()]"/> <t t-esc="o.x_retoma.strftime('%d/%m/%Y')"/></t> (en su horario habitual)</td></tr>
  </table>
  <table style="width: 100%; margin-top: 14mm;"><tr><td style="width: 55%;"/><td style="border-top: 1px solid #000; text-align: center; font-size: 9pt; padding-top: 1mm;">Firma del empleador</td></tr></table>
  <div style="margin-top: 6mm; font-size: 10pt;">En la fecha me notifico, recibiendo copia de la presente.</div>
  <table style="width: 100%; margin-top: 14mm;"><tr>
    <td style="width: 38%; border-top: 1px solid #000; text-align: center; font-size: 9pt; padding-top: 1mm;">Firma del empleado</td>
    <td style="width: 24%;"/>
    <td style="width: 38%; border-top: 1px solid #000; text-align: center; font-size: 9pt; padding-top: 1mm;">Aclaración de firma</td>
  </tr></table>
</div>
</t>
</div>
</t>
</t>
</t>"""
ids["vista_nota_vacaciones"] = upsert("ir.ui.view", [["key", "=", KEY]], {"name": KEY, "key": KEY, "type": "qweb", "arch": ARCH})
ids["reporte_nota_vacaciones"] = upsert("ir.actions.report", [["report_name", "=", KEY]], {
    "name": "Notificación de vacaciones", "model": "hr.leave", "report_type": "qweb-pdf", "report_name": KEY, "report_file": KEY,
    "binding_model_id": M_LEAVE, "binding_type": "report",
    "print_report_name": "'Notificacion vacaciones - %s' % object.employee_id.name",
})
json.dump(ids, open(LOG, "w"), indent=1, ensure_ascii=False)
print({k: v for k, v in ids.items() if k not in ("empleados", "feriados", "etiquetas")})
