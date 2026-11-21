insert into persona (
   numero_de_dni,
   nombre,
   apellido,
   rol
) values
   ( '11111111',
     'Micaela',
     'Green',
     'PACIENTE' );
insert into persona (
   numero_de_dni,
   nombre,
   apellido,
   rol
) values
   ( '22222222',
     'Milagros',
     'Gotthelf',
     'PACIENTE' );
insert into persona (
   numero_de_dni,
   nombre,
   apellido,
   rol
) values
   ( '33333333',
     'Tomas',
     'Frickmann',
     null );
insert into persona (
   numero_de_dni,
   nombre,
   apellido,
   rol
) values
   ( '44444444',
     'Octavio',
     'Esteban',
     null );
insert into persona (
   numero_de_dni,
   nombre,
   apellido,
   rol
) values
   ( '55555555',
     'Lautaro',
     'Goni',
     'PACIENTE' );
insert into persona (
   numero_de_dni,
   nombre,
   apellido,
   rol
) values
   ( '66666666',
     'Luciano',
     'Julachis',
     'PACIENTE' );
insert into persona (
   numero_de_dni,
   nombre,
   apellido,
   rol
) values
   ( '77777777',
     'Emilia',
     'La Grasta',
     null );
insert into persona (
   numero_de_dni,
   nombre,
   apellido,
   rol
) values
   ( '88888888',
     'Laura',
     'Tolaba',
     null );


insert into paciente (
   numero_de_dni,
   sexo,
   fecha_de_nacimiento
) values
   ( '11111111',
     'FEMENINO',
     to_date('2003-11-25','YYYY-MM-DD') );
insert into paciente (
   numero_de_dni,
   sexo,
   fecha_de_nacimiento
) values
   ( '22222222',
     'FEMENINO',
     to_date('2004-06-25','YYYY-MM-DD') );
insert into paciente (
   numero_de_dni,
   sexo,
   fecha_de_nacimiento
) values
   ( '55555555',
     'MASCULINO',
     to_date('2002-08-30','YYYY-MM-DD') );
insert into paciente (
   numero_de_dni,
   sexo,
   fecha_de_nacimiento
) values
   ( '66666666',
     'MASCULINO',
     to_date('2001-12-12','YYYY-MM-DD') );

-- Caso para probar que el trigger evite que se atienda a sí mismo si fuera paciente y médico a la vez:
insert into medico (
   numero_de_matricula,
   cuil,
   guardias_max,
   numero_de_dni
) values
   ( 'M100',
     '27111111119',
     2,
     '11111111' );
insert into medico (
   numero_de_matricula,
   cuil,
   guardias_max,
   numero_de_dni
) values
   ( 'M101',
     '20333333339',
     5,
     '33333333' );
insert into medico (
   numero_de_matricula,
   cuil,
   guardias_max,
   numero_de_dni
) values
   ( 'M102',
     '20444444449',
     1,
     '44444444' );
insert into medico (
   numero_de_matricula,
   cuil,
   guardias_max,
   numero_de_dni
) values
   ( 'M103',
     '27777777779',
     5,
     '77777777' );
insert into medico (
   numero_de_matricula,
   cuil,
   guardias_max,
   numero_de_dni
) values
   ( 'M104',
     '27888888889',
     1,
     '88888888' );


insert into sector ( nombre ) values
   ( 'Terapia Intensiva' );
insert into sector ( nombre ) values
   ( 'Pediatría' );


insert into ronda (
   turno,
   dia_semana
) values
   ( 1,
     'LUNES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 2,
     'LUNES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 3,
     'LUNES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 4,
     'LUNES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 1,
     'MARTES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 2,
     'MARTES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 3,
     'MARTES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 4,
     'MARTES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 1,
     'MIERCOLES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 2,
     'MIERCOLES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 3,
     'MIERCOLES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 4,
     'MIERCOLES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 1,
     'JUEVES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 2,
     'JUEVES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 3,
     'JUEVES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 4,
     'JUEVES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 1,
     'VIERNES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 2,
     'VIERNES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 3,
     'VIERNES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 4,
     'VIERNES' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 1,
     'SABADO' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 2,
     'SABADO' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 3,
     'SABADO' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 4,
     'SABADO' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 1,
     'DOMINGO' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 2,
     'DOMINGO' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 3,
     'DOMINGO' );
insert into ronda (
   turno,
   dia_semana
) values
   ( 4,
     'DOMINGO' );

insert into habitacion (
   orientacion,
   piso,
   id_sector
) values
   ( 'NORTE',
     '1',
     1 );
insert into habitacion (
   orientacion,
   piso,
   id_sector
) values
   ( 'SUR',
     '2',
     2 );
insert into compuesta_por (
   id_ronda,
   id_habitacion
) values
   ( 1,
     1 );
insert into compuesta_por (
   id_ronda,
   id_habitacion
) values
   ( 6,
     1 );
insert into compuesta_por (
   id_ronda,
   id_habitacion
) values
   ( 11,
     1 );
insert into compuesta_por (
   id_ronda,
   id_habitacion
) values
   ( 16,
     1 );
insert into compuesta_por (
   id_ronda,
   id_habitacion
) values
   ( 17,
     1 );
insert into compuesta_por (
   id_ronda,
   id_habitacion
) values
   ( 22,
     1 );
insert into compuesta_por (
   id_ronda,
   id_habitacion
) values
   ( 27,
     1 );
