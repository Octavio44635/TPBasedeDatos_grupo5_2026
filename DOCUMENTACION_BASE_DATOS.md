# Documentacion de la base de datos del hospital

Este documento describe los objetos definidos actualmente en `create-table.sql` y la configuracion de cuentas y permisos de `create-users.sql`, `grant-admin-hospital.sql` y `ejecutar.sql`.

> La descripcion refleja el codigo fuente SQL del repositorio. No implica que todos los objetos esten instalados ni habilitados en una instancia Oracle concreta.

## 1. Como se crea el esquema

El archivo `create-table.sql` primero intenta eliminar las tablas del esquema y luego las crea de nuevo. Los `DROP TABLE ... CASCADE CONSTRAINTS` borran tambien los datos y las restricciones dependientes. No ejecutar este archivo sobre una base que contenga datos que se quieran conservar.

El script crea 18 tablas, un indice unico funcional, triggers y procedimientos almacenados. Las claves foraneas conectan los registros relacionados; las tablas asociativas modelan las relaciones de muchos a muchos.

## 2. Tablas

| Tabla | Para que se utiliza |
|---|---|
| `PERSONA` | Datos comunes de una persona: DNI, nombre, apellido y rol. Es la entidad base asociada a pacientes y medicos. |
| `PACIENTE` | Datos propios del paciente, como sexo y fecha de nacimiento. Su DNI referencia a `PERSONA`. |
| `MEDICO` | Datos profesionales: matricula, CUIL, foto, maximo mensual de guardias, fecha de ingreso y DNI. El DNI identifica a la persona asociada. |
| `VACACION` | Periodos de vacaciones de cada medico, identificados por matricula y numero de vacacion. |
| `SECTOR` | Sectores del hospital, identificados por nombre e ID generado automaticamente. |
| `ESPECIALIDAD` | Catalogo de especialidades medicas. |
| `RONDA` | Configuracion de rondas por dia de la semana y turno numerico (1 a 4). |
| `GUARDIA` | Guardia programada en una fecha y turno (manana, tarde o noche). |
| `INTERNACION` | Internaciones de pacientes, con fechas de inicio/fin, paciente y medico a cargo. `fecha_fin` nula indica internacion activa. |
| `HABITACION` | Habitaciones del hospital, con piso, orientacion y sector. |
| `CAMA` | Camas dentro de una habitacion, con numero y estado (`LIBRE` o `OCUPADA`). La clave primaria combina habitacion y numero de cama. |
| `RECORRIDO` | Visita de un medico en una fecha y ronda determinada. |
| `COMENTARIO` | Comentario clinico asociado a una internacion y al recorrido en que se registra. |
| `POSEE` | Historial de camas asignadas a una internacion, con marca temporal. Permite conservar los traslados. |
| `COMPUESTA_POR` | Relacion entre rondas y habitaciones: indica que habitaciones se recorren en cada ronda. |
| `TIENE` | Relacion entre medicos y especialidades, junto con el indicador `dispuesto` para guardias. |
| `CUBIERTA_POR` | Asignaciones de medicos y especialidades a guardias. |
| `AUDITORIA_GUARDIAS` | Registro de operaciones sobre asignaciones de guardias y cambios de fecha/turno de una guardia. |

### Relaciones principales

- `PERSONA` es el registro general y `PACIENTE`/`MEDICO` contienen informacion especializada.
- Una internacion se vincula con un paciente y un medico; `POSEE` guarda las camas que ocupo a lo largo del tiempo.
- Una habitacion pertenece a un sector y contiene camas.
- `COMPUESTA_POR` vincula habitaciones con rondas; `RECORRIDO` registra la realizacion de una ronda.
- `COMENTARIO` vincula una internacion con un recorrido.
- `TIENE` vincula medicos y especialidades; `CUBIERTA_POR` usa esa asociacion para asignar personal a guardias.

El indice `uq_paciente_int_activa`, creado sobre `INTERNACION`, impide que un mismo paciente tenga mas de una internacion con `fecha_fin IS NULL`. Un trigger complementario comprueba el solapamiento de rangos de fechas, incluidas internaciones historicas.

## 3. Stored procedures

Los procedimientos que modifican datos suelen confirmar la operacion con `COMMIT` y ejecutar `ROLLBACK` si ocurre una excepcion. Los procedimientos de consulta abren cursores (`SYS_REFCURSOR`) para que la aplicacion lea los resultados.

### Camas e internaciones

