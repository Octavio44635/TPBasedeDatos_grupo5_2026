GRANT CREATE USER TO hospital;
GRANT ALTER USER TO hospital;
GRANT DROP USER TO hospital;
-- 2. Permiso para otorgar privilegios del sistema a otros usuarios (ej: GRANT CREATE SESSION)
GRANT GRANT ANY PRIVILEGE TO hospital;
GRANT CREATE PUBLIC SYNONYM TO hospital;
GRANT DROP PUBLIC SYNONYM TO hospital;