insert into compuesta_por (
   id_ronda,
   id_habitacion
) values
   ( 2,
     1 );
insert into compuesta_por (
   id_ronda,
   id_habitacion
) values
   ( 2,
     2 );
insert into compuesta_por (
   id_ronda,
   id_habitacion
) values
   ( 7,
     2 );
insert into compuesta_por (
   id_ronda,
   id_habitacion
) values
   ( 12,
     2 );
insert into compuesta_por (
   id_ronda,
   id_habitacion
) values
   ( 15,
     2 );
insert into compuesta_por (
   id_ronda,
   id_habitacion
) values
   ( 18,
     2 );
insert into compuesta_por (
   id_ronda,
   id_habitacion
) values
   ( 23,
     2 );
insert into compuesta_por (
   id_ronda,
   id_habitacion
) values
   ( 28,
     2 );



insert into cama (
   id_habitacion,
   nro_cama,
   estado
) values
   ( 1,
     1,
     'OCUPADA' );
insert into cama (
   id_habitacion,
   nro_cama,
   estado
) values
   ( 1,
     2,
     'LIBRE' );
insert into cama (
   id_habitacion,
   nro_cama,
   estado
) values
   ( 2,
     1,
     'LIBRE' );


insert into vacacion (
   numero_de_matricula,
   nro_vacacion,
   fecha_inicio_vac,
   fecha_fin_vac
) values
   ( 'M101',
     1,
     to_date('2026-12-15','YYYY-MM-DD'),
     to_date('2026-12-30','YYYY-MM-DD') );

insert into vacacion (
   numero_de_matricula,
   nro_vacacion,
   fecha_inicio_vac,
   fecha_fin_vac
) values
   ( 'M102',
     1,
     to_date('2026-11-15','YYYY-MM-DD'),
     to_date('2026-11-30','YYYY-MM-DD') );


insert into internacion (
   fecha_inicio,
   numero_de_dni,
   numero_de_matricula
) values
   ( to_date('2026-11-15','YYYY-MM-DD'),
     '11111111',
     'M103' );

-- Caso de prueba del TRIGGER trg_evitar_autoatencion (descomentar para probar que rechaza la autoatencion)
-- INSERT INTO INTERNACION (fecha_inicio, numero_de_DNI, numero_de_matricula) VALUES (SYSDATE - 1, '11111111', 'M100');

-- Caso de prueba del TRIGGER trg_validar_fecha_inicio_int (descomentar para probar que rechaza fecha futura mayor a SYSDATE)
-- INSERT INTO INTERNACION (fecha_inicio, numero_de_DNI, numero_de_matricula) VALUES (SYSDATE + 1, '22222222', 'M103');

-- Caso de prueba del TRIGGER trg_medico_internacion_vacaciones (descomentar para probar que rechaza internación si el médico está de vacaciones, debe arrojar error ORA-20048)
-- INSERT INTO INTERNACION (fecha_inicio, numero_de_DNI, numero_de_matricula) VALUES (SYSDATE - 2, '22222222', 'M102');

insert into posee (
   id_internacion,
   id_habitacion,
   nro_cama,
   fechahora
) values
   ( 1,
     1,
     1,
     systimestamp - interval '4' day );




insert into recorrido (
   fecha,
   id_ronda,
   numero_de_matricula
) values
   ( sysdate - 2,
     1,
     'M101' );
insert into recorrido (
   fecha,
   id_ronda,
   numero_de_matricula
) values
   ( sysdate - 1,
     2,
     'M101' );


insert into comentario (
   contenido,
   id_internacion,
   id_recorrido
) values
   ( 'El paciente presenta leve mejoría.',
     1,
     1 );
insert into comentario (
   contenido,
   id_internacion,
   id_recorrido
) values
   ( 'Estudios normales, listo para el alta mañana.',
     1,
     2 );

-- Caso de prueba del TRIGGER trg_comentario_ronda (descomentar para verificar que rechaza comentario para internación cuya habitación no pertenece a la ronda del recorrido)
-- INSERT INTO COMENTARIO (contenido, id_internacion, id_recorrido) VALUES ('Prueba habitación fuera de ronda', 1, 3);


insert into especialidad ( nombre ) values
   ( 'Cardiología' );
insert into especialidad ( nombre ) values
   ( 'Cirugía General' );
insert into especialidad ( nombre ) values
   ( 'Pediatría' );
insert into tiene (
   numero_de_matricula,
   id_especialidad,
   dispuesto
) values
   ( 'M101',
     1,
     'Si' );
insert into tiene (
   numero_de_matricula,
   id_especialidad,
   dispuesto
) values
   ( 'M100',
     2,
     'Si' );
insert into tiene (
   numero_de_matricula,
   id_especialidad,
   dispuesto
) values
   ( 'M102',
     2,
     'No' );

insert into tiene (
   numero_de_matricula,
   id_especialidad,
   dispuesto
) values
   ( 'M101',
     3,
     'Si' );

-- Caso de prueba del TRIGGER trg_medico_en_vacaciones (descomentar para probar que rechaza asignar guardia en vacaciones):
-- INSERT INTO GUARDIA (id_guardia, turno, fecha) VALUES (999, 'NOCHE', TO_DATE('2026-12-20', 'YYYY-MM-DD'));
-- INSERT INTO CUBIERTA_POR (numero_de_matricula, id_especialidad, id_guardia) VALUES ('M101', 1, 999);

commit;

