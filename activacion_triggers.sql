set autocommit off;
-- trg_posee_fecha: cama asignada antes del inicio de la internación
-- Internación 1 inició el 15/11/2026
insert into POSEE (
    id_internacion, 
    id_habitacion, 
    nro_cama, 
    fechahora
) values (
    1,
    1,
    2,
    timestamp '2026-11-10 10:00:00'
); rollback;

-- trg_posee_fecha: cama asignada después del fin de la internación
-- primero creo una internacion finalizada
insert into INTERNACION(
    id_internacion,
    fecha_inicio,
    fecha_fin,
    numero_de_DNI,
    numero_de_matricula
) values (
    999,
    DATE '2026-11-01',
    DATE '2026-11-05',
    '22222222',
    'M103'
);
insert into POSEE (
    id_internacion, 
    id_habitacion, 
    nro_cama, 
    fechahora
) values (
    999,
    1,
    2,
    timestamp '2026-11-10 10:00:00'
); rollback;

-- trg_liberar_cama_fin_int: libera Cama 1 de Hab 1 al dar alta
update INTERNACION
set fecha_fin = DATE '2026-11-20'
where id_internacion = 1;
select id_habitacion, nro_cama, estado
from CAMA
where id_habitacion = 1 AND nro_cama = 1;
--Debe figurar libre
rollback;

-- trg_evitar_autoatencion: medico no puede atenderse a si mismo
-- DNI '11111111' es paciente y medico a la vez
insert into INTERNACION (
    fecha_inicio,
    fecha_fin,
    numero_de_DNI,
    numero_de_matricula
) values (
    DATE '2026-11-01',
    DATE '2026-11-05',
    '11111111',
    'M100'
);
rollback;

-- trg_evitar_internacion_multiple
-- paciente '11111111' tiene internacion activa desde 15-11-2026
insert into INTERNACION (
    fecha_inicio,
    
    numero_de_dni,
    numero_de_matricula
) values (
    DATE '2026-11-20',
    '11111111',
    'M101'
);
rollback;

-- trg_validar_fecha_inicio_int: fecha de inicio > sysdate error
insert into INTERNACION (
    fecha_inicio,
    numero_de_DNI,
    numero_de_matricula
) values (
    DATE '2026-11-29',
    '22222222',
    'M101'
);
rollback;

-- trg_medico_dispuesto: tira error si no esta dispuesto o no tiene especialidad
insert into GUARDIA (
    id_guardia, 
    turno, 
    fecha
) values (
    901, 
    'MAÑANA', 
    DATE '2026-12-05'
);
--M102 tiene especialidad 2 pero dispuesto = 'NO'
insert into CUBIERTA_POR (
    numero_de_matricula,
    id_especialidad,
    id_guardia
) values (
    'M102',
    2,
    901
);
--M103 no tiene especialidad 1 registrada
insert into CUBIERTA_POR (
    numero_de_matricula,
    id_especialidad,
    id_guardia
) values (
    'M103',
    1,
    901
);
rollback;

-- trg_limite_guardias: supera guardias_max al asignar en CUBIERTA_POR
-- M100 tiene guardias_max = 2 y especialidad 2 con dispuesto = 'Si'.
insert into GUARDIA (
    id_guardia, 
    turno, 
    fecha
) values (
    911, 
    'MAÑANA', 
    DATE '2027-01-01'
);
insert into GUARDIA (
    id_guardia, 
    turno, 
    fecha
) values (
    912, 
    'MAÑANA', 
    DATE '2027-01-03'
);
insert into GUARDIA (
    id_guardia, 
    turno, 
    fecha) 
values (
    913, 
    'MAÑANA', 
    DATE '2027-01-05'
);
insert into CUBIERTA_POR (
    numero_de_matricula, 
    id_especialidad, 
    id_guardia
) values (
    'M100', 
    2, 
    911
);
insert into CUBIERTA_POR (
    numero_de_matricula, 
    id_especialidad, 
    id_guardia
) values (
    'M100', 
    2, 
    912
);
insert into CUBIERTA_POR (
    numero_de_matricula, 
    id_especialidad, 
    id_guardia
) values (
    'M100', 
    2, 
    913
);
rollback;

