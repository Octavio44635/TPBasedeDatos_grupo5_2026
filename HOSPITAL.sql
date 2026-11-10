INSERT INTO PERSONA (numero_de_DNI, nombre, apellido, rol) VALUES ('11111111', 'Micaela', 'Green', 'PACIENTE');
INSERT INTO PERSONA (numero_de_DNI, nombre, apellido, rol) VALUES ('22222222', 'Milagros', 'Gotthelf', 'PACIENTE');
INSERT INTO PERSONA (numero_de_DNI, nombre, apellido, rol) VALUES ('33333333', 'Tomas', 'Frickmann', NULL);
INSERT INTO PERSONA (numero_de_DNI, nombre, apellido, rol) VALUES ('44444444', 'Octavio', 'Esteban', NULL);
INSERT INTO PERSONA (numero_de_DNI, nombre, apellido, rol) VALUES ('55555555', 'Lautaro', 'Goni', 'PACIENTE');
INSERT INTO PERSONA (numero_de_DNI, nombre, apellido, rol) VALUES ('66666666', 'Luciano', 'Julachis', 'PACIENTE');
INSERT INTO PERSONA (numero_de_DNI, nombre, apellido, rol) VALUES ('77777777', 'Emilia', 'La Grasta', NULL);
INSERT INTO PERSONA (numero_de_DNI, nombre, apellido, rol) VALUES ('88888888', 'Laura', 'Tolaba', NULL);


INSERT INTO PACIENTE (numero_de_DNI, sexo, fecha_de_nacimiento) VALUES ('11111111', 'FEMENINO', TO_DATE('2003-11-25', 'YYYY-MM-DD'));
INSERT INTO PACIENTE (numero_de_DNI, sexo, fecha_de_nacimiento) VALUES ('22222222', 'FEMENINO', TO_DATE('2004-06-25', 'YYYY-MM-DD'));
INSERT INTO PACIENTE (numero_de_DNI, sexo, fecha_de_nacimiento) VALUES ('55555555', 'MASCULINO', TO_DATE('2002-08-30', 'YYYY-MM-DD'));
INSERT INTO PACIENTE (numero_de_DNI, sexo, fecha_de_nacimiento) VALUES ('66666666', 'MASCULINO', TO_DATE('2001-12-12', 'YYYY-MM-DD'));

INSERT INTO MEDICO (numero_de_matricula, CUIL, guardias_max, numero_de_DNI) VALUES ('M100', '27111111119', 2, '11111111'); -- Este es un caso para probar que el trigger evite que se atienda a sí mismo si fuera paciente y médico a la vez.
INSERT INTO MEDICO (numero_de_matricula, CUIL, guardias_max, numero_de_DNI) VALUES ('M101', '20333333339', 5, '33333333');
INSERT INTO MEDICO (numero_de_matricula, CUIL, guardias_max, numero_de_DNI) VALUES ('M102', '20444444449', 1, '44444444');
INSERT INTO MEDICO (numero_de_matricula, CUIL, guardias_max, numero_de_DNI) VALUES ('M103', '27777777779', 5, '77777777');
INSERT INTO MEDICO (numero_de_matricula, CUIL, guardias_max, numero_de_DNI) VALUES ('M104', '27888888889', 1, '88888888');


INSERT INTO SECTOR (nombre) VALUES ('Terapia Intensiva');
INSERT INTO SECTOR (nombre) VALUES ('Pediatría');


INSERT INTO RONDA (turno, dia_semana) VALUES (1, 'LUNES');
INSERT INTO RONDA (turno, dia_semana) VALUES (2, 'LUNES');
INSERT INTO RONDA (turno, dia_semana) VALUES (3, 'LUNES');
INSERT INTO RONDA (turno, dia_semana) VALUES (4, 'LUNES');
INSERT INTO RONDA (turno, dia_semana) VALUES (1, 'MARTES');
INSERT INTO RONDA (turno, dia_semana) VALUES (2, 'MARTES');
INSERT INTO RONDA (turno, dia_semana) VALUES (3, 'MARTES');
INSERT INTO RONDA (turno, dia_semana) VALUES (4, 'MARTES');
INSERT INTO RONDA (turno, dia_semana) VALUES (1, 'MIERCOLES');
INSERT INTO RONDA (turno, dia_semana) VALUES (2, 'MIERCOLES');
INSERT INTO RONDA (turno, dia_semana) VALUES (3, 'MIERCOLES');
INSERT INTO RONDA (turno, dia_semana) VALUES (4, 'MIERCOLES');
INSERT INTO RONDA (turno, dia_semana) VALUES (1, 'JUEVES');
INSERT INTO RONDA (turno, dia_semana) VALUES (2, 'JUEVES');
INSERT INTO RONDA (turno, dia_semana) VALUES (3, 'JUEVES');
INSERT INTO RONDA (turno, dia_semana) VALUES (4, 'JUEVES');
INSERT INTO RONDA (turno, dia_semana) VALUES (1, 'VIERNES');
INSERT INTO RONDA (turno, dia_semana) VALUES (2, 'VIERNES');
INSERT INTO RONDA (turno, dia_semana) VALUES (3, 'VIERNES');
INSERT INTO RONDA (turno, dia_semana) VALUES (4, 'VIERNES');
INSERT INTO RONDA (turno, dia_semana) VALUES (1, 'SABADO');
INSERT INTO RONDA (turno, dia_semana) VALUES (2, 'SABADO');
INSERT INTO RONDA (turno, dia_semana) VALUES (3, 'SABADO');
INSERT INTO RONDA (turno, dia_semana) VALUES (4, 'SABADO');
INSERT INTO RONDA (turno, dia_semana) VALUES (1, 'DOMINGO');
INSERT INTO RONDA (turno, dia_semana) VALUES (2, 'DOMINGO');
INSERT INTO RONDA (turno, dia_semana) VALUES (3, 'DOMINGO');
INSERT INTO RONDA (turno, dia_semana) VALUES (4, 'DOMINGO');

