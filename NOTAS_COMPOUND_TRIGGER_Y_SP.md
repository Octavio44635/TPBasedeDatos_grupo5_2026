# Notas técnicas para la defensa oral (Triggers, Transacciones y Diseño)

Documento de respaldo para estudio y defensa oral basado en [REVISION_TP.md](REVISION_TP.md).

---

## 1. `COMPOUND TRIGGER` vs. `PRAGMA AUTONOMOUS_TRANSACTION`

### El problema de origen: *Mutating Table* (`ORA-04091`)

En Oracle, si un trigger común de fila (`BEFORE/AFTER INSERT OR UPDATE ... FOR EACH ROW`) intenta ejecutar un `SELECT` sobre **la misma tabla que se está modificando**, Oracle lanza **`ORA-04091: table is mutating`**. Esto ocurre porque la sentencia todavía está a mitad de ejecutarse y la tabla se encuentra en un estado intermedio inconsistente.

---

### Qué es y para qué sirve `COMPOUND TRIGGER`

Un `COMPOUND TRIGGER` agrupa en un único trigger las distintas fases de una sentencia SQL compartiendo variables/colecciones en memoria, **siempre dentro de la misma transacción principal**:

1. **`BEFORE STATEMENT`**: limpia la colección en memoria.
2. **`BEFORE EACH ROW` / `AFTER EACH ROW`**: **no consulta la tabla mutante**; solo anota las claves o filas afectadas en la colección en memoria.
3. **`AFTER STATEMENT`**: cuando la sentencia terminó de modificar todas las filas y la tabla ya no está mutando, ejecuta las consultas (`SELECT`) de validación contra los datos reales.

**Qué resuelve:**
- **Evita `ORA-04091`** sin abrir transacciones paralelas.
- **Ve los cambios sin confirmar (`COMMIT`) de la misma transacción**: permite leer una `GUARDIA` recién insertada antes del `COMMIT` o verificar conflictos entre múltiples filas modificadas en la misma transacción.
- **Respeta ACID / atomicidad**: si falla con `RAISE_APPLICATION_ERROR`, revierte toda la operación principal sin dejar efectos secundarios.

