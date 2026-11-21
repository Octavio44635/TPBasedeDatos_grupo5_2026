-- =============================================================================
-- CREACIÓN DE USUARIOS MÉDICOS Y ASIGNACIÓN DIRECTA DE PERMISOS
-- (Sin uso de roles: los permisos se otorgan directamente a cada usuario)
-- Ejecutar conectado como HOSPITAL (con permisos DBA/SYSTEM) o como SYSTEM
-- =============================================================================

-- =============================================================================
-- 1. CREACIÓN DE USUARIOS (DNI)
-- Nota: La contraseña numérica va entre comillas dobles para compatibilidad Oracle
-- =============================================================================
DROP USER "44444444" CASCADE;
DROP USER "33333333" CASCADE;


CREATE USER "44444444" IDENTIFIED BY "1234";
CREATE USER "33333333" IDENTIFIED BY "1234";

-- =============================================================================
-- 2. PERMISO BÁSICO DE CONEXIÓN
-- =============================================================================
GRANT CREATE SESSION TO "44444444", "33333333";

-- =============================================================================
-- 3. PERMISOS DIRECTOS DE LECTURA Y EDICIÓN SOBRE LAS TABLAS DE HOSPITAL
-- =============================================================================
GRANT SELECT, INSERT, UPDATE, DELETE ON HOSPITAL.PERSONA            TO "44444444", "33333333";
GRANT SELECT, INSERT, UPDATE, DELETE ON HOSPITAL.PACIENTE           TO "44444444", "33333333";
GRANT SELECT, INSERT, UPDATE, DELETE ON HOSPITAL.MEDICO             TO "44444444", "33333333";
GRANT SELECT, INSERT, UPDATE, DELETE ON HOSPITAL.VACACION           TO "44444444", "33333333";
GRANT SELECT, INSERT, UPDATE, DELETE ON HOSPITAL.SECTOR             TO "44444444", "33333333";
GRANT SELECT, INSERT, UPDATE, DELETE ON HOSPITAL.ESPECIALIDAD       TO "44444444", "33333333";
GRANT SELECT, INSERT, UPDATE, DELETE ON HOSPITAL.RONDA              TO "44444444", "33333333";
GRANT SELECT, INSERT, UPDATE, DELETE ON HOSPITAL.GUARDIA            TO "44444444", "33333333";
GRANT SELECT, INSERT, UPDATE, DELETE ON HOSPITAL.INTERNACION        TO "44444444", "33333333";
GRANT SELECT, INSERT, UPDATE, DELETE ON HOSPITAL.HABITACION         TO "44444444", "33333333";
GRANT SELECT, INSERT, UPDATE, DELETE ON HOSPITAL.CAMA               TO "44444444", "33333333";
GRANT SELECT, INSERT, UPDATE, DELETE ON HOSPITAL.RECORRIDO          TO "44444444", "33333333";
GRANT SELECT, INSERT, UPDATE, DELETE ON HOSPITAL.COMENTARIO         TO "44444444", "33333333";
GRANT SELECT, INSERT, UPDATE, DELETE ON HOSPITAL.POSEE              TO "44444444", "33333333";
GRANT SELECT, INSERT, UPDATE, DELETE ON HOSPITAL.COMPUESTA_POR      TO "44444444", "33333333";
GRANT SELECT, INSERT, UPDATE, DELETE ON HOSPITAL.TIENE              TO "44444444", "33333333";
GRANT SELECT, INSERT, UPDATE, DELETE ON HOSPITAL.CUBIERTA_POR       TO "44444444", "33333333";

-- Permiso sobre la secuencia de guardias ????
-- GRANT SELECT ON HOSPITAL.SEQ_GUARDIA TO "44444444", "33333333";

