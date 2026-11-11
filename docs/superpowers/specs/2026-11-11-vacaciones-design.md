# App de vacaciones GFI — diseño

Fecha: 2026-11-11 · Estado: aprobado por el usuario ("hacelo y vamos probando").

## Objetivo

Reemplazar la planilla `GFI-VACACIONES_2025.xlsx` por una página web privada en claude.ai
que lleve las vacaciones de ~70–100 empleados (GFI y AZ; convenios madera CCT 335/75 y
comercio CCT 130/75) sin regalar días cuando se otorgan días sueltos.

## Marco legal (noviembre 2026)

- LCT art. 150: 14 / 21 / 28 / 35 días **corridos** según antigüedad al 31/12 del año
  (hasta 5 años, más de 5, más de 10, más de 20).
- Art. 151 / 153: si no trabajó la mitad de los hábiles del año, 1 día cada 20 trabajados.
- Art. 154 (Ley 27.802, BO 06/03/2026): fraccionamiento por acuerdo en tramos de al menos
  7 días; aviso con 30 días de anticipación.
- CCT 130/75 (comercio) y CCT 335/75 (madera, art. 20) remiten a la escala de la LCT.
- La empresa otorga tramos más cortos como **beneficio**: la app los permite sin advertir.

## Regla de cálculo

- Unidad interna: **días hábiles** (lunes a viernes). 5 hábiles = 7 corridos, así
  14 → 10, 21 → 15, 28 → 20, 35 → 25 (igual que las hojas ADRIAN/ANDRÉS: 25 háb + 10 finde).
- Cada pedido descuenta los hábiles que contiene; los fines de semana quedan cubiertos por la
  equivalencia. Ejemplo: 14 corridos, pide 3 + 3 → quedan 4 hábiles = 6 corridos.
- Saldo en corridos = corr(total) − corr(usados), con corr(h) = h + 2·⌊h/5⌋.
- Feriados dentro del pedido: **no descuentan** (configurable).
- Ingresantes con menos de medio año: round(hábiles trabajados / 20), contados como hábiles
  (igual que el Excel).
- El saldo de cada período pasa solo al siguiente (positivo = pendiente, negativo = anticipo).
- Ajustes manuales en hábiles con motivo.

## Datos (db del artifact)

| Ruta | Contenido |
|---|---|
| `config/general` | período activo, feriados `[{fecha, nombre}]`, `feriadosDescuentan`, localidad, empresas `{sigla: razón social}`, texto y subtítulo de la nota |
| `empleados/{id}` | nombre, ingreso, empresa, sector, convenio, activo, baja, `inicio {anio, arrastre, origen}`, revisar |
| `periodos/{anio}/movs/{id}` | `tipo: 'vac'` → empId, desde, hasta, habiles, corridos, estado (confirmado/planificado), fechaNota, obs; `tipo: 'ajuste'` → empId, dias, obs |

Los hábiles de cada pedido se guardan al cargarlo (lo que se le informó al empleado), así un
cambio posterior en los feriados no altera pedidos viejos.

## Pantallas

1. Empleados: resumen, filtros, saldo por período en hábiles y corridos.
2. Ficha: saldo, períodos encadenados, carga y edición de pedidos con vista previa
   (hábiles, corridos, feriados, retoma, saldo después, superposiciones), ajustes, datos.
3. Planificación: grilla semanal (dic–mar por defecto), carga masiva para el cierre de planta.
4. Configuración: período activo, feriados, nota, empresas.
5. Nota de notificación en PDF (dos copias por hoja A4) y exportación a Excel.

## Importación inicial

`tools/importar_excel.py` lee la hoja del año (2026) y `VAC ADMIN 25`:
arrastre = round(pendiente × 5/7) − round(anticipo × 5/7), marcado "revisar".
El personal de VAC ADMIN sin fecha de ingreso queda marcado "completar ingreso".

## Pruebas

- `node --test tests/*.test.mjs`: reglas de cálculo con casos del Excel.
- `tests/ui-smoke.mjs`: Playwright con una simulación de `window.claude`.