INSERT INTO HABITACION (orientacion, piso, id_sector) VALUES ('NORTE', '1', 1);
INSERT INTO HABITACION (orientacion, piso, id_sector) VALUES ('SUR', '2', 2);
INSERT INTO COMPUESTA_POR (id_ronda, id_habitacion) VALUES (1, 1);
INSERT INTO COMPUESTA_POR (id_ronda, id_habitacion) VALUES (6, 1);
INSERT INTO COMPUESTA_POR (id_ronda, id_habitacion) VALUES (11, 1);
INSERT INTO COMPUESTA_POR (id_ronda, id_habitacion) VALUES (16, 1);
INSERT INTO COMPUESTA_POR (id_ronda, id_habitacion) VALUES (17, 1);
INSERT INTO COMPUESTA_POR (id_ronda, id_habitacion) VALUES (22, 1);
INSERT INTO COMPUESTA_POR (id_ronda, id_habitacion) VALUES (27, 1);
INSERT INTO COMPUESTA_POR (id_ronda, id_habitacion) VALUES (2, 2);
INSERT INTO COMPUESTA_POR (id_ronda, id_habitacion) VALUES (7, 2);
INSERT INTO COMPUESTA_POR (id_ronda, id_habitacion) VALUES (12,2);
INSERT INTO COMPUESTA_POR (id_ronda, id_habitacion) VALUES (15,2);
INSERT INTO COMPUESTA_POR (id_ronda, id_habitacion) VALUES (18,2);
INSERT INTO COMPUESTA_POR (id_ronda, id_habitacion) VALUES (23,2);
INSERT INTO COMPUESTA_POR (id_ronda, id_habitacion) VALUES (28,2);



INSERT INTO CAMA (id_habitacion, nro_cama, estado) VALUES (1, 1, 'OCUPADA');
INSERT INTO CAMA (id_habitacion, nro_cama, estado) VALUES (1, 2, 'LIBRE');
INSERT INTO CAMA (id_habitacion, nro_cama, estado) VALUES (2, 1, 'LIBRE');

-- Insercion valida - Paciente Micaela Green ('11111111') atendida por el medico Octavio Esteban ('M102')
-- Debe ejecutarse con exito para que los inserts siguientes (POSEE, COMENTARIO con id_internacion = 1) funcionen
INSERT INTO INTERNACION (fecha_inicio, numero_de_DNI, numero_de_matricula) VALUES (SYSDATE - 5, '11111111', 'M102');

-- Caso de prueba del TRIGGER trg_evitar_autoatencion (descomentar para probar que rechaza la autoatencion, debe arrojar error ORA-20008)
-- INSERT INTO INTERNACION (fecha_inicio, numero_de_DNI, numero_de_matricula) VALUES (SYSDATE - 1, '11111111', 'M100');

INSERT INTO POSEE (id_internacion, id_habitacion, nro_cama, fechaHora) VALUES (1, 1, 1, SYSTIMESTAMP - INTERVAL '4' DAY);




INSERT INTO RECORRIDO (fecha, id_ronda, numero_de_matricula) VALUES (SYSDATE - 2, 1, 'M101');
INSERT INTO RECORRIDO (fecha, id_ronda, numero_de_matricula) VALUES (SYSDATE - 1, 2, 'M101');


INSERT INTO COMENTARIO (contenido, id_internacion, id_recorrido) VALUES ('El paciente presenta leve mejoría.', 1, 1);
INSERT INTO COMENTARIO (contenido, id_internacion, id_recorrido) VALUES ('Estudios normales, listo para el alta mañana.', 1, 2);


INSERT INTO ESPECIALIDAD (nombre) VALUES ('Cardiología');
INSERT INTO ESPECIALIDAD (nombre) VALUES ('Cirugía General');

INSERT INTO TIENE (numero_de_matricula, id_especialidad, dispuesto) VALUES ('M101', 1, 'Si');
INSERT INTO TIENE (numero_de_matricula, id_especialidad, dispuesto) VALUES ('M102', 2, 'No'); 

INSERT INTO GUARDIA (turno, fecha) VALUES ('MAÑANA', SYSDATE + 2);
INSERT INTO GUARDIA (turno, fecha) VALUES ('NOCHE', SYSDATE + 5);

COMMIT;
INSERT INTO CUBIERTA_POR (numero_de_matricula, id_especialidad, id_guardia) VALUES ('M101', 1, 1);
INSERT INTO VACACION (numero_de_matricula, nro_vacacion, fecha_inicio_vac, fecha_fin_vac) 
VALUES ('M101', 1, TO_DATE('2026-12-15', 'YYYY-MM-DD'), TO_DATE('2026-12-30', 'YYYY-MM-DD'));
COMMIT;