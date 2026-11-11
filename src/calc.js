/*
 * Lógica de vacaciones (LCT 20.744, arts. 150, 151, 153 y 154).
 *
 * Unidad interna: DÍAS HÁBILES (semana de lunes a viernes).
 *   14 corridos = 10 hábiles, 21 = 15, 28 = 20, 35 = 25.
 * Cada pedido descuenta los hábiles que contiene; los fines de semana
 * se "cobran" solos porque cada 5 hábiles equivalen a 7 corridos.
 *
 * Funciona como script del navegador (window.Calc) y como módulo de Node.
 */
(function (root) {
  'use strict';

  const DIA = 86400000;

  // ---- Fechas (siempre en UTC para evitar problemas de horario) ----
  function parse(iso) {
    if (!iso || typeof iso !== 'string') return null;
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
    if (!m) return null;
    const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
    return isNaN(d) ? null : d;
  }
  function iso(d) {
    return d.toISOString().slice(0, 10);
  }
  function addDays(d, n) {
    return new Date(d.getTime() + n * DIA);
  }
  function addYears(d, n) {
    return new Date(Date.UTC(d.getUTCFullYear() + n, d.getUTCMonth(), d.getUTCDate()));
  }
  function esFinde(d) {
    const w = d.getUTCDay();
    return w === 0 || w === 6;
  }
  function hoyISO() {
    const n = new Date();
    return iso(new Date(Date.UTC(n.getFullYear(), n.getMonth(), n.getDate())));
  }

  /** Días lunes a viernes entre dos fechas inclusive (como NETWORKDAYS de Excel, sin feriados). */
  function lunesAViernes(desde, hasta) {
    let n = 0;
    for (let d = desde; d <= hasta; d = addDays(d, 1)) if (!esFinde(d)) n++;
    return n;
  }

  /**
   * Cuenta un pedido de vacaciones.
   * @param {string} desdeISO
   * @param {string} hastaISO
   * @param {Set<string>} feriados  fechas ISO
   * @param {boolean} feriadosDescuentan  si true, un feriado hábil dentro del rango descuenta
   * @returns {{corridos:number, habiles:number, finde:number, feriados:number}|null}
   */
  function contarRango(desdeISO, hastaISO, feriados, feriadosDescuentan) {
    const a = parse(desdeISO), b = parse(hastaISO);
    if (!a || !b || b < a) return null;
    const fer = feriados || new Set();
    let corridos = 0, habiles = 0, finde = 0, nFer = 0;
    for (let d = a; d <= b; d = addDays(d, 1)) {
      corridos++;
      if (esFinde(d)) { finde++; continue; }
      if (fer.has(iso(d))) {
        nFer++;
        if (!feriadosDescuentan) continue;
      }
      habiles++;
    }
    return { corridos, habiles, finde, feriados: nFer };
  }

  /**
   * Días que corresponden por el período (año calendario) `anio`.
   * - Antigüedad al 31/12 del año (art. 150).
   * - Si ingresó ese año y no trabajó la mitad de los hábiles del año:
   *   1 día cada 20 hábiles trabajados (art. 153), contado como hábil
   *   (igual que la planilla Excel actual).
   */
  function derecho(ingresoISO, anio) {
    const ing = parse(ingresoISO);
    if (!ing) return { tipo: 'sin-ingreso', corridos: 0, habiles: 0, antig: null };
    const fin = new Date(Date.UTC(anio, 11, 31));
    if (ing > fin) return { tipo: 'sin-derecho', corridos: 0, habiles: 0, antig: 0 };
    const ini = new Date(Date.UTC(anio, 0, 1));
    if (ing >= ini) {
      const trabajados = lunesAViernes(ing, fin);
      const delAnio = lunesAViernes(ini, fin);
      if (trabajados < delAnio / 2) {
        const h = Math.round(trabajados / 20);
        return { tipo: 'proporcional', corridos: habACorr(h), habiles: h, antig: 0, trabajados };
      }
    }
    let corridos;
    if (fin > addYears(ing, 20)) corridos = 35;
    else if (fin > addYears(ing, 10)) corridos = 28;
    else if (fin > addYears(ing, 5)) corridos = 21;
    else corridos = 14;
    return { tipo: 'escala', corridos, habiles: (corridos / 7) * 5, antig: antiguedad(ingresoISO, anio) };
  }

  /** Años completos de antigüedad al 31/12 del año (para mostrar). */
  function antiguedad(ingresoISO, anio) {
    const ing = parse(ingresoISO);
    if (!ing) return null;
    let n = anio - ing.getUTCFullYear();
    // al 31/12 ya se cumplió el aniversario del año, salvo que sea posterior (no ocurre)
    return Math.max(0, n);
  }

  /** Hábiles a corridos: cada 5 hábiles se suma un fin de semana (2 días). */
  function habACorr(h) {
    const s = h < 0 ? -1 : 1;
    const a = Math.abs(h);
    return s * (a + 2 * Math.floor(a / 5));
  }

  /**
   * Saldo expresado en corridos, con la regla del fin de semana acumulado:
   * los corridos ya descontados son habACorr(usados).
   */
  function saldoCorridos(totalHab, usadosHab) {
    if (usadosHab <= totalHab) return habACorr(totalHab) - habACorr(usadosHab);
    return -habACorr(usadosHab - totalHab);
  }

  /**
   * Saldos por período, encadenados: lo que sobra (o falta) pasa al año siguiente.
   * @param {{ingreso:string, inicio?:{anio:number, arrastre:number}, baja?:string}} emp
   * @param {Object<number, Array<{tipo:string, habiles?:number, dias?:number}>>} movsPorAnio
   * @param {number} hastaAnio
   */
  function saldos(emp, movsPorAnio, hastaAnio) {
    const ing = parse(emp.ingreso);
    let desde = emp.inicio && emp.inicio.anio ? emp.inicio.anio : ing ? ing.getUTCFullYear() : hastaAnio;
    const baja = parse(emp.baja);
    const hasta = baja ? Math.min(hastaAnio, baja.getUTCFullYear()) : hastaAnio;
    let arrastre = emp.inicio && emp.inicio.anio ? Number(emp.inicio.arrastre) || 0 : 0;
    const out = [];
    for (let anio = desde; anio <= hasta; anio++) {
      const d = derecho(emp.ingreso, anio);
      let tomado = 0, ajustes = 0, planificado = 0;
      for (const m of (movsPorAnio && movsPorAnio[anio]) || []) {
        if (m.tipo === 'ajuste') ajustes += Number(m.dias) || 0;
        else {
          tomado += Number(m.habiles) || 0;
          if (m.estado === 'planificado') planificado += Number(m.habiles) || 0;
        }
      }
      const total = d.habiles + arrastre + ajustes;
      const saldo = total - tomado;
      out.push({
        anio, derecho: d.habiles, derechoCorridos: d.corridos, tipo: d.tipo, antig: d.antig,
        arrastre, ajustes, tomado, planificado, total, saldo,
        saldoCorridos: saldoCorridos(total, tomado),
      });
      arrastre = saldo;
    }
    return out;
  }

  // ---- Números en letras (para la nota) ----
  const U = ['CERO', 'UNO', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE', 'DIEZ',
    'ONCE', 'DOCE', 'TRECE', 'CATORCE', 'QUINCE', 'DIECISÉIS', 'DIECISIETE', 'DIECIOCHO', 'DIECINUEVE', 'VEINTE',
    'VEINTIUNO', 'VEINTIDÓS', 'VEINTITRÉS', 'VEINTICUATRO', 'VEINTICINCO', 'VEINTISÉIS', 'VEINTISIETE',
    'VEINTIOCHO', 'VEINTINUEVE'];
  const D = { 3: 'TREINTA', 4: 'CUARENTA', 5: 'CINCUENTA', 6: 'SESENTA', 7: 'SETENTA', 8: 'OCHENTA', 9: 'NOVENTA' };
  function enLetras(n) {
    n = Math.trunc(n);
    if (n < 0 || n > 99) return String(n);
    if (n < 30) return U[n];
    const dec = D[Math.floor(n / 10)], u = n % 10;
    return u ? dec + ' Y ' + U[u] : dec;
  }

  /** Día en que retoma tareas: el siguiente lunes a viernes no feriado. */
  function retoma(hastaISO, feriados) {
    let d = addDays(parse(hastaISO), 1);
    const fer = feriados || new Set();
    while (esFinde(d) || fer.has(iso(d))) d = addDays(d, 1);
    return iso(d);
  }

  /** Lunes de cada semana que toca el rango. */
  function semanas(desdeISO, hastaISO) {
    let d = parse(desdeISO);
    const b = parse(hastaISO);
    if (!d || !b) return [];
    d = addDays(d, -((d.getUTCDay() + 6) % 7));
    const out = [];
    for (; d <= b; d = addDays(d, 7)) out.push(iso(d));
    return out;
  }

  /** Días (corridos) del rango [desde, hasta] que caen en la semana que empieza `lunesISO`. */
  function diasEnSemana(desdeISO, hastaISO, lunesISO) {
    const a = parse(desdeISO), b = parse(hastaISO), l = parse(lunesISO);
    if (!a || !b || !l) return 0;
    const s = a > l ? a : l;
    const e0 = addDays(l, 6);
    const e = b < e0 ? b : e0;
    return e < s ? 0 : Math.round((e - s) / DIA) + 1;
  }

  const NOMBRE_DIA = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
  function diaSemana(isoStr) {
    const d = parse(isoStr);
    return d ? NOMBRE_DIA[d.getUTCDay()] : '';
  }
  function ddmmaaaa(isoStr) {
    const d = parse(isoStr);
    if (!d) return '';
    return iso(d).split('-').reverse().join('/');
  }

  const Calc = {
    parse, iso, addDays, esFinde, hoyISO, lunesAViernes, contarRango, derecho, antiguedad,
    habACorr, saldoCorridos, saldos, enLetras, retoma, semanas, diasEnSemana, diaSemana, ddmmaaaa,
  };
  root.Calc = Calc;
  if (typeof module !== 'undefined' && module.exports) module.exports = Calc;
})(typeof globalThis !== 'undefined' ? globalThis : this);
