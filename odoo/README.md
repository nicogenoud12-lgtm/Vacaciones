# Vacaciones en Odoo (stage)

Scripts para armar en `genoud-stage.odoo.com` lo mismo que hace la app: Empleados + Ausencias de Odoo,
contando en días hábiles (14/21/28/35 corridos = 10/15/20/25 hábiles), sin descontar feriados.

Usan la API JSON-2 de Odoo 19 (`o.py`). La clave API la inyecta el proxy del entorno de Claude; no está en el código.
Todos los IDs creados quedan en `stage_ids.json`.

| Paso | Script | Permiso necesario | Estado |
|---|---|---|---|
| 1 | `paso1_config.py seed.json` — campo `x_fecha_ingreso`, etiquetas, 35 feriados 2026-2027 | Administrador | Hecho |
| 2 | `paso2_empleados.py seed.json` — 71 empleados del Excel | Empleados / Administrador | Hecho |
| 3 | `paso3_tipo_ausencia.py` — tipo "Vacaciones" (días, saldo negativo hasta 35, feriados no descuentan, aprueba RRHH) | **Ausencias / Administrador** | Pendiente |
| 4 | `paso4_acciones_y_reporte.py` — fecha de ingreso en la ficha, acción "Generar vacaciones del período", campos `x_dias_corridos` y `x_retoma`, nota PDF | Administrador | Hecho |
| 5 | Generar asignaciones 2026 + saldo inicial del Excel + pruebas | **Ausencias / Administrador** | Pendiente |

`deshacer_stage.py` borra todo lo anterior (no correr sin confirmarlo).

## Cómo se usa en Odoo

- **Fecha de ingreso**: ficha del empleado, campo "Fecha de ingreso (antigüedad)".
- **Cada octubre**: Empleados → seleccionar todos → Acciones → *Generar vacaciones del período*. Crea "Vacaciones AAAA" a cada uno según su antigüedad (no duplica si ya existe).
- **Pedido de días**: Ausencias → Nueva → tipo Vacaciones. Odoo cuenta los hábiles y saltea feriados. "Para aprobar" = planificado; "Aprobado" = confirmado.
- **Nota**: desde la ausencia, Imprimir → *Notificación de vacaciones*.
