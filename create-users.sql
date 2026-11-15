-- =============================================================================
-- 1. CREACIÓN DEL ROL MÉDICO
-- =============================================================================
CREATE ROLE ROL_MEDICO;

-- Permiso básico para que los usuarios con este rol puedan conectarse a la BD
GRANT CREATE SESSION TO ROL_MEDICO;

-- =============================================================================
-- 2. ASIGNACIÓN DE PERMISOS DE LECTURA Y EDICIÓN SOBRE TODAS LAS TABLAS
-- (SELECT: lectura | INSERT, UPDATE, DELETE: edición)
-- =============================================================================
GRANT SELECT, INSERT, UPDATE, DELETE ON PERSONA            TO ROL_MEDICO;
GRANT SELECT, INSERT, UPDATE, DELETE ON PACIENTE           TO ROL_MEDICO;
GRANT SELECT, INSERT, UPDATE, DELETE ON MEDICO             TO ROL_MEDICO;
GRANT SELECT, INSERT, UPDATE, DELETE ON VACACION           TO ROL_MEDICO;
GRANT SELECT, INSERT, UPDATE, DELETE ON SECTOR             TO ROL_MEDICO;
GRANT SELECT, INSERT, UPDATE, DELETE ON ESPECIALIDAD       TO ROL_MEDICO;
GRANT SELECT, INSERT, UPDATE, DELETE ON RONDA              TO ROL_MEDICO;
GRANT SELECT, INSERT, UPDATE, DELETE ON GUARDIA            TO ROL_MEDICO;
GRANT SELECT, INSERT, UPDATE, DELETE ON INTERNACION        TO ROL_MEDICO;
GRANT SELECT, INSERT, UPDATE, DELETE ON HABITACION         TO ROL_MEDICO;
GRANT SELECT, INSERT, UPDATE, DELETE ON CAMA               TO ROL_MEDICO;
GRANT SELECT, INSERT, UPDATE, DELETE ON RECORRIDO          TO ROL_MEDICO;
GRANT SELECT, INSERT, UPDATE, DELETE ON COMENTARIO         TO ROL_MEDICO;
GRANT SELECT, INSERT, UPDATE, DELETE ON POSEE              TO ROL_MEDICO;
GRANT SELECT, INSERT, UPDATE, DELETE ON COMPUESTA_POR      TO ROL_MEDICO;
GRANT SELECT, INSERT, UPDATE, DELETE ON TIENE              TO ROL_MEDICO;
GRANT SELECT, INSERT, UPDATE, DELETE ON CUBIERTA_POR       TO ROL_MEDICO;
GRANT SELECT, INSERT, UPDATE, DELETE ON AUDITORIA_GUARDIAS TO ROL_MEDICO;

-- =============================================================================
-- 3. CREACIÓN DE LOS USUARIOS
-- =============================================================================
CREATE USER "44444444" IDENTIFIED BY Medico1234;
CREATE USER "33333333" IDENTIFIED BY Medico1234;

-- =============================================================================
-- 4. ASIGNACIÓN DEL ROL A LOS USUARIOS
-- =============================================================================
GRANT ROL_MEDICO TO "44444444";
GRANT ROL_MEDICO TO "33333333";

-- Establecer el rol como predeterminado al iniciar sesión
ALTER USER "44444444" DEFAULT ROLE ROL_MEDICO;
ALTER USER "33333333" DEFAULT ROLE ROL_MEDICO;
