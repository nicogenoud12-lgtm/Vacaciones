"""Genera la nota PDF de una ausencia de stage y la guarda localmente (para revisarla).
Uso: python3 ver_nota_pdf.py ID_AUSENCIA salida.pdf
Crea una acción temporal con nombre único y la borra SOLO por su ID."""
import base64, os, sys, uuid
sys.path.insert(0, os.path.dirname(__file__))
from o import call, HOST
assert "genoud-stage" in HOST
lid, out = int(sys.argv[1]), sys.argv[2]
code = """pdf = env['ir.actions.report']._render_qweb_pdf('genoud.report_vacaciones_notificacion', records.ids)[0]
action = {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {'title': 'pdf', 'message': b64encode(pdf).decode()}}"""
a = call("ir.actions.server", "create", vals_list=[{"name": "claude-tmp-" + uuid.uuid4().hex[:8], "model_id": 1352, "state": "code", "code": code}])[0]
try:
    r = call("ir.actions.server", "run", ids=[a], context={"active_model": "hr.leave", "active_ids": [lid], "active_id": lid, "allowed_company_ids": [1, 2]})
    open(out, "wb").write(base64.b64decode(r["params"]["message"]))
finally:
    call("ir.actions.server", "unlink", ids=[a])
print("ok", out)
