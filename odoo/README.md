# Vacaciones en Odoo (stage)

Scripts para armar en `genoud-stage.odoo.com` lo mismo que hace la app: Empleados + Ausencias de Odoo,
contando en días hábiles (14/21/28/35 corridos = 10/15/20/25 hábiles), sin descontar feriados.

Usan la API JSON-2 de Odoo 19 (`o.py`). La clave API la inyecta el proxy del entorno de Claude; no está en el código.
Los IDs de lo creado quedan en `stage_ids.json`. El mapa empleado → ID queda en `stage_empleados.local.json`, que **no se sube** (tiene nombres de empleados); `paso2_empleados.py` lo reconstruye.

| Paso | Script | Permiso necesario | Estado |
|---|---|---|---|
| 1 | `paso1_config.py seed.json` — campo `x_fecha_ingreso`, etiquetas, 35 feriados 2026-2027 **por compañía** (Genoud y Arazá) | Administrador | Hecho |
| 2 | `paso2_empleados.py seed.json` — 71 empleados del Excel | Empleados / Administrador | Hecho |
| 3 | `paso3_tipo_ausencia.py` — tipo "Vacaciones" (días, saldo negativo hasta 35, feriados no descuentan, aprueba RRHH) | Ausencias / Administrador | Hecho (tipo 74) |
| 4 | `paso4_acciones_y_reporte.py` — fecha de ingreso en la ficha, acción "Generar vacaciones del período", campos `x_dias_corridos` y `x_retoma`, nota PDF (formato de página propio, 2 copias por A4) | Administrador | Hecho |
| 5 | Acción sobre los 71 + `paso5_saldo_inicial.py seed.json` (pendientes suman, anticipos restan) | Ausencias / Administrador | Hecho: 61 asignaciones, 21 saldos; 61/61 saldos iguales a la app |

`deshacer_stage.py` borra todo lo anterior (no correr sin confirmarlo).

## Cómo se usa en Odoo

- **Fecha de ingreso**: ficha del empleado, pestaña Trabajo, campo "Fecha de ingreso (antigüedad)".
- **Cada octubre**: Empleados → seleccionar todos → Acciones → *Generar vacaciones del período*. Crea "Vacaciones AAAA" a cada uno según su antigüedad (no duplica si ya existe).
- **Pedido de días**: Ausencias → Nueva → tipo Vacaciones. Odoo cuenta los hábiles y saltea feriados. "Para aprobar" = planificado; "Aprobado" = confirmado.
- **Nota**: desde la ausencia, Imprimir → *Notificación de vacaciones*.

## Pruebas hechas en stage (11/11/2026)

- Saldos: los 61 empleados con fecha de ingreso tienen en Odoo el mismo saldo que en la app.
- Assad (10 háb): 14–16/12 descuenta 3 → quedan 7; 21–23/12 descuenta 3 → quedan 4; 24–28/12 descuenta 2 (Navidad no cuenta), 5 corridos, retoma martes 29/12.
  Quedan cargadas como ejemplo (IDs 1 aprobada, 2 y 3 para aprobar).
- Leiva (15 háb): pedido de 25 háb → saldo −10 (anticipo permitido). Borrado después.
- Nota PDF: `ver_nota_pdf.py ID salida.pdf`.

**Ojo:** para limpiar acciones temporales borrar siempre por ID, nunca buscando por nombre. Buscar "TEMP " borró la acción 1081, que ya existía en stage.

## Revisión del 11/11/2026: trampas encontradas

- **Los feriados siempre quedan con una compañía.** Aunque se mande `company_id: False`, Odoo les pone la compañía activa, y no admite dos
  feriados superpuestos *de la misma compañía*. Hay que crearlos una vez por compañía, cada vez con esa compañía como activa
  (`allowed_company_ids: [cia]`). Creados solo con Genoud, a los empleados de Arazá no se les salteaban.
- **Odoo renombra la asignación al editar los días** ("Vacaciones 2026" → "Vacaciones (14.0 day(s))"). Al escribir `number_of_days`
  hay que reescribir `name`. La acción *Generar vacaciones del período* igual no duplica: también busca por fecha de inicio.
- **Una asignación o ausencia aprobada no se puede borrar**: primero `action_refuse`, después `unlink`.
- Verificado después de las correcciones: 61/61 saldos iguales a la app; feriado salteado para un empleado de Arazá
  (24 al 28/12 descuenta 2); volver a correr los pasos 1, 2, 5 y la acción no crea nada nuevo.