-- trg_limite_guardias_fecha: supera guardias_max al mover fecha de GUARDIA
insert into GUARDIA (
    id_guardia, 
    turno, 
    fecha
) values (
    921, 
    'MAÑANA', 
    DATE '2027-02-01'
);
insert into GUARDIA (
    id_guardia, 
    turno, 
    fecha
) values (
    922, 
    'MAÑANA', 
    DATE '2027-02-03'
);
insert into GUARDIA (
    id_guardia, 
    turno, 
    fecha
) values (
    923, 
    'MAÑANA', 
    DATE '2027-03-05'
);
insert into CUBIERTA_POR (
    numero_de_matricula, 
    id_especialidad, 
    id_guardia
) values (
    'M100', 
    2, 
    921
);
insert into CUBIERTA_POR (
    numero_de_matricula, 
    id_especialidad, 
    id_guardia
) values (
    'M100', 
    2, 
    922
);
insert into CUBIERTA_POR (
    numero_de_matricula, 
    id_especialidad, 
    id_guardia
) values (
    'M100', 
    2, 
    923
);
update GUARDIA 
set fecha = DATE '2027-02-10' 
where id_guardia = 923; 
rollback;

-- trg_medico_en_vacaciones: asignar guardia durante vacaciones
-- M101 está de vacaciones del 15/12/2026 al 30/12/2026
insert into GUARDIA (
    id_guardia,
    turno,
    fecha
) values (
    931,
    'NOCHE',
    DATE '2026-12-20'
);
insert into CUBIERTA_POR (
    numero_de_matricula,
    id_especialidad,
    id_guardia
) values (
    'M101',
    1,
    931
);
rollback;

-- trg_evitar_guardia_superpuesta: mismo médico en igual fecha y turno
insert into GUARDIA (
    id_guardia,
    turno,
    fecha
) values (
    941,
    'MAÑANA',
    DATE '2027-04-01'
);
insert into GUARDIA (
    id_guardia,
    turno,
    fecha
) values (
    942,
    'MAÑANA',
    DATE '2027-04-01'
);
insert into CUBIERTA_POR (
    numero_de_matricula,
    id_especialidad,
    id_guardia
) values (
    'M101',
    1,
    941
);
insert into CUBIERTA_POR (
    numero_de_matricula,
    id_especialidad,
    id_guardia
) values (
    'M101',
    1,
    942
);
rollback;

-- trg_validar_cambio_guardia: superposición al modificar turno/fecha de GUARDIA
insert into GUARDIA (
    id_guardia,
    turno,
    fecha
) values (
    951,
    'MAÑANA',
    DATE '2027-05-01'
);
insert into GUARDIA (
    id_guardia,
    turno,
    fecha
) values (
    952,
    'TARDE',
    DATE '2027-05-01'
);
insert into CUBIERTA_POR (
    numero_de_matricula,
    id_especialidad,
    id_guardia
) values (
    'M101',
    1,
    951
);
insert into CUBIERTA_POR (
    numero_de_matricula,
    id_especialidad,
    id_guardia
) values (
    'M101',
    1,
    952
);
update GUARDIA
set turno = 'MAÑANA'
where id_guardia = 952;
rollback;

-- trg_validar_cambio_guardia: vacaciones al mover fecha de GUARDIA
insert into GUARDIA (
    id_guardia,
    turno,
    fecha
) values (
    953,
    'NOCHE',
    DATE '2026-12-01'
);
insert into CUBIERTA_POR (
    numero_de_matricula,
    id_especialidad,
    id_guardia
) values (
    'M101',
    1,
    953
);
update GUARDIA
set fecha = DATE '2026-12-20'
where id_guardia = 953;
rollback;

-- trg_auditoria_guardias: audita INSERT, UPDATE y DELETE en CUBIERTA_POR
insert into GUARDIA (
    id_guardia,
    turno,
    fecha
) values (
    961,
    'TARDE',
    DATE '2027-06-01'
);
insert into CUBIERTA_POR (
    numero_de_matricula,
    id_especialidad,
    id_guardia
) values (
    'M101',
    1,
    961
);
update CUBIERTA_POR
set numero_de_matricula = 'M100',
    id_especialidad = 2
where id_guardia = 961
  and numero_de_matricula = 'M101'
  and id_especialidad = 1;
delete from CUBIERTA_POR
where id_guardia = 961;
select *
from AUDITORIA_GUARDIAS
where id_guardia = 961
order by id_auditoria;
rollback;

-- trg_auditoria_guardia_update: audita UPDATE de fecha/turno en GUARDIA
insert into GUARDIA (
    id_guardia,
    turno,
    fecha
) values (
    962,
    'MAÑANA',
    DATE '2027-06-10'
);
insert into CUBIERTA_POR (
    numero_de_matricula,
    id_especialidad,
    id_guardia
) values (
    'M101',
    1,
    962
);
update GUARDIA
set turno = 'NOCHE'
where id_guardia = 962;
select *
from AUDITORIA_GUARDIAS
where id_guardia = 962
order by id_auditoria;
rollback;