| Procedimiento | Funcion |
|---|---|
| `sp_ocupar_cama_posee` | Asigna o traslada una internacion a una cama: valida internacion activa y cama disponible, registra el historial en `POSEE` y actualiza el estado de las camas. |
| `listar_camas_disponibles` | Devuelve dos cursores: cantidad de camas libres por sector y detalle de cada cama libre. |
| `listar_comentarios_internacion` | Devuelve datos del paciente y comentarios de una internacion, incluyendo fecha, turno, medico y texto. |
| `sp_registrar_internacion` | Valida paciente, medico, fecha y cama; crea la internacion y su asignacion inicial. Acepta internaciones activas o finalizadas, y una hora de ingreso opcional. |
| `sp_dar_alta_internacion` | Registra el alta de una internacion activa y libera la cama que figura como la asignacion mas reciente. |
| `sp_obtener_datos_alta` | Recupera datos de una internacion y su ultima cama para mostrar o confirmar el alta. |
| `sp_consultar_cama_actual` | Consulta paciente, cama mas reciente, estado, sector y fechas de la internacion. |
| `sp_listar_internaciones_activas` | Lista las internaciones sin fecha de alta. |
| `sp_internaciones_de_recorrido` | Devuelve informacion de la ronda y las internaciones activas en habitaciones incluidas en esa ronda. |

### Personas, medicos y estructura del hospital

| Procedimiento | Funcion |
|---|---|
| `sp_registrar_paciente` | Registra una persona si aun no existe y crea su fila en `PACIENTE`, validando DNI, sexo y fecha de nacimiento. |
| `sp_registrar_medico` | Registra la persona si no existe y crea el registro profesional, validando DNI y CUIL. La foto es opcional. |
| `sp_crear_sector` | Crea un sector y devuelve el ID generado. |
| `sp_crear_habitacion_con_rondas` | Crea una habitacion y la asocia a una ronda para cada dia de la semana, creando la ronda si no se encuentra. |
| `sp_crear_cama` | Crea una cama en una habitacion con el estado indicado; por defecto, `LIBRE`. |
| `sp_listar_pacientes` | Lista los pacientes y sus datos personales principales. |
| `sp_obtener_foto_medico` | Devuelve la foto asociada a una matricula. |
| `sp_listar_medicos` | Lista datos de los medicos e indica si cada uno tiene foto. |
| `sp_listar_medicos_combo` | Devuelve matricula y nombre para listas de seleccion. |
| `sp_listar_sectores_combo` | Devuelve ID y nombre de sectores para listas de seleccion. |
| `sp_listar_sectores` | Lista los sectores y cuenta sus habitaciones. |
| `sp_obtener_rondas_habitacion` | Lista las rondas asociadas a una habitacion. |
| `sp_listar_habitaciones` | Lista habitaciones, sector y cantidad de rondas asociadas. |
| `sp_listar_todas_camas` | Lista camas, estados y sectores. |
| `sp_listar_especialidades_medico` | Lista especialidades y la disposicion de un medico para cada una, si esta registrada. |
| `sp_verificar_medico_especialidad` | Informa si la especialidad esta habilitada, no dispuesta o no registrada para un medico. |
| `sp_asignar_especialidad_medico` | Asocia una especialidad a un medico o actualiza su indicador de disposicion (`Si`/`No`) para realizar guardias. |
| `sp_quitar_especialidad_medico` | Elimina la asociacion entre un medico y una especialidad en la tabla `TIENE`. |

### Guardias

| Procedimiento | Funcion |
|---|---|
| `sp_crear_y_asignar_guardia` | Crea una guardia y asigna un medico/especialidad en una misma operacion. Valida que el medico y la especialidad existan y que el medico este dispuesto. |
| `sp_modificar_guardia` | Cambia fecha, turno y asignaciones de una guardia en una operacion atomica. Recibe las asignaciones como texto con formato `MATRICULA:ID_ESPECIALIDAD,MATRICULA:ID_ESPECIALIDAD`. |
| `sp_eliminar_guardia` | Elimina las asignaciones de la guardia y luego la guardia. |
| `sp_listar_guardias` | Lista guardias y medicos/especialidades asignados. |
| `sp_obtener_datos_guardia` | Devuelve dos cursores: fecha/turno de la guardia y lista de medicos asignados. |

### Recorridos y comentarios

| Procedimiento | Funcion |
|---|---|
| `sp_registrar_recorrido` | Registra un recorrido para un medico y ronda en una fecha. |
| `sp_eliminar_recorrido` | Elimina un recorrido solo si no tiene comentarios asociados. |
| `sp_registrar_comentario` | Registra un comentario para una internacion y un recorrido. |
| `sp_eliminar_comentario` | Elimina un comentario existente. |
| `sp_listar_recorridos` | Lista recorridos con medico, ronda y cantidad de comentarios. |
| `sp_listar_recorridos_medico` | Lista los recorridos de una matricula y la cantidad de comentarios. |
| `sp_listar_comentarios_recorrido` | Lista comentarios de un recorrido junto con la internacion y el nombre del paciente. |
| `sp_listar_rondas_combo` | Lista ID, turno y dia de las rondas para una lista de seleccion. |