-- =============================================================================
-- 4. SINÓNIMOS PÚBLICOS
-- Permite que los usuarios accedan a las tablas con su nombre simple (ej: SELECT * FROM GUARDIA)
-- =============================================================================
CREATE OR REPLACE PUBLIC SYNONYM PERSONA            FOR HOSPITAL.PERSONA;
CREATE OR REPLACE PUBLIC SYNONYM PACIENTE           FOR HOSPITAL.PACIENTE;
CREATE OR REPLACE PUBLIC SYNONYM MEDICO             FOR HOSPITAL.MEDICO;
CREATE OR REPLACE PUBLIC SYNONYM VACACION           FOR HOSPITAL.VACACION;
CREATE OR REPLACE PUBLIC SYNONYM SECTOR             FOR HOSPITAL.SECTOR;
CREATE OR REPLACE PUBLIC SYNONYM ESPECIALIDAD       FOR HOSPITAL.ESPECIALIDAD;
CREATE OR REPLACE PUBLIC SYNONYM RONDA              FOR HOSPITAL.RONDA;
CREATE OR REPLACE PUBLIC SYNONYM GUARDIA            FOR HOSPITAL.GUARDIA;
CREATE OR REPLACE PUBLIC SYNONYM INTERNACION        FOR HOSPITAL.INTERNACION;
CREATE OR REPLACE PUBLIC SYNONYM HABITACION         FOR HOSPITAL.HABITACION;
CREATE OR REPLACE PUBLIC SYNONYM CAMA               FOR HOSPITAL.CAMA;
CREATE OR REPLACE PUBLIC SYNONYM RECORRIDO          FOR HOSPITAL.RECORRIDO;
CREATE OR REPLACE PUBLIC SYNONYM COMENTARIO         FOR HOSPITAL.COMENTARIO;
CREATE OR REPLACE PUBLIC SYNONYM POSEE              FOR HOSPITAL.POSEE;
CREATE OR REPLACE PUBLIC SYNONYM COMPUESTA_POR      FOR HOSPITAL.COMPUESTA_POR;
CREATE OR REPLACE PUBLIC SYNONYM TIENE              FOR HOSPITAL.TIENE;
CREATE OR REPLACE PUBLIC SYNONYM CUBIERTA_POR       FOR HOSPITAL.CUBIERTA_POR;
CREATE OR REPLACE PUBLIC SYNONYM AUDITORIA_GUARDIAS FOR HOSPITAL.AUDITORIA_GUARDIAS;
-- CREATE OR REPLACE PUBLIC SYNONYM SEQ_GUARDIA        FOR HOSPITAL.SEQ_GUARDIA;


-- =============================================================================
-- 5. PERMISOS DE EJECUCIÓN SOBRE STORED PROCEDURES
-- =============================================================================
GRANT EXECUTE ON HOSPITAL.sp_ocupar_cama_posee            TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.listar_camas_disponibles         TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.listar_comentarios_internacion   TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_registrar_paciente           TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_registrar_medico             TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_crear_sector                 TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_crear_habitacion_con_rondas   TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_crear_cama                   TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_registrar_internacion        TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_dar_alta_internacion         TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_obtener_datos_alta           TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_consultar_cama_actual        TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_crear_y_asignar_guardia      TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_modificar_guardia            TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_eliminar_guardia             TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_registrar_recorrido          TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_eliminar_recorrido           TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_registrar_comentario         TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_eliminar_comentario          TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_internaciones_de_recorrido   TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_listar_internaciones_activas TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_listar_pacientes             TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_obtener_foto_medico          TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_listar_medicos               TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_listar_medicos_combo         TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_listar_sectores_combo        TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_listar_sectores              TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_obtener_rondas_habitacion    TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_listar_habitaciones          TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_listar_todas_camas           TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_listar_especialidades_medico TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_verificar_medico_especialidad TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_listar_guardias              TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_obtener_datos_guardia        TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_listar_rondas_combo          TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_listar_recorridos            TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_listar_recorridos_medico     TO "44444444", "33333333";
GRANT EXECUTE ON HOSPITAL.sp_listar_comentarios_recorrido TO "44444444", "33333333";

