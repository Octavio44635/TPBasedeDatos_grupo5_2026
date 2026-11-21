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

- [ ] **Se rompe la Atomicidad al modificar guardias** ([`app.py`](app.py#L3115-L3147)):
  - `guardar_modificacion` encadena varias llamadas a SPs (`sp_actualizar_guardia`, `sp_reemplazar_medico_guardia`, `sp_asignar_medico_guardia`, `sp_desasignar_medico_guardia`), pero **cada SP ejecuta su propio `COMMIT;` interno** ([`create-table.sql`](create-table.sql#L1314-L1442)).
  - Si falla un paso intermedio (por ejemplo, médico de vacaciones o límite de guardias superado), el `conn_save.rollback()` de Python **no revierte** los pasos anteriores ya confirmados, dejando la guardia modificada a medias aunque el log diga `"ROLLBACK aplicado"`.
  - **Solución recomendada**: quitar `COMMIT`/`ROLLBACK` de los SPs granulares cuando se componen desde Python (y manejar la transacción con `conn.commit()` / `conn.rollback()` desde la app), o bien encapsular toda la modificación de la guardia en un único SP transaccional.

- [ ] **Mal uso de `PRAGMA AUTONOMOUS_TRANSACTION` en 3 triggers**:
  - [`trg_auditoria_guardia_update`](create-table.sql#L546-L557): corre `AFTER UPDATE FOR EACH ROW` con transacción autónoma y `COMMIT;`, ejecutándose **antes** de que [`trg_validar_cambio_guardia`](create-table.sql#L624-L680) valide en `AFTER STATEMENT`. Si el `UPDATE` falla y hace rollback, **el registro de auditoría queda guardado igual** (auditoría fantasma, rompe Atomicidad). No existe tabla mutante aquí (lee `CUBIERTA_POR` y escribe en `AUDITORIA_GUARDIAS`), por lo que el `PRAGMA` sobra.
  - [`trg_limite_guardias`](create-table.sql#L242-L272): al usar transacción autónoma solo ve filas ya commiteadas. Si una misma transacción asigna varias guardias antes del `COMMIT`, no ve las asignaciones previas y permite superar `guardias_max`. Debe reescribirse como `COMPOUND TRIGGER`.
  - [`trg_evitar_internacion_multiple`](create-table.sql#L699-L719): mismo problema de visibilidad intra-transacción y condición de carrera entre dos sesiones simultáneas. En Oracle se resuelve de forma atómica con un índice único basado en función:
    ```sql
    CREATE UNIQUE INDEX uq_paciente_int_activa
    ON INTERNACION (CASE WHEN fecha_fin IS NULL THEN numero_de_DNI END);
    ```

- [ ] **Bloqueos (`FOR UPDATE`) incompletos y riesgo de condiciones de carrera / deadlocks**:
  - [`sp_ocupar_cama_posee`](create-table.sql#L361-L458): bloquea la cama destino con `FOR UPDATE` ([L399-L404](create-table.sql#L399-L404)), pero **no bloquea la fila de `INTERNACION`** ([L374-L377](create-table.sql#L374-L377)). Dos traslados simultáneos del mismo paciente pueden dejarlo ocupando dos camas a la vez, o un traslado simultáneo con [`sp_dar_alta_internacion`](create-table.sql#L1123-L1172) puede asignar una cama a un paciente ya dado de alta. Tampoco bloquea cama origen y destino en orden determinista (riesgo de deadlock `ORA-00060` si dos sesiones intercambian camas).
  - [`sp_desasignar_medico_guardia`](create-table.sql#L1361-L1386): no bloquea la fila padre en `GUARDIA` con `FOR UPDATE`. Bajo `READ COMMITTED`, dos sesiones que quiten simultáneamente a los últimos 2 médicos verán `v_cant = 1` cada una y dejarán la guardia con 0 médicos.
  - [`sp_registrar_internacion`](create-table.sql#L1020-L1119): bloquea la `CAMA`, pero no bloquea al `PACIENTE`; combinado con la transacción autónoma del trigger, permite internar al mismo paciente en dos camas simultáneamente.

---

## 3. Restricciones del modelo no respetadas o con bugs

- [ ] **[`trg_limite_guardias`](create-table.sql#L242-L272) filtra por `SYSDATE` en lugar del mes de la guardia**:
  - En [L265-L266](create-table.sql#L265-L266) filtra por `EXTRACT(MONTH FROM g.FECHA) = EXTRACT(MONTH FROM SYSDATE)`. Si se carga una guardia para otro mes (ej. diciembre estando en noviembre), cuenta las guardias del mes actual en vez de las del mes de la guardia.
  - Si se cambia la fecha de una guardia a otro mes (`UPDATE GUARDIA SET fecha = ...`), [`trg_validar_cambio_guardia`](create-table.sql#L624-L680) no re-valida `guardias_max` en el nuevo mes.
  - En [L253](create-table.sql#L253), `IF UPDATING AND :OLD.NUMERO_DE_MATRICULA = :NEW.NUMERO_DE_MATRICULA THEN RETURN;` saltea la validación incluso si el `UPDATE` cambia `id_guardia` hacia otro mes.

- [ ] **[`sp_registrar_internacion`](create-table.sql#L1104-L1105) falla al registrar internaciones finalizadas/históricas**:
  - Aunque el SP y `app.py` permiten ingresar `p_fecha_fin`, en [L1105](create-table.sql#L1105) inserta `POSEE.fechaHora = SYSTIMESTAMP`, lo que dispara siempre `ORA-20002` en [`trg_posee_fecha`](create-table.sql#L215-L217) (`fechaHora > fecha_fin`).

- [ ] **Inconsistencias en `CAMA.estado` respecto a `INTERNACION` y `POSEE`**:
  - No existe trigger sobre `POSEE` ni sobre `CAMA`: un `INSERT` directo en `POSEE` permite asignar la misma cama a múltiples internaciones activas al mismo tiempo y no actualiza `CAMA.estado`.
  - [`sp_crear_cama`](create-table.sql#L998-L1016) y el formulario de `app.py` permiten crear una cama directamente como `'OCUPADA'` sin ninguna internación asociada.
  - El modelo indica que una cama está `'Ocupada'` si `fecha_fin IS NULL` **o `fecha_fin > fecha actual`**. Sin embargo, [`sp_registrar_internacion`](create-table.sql#L1096-L1112) y [`trg_liberar_cama_fin_int`](create-table.sql#L322-L346) solo evalúan `IS NULL` / `IS NOT NULL`: si se registra una internación con `fecha_fin` futura, deja la cama `'LIBRE'` y no valida si estaba ocupada.
  - En [`sp_dar_alta_internacion`](create-table.sql#L1146-L1165):
    - Asigna `fecha_fin = GREATEST(TRUNC(SYSDATE), v_fecha_inicio)`. Si el alta es el mismo día del ingreso, queda `fecha_fin = fecha_inicio` (el PDF pide `>` estricto, mientras `chk_internacion_fechas` usa `>=`) y con hora `00:00:00`, **menor** que `POSEE.fechaHora` registrado ese mismo día.
    - Actualiza `CAMA` a `'LIBRE'` dos veces (primero por `trg_liberar_cama_fin_int` y luego explícitamente en el SP).

- [ ] **Solapamiento mal calculado en vacaciones vs. internaciones y chequeo faltante vs. guardias**:
  - En [`trg_medico_internacion_vacaciones`](create-table.sql#L745) y [`trg_vacacion_medico_internacion`](create-table.sql#L771): cuando `fecha_fin IS NULL`, solo verifican si `fecha_inicio` cae dentro de la vacación. Si el paciente ingresó antes (ej. 10/11, sigue internado sin alta) y el médico carga vacaciones del 15/11 al 30/11, `10/11 >= 15/11` es falso y lo permite.
  - [`trg_vacacion_medico_internacion`](create-table.sql#L760-L782) solo verifica `INTERNACION`, pero **no verifica** si el médico ya tiene guardias asignadas en `CUBIERTA_POR` durante esas fechas de vacaciones.

- [ ] **Restricciones de dominio, `NOT NULL`, FKs y triggers con huecos en [`create-table.sql`](create-table.sql)**:
  - **`TIENE.dispuesto`** ([L167](create-table.sql#L167)): falta `CONSTRAINT chk_tiene_dispuesto CHECK (dispuesto IN ('Si', 'No'))`. Como [`trg_medico_dispuesto`](create-table.sql#L237) y los SPs validan `= 'NO'` en vez de `!= 'SI'`, cualquier valor inválido (ej. `'XX'`) permite hacer guardia.
  - **`CUBIERTA_POR`** ([L182-L186](create-table.sql#L182-L186)): tiene dos FKs separadas a `MEDICO` y `ESPECIALIDAD` en lugar de la FK compuesta a `TIENE(numero_de_matricula, id_especialidad)` definida en el MLR.
  - **`PERSONA.numero_de_DNI` y `MEDICO.CUIL`** ([L24](create-table.sql#L24), [L45-L46](create-table.sql#L45-L46)): no validan formato numérico (`REGEXP_LIKE(..., '^[0-9]+$')`). Además `PERSONA` permite 7 u 8 caracteres, pero si un médico tuviera DNI de 7 caracteres nunca podría cumplir `numero_de_DNI = SUBSTR(CUIL, 3, 8)`.
  - **Faltan `NOT NULL` en columnas con `CHECK`** (en Oracle, `NULL` pasa los `CHECK`): `PACIENTE.sexo`, `MEDICO.guardias_max` (`NULL` desactiva `>= v_guardias_max`), `CAMA.estado` (`NULL` saltea `!= 'LIBRE'` en `sp_ocupar_cama_posee`), `HABITACION.orientacion`, `RONDA.turno`, `RONDA.dia_semana`, `GUARDIA.turno`, y `VACACION.fecha_inicio_vac`.
  - **`CAMA.nro_cama` y `POSEE.nro_cama`** son `NUMBER(1)` ([L108](create-table.sql#L108), [L142](create-table.sql#L142)): solo admiten camas del 1 al 9.
  - **Trigger duplicado en `INTERNACION`**: [`trg_validar_fecha_inicio`](create-table.sql#L191-L198) (`-20009`) y [`trg_validar_fecha_inicio_int`](create-table.sql#L721-L728) (`-20011`) validan lo mismo.
  - **[`trg_evitar_internacion_multiple`](create-table.sql#L699-L719)** no verifica `IF :NEW.fecha_fin IS NULL`: impide insertar/actualizar una internación histórica ya cerrada si el paciente tiene una internación activa.
  - **[`sp_crear_habitacion_con_rondas`](create-table.sql#L974-L977)**: hace `SELECT id_ronda INTO v_id_ronda FROM RONDA WHERE dia_semana = ... AND turno = ...`. Si hay más de una ronda por día y turno (hipótesis explícita del grupo), falla con `ORA-01422`.
  - **Participaciones obligatorias del MLR no garantizadas**: `SECTOR` sin habitaciones (`sp_crear_sector`), `HABITACION` sin camas (`sp_crear_habitacion_con_rondas`), `MEDICO` sin especialidad (`sp_registrar_medico`), `PERSONA` sin rol ni registro en `PACIENTE`/`MEDICO` (y en `sp_registrar_paciente`, si ya existía como médico con `rol = NULL`, nunca actualiza `rol = 'PACIENTE'`). Tampoco se valida que `RECORRIDO.fecha` coincida con `RONDA.dia_semana` ni que el médico no esté de vacaciones al hacer un recorrido.
  - **`GUARDIA`** no tiene `UNIQUE (fecha, turno)`: [`sp_crear_y_asignar_guardia`](create-table.sql#L1279-L1281) crea una fila nueva en `GUARDIA` cada vez, aunque ya exista una guardia para esa fecha y turno.

---

## 4. Errores en `app.py`

- [ ] **Crash en `accion_insertar_medico` (`NameError`)** ([`app.py`](app.py#L1781-L1782)):
  - Usa la variable `texto_foto` que nunca fue definida. Falla cada vez que se registra un médico (después de que `sp_registrar_medico` ya hizo `COMMIT`).

- [ ] **Crash en `reemplazar_medico_lista` (`AttributeError`)** ([`app.py`](app.py#L3037)):
  - Llama a `self.log_evento(...)`, método que no existe (solo existen `log_info`, `log_exito`, `log_error`). Falla al reemplazar un médico en el modal de modificación de guardias.

- [ ] **Colisión de código de error `-20048`**:
  - [`create-table.sql`](create-table.sql#L751) usa `-20048` para vacaciones en internación y [`sp_asignar_medico_guardia`](create-table.sql#L1331) también usa `-20048` para parámetros nulos. [`traducir_error_oracle`](app.py#L200) siempre lo muestra como *"Médico en período de vacaciones"*.

- [ ] **Falsos positivos en [`traducir_error_oracle`](app.py#L148)**:
  - La condición `"FECHA_INICIO" in mensaje_mayus` provoca que cualquier error que mencione esa subcadena (por ejemplo `NN_INTERNACION_FECHA_INICIO` o `fecha_inicio_vac`) se traduzca erróneamente como *"Fecha de inicio en el futuro"*.

- [ ] **Rutas relativas en [`ejecutar_archivo_sql`](app.py#L559-L565)**:
  - Usa `"create-table.sql"`, `"HOSPITAL.sql"` y `"create-users.sql"` como rutas relativas ([L631](app.py#L631), [L634](app.py#L634), [L649](app.py#L649), [L657](app.py#L657), [L709](app.py#L709), [L715](app.py#L715), [L720](app.py#L720)). Si la app se ejecuta desde otro directorio de trabajo, no encuentra los archivos. Conviene resolverlos con `os.path.join(DIRECTORIO_APP, archivo)`.

- [ ] **Fuga de conexión en `guardar_modificacion`** ([`app.py`](app.py#L3082-L3095)):
  - Abre `conn_save` en [L3082](app.py#L3082) antes de validar el formato de `fecha_nueva`; si la fecha es inválida, retorna en [L3095](app.py#L3095) sin cerrar `conn_save`.

- [ ] **Método duplicado `_obtener_opciones_medicos`**:
  - Definido dos veces en [`HospitalApp`](app.py#L2558) ([L2558](app.py#L2558) y [L3233](app.py#L3233)).

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

- [ ] **Inconsistencia día/ronda en `RECORRIDO`** ([`HOSPITAL.sql`](HOSPITAL.sql#L534-L549)):
  - Los dos recorridos tienen fechas `sysdate - 2` y `sysdate - 1` (días consecutivos), pero ambos apuntan a rondas del día `LUNES` (`id_ronda` 1 y 2).

- [ ] **Sin datos iniciales de `GUARDIA` y `CUBIERTA_POR`**:
  - No hay guardias precargadas para evaluar de inmediato las consultas de guardias, auditoría y asignación mensual.

---

## 6. Erratas menores en el informe PDF del grupo

- [ ] **Pág. 3**: dice `Dom(Medico.sexo)` en lugar de `Dom(Paciente.sexo)`.
- [ ] **Pág. 3**: están repetidas dos veces la restricción *"En una ronda no puede haber habitaciones repetidas"* y la de `Vacacion.fecha_fin_vac` mayor a `Vacacion.fecha_inicio_vac`.
- [ ] **Pág. 4**: en `COMENTARIO` dice `PK=CK={id_cometario}` (falta la `n`).
- [ ] **Pág. 5**: dice `RECORRIDO.id_ronda puede no estar en RONDA.id_ronda` (debería decir **debe** estar).
- [ ] **Pág. 7**: en el esquema de `PERSONA` dice `PERSONA (numero_de_DNI, nombre, apellido, es)` (`es` en lugar de `rol`).