## 4. Triggers y validaciones automaticas

Los triggers aplican reglas cuando se insertan o modifican filas. Por ello, tambien actuan cuando los cambios se realizan directamente sobre las tablas y no a traves de la aplicacion.

### Normalizacion de identificadores

| Trigger | Tabla / evento | Funcion |
|---|---|---|
| `trg_normalizar_dni_persona` | `PERSONA`, antes de insertar o actualizar DNI | Completa con un cero inicial los DNI numericos de 7 digitos. |
| `trg_normalizar_dni_paciente` | `PACIENTE`, antes de insertar o actualizar DNI | Aplica la misma normalizacion. |
| `trg_normalizar_dni_medico` | `MEDICO`, antes de insertar o actualizar DNI | Aplica la misma normalizacion. |
| `trg_normalizar_dni_internacion` | `INTERNACION`, antes de insertar o actualizar DNI | Aplica la misma normalizacion. |

Las restricciones de las tablas verifican, entre otras condiciones, que DNI tenga 8 digitos y CUIL 11 digitos.

### Camas e internaciones

| Trigger | Tabla / evento | Funcion |
|---|---|---|
| `trg_posee_fecha` | `POSEE`, antes de insertar o actualizar | Impide registrar una asignacion de cama anterior al inicio o posterior al fin de la internacion. |
| `trg_liberar_cama_fin_int` | `INTERNACION`, despues de pasar de activa a finalizada | Busca la ultima cama registrada y la marca como `LIBRE`. |
| `trg_evitar_autoatencion` | `INTERNACION`, antes de insertar o actualizar | Impide que el medico responsable sea el mismo paciente. |
| `trg_evitar_internacion_multiple` | `INTERNACION`, despues de insertar o actualizar | Detecta rangos de internacion que se superponen para un mismo paciente. Junto al indice unico, protege tambien las internaciones activas. |
| `trg_validar_fecha_inicio_int` | `INTERNACION`, antes de insertar o actualizar | Impide iniciar una internacion en una fecha posterior a la fecha del sistema. |

### Guardias, especialidades y vacaciones

| Trigger | Tabla / evento | Funcion |
|---|---|---|
| `trg_medico_dispuesto` | `CUBIERTA_POR`, antes de insertar o actualizar | Comprueba que la relacion medico/especialidad exista en `TIENE` y que `dispuesto` sea `Si`. |
| `trg_limite_guardias` | `CUBIERTA_POR`, despues de insertar o actualizar | Comprueba el maximo mensual de guardias del medico usando el mes y anio de cada guardia. |
| `trg_limite_guardias_fecha` | `GUARDIA`, despues de actualizar la fecha | Revalida el maximo mensual si el cambio de fecha mueve asignaciones a otro mes. |
| `trg_medico_en_vacaciones` | `CUBIERTA_POR`, antes de insertar o actualizar | Impide asignar una guardia que coincida con las vacaciones del medico. |
| `trg_evitar_guardia_superpuesta` | `CUBIERTA_POR`, insercion o actualizacion | Impide asignar al mismo medico dos guardias con igual fecha y turno. No valida dias consecutivos ni turnos distintos del mismo dia. |
| `trg_validar_cambio_guardia` | `GUARDIA`, antes de cambiar fecha o turno | Comprueba que las asignaciones existentes no generen conflicto de fecha/turno ni coincidan con vacaciones. |
| `trg_vacacion_medico_guardia` | `VACACION`, antes de insertar o actualizar | Impide registrar vacaciones que se crucen con guardias ya asignadas. |

### Recorridos y comentarios

| Trigger | Tabla / evento | Funcion |
|---|---|---|
| `trg_recorrido_medico_vacaciones` | `RECORRIDO`, antes de insertar o cambiar medico/fecha | Impide registrar un recorrido durante las vacaciones del medico. |
| `trg_vacacion_medico_recorrido` | `VACACION`, antes de insertar o actualizar | Impide registrar vacaciones que se crucen con recorridos existentes. |
| `trg_recorrido_dia_ronda` | `RECORRIDO`, antes de insertar o cambiar fecha/ronda | Comprueba que el dia de la fecha coincida con el dia configurado en la ronda. |
| `trg_ronda_dia_recorridos` | `RONDA`, antes de cambiar el dia | Impide cambiar el dia de una ronda si contradice recorridos ya registrados. |
| `trg_comentario_ronda` | `COMENTARIO`, antes de insertar o actualizar | Impide comentar internaciones finalizadas, exige una cama registrada y comprueba que la habitacion actual pertenezca a la ronda del recorrido. |