-- =============================================================================
-- 6. SINÓNIMOS PÚBLICOS DE PROCEDIMIENTOS ALMACENADOS
-- =============================================================================
CREATE OR REPLACE PUBLIC SYNONYM sp_ocupar_cama_posee            FOR HOSPITAL.sp_ocupar_cama_posee;
CREATE OR REPLACE PUBLIC SYNONYM listar_camas_disponibles         FOR HOSPITAL.listar_camas_disponibles;
CREATE OR REPLACE PUBLIC SYNONYM listar_comentarios_internacion   FOR HOSPITAL.listar_comentarios_internacion;
CREATE OR REPLACE PUBLIC SYNONYM sp_registrar_paciente           FOR HOSPITAL.sp_registrar_paciente;
CREATE OR REPLACE PUBLIC SYNONYM sp_registrar_medico             FOR HOSPITAL.sp_registrar_medico;
CREATE OR REPLACE PUBLIC SYNONYM sp_crear_sector                 FOR HOSPITAL.sp_crear_sector;
CREATE OR REPLACE PUBLIC SYNONYM sp_crear_habitacion_con_rondas   FOR HOSPITAL.sp_crear_habitacion_con_rondas;
CREATE OR REPLACE PUBLIC SYNONYM sp_crear_cama                   FOR HOSPITAL.sp_crear_cama;
CREATE OR REPLACE PUBLIC SYNONYM sp_registrar_internacion        FOR HOSPITAL.sp_registrar_internacion;
CREATE OR REPLACE PUBLIC SYNONYM sp_dar_alta_internacion         FOR HOSPITAL.sp_dar_alta_internacion;
CREATE OR REPLACE PUBLIC SYNONYM sp_obtener_datos_alta           FOR HOSPITAL.sp_obtener_datos_alta;
CREATE OR REPLACE PUBLIC SYNONYM sp_consultar_cama_actual        FOR HOSPITAL.sp_consultar_cama_actual;
CREATE OR REPLACE PUBLIC SYNONYM sp_crear_y_asignar_guardia      FOR HOSPITAL.sp_crear_y_asignar_guardia;
CREATE OR REPLACE PUBLIC SYNONYM sp_modificar_guardia            FOR HOSPITAL.sp_modificar_guardia;
CREATE OR REPLACE PUBLIC SYNONYM sp_eliminar_guardia             FOR HOSPITAL.sp_eliminar_guardia;
CREATE OR REPLACE PUBLIC SYNONYM sp_registrar_recorrido          FOR HOSPITAL.sp_registrar_recorrido;
CREATE OR REPLACE PUBLIC SYNONYM sp_eliminar_recorrido           FOR HOSPITAL.sp_eliminar_recorrido;
CREATE OR REPLACE PUBLIC SYNONYM sp_registrar_comentario         FOR HOSPITAL.sp_registrar_comentario;
CREATE OR REPLACE PUBLIC SYNONYM sp_eliminar_comentario          FOR HOSPITAL.sp_eliminar_comentario;
CREATE OR REPLACE PUBLIC SYNONYM sp_internaciones_de_recorrido   FOR HOSPITAL.sp_internaciones_de_recorrido;
CREATE OR REPLACE PUBLIC SYNONYM sp_listar_internaciones_activas FOR HOSPITAL.sp_listar_internaciones_activas;
CREATE OR REPLACE PUBLIC SYNONYM sp_listar_pacientes             FOR HOSPITAL.sp_listar_pacientes;
CREATE OR REPLACE PUBLIC SYNONYM sp_obtener_foto_medico          FOR HOSPITAL.sp_obtener_foto_medico;
CREATE OR REPLACE PUBLIC SYNONYM sp_listar_medicos               FOR HOSPITAL.sp_listar_medicos;
CREATE OR REPLACE PUBLIC SYNONYM sp_listar_medicos_combo         FOR HOSPITAL.sp_listar_medicos_combo;
CREATE OR REPLACE PUBLIC SYNONYM sp_listar_sectores_combo        FOR HOSPITAL.sp_listar_sectores_combo;
CREATE OR REPLACE PUBLIC SYNONYM sp_listar_sectores              FOR HOSPITAL.sp_listar_sectores;
CREATE OR REPLACE PUBLIC SYNONYM sp_obtener_rondas_habitacion    FOR HOSPITAL.sp_obtener_rondas_habitacion;
CREATE OR REPLACE PUBLIC SYNONYM sp_listar_habitaciones          FOR HOSPITAL.sp_listar_habitaciones;
CREATE OR REPLACE PUBLIC SYNONYM sp_listar_todas_camas           FOR HOSPITAL.sp_listar_todas_camas;
CREATE OR REPLACE PUBLIC SYNONYM sp_listar_especialidades_medico FOR HOSPITAL.sp_listar_especialidades_medico;
CREATE OR REPLACE PUBLIC SYNONYM sp_verificar_medico_especialidad FOR HOSPITAL.sp_verificar_medico_especialidad;
CREATE OR REPLACE PUBLIC SYNONYM sp_listar_guardias              FOR HOSPITAL.sp_listar_guardias;
CREATE OR REPLACE PUBLIC SYNONYM sp_obtener_datos_guardia        FOR HOSPITAL.sp_obtener_datos_guardia;
CREATE OR REPLACE PUBLIC SYNONYM sp_listar_rondas_combo          FOR HOSPITAL.sp_listar_rondas_combo;
CREATE OR REPLACE PUBLIC SYNONYM sp_listar_recorridos            FOR HOSPITAL.sp_listar_recorridos;
CREATE OR REPLACE PUBLIC SYNONYM sp_listar_recorridos_medico     FOR HOSPITAL.sp_listar_recorridos_medico;
CREATE OR REPLACE PUBLIC SYNONYM sp_listar_comentarios_recorrido FOR HOSPITAL.sp_listar_comentarios_recorrido;
