-- =============================================================================
-- PRIVILEGIOS ADMINISTRATIVOS PARA EL USUARIO 'HOSPITAL'
-- Ejecutar conectado como SYSTEM o SYS AS SYSDBA
-- =============================================================================

-- 1. Permisos para gestionar usuarios (Crear, Modificar, Eliminar)
GRANT CREATE USER TO hospital;
GRANT ALTER USER TO hospital;
GRANT DROP USER TO hospital;

-- 2. Permiso para otorgar privilegios del sistema a otros usuarios (ej: GRANT CREATE SESSION)
GRANT GRANT ANY PRIVILEGE TO hospital;

-- 3. Permisos para crear y eliminar sinónimos públicos (CREATE PUBLIC SYNONYM)
GRANT CREATE PUBLIC SYNONYM TO hospital;
GRANT DROP PUBLIC SYNONYM TO hospital;

-- =============================================================================
-- OPCIÓN ALTERNATIVA: Rol de Administrador Completo (DBA)
-- Si estás en un entorno de desarrollo/facultad y quieres darle control total:
-- =============================================================================
-- GRANT DBA TO hospital;
