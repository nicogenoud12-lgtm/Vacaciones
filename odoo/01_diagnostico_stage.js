// Diagnóstico de solo lectura para genoud-stage.odoo.com
// Pegar entero en la consola del navegador (F12 > Consola) con la sesión de Odoo abierta.
// No escribe nada: solo lee qué módulos, horarios, feriados y tipos de ausencia hay.
(async () => {
  const kw = (model, method, args = [], kwargs = {}) =>
    fetch('/web/dataset/call_kw', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: { model, method, args, kwargs } }),
    }).then((r) => r.json())
      .then((r) => { if (r.error) throw new Error(r.error.data?.message || r.error.message); return r.result; });
  const paso = async (titulo, fn) => { try { console.log('=== ' + titulo); await fn(); } catch (e) { console.log('   (no se pudo leer: ' + e.message + ')'); } };

  console.log('Entorno:', location.host);
  let mods = [];
  await paso('Módulos de RRHH', async () => {
    mods = await kw('ir.module.module', 'search_read',
      [[['name', 'in', ['hr', 'hr_holidays', 'hr_contract', 'hr_work_entry', 'hr_org_chart', 'hr_skills', 'resource']]]],
      { fields: ['name', 'shortdesc', 'state'] });
    console.table(mods.map((m) => ({ modulo: m.name, nombre: m.shortdesc, estado: m.state })));
  });
  const instalado = (n) => mods.some((m) => m.name === n && m.state === 'installed');

  await paso('Compañías', async () => {
    console.table(await kw('res.company', 'search_read', [[]], { fields: ['name'] }));
  });

  await paso('Horarios de trabajo (resource.calendar)', async () => {
    const cals = await kw('resource.calendar', 'search_read', [[]], { fields: ['name', 'company_id', 'hours_per_day'] });
    console.table(cals.map((c) => ({ id: c.id, nombre: c.name, compania: c.company_id && c.company_id[1], horas_dia: c.hours_per_day })));
  });

  await paso('Feriados cargados desde 2026', async () => {
    const fer = await kw('resource.calendar.leaves', 'search_read',
      [[['resource_id', '=', false], ['date_from', '>=', '2026-01-01 00:00:00']]], { fields: ['name', 'date_from', 'calendar_id', 'company_id'], limit: 60 });
    console.log('   cantidad:', fer.length);
    if (fer.length) console.table(fer.map((f) => ({ fecha: f.date_from, nombre: f.name, horario: f.calendar_id && f.calendar_id[1] })));
  });

  if (instalado('hr')) {
    await paso('Empleados', async () => {
      const n = await kw('hr.employee', 'search_count', [[]]);
      const emps = await kw('hr.employee', 'search_read', [[]], { fields: ['company_id'] });
      const porCia = {};
      for (const e of emps) { const c = e.company_id ? e.company_id[1] : '(sin compañía)'; porCia[c] = (porCia[c] || 0) + 1; }
      console.log('   empleados activos:', n);
      console.table(porCia);
      const f = await kw('hr.employee', 'fields_get', [], { attributes: ['string', 'type'] });
      console.log('   campos de fecha:', Object.entries(f).filter(([, v]) => v.type === 'date').map(([k, v]) => k + ' (' + v.string + ')').join(', '));
    });
  } else console.log('=== Empleados: el módulo hr no está instalado');

  if (instalado('hr_holidays')) {
    await paso('Tipos de ausencia', async () => {
      const f = await kw('hr.leave.type', 'fields_get', [], { attributes: ['string', 'type'] });
      const campos = Object.keys(f).filter((k) => /request_unit|requires_allocation|allows_negative|max_allowed_negative|leave_validation_type|company_id/.test(k));
      const t = await kw('hr.leave.type', 'search_read', [[]], { fields: ['name', ...campos], context: { active_test: false } });
      console.table(t);
    });
    await paso('Asignaciones y ausencias existentes', async () => {
      console.log('   asignaciones:', await kw('hr.leave.allocation', 'search_count', [[]]));
      console.log('   ausencias:', await kw('hr.leave', 'search_count', [[]]));
    });
  } else console.log('=== Ausencias: el módulo hr_holidays no está instalado');

  console.log('Listo. Copiá todo lo que salió desde "Entorno:" y pegalo en el chat.');
})();
