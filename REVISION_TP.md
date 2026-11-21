# Revisión del TP de Bases de Datos (Grupo 5)

Listado completo de puntos a revisar y corregir en el esquema SQL, transacciones, restricciones de integridad, aplicación Python, datos de prueba y documentación del informe.

---

## 1. Requerimientos del enunciado faltantes o incompletos

- [ ] **Falta el Stored Procedure de asignación mensual de guardias** (enunciado, pág. 3):
  - No está implementado el procedimiento que emite un *"listado con la asignación posible del personal para cubrir cada guardia del mes"* respetando vacaciones, `guardias_max`, `dispuesto`, 3 turnos diarios por especialidad, equidad y no asignar guardias en días consecutivos.

- [ ] **Falta la restricción de "un médico no puede estar de guardia dos días seguidos"** (ni dos turnos distintos el mismo día):
  - [`trg_evitar_guardia_superpuesta`](create-table.sql#L565-L620) y [`trg_validar_cambio_guardia`](create-table.sql#L624-L680) solo comparan `TRUNC(g.fecha) = TRUNC(v_fecha) AND UPPER(g.turno) = v_turno`.
  - Actualmente permiten asignar al mismo médico en turno `MAÑANA` y `TARDE` del mismo día, o en días consecutivos (`ABS(TRUNC(g.fecha) - TRUNC(v_fecha)) <= 1`).

- [ ] **Auditoría de guardias incompleta y vulnerable**:
  - El enunciado pide auditar altas, bajas y cambios *"sobre los datos que afectan a este proceso"*.
  - Actualmente [`trg_auditoria_guardias`](create-table.sql#L516-L542) y [`trg_auditoria_guardia_update`](create-table.sql#L546-L557) solo auditan `CUBIERTA_POR` y `UPDATE` de `GUARDIA`.
  - **Falta auditar**: cambios en `VACACION`, `TIENE` (especialmente `dispuesto`), `MEDICO` (`guardias_max`, `CUIL`, `fecha_ingreso`), `ESPECIALIDAD` e `INSERT`/`DELETE` directo en `GUARDIA`.
  - En `UPDATE` de `CUBIERTA_POR` no se registra el valor anterior (`:OLD`) ni la tabla afectada.
  - En [`create-users.sql`](create-users.sql#L43) se otorgan permisos `INSERT, UPDATE, DELETE` sobre `HOSPITAL.AUDITORIA_GUARDIAS` a los usuarios `"44444444"` y `"33333333"`. Un usuario auditado podría borrar o alterar sus propios registros de auditoría desde SQL. Deben conservar solo `SELECT` (los triggers ejecutan con permisos del dueño `HOSPITAL`).

- [ ] **Falta el `turno` en el informe de comentarios de internación**:
  - [`listar_comentarios_internacion`](create-table.sql#L480-L505) devuelve fecha, médico, matrícula y contenido, pero no el `turno` de la ronda (el enunciado, pág. 3, indica que de un comentario es necesario saber *"la fecha, el turno, el médico que lo escribió y el texto del comentario"*).

---

## 2. Transacciones y Concurrencia (ACID)

- [x] **Se rompe la Atomicidad al modificar guardias** ([`app.py`](app.py#L3068-L3118)):
  - ~~`guardar_modificacion` encadena varias llamadas a SPs (`sp_actualizar_guardia`, `sp_reemplazar_medico_guardia`, `sp_asignar_medico_guardia`, `sp_desasignar_medico_guardia`), pero cada SP ejecuta su propio `COMMIT;` interno.~~
  - **Resuelto**: se encapsuló toda la modificación en el Stored Procedure transaccional único [`sp_modificar_guardia`](create-table.sql) con bloqueo `FOR UPDATE` sobre `GUARDIA`, un único `COMMIT` final y `ROLLBACK` completo ante cualquier fallo.

- [x] **Mal uso de `PRAGMA AUTONOMOUS_TRANSACTION` en 3 triggers**:
  - [x] [`trg_auditoria_guardia_update`](create-table.sql): **resuelto** — se eliminó `PRAGMA AUTONOMOUS_TRANSACTION` y `COMMIT;` para que la auditoría acompañe atómicamente el `COMMIT`/`ROLLBACK` de la transacción principal.
  - [x] [`trg_limite_guardias`](create-table.sql): **resuelto** — se reescribió como trigger a nivel de sentencia (`AFTER INSERT OR UPDATE ON CUBIERTA_POR`, sin `FOR EACH ROW` ni `PRAGMA AUTONOMOUS_TRANSACTION`), evitando `ORA-04091` y viendo filas sin commitear de la misma transacción.
  - [x] [`trg_evitar_internacion_multiple`](create-table.sql): **resuelto** — se creó el índice único basado en función `uq_paciente_int_activa` (`CASE WHEN fecha_fin IS NULL THEN numero_de_DNI END`) y se reescribió el trigger a nivel de sentencia sin `PRAGMA AUTONOMOUS_TRANSACTION` para validar superposición de rangos de fechas (`-20054`).

- [ ] **Bloqueos (`FOR UPDATE`) incompletos y riesgo de condiciones de carrera / deadlocks**:
  - [`sp_ocupar_cama_posee`](create-table.sql#L361-L458): bloquea la cama destino con `FOR UPDATE` ([L399-L404](create-table.sql#L399-L404)), pero **no bloquea la fila de `INTERNACION`** ([L374-L377](create-table.sql#L374-L377)). Dos traslados simultáneos del mismo paciente pueden dejarlo ocupando dos camas a la vez, o un traslado simultáneo con [`sp_dar_alta_internacion`](create-table.sql#L1123-L1172) puede asignar una cama a un paciente ya dado de alta. Tampoco bloquea cama origen y destino en orden determinista (riesgo de deadlock `ORA-00060` si dos sesiones intercambian camas).
  - [x] Desasignación/modificación de guardias: **resuelto** al consolidar en [`sp_modificar_guardia`](create-table.sql), que bloquea la fila padre en `GUARDIA` con `FOR UPDATE` antes de modificar `CUBIERTA_POR`.
  - [x] [`sp_registrar_internacion`](create-table.sql): **resuelto** el riesgo de doble internación activa concurrente mediante el índice único `uq_paciente_int_activa` (eliminando la transacción autónoma).

---

## 3. Restricciones del modelo no respetadas o con bugs

- [x] **[`trg_limite_guardias`](create-table.sql) filtra por `SYSDATE` en lugar del mes de la guardia**:
  - **Resuelto**: ahora [`trg_limite_guardias`](create-table.sql) (`CUBIERTA_POR`) y [`trg_limite_guardias_fecha`](create-table.sql) (`GUARDIA`) validan a nivel de sentencia el límite mensual por `(médico, año, mes de g.fecha)` real tanto al asignar/reasignar médicos como al mover la fecha de una guardia.

- [x] **[`sp_registrar_internacion`](create-table.sql) falla al registrar internaciones finalizadas/históricas**:
  - **Resuelto**: se agregó el parámetro `p_fecha_hora IN TIMESTAMP DEFAULT NULL` y el campo `Hora Ingreso` en [`app.py`](app.py) para guardar `POSEE.fechaHora` con la fecha y hora ingresadas al crear la internación (manteniendo `SYSTIMESTAMP` en los traslados de cama en [`sp_ocupar_cama_posee`](create-table.sql)), y [`trg_posee_fecha`](create-table.sql) ahora compara la fecha truncada con `TRUNC(...)`.

- [ ] **Inconsistencias en `CAMA.estado` respecto a `INTERNACION` y `POSEE`**:
  - No existe trigger sobre `POSEE` ni sobre `CAMA`: un `INSERT` directo en `POSEE` permite asignar la misma cama a múltiples internaciones activas al mismo tiempo y no actualiza `CAMA.estado`.
  - [`sp_crear_cama`](create-table.sql#L998-L1016) y el formulario de `app.py` permiten crear una cama directamente como `'OCUPADA'` sin ninguna internación asociada.
  - El modelo indica que una cama está `'Ocupada'` si `fecha_fin IS NULL` **o `fecha_fin > fecha actual`**. Sin embargo, [`sp_registrar_internacion`](create-table.sql#L1096-L1112) y [`trg_liberar_cama_fin_int`](create-table.sql#L322-L346) solo evalúan `IS NULL` / `IS NOT NULL`: si se registra una internación con `fecha_fin` futura, deja la cama `'LIBRE'` y no valida si estaba ocupada.
  - En [`sp_dar_alta_internacion`](create-table.sql#L1146-L1165):
    - Asigna `fecha_fin = GREATEST(TRUNC(SYSDATE), v_fecha_inicio)`. Si el alta es el mismo día del ingreso, queda `fecha_fin = fecha_inicio` (el PDF pide `>` estricto, mientras `chk_internacion_fechas` usa `>=`) y con hora `00:00:00`, **menor** que `POSEE.fechaHora` registrado ese mismo día.
    - Actualiza `CAMA` a `'LIBRE'` dos veces (primero por `trg_liberar_cama_fin_int` y luego explícitamente en el SP).

- [x] **Solapamiento mal calculado en vacaciones vs. internaciones y chequeo faltante vs. guardias**:
  - **Resuelto**: se eliminó la restricción de vacaciones sobre `INTERNACION` (`trg_medico_internacion_vacaciones` y validación en `sp_registrar_internacion`) y se reemplazó `trg_vacacion_medico_internacion` por [`trg_vacacion_medico_guardia`](create-table.sql), validando bidireccionalmente entre `VACACION` y `GUARDIA`/`CUBIERTA_POR`.

- [ ] **Restricciones de dominio, `NOT NULL`, FKs y triggers con huecos en [`create-table.sql`](create-table.sql)**:
  - [x] **`TIENE.dispuesto`**: **resuelto** — se agregó `chk_tiene_dispuesto CHECK (dispuesto IN ('Si', 'No'))` y se unificó la validación a `!= 'SI'`.
  - [x] **`CUBIERTA_POR`**: **resuelto** — se unificaron las dos FKs en la FK compuesta `fk_cubierta_tiene` hacia `TIENE(numero_de_matricula, id_especialidad)`.
  - [x] **`PERSONA.numero_de_DNI` y `MEDICO.CUIL`**: **resuelto** — se validan con `REGEXP_LIKE` numérico (`chk_persona_dni_num` de 8 dígitos y `chk_medico_cuil_num` de 11 dígitos) y los DNIs de 7 dígitos se rellenan automáticamente con `'0'` adelante mediante triggers `trg_normalizar_dni_*` y en los SPs.
  - [x] **Faltan `NOT NULL` en columnas con `CHECK`**: **resuelto** — agregados `NOT NULL` en `PACIENTE.sexo`, `MEDICO.guardias_max`, `MEDICO.fecha_ingreso`, `VACACION.fecha_inicio_vac`, `RONDA.turno`, `RONDA.dia_semana`, `GUARDIA.turno`, `HABITACION.orientacion` y `CAMA.estado`.
  - **`CAMA.nro_cama` y `POSEE.nro_cama`** son `NUMBER(1)` ([L108](create-table.sql#L108), [L142](create-table.sql#L142)): solo admiten camas del 1 al 9.
  - [x] **Trigger duplicado en `INTERNACION`**: **resuelto** — eliminado `trg_validar_fecha_inicio` (`-20009`), manteniendo `trg_validar_fecha_inicio_int` (`-20011`).
  - [x] **[`trg_evitar_internacion_multiple`](create-table.sql)**: **resuelto** — permite cargar internaciones históricas finalizadas (`fecha_fin IS NOT NULL`) incluso con una internación activa vigente, bloqueando únicamente dos internaciones activas simultáneas (`uq_paciente_int_activa`) o rangos de fechas superpuestos (`-20054`).
  - **[`sp_crear_habitacion_con_rondas`](create-table.sql#L974-L977)**: hace `SELECT id_ronda INTO v_id_ronda FROM RONDA WHERE dia_semana = ... AND turno = ...`. Si hay más de una ronda por día y turno (hipótesis explícita del grupo), falla con `ORA-01422`.
  - **Participaciones obligatorias del MLR no garantizadas**: `SECTOR` sin habitaciones (`sp_crear_sector`), `HABITACION` sin camas (`sp_crear_habitacion_con_rondas`), `MEDICO` sin especialidad (`sp_registrar_medico`), `PERSONA` sin rol ni registro en `PACIENTE`/`MEDICO` (y en `sp_registrar_paciente`, si ya existía como médico con `rol = NULL`, nunca actualiza `rol = 'PACIENTE'`). *(En recorridos, la validación de vacaciones quedó resuelta con [`trg_recorrido_medico_vacaciones`](create-table.sql) y [`trg_vacacion_medico_recorrido`](create-table.sql), y la coincidencia entre `RECORRIDO.fecha` y `RONDA.dia_semana` quedó validada de forma provisoria con [`trg_recorrido_dia_ronda`](create-table.sql) y [`trg_ronda_dia_recorridos`](create-table.sql)).*
  - **`GUARDIA`** no tiene `UNIQUE (fecha, turno)`: [`sp_crear_y_asignar_guardia`](create-table.sql#L1279-L1281) crea una fila nueva en `GUARDIA` cada vez, aunque ya exista una guardia para esa fecha y turno.

---

## 4. Errores en `app.py`

- [ ] **Crash en `accion_insertar_medico` (`NameError`)** ([`app.py`](app.py#L1781-L1782)):
  - Usa la variable `texto_foto` que nunca fue definida. Falla cada vez que se registra un médico (después de que `sp_registrar_medico` ya hizo `COMMIT`).

- [x] **Crash en `reemplazar_medico_lista` (`AttributeError`)** ([`app.py`](app.py#L3036)):
  - **Resuelto**: se reemplazó `self.log_evento(...)` por `self.log_info(...)`.

- [x] **Colisión de código de error `-20048`**:
  - **Resuelto**: se eliminó `sp_asignar_medico_guardia` (reemplazado por [`sp_modificar_guardia`](create-table.sql)), por lo que `-20048` queda reservado únicamente para vacaciones en internación.

- [ ] **Falsos positivos en [`traducir_error_oracle`](app.py#L148)**:
  - La condición `"FECHA_INICIO" in mensaje_mayus` provoca que cualquier error que mencione esa subcadena (por ejemplo `NN_INTERNACION_FECHA_INICIO` o `fecha_inicio_vac`) se traduzca erróneamente como *"Fecha de inicio en el futuro"*.

- [ ] **Rutas relativas en [`ejecutar_archivo_sql`](app.py#L559-L565)**:
  - Usa `"create-table.sql"`, `"HOSPITAL.sql"` y `"create-users.sql"` como rutas relativas ([L631](app.py#L631), [L634](app.py#L634), [L649](app.py#L649), [L657](app.py#L657), [L709](app.py#L709), [L715](app.py#L715), [L720](app.py#L720)). Si la app se ejecuta desde otro directorio de trabajo, no encuentra los archivos. Conviene resolverlos con `os.path.join(DIRECTORIO_APP, archivo)`.

- [x] **Fuga de conexión en `guardar_modificacion`** ([`app.py`](app.py#L3082-L3099)):
  - **Resuelto**: ahora `fecha_dt` se valida antes de llamar a `self.obtener_conexion_guardias()`.

- [x] **Método duplicado `_obtener_opciones_medicos`**:
  - **Resuelto**: se eliminó la definición duplicada en [`HospitalApp`](app.py#L2602) dejando una única implementación.

- [ ] **Mojibake / errores de codificación UTF-8 en [`create-table.sql`](create-table.sql#L879-L1575)**:
  - Hay 28 líneas con caracteres mal codificados (ej. `MatrÃ­cula`, `internaciÃ³n`, `habitaciÃ³n`) entre las líneas 879 y 1575.

---

## 5. Problemas en los datos de prueba (`HOSPITAL.sql`)

- [ ] **Incompatibilidad de fechas** ([`HOSPITAL.sql`](HOSPITAL.sql#L507), [L529](HOSPITAL.sql#L529)):
  - `INTERNACION` usa fecha fija `2026-11-15` y `POSEE` usa `systimestamp - interval '4' day`. Si se ejecuta antes del `19/11/2026` (por ejemplo, en octubre), falla por `trg_validar_fecha_inicio` o `trg_posee_fecha`. Conviene usar fechas relativas a `SYSDATE` (ej. `TRUNC(SYSDATE) - 5`) o fechas fijas coherentes en el pasado.

- [ ] **Médicos sin especialidad en `TIENE`** ([`HOSPITAL.sql`](HOSPITAL.sql#L579-L611)):
  - `M103` y `M104` no tienen filas en `TIENE`, violando la restricción `MEDICO.numero_de_matricula debe estar en TIENE.numero_de_matricula`.

- [ ] **Rondas sin habitaciones en `COMPUESTA_POR`** ([`HOSPITAL.sql`](HOSPITAL.sql#L175-L449)):
  - 14 de las 28 rondas creadas no tienen ninguna habitación asociada, violando `RONDA.id_ronda debe estar en COMPUESTA_POR.id_ronda`.

- [x] **Inconsistencia día/ronda en `RECORRIDO`** ([`HOSPITAL.sql`](HOSPITAL.sql#L526-L542)):
  - **Resuelto**: ambos recorridos de prueba usan la fecha lunes `16/11/2026`, coherente con las rondas `1` y `2` (`LUNES`, turnos 1 y 2).

- [ ] **Sin datos iniciales de `GUARDIA` y `CUBIERTA_POR`**:
  - No hay guardias precargadas para evaluar de inmediato las consultas de guardias, auditoría y asignación mensual.

---

## 6. Erratas menores en el informe PDF del grupo

- [ ] **Pág. 3**: dice `Dom(Medico.sexo)` en lugar de `Dom(Paciente.sexo)`.
- [ ] **Pág. 3**: están repetidas dos veces la restricción *"En una ronda no puede haber habitaciones repetidas"* y la de `Vacacion.fecha_fin_vac` mayor a `Vacacion.fecha_inicio_vac`.
- [ ] **Pág. 4**: en `COMENTARIO` dice `PK=CK={id_cometario}` (falta la `n`).
- [ ] **Pág. 5**: dice `RECORRIDO.id_ronda puede no estar en RONDA.id_ronda` (debería decir **debe** estar).
- [ ] **Pág. 7**: en el esquema de `PERSONA` dice `PERSONA (numero_de_DNI, nombre, apellido, es)` (`es` en lugar de `rol`).
