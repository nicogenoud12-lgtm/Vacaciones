# Vacaciones en Odoo (stage y producción)

Scripts para armar en `genoud-stage.odoo.com` lo mismo que hace la app: Empleados + Ausencias de Odoo,
contando en días hábiles (14/21/28/35 corridos = 10/15/20/25 hábiles), sin descontar feriados.

Usan la API JSON-2 de Odoo 19 (`o.py`). Entorno con la variable `ODOO_ENV` (`stage` por defecto, `prod` para producción); cada script imprime `>>> ESTAS EN:` al arrancar. La clave API la inyecta el proxy del entorno de Claude; no está en el código.
Los IDs de lo creado quedan en `stage_ids.json`. El mapa empleado → ID queda en `stage_empleados.local.json`, que **no se sube** (tiene nombres de empleados); `paso2_empleados.py` lo reconstruye.

| Paso | Script | Permiso necesario | Estado |
|---|---|---|---|
| 1 | `paso1_config.py seed.json` — campo `x_fecha_ingreso`, etiquetas, 35 feriados 2026-2027 **por compañía** (Genoud y Arazá) | Administrador | Hecho |
| 2 | `paso2_empleados.py seed.json` — 71 empleados del Excel | Empleados / Administrador | Hecho |
| 3 | `paso3_tipo_ausencia.py` — tipo "Vacaciones" (días, saldo negativo hasta 35, feriados no descuentan, aprueba RRHH) | Ausencias / Administrador | Hecho (tipo 74) |
| 4 | `paso4_acciones_y_reporte.py` — fecha de ingreso en la ficha, acción "Generar vacaciones del período", campos `x_dias_corridos` y `x_retoma`, nota PDF (formato de página propio, 2 copias por A4) | Administrador | Hecho |
| 5 | Acción sobre los 71 + `paso5_saldo_inicial.py seed.json` (pendientes suman, anticipos restan) | Ausencias / Administrador | Hecho: 61 asignaciones, 21 saldos; 61/61 saldos iguales a la app |

| 6 | `paso6_saldo_real.py` — menú **Vacaciones → Reportes → Saldo de vacaciones**: saldo real por empleado en hábiles y corridos, con anticipos en rojo | Administrador | Hecho |
| 7 | `paso7_resumen_empleado.py` — al tocar una fila de *Saldo de vacaciones* se abre el **Resumen de vacaciones**: saldo de hoy, días que le corresponden con su detalle, y cada pedido con su período y lo que le quedó después | Administrador | Hecho |

`deshacer.py` borra todo lo anterior (no correr sin confirmarlo).

## Cómo se usa en Odoo

- **Fecha de ingreso**: ficha del empleado, pestaña Trabajo, campo "Fecha de ingreso (antigüedad)".
- **Cada octubre**: Empleados → seleccionar todos → Acciones → *Generar vacaciones del período*. Crea "Vacaciones AAAA" a cada uno según su antigüedad (no duplica si ya existe).
- **Pedido de días**: Ausencias → Nueva → tipo Vacaciones. Odoo cuenta los hábiles y saltea feriados. "Para aprobar" = planificado; "Aprobado" = confirmado.
- **Nota**: desde la ausencia, Imprimir → *Notificación de vacaciones*.
- **Saldos**: Vacaciones → Reportes → *Saldo de vacaciones*; tocando una persona se abre su resumen. **No usar Reportes → Balance para ver anticipos**: calcula el restante por asignación y nunca baja de 0 (con 4 asignados y 5 tomados muestra Restante 0, Tomado 5).

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

## Producción (12/11/2026)

Desplegado con los mismos scripts (`ODOO_ENV=prod`). IDs en `prod_ids.json`; mapas con nombres en `prod_*.local.json` (no se suben).

