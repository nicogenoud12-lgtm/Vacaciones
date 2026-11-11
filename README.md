# Vacaciones GFI

Página web privada (Artifact de claude.ai) para llevar las vacaciones del personal de
Genoud Foresto Industrial y AZ. Reemplaza la planilla `GFI-VACACIONES_*.xlsx`.

## Cómo cuenta los días

- Lo que corresponde sale de la antigüedad al 31/12 (LCT art. 150): 14, 21, 28 o 35 corridos.
- Internamente todo se lleva en **días hábiles**: 5 hábiles = 7 corridos
  (14 → 10, 21 → 15, 28 → 20, 35 → 25).
- Cada pedido descuenta los hábiles que contiene, sean días sueltos o semanas completas.
  Así, aunque alguien pida siempre de lunes a viernes, nunca se lleva más días de los que le tocan.
- Ejemplo: 14 corridos, pide 3 días y después 3 más → le quedan 4 hábiles (= 6 corridos).
- Los feriados que caen dentro de un pedido no descuentan (se puede cambiar en Configuración).
- El saldo de un año pasa solo al siguiente: si sobra, como pendiente; si falta, como anticipo.

Detalle completo en [`docs/superpowers/specs/2026-11-11-vacaciones-design.md`](docs/superpowers/specs/2026-11-11-vacaciones-design.md).

## Estructura

| Archivo | Qué es |
|---|---|
| `src/calc.js` | Reglas de cálculo (sin interfaz). |
| `src/app.html` | Interfaz de la página. |
| `build.mjs` | Junta los dos en `dist/vacaciones.html`, que es lo que se publica. |
| `tools/importar_excel.py` | Lee la planilla Excel y genera los datos iniciales. |
| `tests/` | Pruebas de cálculo y prueba de la interfaz con Playwright. |

## Comandos

```bash
node build.mjs
```

```bash
node --test tests/*.test.mjs
```

```bash
python3 -I tools/importar_excel.py GFI-VACACIONES_2025.xlsx --anio 2026 > seed.json
```

```bash
node tests/ui-smoke.mjs seed.json carpeta-capturas
```
