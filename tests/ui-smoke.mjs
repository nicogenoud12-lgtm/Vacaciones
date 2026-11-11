// Prueba de humo de la interfaz con Playwright y la simulación de window.claude.
// Uso: node tests/ui-smoke.mjs seed.json carpeta-capturas
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const [seedPath, outDir] = process.argv.slice(2);
const page0 = readFileSync(new URL('../dist/vacaciones.html', import.meta.url), 'utf8');
const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>:root{color-scheme:light;padding-top:env(safe-area-inset-top);padding-bottom:env(safe-area-inset-bottom)}body{margin:0;font:14px system-ui}img{max-width:100%}[hidden]{display:none!important}</style></head><body>${page0}</body></html>`;
const file = outDir + '/page.html';
writeFileSync(file, html);
const seed = JSON.parse(readFileSync(seedPath, 'utf8'));
const mock = readFileSync(new URL('./mock-claude.js', import.meta.url), 'utf8');

const browser = await chromium.launch();
const errors = [];
async function open(opts) {
  const ctx = await browser.newContext(opts);
  const page = await ctx.newPage();
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  await page.addInitScript(mock);
  // Sin acceso a cdnjs/Google Fonts en el entorno de pruebas: servir las librerías desde LIBS_DIR (npm).
  if (process.env.LIBS_DIR) {
    await page.route('https://cdnjs.cloudflare.com/**', (route) => {
      const u = route.request().url();
      const f = u.includes('jspdf') ? '/node_modules/jspdf/dist/jspdf.umd.min.js' : '/node_modules/xlsx/dist/xlsx.full.min.js';
      route.fulfill({ path: process.env.LIBS_DIR + f, contentType: 'application/javascript' });
    });
  }
  await page.route('https://fonts.googleapis.com/**', (route) => route.fulfill({ body: '', contentType: 'text/css' }));
  await page.route('https://fonts.gstatic.com/**', (route) => route.abort());
  await page.goto('file://' + file);
  await page.evaluate((s) => window.__seed(s), seed);
  await page.waitForSelector('tr[data-act="abrir"]');
  return page;
}
const check = (cond, msg) => { if (!cond) { console.log('FALLA:', msg); process.exitCode = 1; } else console.log('ok:', msg); };

const page = await open({ viewport: { width: 1280, height: 900 } });
const rows = await page.$$eval('tr[data-act="abrir"]', (r) => r.length);
check(rows === 71, `lista 71 empleados activos (${rows})`);
await page.screenshot({ path: outDir + '/1-empleados.png' });

// Alfaro: 21 corridos (15 háb) + arrastre 5 = 20 háb
const alfaro = await page.textContent('tr[data-id="alfaro-axel-leonel"]');
check(/20 háb/.test(alfaro), 'Alfaro tiene 20 háb disponibles: ' + alfaro.replace(/\s+/g, ' '));
const leiva = await page.textContent('tr[data-id="leiva-carlos-ariel"]');
check(/15 háb/.test(leiva), 'Leiva 25 - 10 anticipo = 15 háb: ' + leiva.replace(/\s+/g, ' '));

// Ejemplo de Nicolás con Assad (14 corridos = 10 háb): 3 días y después 3 más
await page.click('tr[data-id="assad-thiago"]');
await page.fill('#m-desde', '2026-12-14'); await page.fill('#m-hasta', '2026-12-16');
await page.dispatchEvent('#m-hasta', 'input');
let prev = await page.textContent('#m-preview');
check(/Descuenta 3 días hábiles/.test(prev) && /Le quedan 7 hábiles \(= 11 corridos\)/.test(prev), 'primer pedido 3 días: ' + prev);
await page.click('#m-guardar');
await page.waitForFunction(() => document.querySelector('#f-hist').textContent.includes('14/12/2026'));
await page.fill('#m-desde', '2026-12-21'); await page.fill('#m-hasta', '2026-12-23'); await page.dispatchEvent('#m-hasta', 'input');
prev = await page.textContent('#m-preview');
check(/Le quedan 4 hábiles \(= 6 corridos\)/.test(prev), 'segundo pedido 3 días: ' + prev);
await page.click('#m-guardar');
await page.waitForFunction(() => document.querySelector('#f-hist').textContent.includes('21/12/2026'));
// Feriado 25/12 dentro de un rango
await page.fill('#m-desde', '2026-12-24'); await page.fill('#m-hasta', '2026-12-28'); await page.dispatchEvent('#m-hasta', 'input');
prev = await page.textContent('#m-preview');
check(/Descuenta 2 días hábiles/.test(prev) && /Navidad/.test(prev), 'feriado no descuenta: ' + prev);
await page.screenshot({ path: outDir + '/2-ficha.png' });
// Nota PDF
await page.click('#f-hist button[data-act="nota"]');
await page.waitForFunction(() => window.__downloads.length > 0, null, { timeout: 20000 }).catch(() => {});
const dls = await page.evaluate(() => window.__downloads);
check(dls.length === 1 && /\.pdf$/.test(dls[0].filename) && dls[0].size > 2000, 'nota PDF generada: ' + JSON.stringify(dls));
if (dls.length) writeFileSync(outDir + '/nota.pdf', Buffer.from(await page.evaluate((f) => window.__files[f], dls[0].filename), 'base64'));
await page.keyboard.press('Escape');

// Editar, ajustar y eliminar (Assad: 10 háb, tomó 3 + 3)
await page.click('tr[data-id="assad-thiago"]');
await page.waitForSelector('#f-hist button[data-act="editar-mov"]');
await page.click('#f-hist li:first-child button[data-act="editar-mov"]');   // el del 21 al 23/12
await page.fill('#m-hasta', '2026-12-22'); await page.dispatchEvent('#m-hasta', 'input');
await page.click('#m-guardar');
await page.waitForFunction(() => /22\/12\/2026/.test(document.querySelector('#f-hist').textContent));
let res = await page.textContent('#f-resumen');
check(/^\s*5\s*días hábiles le quedan/.test(res), 'editar a 2 días deja 5 háb: ' + res.slice(0, 60).replace(/\s+/g, ' '));
// fin de semana solo: no se guarda
await page.fill('#m-desde', '2026-12-19'); await page.fill('#m-hasta', '2026-12-20'); await page.dispatchEvent('#m-hasta', 'input');
await page.click('#m-guardar');
check((await page.$$eval('#f-hist li', (l) => l.length)) === 2, 'un pedido de sábado y domingo no se guarda');
await page.fill('#m-desde', ''); await page.fill('#m-hasta', '');
// ajuste manual +2
await page.click('details:has(#a-dias) summary');
await page.fill('#a-dias', '2'); await page.fill('#a-motivo', 'Acuerdo especial');
await page.click('button[data-act="guardar-ajuste"]');
await page.waitForFunction(() => /Ajuste \+2/.test(document.querySelector('#f-hist').textContent));
res = await page.textContent('#f-resumen');
check(/^\s*7\s*días hábiles le quedan/.test(res), 'ajuste +2 deja 7 háb');
// eliminar (dos toques) el pedido del 14 al 16/12
const del = page.locator('#f-hist li', { hasText: '14/12/2026' }).locator('button[data-act="borrar-mov"]');
await del.click(); await del.click();
await page.waitForFunction(() => !/14\/12\/2026/.test(document.querySelector('#f-hist').textContent));
res = await page.textContent('#f-resumen');
check(/^\s*10\s*días hábiles le quedan/.test(res), 'eliminar el pedido de 3 días deja 10 háb');
await page.keyboard.press('Escape');

// Empleado nuevo con antigüedad: no acumula los años anteriores
await page.click('button[data-act="nuevo-emp"]');
await page.fill('#e-nombre', 'PRUEBA, Antiguo'); await page.fill('#e-ingreso', '2012-03-01');
await page.click('button[data-act="guardar-emp"]');
await page.waitForSelector('#f-resumen .big-saldo');
res = await page.textContent('#f-resumen');
check(/^\s*20\s*días hábiles le quedan del período 2026/.test(res), 'alta de empleado con 14 años de antigüedad: 20 háb, sin acumular años previos: ' + res.slice(0, 70).replace(/\s+/g, ' '));
// baja con fecha futura: sigue activo; con fecha pasada: pasa a "Dados de baja"
await page.click('details:has(#e-nombre) summary');
await page.fill('#e-baja', '2099-01-01'); await page.click('button[data-act="guardar-emp"]');
await page.waitForFunction(() => window.__mockStore && [...window.__mockStore.values()].some((d) => d.baja === '2099-01-01'));
await page.keyboard.press('Escape');
check((await page.$$eval('tr[data-act="abrir"]', (r) => r.length)) === 72, 'baja con fecha futura: sigue en la lista de activos');
await page.fill('#f-q', 'prueba'); await page.click('tr[data-act="abrir"]');
await page.click('details:has(#e-nombre) summary');
await page.fill('#e-baja', '2026-01-31'); await page.click('button[data-act="guardar-emp"]');
await page.waitForFunction(() => [...window.__mockStore.values()].some((d) => d.baja === '2026-01-31'));
await page.keyboard.press('Escape'); await page.fill('#f-q', '');
await page.waitForFunction(() => document.querySelectorAll('tr[data-act="abrir"]').length === 71);
check(true, 'baja con fecha pasada: sale de la lista de activos');

// Configuración: los feriados pasan a descontar
await page.click('a[data-view="configuracion"]');
await page.waitForSelector('#cfg-form');
await page.check('#c-ferdesc'); await page.click('#cfg-form button[type="submit"]');
await page.waitForFunction(() => window.__mockStore.get('config/general').feriadosDescuentan === true);
await page.click('a[data-view="empleados"]');
await page.click('tr[data-id="assad-thiago"]');
await page.fill('#m-desde', '2026-12-24'); await page.fill('#m-hasta', '2026-12-28'); await page.dispatchEvent('#m-hasta', 'input');
prev = await page.textContent('#m-preview');
check(/Descuenta 3 días hábiles/.test(prev) && /sí descuenta/.test(prev), 'con la opción activada, Navidad descuenta: ' + prev.slice(0, 90));
await page.keyboard.press('Escape');
await page.click('a[data-view="configuracion"]');
await page.uncheck('#c-ferdesc'); await page.click('#cfg-form button[type="submit"]');
await page.waitForFunction(() => window.__mockStore.get('config/general').feriadosDescuentan === false);

// Planificación + carga masiva
await page.click('a[data-view="planificacion"]');
await page.waitForSelector('table.plan');
await page.click('#bulk summary');
await page.check('input[data-bulk="alfaro-axel-leonel"]');
await page.check('input[data-bulk="leiva-carlos-ariel"]');
await page.fill('#b-desde', '2027-01-11'); await page.fill('#b-hasta', '2027-01-24'); await page.dispatchEvent('#b-hasta', 'input');
const bp = await page.textContent('#b-preview');
check(/10 hábiles/.test(bp) && /14 corridos/.test(bp) && /2 empleados/.test(bp), 'carga masiva preview: ' + bp);
await page.click('#b-cargar');
await page.waitForFunction(() => document.querySelectorAll('td.cell.plan').length >= 4);
await page.screenshot({ path: outDir + '/3-plan.png' });

// Excel
await page.click('#btn-exportar');
await page.waitForFunction(() => window.__downloads.length > 1, null, { timeout: 20000 }).catch(() => {});
const dl2 = await page.evaluate(() => window.__downloads);
check(dl2.length === 2 && /\.xlsx$/.test(dl2[1].filename), 'Excel exportado: ' + JSON.stringify(dl2[1] || null));

await page.click('a[data-view="configuracion"]');
await page.waitForSelector('#cfg-form');
await page.screenshot({ path: outDir + '/4-config.png', fullPage: true });

// Celular, modo oscuro
const ph = await open({ viewport: { width: 390, height: 844 }, colorScheme: 'dark' });
await ph.screenshot({ path: outDir + '/5-celular.png' });
const sw = await ph.evaluate(() => document.documentElement.scrollWidth);
check(sw <= 390, 'sin scroll horizontal en celular (' + sw + ')');
await ph.click('tr[data-id="picado-ricardo"]');
await ph.waitForTimeout(400);
await ph.screenshot({ path: outDir + '/6-celular-ficha.png' });

check(errors.length === 0, 'sin errores de consola: ' + errors.join(' | '));
await browser.close();