- 71 empleados: **13 reutilizan su ficha existente** (los que ya tenían usuario o ficha: Nicolás, Langoni, Adrian, Graciela,
  Mauricio, Maxi, Bernardo, Sebastián, Ángeles, Ariel, Cristian, González Gustavo y Pacheco Santiago — estos dos en Arazá) y 58 nuevas.
- 61 asignaciones "Vacaciones 2026" + 16 "Saldo inicial 2025 (Excel)" + 5 anticipos descontados. Verificado: 61/61 iguales a la app.
- 35 feriados por compañía. Campos, acción, nota PDF (probada), Saldo de vacaciones y resumen por empleado.
- **Tipo de ausencia:** producción ya tenía un "Vacaciones" (ID 74) sin asignaciones y con 2 pedidos; Odoo no deja cambiarlo.
  Se renombró **"Vacaciones (anterior)"** y se creó el **"Vacaciones" nuevo (ID 75)** con `paso3b_migrar_tipo_existente.py`
  (autorizado por el usuario). El pedido de Nicolás (30/11–8/12, aprobado, 5 háb) pasó al tipo nuevo.
  El de **Langoni (19–25/7/2027, por aprobar) sigue en "Vacaciones (anterior)"**: el tipo nuevo exige días asignados y Langoni
  no tiene fecha de ingreso. Cuando se le cargue y se corra la acción, volver a correr `paso3b` lo pasa y archiva el tipo anterior.
  Primer intento (fallido) dejó el pedido de Langoni restaurado con ID 6 (antes 4), mismas fechas y estado.
- `deshacer.py` nunca borra fichas reutilizadas, el tipo preexistente ni pedidos/asignaciones anteriores a `inicio_despliegue`.

### Arazá (12/11/2026, planilla `AZ-VACACIONES_2025.xlsx`, hoja 2026)

- `python3 -I tools/importar_excel.py AZ-VACACIONES_2025.xlsx --anio 2026 --empresa AZ` → 52 personas (se omiten las filas sin
  "VAC 2026": Caliva y Lira). El área de la columna A define el sector (ADMIN = Administración/Comercio; el resto Planta/Madera).
- 19 ya tenían ficha (6 cargadas desde la planilla GFI + 7 fichas propias de Arazá + Freggiaro, asociado a mano); 33 nuevas.
- **Gómez Uriel, Jaén, Lupi y Rueda José Luis** estaban en las dos planillas: se pasaron a Arazá (`cambio_empresa_a_araza`).
- Días verificados contra la planilla: 52/52. Única diferencia con la ley: **Wasskiewich, Fausto Luciano** (ingreso 02/08/2026):
  la planilla le da 14 corridos; por art. 153 serían 5 hábiles → se cargó un ajuste de +5 para igualar la planilla.
- El pedido de Langoni pasó al tipo nuevo y "Vacaciones (anterior)" quedó archivado.
- Confirmado por el usuario: "Martin" (ficha 4, Arazá) es **Bonet, Martín Ariel** → se le cargaron los datos y se borró la ficha
  duplicada 111 que se había creado. "Mauricio" (9, Genoud) es **Santinelli** (ya estaba así; falta su fecha de ingreso).
  **Ariel Lira** (48) sigue trabajando: ingreso 01/10/2003 de la planilla, 25 háb, sin saldo anterior cargado (marcado revisar).
  **Caliva, Vicente Oscar** sigue trabajando: ficha nueva en Arazá, ingreso 01/09/2003, 25 háb, marcado revisar.
- Nombres de las fichas reutilizadas ("Adrian", "Martin"…): se dejan como están, por decisión del usuario.

### Usuarios y empleados

Odoo crea una ficha de empleado **por compañía** para cada usuario (por eso "Adrian" aparece en Genoud y en Arazá). Las vacaciones
se cargan en **una sola**: la de la empresa empleadora. La otra queda vacía y no aparece en *Saldo de vacaciones*; no se borra
porque Odoo la usa cuando ese usuario trabaja con la otra empresa seleccionada.