-- trg_vacacion_medico_guardia: vacaciones cuando ya tiene guardia asignada
insert into GUARDIA (
    id_guardia,
    turno,
    fecha
) values (
    971,
    'MAÑANA',
    DATE '2027-07-10'
);
insert into CUBIERTA_POR (
    numero_de_matricula,
    id_especialidad,
    id_guardia
) values (
    'M100',
    2,
    971
);
insert into VACACION (
    numero_de_matricula,
    nro_vacacion,
    fecha_inicio_vac,
    fecha_fin_vac
) values (
    'M100',
    1,
    DATE '2027-07-05',
    DATE '2027-07-15'
);
rollback;
-- trg_vacacion_medico_recorrido: vacaciones cuando ya tiene recorrido asignado
-- M101 tiene recorridos #1 y #2 el 16/11/2026
insert into VACACION (
    numero_de_matricula,
    nro_vacacion,
    fecha_inicio_vac,
    fecha_fin_vac
) values (
    'M101',
    2,
    DATE '2026-11-10',
    DATE '2026-11-20'
);
rollback;
-- trg_recorrido_medico_vacaciones: médico de vacaciones en fecha del recorrido
-- 21/12/2026 es LUNES (coincide con ronda #1), pero M101 está de vacaciones (15/12..30/12)
insert into RECORRIDO (
    fecha,
    id_ronda,
    numero_de_matricula
) values (
    DATE '2026-12-21',
    1,
    'M101'
);
rollback;
-- trg_recorrido_dia_ronda: día del recorrido no coincide con el día de la ronda
-- 17/11/2026 es MARTES, pero la ronda #1 es de LUNES
insert into RECORRIDO (
    fecha,
    id_ronda,
    numero_de_matricula
) values (
    DATE '2026-11-17',
    1,
    'M101'
);
rollback;
-- trg_ronda_dia_recorridos: cambiar día de ronda que ya tiene recorridos
-- La ronda #1 (LUNES) ya tiene el recorrido #1 del 16/11/2026
update RONDA
set dia_semana = 'MARTES'
where id_ronda = 1;
rollback;
-- trg_comentario_ronda: comentario en internación ya finalizada
insert into INTERNACION (
    id_internacion,
    fecha_inicio,
    fecha_fin,
    numero_de_DNI,
    numero_de_matricula
) values (
    982,
    DATE '2026-11-01',
    DATE '2026-11-05',
    '22222222',
    'M103'
);
insert into COMENTARIO (
    contenido,
    id_internacion,
    id_recorrido
) values (
    'Prueba internación cerrada',
    982,
    1
);
rollback;
-- trg_comentario_ronda: internación sin habitación asignada en POSEE
insert into INTERNACION (
    id_internacion,
    fecha_inicio,
    fecha_fin,
    numero_de_DNI,
    numero_de_matricula
) values (
    983,
    DATE '2026-11-16',
    null,
    '55555555',
    'M103'
);
insert into COMENTARIO (
    contenido,
    id_internacion,
    id_recorrido
) values (
    'Prueba sin cama en POSEE',
    983,
    1
);
rollback;
-- trg_comentario_ronda: habitación del paciente no pertenece a la ronda
-- Internación #1 está en Hab 1; la ronda #7 (MARTES T3) solo incluye Hab 2
insert into RECORRIDO (
    id_recorrido,
    fecha,
    id_ronda,
    numero_de_matricula
) values (
    981,
    DATE '2026-11-17',
    7,
    'M101'
);
insert into COMENTARIO (
    contenido,
    id_internacion,
    id_recorrido
) values (
    'Prueba habitación fuera de ronda',
    1,
    981
);
rollback;
-- trg_normalizar_dni_persona, paciente, medico e internacion: 7 dígitos -> rellena con '0' adelante
insert into PERSONA (
    numero_de_DNI,
    nombre,
    apellido,
    rol
) values (
    '9876543',
    'Juan',
    'Perez',
    'PACIENTE'
);
insert into PACIENTE (
    numero_de_DNI,
    sexo,
    fecha_de_nacimiento
) values (
    '9876543',
    'MASCULINO',
    DATE '1995-05-10'
);
insert into MEDICO (
    numero_de_matricula,
    CUIL,
    guardias_max,
    numero_de_DNI
) values (
    'M999',
    '20098765439',
    3,
    '9876543'
);
insert into INTERNACION (
    fecha_inicio,
    fecha_fin,
    numero_de_DNI,
    numero_de_matricula
) values (
    DATE '2026-11-01',
    DATE '2026-11-03',
    '9876543',
    'M103'
);
-- Debe figurar '09876543' en las 4 tablas
select numero_de_DNI 
from PERSONA 
where numero_de_DNI = '09876543';
select numero_de_DNI 
from PACIENTE 
where numero_de_DNI = '09876543';
select numero_de_DNI 
from MEDICO 
where numero_de_matricula = 'M999';
select numero_de_DNI 
from INTERNACION 
where numero_de_DNI = '09876543';
rollback;