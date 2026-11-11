// Pruebas de la lógica de vacaciones. Ejecutar con: node --test tests/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const C = require('../src/calc.js');

const sinFeriados = new Set();

test('escala LCT art. 150 según antigüedad al 31/12 del período', () => {
  // Menos de 5 años -> 14 corridos = 10 hábiles
  assert.deepEqual(pick(C.derecho('2023-09-01', 2026)), { tipo: 'escala', corridos: 14, habiles: 10 });
  // Ingreso 2018 -> 8 años -> 21 / 15
  assert.deepEqual(pick(C.derecho('2018-02-01', 2026)), { tipo: 'escala', corridos: 21, habiles: 15 });
  // Ingreso 2011 -> 15 años -> 28 / 20
  assert.deepEqual(pick(C.derecho('2011-10-11', 2026)), { tipo: 'escala', corridos: 28, habiles: 20 });
  // Ingreso 1997 -> 29 años -> 35 / 25
  assert.deepEqual(pick(C.derecho('1997-01-02', 2026)), { tipo: 'escala', corridos: 35, habiles: 25 });
});

test('antigüedad: "no exceda de 5 años" es 14, recién más de 5 es 21', () => {
  assert.equal(C.derecho('2021-12-31', 2026).corridos, 14); // exactamente 5 años
  assert.equal(C.derecho('2021-12-30', 2026).corridos, 21); // 5 años y 1 día
  assert.equal(C.derecho('2016-12-31', 2026).corridos, 21); // exactamente 10
  assert.equal(C.derecho('2016-12-30', 2026).corridos, 28);
  assert.equal(C.derecho('2006-12-31', 2026).corridos, 28); // exactamente 20
  assert.equal(C.derecho('2006-12-30', 2026).corridos, 35);
});

test('ingresante con más de medio año trabajado cobra la escala completa', () => {
  // Excel: Di Lorenzo 13/04/2026 y Villagómez 30/04/2026 -> 14
  assert.equal(C.derecho('2026-04-13', 2026).corridos, 14);
  assert.equal(C.derecho('2026-04-30', 2026).corridos, 14);
  // Astrada 02/06/2025 -> 14 en 2025
  assert.equal(C.derecho('2025-06-02', 2025).corridos, 14);
});

test('ingresante con menos de medio año: 1 día cada 20 hábiles (art. 153)', () => {
  // Excel: De Pascua 11/08/2025 -> ROUND(NETWORKDAYS/20) = 5
  const d = C.derecho('2025-08-11', 2025);
  assert.equal(d.tipo, 'proporcional');
  assert.equal(d.habiles, 5);
  // Genoud 03/09/2026 -> 4 hábiles
  assert.equal(C.derecho('2026-09-03', 2026).habiles, 4);
  // El año siguiente ya cobra escala
  assert.equal(C.derecho('2025-08-11', 2026).corridos, 14);
});

test('sin fecha de ingreso o ingreso posterior al período: sin derecho calculable', () => {
  assert.equal(C.derecho(null, 2026).tipo, 'sin-ingreso');
  assert.equal(C.derecho('2027-02-01', 2026).habiles, 0);
});

test('contar días de un pedido: hábiles y corridos', () => {
  // Cierre de planta "12 a 25" de enero 2026: lun a dom, 14 corridos, 10 hábiles
  assert.deepEqual(pickR(C.contarRango('2026-01-12', '2026-01-25', sinFeriados)), { corridos: 14, habiles: 10 });
  // "5 a 25": 21 corridos, 15 hábiles
  assert.deepEqual(pickR(C.contarRango('2026-01-05', '2026-01-25', sinFeriados)), { corridos: 21, habiles: 15 });
  // Viernes a lunes: 4 corridos, 2 hábiles
  assert.deepEqual(pickR(C.contarRango('2026-07-10', '2026-07-13', sinFeriados)), { corridos: 4, habiles: 2 });
  // Un solo día
  assert.deepEqual(pickR(C.contarRango('2026-03-09', '2026-03-09', sinFeriados)), { corridos: 1, habiles: 1 });
});

test('feriados dentro del pedido no descuentan (opción por defecto)', () => {
  const fer = new Set(['2026-02-16', '2026-02-17']); // Carnaval
  const r = C.contarRango('2026-02-16', '2026-02-20', fer);
  assert.equal(r.habiles, 3);
  assert.equal(r.feriados, 2);
  // Con la opción contraria descuentan
  assert.equal(C.contarRango('2026-02-16', '2026-02-20', fer, true).habiles, 5);
});