Los comentarios del SQL marcan `trg_recorrido_dia_ronda` y `trg_ronda_dia_recorridos` como provisorios/pendientes de confirmar.

### Auditoria de guardias

| Trigger | Tabla / evento | Funcion |
|---|---|---|
| `trg_auditoria_guardias` | `CUBIERTA_POR`, despues de insertar, actualizar o borrar | Inserta en `AUDITORIA_GUARDIAS` el usuario de base de datos, fecha/hora, operacion, matricula e ID de guardia. |
| `trg_auditoria_guardia_update` | `GUARDIA`, despues de cambiar fecha o turno | Inserta un registro de auditoria por cada medico asignado a esa guardia. |

La auditoria descrita cubre las asignaciones y cambios de fecha/turno, no todas las modificaciones posibles en los datos relacionados con guardias.

## 5. Usuarios y permisos

### Usuario propietario `HOSPITAL`

`grant-admin-hospital.sql` y `ejecutar.sql` contienen los mismos permisos administrativos para el usuario `HOSPITAL`. Deben ejecutarse con una cuenta administrativa Oracle (por ejemplo, `SYSTEM` o `SYS AS SYSDBA`). Otorgan permisos para crear, modificar y eliminar usuarios; conceder privilegios de sistema; y crear/eliminar sinonimos publicos. El permiso `DBA` aparece como alternativa comentada y no se concede en el script tal como esta.

Estos permisos son amplios: `GRANT ANY PRIVILEGE` y la gestion de usuarios deben limitarse a entornos donde realmente sean necesarios.

### Cuentas individuales

`create-users.sql` crea dos cuentas de ejemplo identificadas por DNI. Antes de crearlas, ejecuta `DROP USER ... CASCADE`; esto elimina las cuentas existentes y los objetos que posean. El script usa una contrasena de demostracion compartida: no debe reutilizarse en un entorno real. Cambiarla por una credencial individual y segura antes de ejecutar el script.

A cada cuenta se le asigna:

1. `CREATE SESSION`, para poder conectarse.
2. Privilegios directos `SELECT`, `INSERT`, `UPDATE` y `DELETE` sobre las 17 tablas operativas del esquema.
3. Privilegios `EXECUTE` sobre los procedimientos listados en el script.
4. Sinonimos publicos para omitir el prefijo `HOSPITAL.` al referenciar objetos.

Los sinonimos solo son alias de nombres: no otorgan permisos por si mismos. Los permisos se conceden mediante `GRANT`.

Ejemplo orientativo para una cuenta nueva, con nombres y clave de marcador de posicion:

```sql
CREATE USER usuario_medico IDENTIFIED BY "reemplazar_por_una_clave_segura";
GRANT CREATE SESSION TO usuario_medico;
GRANT SELECT ON HOSPITAL.PERSONA TO usuario_medico;
GRANT EXECUTE ON HOSPITAL.sp_listar_pacientes TO usuario_medico;
```

En una configuracion real se deberian otorgar solo las operaciones y procedimientos que cada cuenta necesita. Evitar permisos directos de escritura si la aplicacion debe forzar las reglas mediante procedimientos.

### Acceso `PUBLIC` a procedimientos

Al final de `create-table.sql` se otorga `EXECUTE` sobre todos los procedimientos a `PUBLIC` y se crean sinonimos publicos. Por tanto, cualquier usuario de la base que pueda conectarse puede ejecutar esos procedimientos, aunque `create-users.sql` tambien conceda permisos directos a las dos cuentas de ejemplo. Esto es mas amplio que un modelo de acceso limitado a usuarios concretos; revisar y retirar los grants a `PUBLIC` si se busca restringir el acceso.

El script no concede explicitamente permisos sobre `AUDITORIA_GUARDIAS` a las cuentas individuales; crear un sinonimo para la tabla tampoco les da acceso.

## 6. Archivos SQL relacionados

- `create-table.sql`: elimina y recrea las tablas, el indice, triggers y procedimientos; tambien define grants de ejecucion a `PUBLIC` y sinonimos.
- `create-users.sql`: crea las cuentas de ejemplo y concede permisos de tablas y procedimientos.
- `grant-admin-hospital.sql`: otorga permisos administrativos al usuario `HOSPITAL`.
- `ejecutar.sql`: repite los permisos administrativos de `grant-admin-hospital.sql`.
- `HOSPITAL.sql`: carga datos de prueba y realiza operaciones de ejemplo.