**Ejemplos en el TP:**
- [`trg_evitar_guardia_superpuesta`](create-table.sql#L918)
- [`trg_validar_cambio_guardia`](create-table.sql#L979)

> **Alternativa cuando la regla es global sobre la tabla:** usar un **trigger a nivel de sentencia** (`AFTER INSERT OR UPDATE ON ...` sin `FOR EACH ROW`), que también se ejecuta dentro de la misma transacción principal una vez finalizada la sentencia y evita `ORA-04091`. Ejemplos en el TP: [`trg_limite_guardias`](create-table.sql#L519) y [`trg_evitar_internacion_multiple`](create-table.sql#L1064).

---

### Qué es y para qué sirve `PRAGMA AUTONOMOUS_TRANSACTION`

`PRAGMA AUTONOMOUS_TRANSACTION` le indica a Oracle que ese bloque PL/SQL (trigger o procedimiento) se ejecute en una **transacción hija completamente independiente**, con su propio `COMMIT` o `ROLLBACK`, sin afectar ni verse afectado por el `COMMIT`/`ROLLBACK` de la transacción principal.

**Cuándo SÍ corresponde usarlo:**
- Para **registrar logs de errores o intentos fallidos** que deben quedar persistidos en una tabla de log aunque la transacción principal aborte y haga `ROLLBACK`.

**Por qué NO debe usarse para validar reglas de negocio ni auditar cambios confirmados:**
- **No ve datos sin `COMMIT` de la transacción principal** (bajo aislamiento `READ COMMITTED`): si en una misma transacción se insertan varias filas antes de confirmar, la transacción autónoma no las ve, dejando pasar violaciones de límites/restricciones o fallando con `ORA-01403` si el padre aún no fue commiteado.
- **Rompe la atomicidad (ACID):** si la transacción principal falla después y hace `ROLLBACK`, cualquier `INSERT` commiteado dentro de la transacción autónoma (por ejemplo, una fila en auditoría) **permanece grabado** registrando una operación que nunca ocurrió.

Por ese motivo se eliminó `PRAGMA AUTONOMOUS_TRANSACTION` de [`trg_auditoria_guardia_update`](create-table.sql#L411), [`trg_limite_guardias`](create-table.sql#L519) y [`trg_evitar_internacion_multiple`](create-table.sql#L1064).

---

### Cuadro comparativo rápido (para el oral)

| Aspecto | `COMPOUND TRIGGER` | `PRAGMA AUTONOMOUS_TRANSACTION` |
|---|---|---|
| **Transacción** | Misma transacción principal | Transacción aparte e independiente |
| **¿Ve cambios sin `COMMIT` de la transacción actual?** | Sí | No |
| **Si la transacción principal hace `ROLLBACK`** | Se revierte todo (preserva atomicidad) | Lo commiteado en el bloque autónomo **no** se revierte |
| **Uso correcto** | Validar reglas de negocio que necesitan leer la misma tabla sin `ORA-04091` | Persistir logs/trazas de errores aunque la operación principal falle |

---

## 2. Internaciones vía SQL directo vs. Stored Procedures

### Por qué operar mediante Stored Procedures

Registrar o trasladar una internación involucra múltiples tablas relacionadas (`INTERNACION`, `POSEE` y `CAMA`) que deben quedar consistentes en una única unidad atómica:

- **[`sp_registrar_internacion`](create-table.sql#L1806)**: inserta la `INTERNACION`, asigna la cama inicial en `POSEE` y actualiza `CAMA.estado` dentro de una misma transacción (con `COMMIT` final o `ROLLBACK` completo ante error).
- **[`sp_ocupar_cama_posee`](create-table.sql#L774)**: bloquea la cama destino con `SELECT ... FOR UPDATE`, libera la cama anterior si corresponde, inserta en `POSEE` con `SYSTIMESTAMP` y ocupa la nueva cama atómicamente.
- Además, la restricción del modelo *"toda internación debe tener al menos una cama asignada en `POSEE`"* (participación obligatoria del padre hacia el hijo) no puede validarse con un trigger simple fila a fila al insertar el padre `INTERNACION` (porque el hijo `POSEE` se inserta después). Orquestar la alta en el SP garantiza que nunca quede una internación sin su registro en `POSEE`.

### Defensa en profundidad (SPs + Restricciones en la BD)

Aunque la aplicación opere por Stored Procedures, las invariantes críticas deben estar protegidas en el motor mediante constraints, índices y triggers ante eventuales DML directos en SQL:
- Unicidad de internación activa por paciente mediante el índice único basado en función `uq_paciente_int_activa` (`CASE WHEN fecha_fin IS NULL THEN numero_de_DNI END`).
- Fechas válidas y sin superposición (`chk_internacion_fechas`, `trg_validar_fecha_inicio_int`, [`trg_evitar_internacion_multiple`](create-table.sql#L1064)).
- Prohibición de autoatención (`trg_evitar_autoatencion`) y coherencia de fechas en cama (`trg_posee_fecha`).
- Liberación automática de cama al registrar el alta (`trg_liberar_cama_fin_int`).

---

## 3. Restricciones declarativas y particularidades de Oracle

- **`CHECK` no valida `NULL` (lógica trivaluada):** en SQL, si una columna toma valor `NULL`, un `CHECK` evalúa a `UNKNOWN` y Oracle **permite insertar la fila**. Por eso se reforzaron con `NOT NULL` las columnas que poseen restricciones `CHECK` (`PACIENTE.sexo`, `MEDICO.guardias_max`, `CAMA.estado`, `GUARDIA.turno`, `RONDA.turno`, `RONDA.dia_semana`, `TIENE.dispuesto`).
- **FK compuesta `fk_cubierta_tiene`:** en lugar de dos claves foráneas independientes hacia `MEDICO` y `ESPECIALIDAD`, una FK compuesta a `TIENE(numero_de_matricula, id_especialidad)` garantiza de forma declarativa que no se pueda asignar una guardia en una especialidad que el médico no tiene registrada.
- **Índice único basado en función (`uq_paciente_int_activa`):**
  ```sql
  CREATE UNIQUE INDEX uq_paciente_int_activa
  ON INTERNACION (CASE WHEN fecha_fin IS NULL THEN numero_de_DNI END);
  ```
  Como Oracle **no indexa valores `NULL`** en un índice B-tree único, permite múltiples internaciones históricas ya finalizadas (`fecha_fin IS NOT NULL` → la expresión devuelve `NULL`), pero garantiza **como máximo una internación activa** por paciente (`fecha_fin IS NULL` → indexa el DNI) de forma atómica incluso bajo concurrencia.
- **Orden de ejecución con `FOLLOWS`:** Oracle no garantiza el orden entre dos triggers del mismo evento (`BEFORE INSERT`). Por eso `trg_evitar_autoatencion` declara `FOLLOWS trg_normalizar_dni_internacion`, asegurando que un DNI de 7 dígitos se complete con `'0'` adelante **antes** de compararlo contra el DNI del médico.

---

## 4. Transacciones, Concurrencia y ACID

- **Aislamiento por defecto de Oracle (`READ COMMITTED`) y `SELECT ... FOR UPDATE`:**
  - En [`sp_ocupar_cama_posee`](create-table.sql#L774) y [`sp_registrar_internacion`](create-table.sql#L1806) se usa bloqueo pesimista (`FOR UPDATE`) sobre la fila de `CAMA` antes de verificar `estado = 'LIBRE'` y pasarla a `'OCUPADA'`, evitando que dos sesiones concurrentes asignen la misma cama al mismo tiempo (*condición de carrera*).
  - En `sp_modificar_guardia` se bloquea la fila padre de `GUARDIA` con `FOR UPDATE` para serializar modificaciones concurrentes sobre sus asignaciones en `CUBIERTA_POR`.
- **Atomicidad real al modificar guardias:** en vez de encadenar varios SPs con `COMMIT` separados (donde un fallo intermedio dejaba cambios a medias), `sp_modificar_guardia` ejecuta toda la actualización en **una sola transacción** con un único `COMMIT` final y `ROLLBACK` completo ante cualquier error. Además realiza `UPDATE CUBIERTA_POR` en los reemplazos 1 a 1 para que la auditoría registre `'UPDATE'` y no `'DELETE'` + `'INSERT'`.
- **Cálculo de día de semana independiente de `NLS`:** en `trg_recorrido_dia_ronda` y `trg_ronda_dia_recorridos` se obtiene el día con `TRUNC(fecha) - TRUNC(fecha, 'IW')` (semana ISO: `0 = LUNES`..`6 = DOMINGO`), evitando errores por configuración regional (`NLS_DATE_LANGUAGE` / `NLS_TERRITORY`) o tildes (`MIÉRCOLES` / `SÁBADO`).

---

## 5. Validaciones bidireccionales (doble sentido)

Las reglas entre dos tablas se controlan desde **ambos extremos** para que no puedan esquivarse modificando cualquiera de las dos:
- **Vacaciones ↔ Guardias:** se valida al asignar médico en `CUBIERTA_POR`, al reprogramar una `GUARDIA` **y** al cargar/editar fechas en `VACACION`.
- **Vacaciones ↔ Recorridos:** se valida al registrar/modificar en `RECORRIDO` **y** al cargar/editar en `VACACION`.
- **Límite mensual de guardias:** se valida al asignar/reemplazar en `CUBIERTA_POR` **y** al mover la fecha de una `GUARDIA`, usando el mes real de `g.fecha` (no `SYSDATE`).
- **Día de ronda ↔ Fecha de recorrido:** se valida al insertar/actualizar `RECORRIDO` **y** al modificar `RONDA.dia_semana`.

---

## 6. Auditoría, Seguridad y Arquitectura

- **Usuario real de BD (`USER`) y atomicidad de la auditoría:** `AUDITORIA_GUARDIAS` registra la función `USER` del motor (por ejemplo los usuarios Oracle `"33333333"` y `"44444444"` definidos en [create-users.sql](create-users.sql)), no un texto enviado por la interfaz. Al eliminar `PRAGMA AUTONOMOUS_TRANSACTION` de [`trg_auditoria_guardia_update`](create-table.sql#L411), si la modificación hace `ROLLBACK`, la auditoría también se revierte y no registra cambios que no ocurrieron.
- **Endurecimiento de permisos (*definer's rights*):** si en producción se revocan `INSERT`/`UPDATE`/`DELETE` directos sobre `AUDITORIA_GUARDIAS` (o sobre `INTERNACION`, `POSEE`, `CAMA`) dejando a los usuarios solo `SELECT` y `EXECUTE` sobre los Stored Procedures, los triggers igual siguen funcionando porque se ejecutan con los privilegios del dueño del esquema (`HOSPITAL`).
- **Independencia del frontend:** todas las reglas de integridad y negocio viven en la base de datos (constraints, índices, triggers y SPs); [`app.py`](app.py) solo invoca los SPs y traduce los códigos `ORA-*`, por lo que las reglas también se cumplen si se opera directamente desde SQL.

---

## 7. Decisiones de modelado útiles para defender

- **Jerarquía `PERSONA` → `PACIENTE` / `MEDICO` con solapamiento:** una misma persona puede ser paciente y médico al mismo tiempo (por ejemplo DNI `'11111111'` / matrícula `'M100'`), mientras `trg_evitar_autoatencion` impide que sea el médico a cargo de su propia internación.
- **Historial de camas en `POSEE`:** `fechaHora` forma parte de la clave primaria para conservar el historial completo de traslados; al crear una internación se guarda la fecha/hora de ingreso (lo que permite registrar internaciones históricas ya finalizadas), y en los traslados (`sp_ocupar_cama_posee`) se utiliza `SYSTIMESTAMP` del servidor. La cama actual se obtiene ordenando por `fechaHora DESC FETCH FIRST 1 ROW ONLY`.