test('hábiles a corridos: cada 5 hábiles se suma un fin de semana', () => {
  assert.equal(C.habACorr(3), 3);
  assert.equal(C.habACorr(5), 7);
  assert.equal(C.habACorr(6), 8);
  assert.equal(C.habACorr(10), 14);
  assert.equal(C.habACorr(15), 21);
  assert.equal(C.habACorr(25), 35);
  assert.equal(C.habACorr(-7), -9);
});

test('ejemplo de Nicolás: 14 corridos, pide 3 y después 3 más', () => {
  const total = 10; // 14 corridos
  assert.equal(C.saldoCorridos(total, 3), 11);
  assert.equal(C.saldoCorridos(total, 6), 6); // 3 + 3 + finde = 8 descontados
  assert.equal(C.saldoCorridos(total, 10), 0);
  assert.equal(C.saldoCorridos(total, 12), -2); // anticipo
});

test('saldos encadenados: el saldo de un año pasa al siguiente', () => {
  const emp = { ingreso: '2018-02-01', inicio: { anio: 2026, arrastre: 5 } };
  const movs = {
    2026: [
      { tipo: 'vac', habiles: 10 },
      { tipo: 'vac', habiles: 3 },
      { tipo: 'ajuste', dias: 1 },
    ],
    2027: [{ tipo: 'vac', habiles: 15 }],
  };
  const s = C.saldos(emp, movs, 2027);
  assert.equal(s.length, 2);
  // 2026: derecho 15 + arrastre 5 + ajuste 1 - 13 = 8
  assert.deepEqual(pickS(s[0]), { anio: 2026, derecho: 15, arrastre: 5, ajustes: 1, tomado: 13, saldo: 8 });
  // 2027: derecho 15 + arrastre 8 - 15 = 8
  assert.deepEqual(pickS(s[1]), { anio: 2027, derecho: 15, arrastre: 8, ajustes: 0, tomado: 15, saldo: 8 });
});

test('anticipo: saldo negativo se descuenta del año siguiente', () => {
  // Leiva: anticipo 2026 de 14 días importado como -10 hábiles
  const emp = { ingreso: '1995-07-01', inicio: { anio: 2026, arrastre: -10 } };
  const s = C.saldos(emp, {}, 2026);
  assert.equal(s[0].saldo, 15); // 25 - 10
});

test('empleado sin inicio explícito arranca el año de ingreso con arrastre 0', () => {
  const emp = { ingreso: '2026-09-03' };
  const s = C.saldos(emp, {}, 2027);
  assert.equal(s[0].anio, 2026);
  assert.equal(s[0].derecho, 4);
  assert.equal(s[1].arrastre, 4);
  assert.equal(s[1].derecho, 10);
});

test('empleado dado de baja no genera períodos posteriores a la baja', () => {
  const emp = { ingreso: '2010-01-01', inicio: { anio: 2025, arrastre: 0 }, baja: '2026-03-31' };
  const s = C.saldos(emp, {}, 2028);
  assert.deepEqual(s.map((x) => x.anio), [2025, 2026]);
});

test('días en letras para la nota', () => {
  assert.equal(C.enLetras(1), 'UNO');
  assert.equal(C.enLetras(7), 'SIETE');
  assert.equal(C.enLetras(14), 'CATORCE');
  assert.equal(C.enLetras(21), 'VEINTIUNO');
  assert.equal(C.enLetras(28), 'VEINTIOCHO');
  assert.equal(C.enLetras(35), 'TREINTA Y CINCO');
  assert.equal(C.enLetras(40), 'CUARENTA');
});

test('retoma tareas: siguiente día hábil después del último día', () => {
  assert.equal(C.retoma('2026-01-25', sinFeriados), '2026-01-26'); // dom -> lun
  assert.equal(C.retoma('2026-03-06', sinFeriados), '2026-03-09'); // vie -> lun
  assert.equal(C.retoma('2026-03-20', new Set(['2026-03-23', '2026-03-24'])), '2026-03-25');
});

test('semanas (lunes) entre dos fechas para la grilla', () => {
  const w = C.semanas('2026-12-02', '2026-12-31');
  assert.deepEqual(w, ['2026-11-30', '2026-12-07', '2026-12-14', '2026-12-21', '2026-12-28']);
});

test('fechas inválidas', () => {
  assert.equal(C.contarRango('2026-01-10', '2026-01-05', sinFeriados), null);
  assert.equal(C.contarRango('', '2026-01-05', sinFeriados), null);
});

function pick(d) { return { tipo: d.tipo, corridos: d.corridos, habiles: d.habiles }; }
function pickR(r) { return { corridos: r.corridos, habiles: r.habiles }; }
function pickS(s) { return { anio: s.anio, derecho: s.derecho, arrastre: s.arrastre, ajustes: s.ajustes, tomado: s.tomado, saldo: s.saldo }; }
