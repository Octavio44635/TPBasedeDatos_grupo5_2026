-- BD taller: 8 automotores / 5 marcas /4 tipos / 5 mecanicos / 16 reparaciones

/* Pendiente Labo SQL: operaciones conjuntos */
-- Insertar Audi en tipo (solo para poder probar con elementos que existen en ambos conjuntos)
INSERT INTO tipo (nombre) VALUES ('Audi');

SELECT m.nombre 
FROM marca m
UNION -- UNION ALL (repite Audi)
-- INTERSECT (solo Audi)
-- EXCEPT (todas las marcas menos Audi)
select t.descripcion 
FROM tipo t
ORDER BY 1

/** VISTAS **/
/* automotores con descripción de tipo y marca */
-- DROP VIEW public.automotor_con_descrips;

CREATE OR REPLACE VIEW public.automotor_con_descrips
 AS
 SELECT a.id_automotor,
    a.patente,
    a.id_marca,
    a.id_tipo,
    m.nombre,
    t.descripcion
   FROM automotor a
     JOIN marca m ON a.id_marca = m.id_marca
     JOIN tipo t ON a.id_tipo = t.id_tipo;

ALTER TABLE public.automotor_con_descrips
    OWNER TO postgres;

SELECT * FROM automotor_con_descrips;


/** STORED PROCEDURES **/
/* SP Marcas Filtradas */
CREATE OR REPLACE PROCEDURE public."MarcasFiltradas"(
	IN subcadena character varying, 
	INOUT _result_cursor refcursor = 'my_cursor')
LANGUAGE plpgsql
AS $BODY$
BEGIN
  OPEN _result_cursor FOR
  SELECT m.* 
  FROM marca m
  WHERE m.nombre like concat(subcadena, '%');
END;
$BODY$;

CALL public."MarcasFiltradas"('P');
FETCH ALL FROM "my_cursor";

/** FUNCIONES **/
/* Listar TODOS los automotores y su cantidad de reparaciones (ejemplo OUTER JOIN ) */

-- De esta manera Lista SOLO los reparados
select DISTINCT id_automotor -- uso DISTINCT
from reparacion
-- Función que retorna un ResulSet (alternativa a SP)
DROP FUNCTION IF EXISTS todos_autos_cantidad_reparaciones();

CREATE OR REPLACE FUNCTION todos_autos_cantidad_reparaciones()
RETURNS TABLE(id_auto INT, patente VARCHAR(7), cant_reparaciones BIGINT)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY SELECT a.id_automotor, a.patente, count(r.id_reparacion) 
	             -- count(*) cuenta como 1 los que no tienen reparaciones
                 FROM automotor a
                 LEFT OUTER JOIN reparacion r ON a.id_automotor = r.id_automotor
                 GROUP BY a.id_automotor, a.patente
                 ORDER BY a.id_automotor;
END;
$$;

-- invocacion
SELECT * FROM todos_autos_cantidad_reparaciones();

/* Ej. 17 Labo SQL. Mostrar los mecánicos que en 2018 realizaron más cantidad de reparaciones que en 2017. // comparaciones entre subconsultas
-- Resultado: Aguero, Acosta, Gonzalez, Garcia */
/* Funcion cantidad de reparaciones en un mes */
CREATE OR REPLACE FUNCTION public.cant_repa_mecanico_anio(
	idmecanico integer,
	anio smallint)
    RETURNS bigint
    LANGUAGE 'plpgsql'
    COST 100
    VOLATILE PARALLEL UNSAFE
AS $BODY$
DECLARE 
    resultado INTEGER;
BEGIN
SELECT COUNT(*) into resultado
FROM reparacion r
WHERE r.id_mecanico = idMecanico
  AND extract(year from r.fecha_salida ) = anio;
RETURN resultado;
END;
$BODY$;

ALTER FUNCTION public.cant_repa_mecanico_anio(integer, smallint)
    OWNER TO postgres;

SELECT public.cant_repa_mecanico_anio(2,2018::SMALLINT)

-- Reusabilidad en Ej. 17 Labo SQL
SELECT m1.nombre, m1.apellido 
FROM mecanico m1 
WHERE (SELECT public.cant_repa_mecanico_anio(m1.id_mecanico,2018::SMALLINT))
      > (SELECT public.cant_repa_mecanico_anio(m1.id_mecanico,2017::SMALLINT))

/* Funcion ocupacion taller determinado dia */
-- Cambios sobre datos
SELECT id_reparacion, fecha_entrada, fecha_salida, descripcion, importe, id_automotor, id_mecanico
	FROM public.reparacion
WHERE fecha_salida < fecha_entrada;
UPDATE public.reparacion SET fecha_salida = NULL
WHERE fecha_salida < fecha_entrada

DROP FUNCTION IF EXISTS ocupacion_taller(fecha DATE);

CREATE OR REPLACE FUNCTION ocupacion_taller(fecha DATE)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE resultado BIGINT;
BEGIN
   SELECT COUNT(*) INTO resultado
   FROM reparacion r
   WHERE fecha BETWEEN r.fecha_entrada AND COALESCE(fecha_salida, CURRENT_DATE);

    RETURN resultado;
END;
$$;

-- invocacion
SELECT * FROM ocupacion_taller(CURRENT_DATE);

/** TRIGGER **/
/* Controlar ingresos reparaciones usando Funcion ocupacion taller determinado dia */
CREATE OR REPLACE FUNCTION validar_ocupacion()
    RETURNS TRIGGER AS $$
    BEGIN
        IF ocupacion_taller(NEW.fecha_entrada) + 1 > 10 THEN 
		-- mejor usar tabla parametrica (para que no falle reemplazar 2 x 10)
            RAISE EXCEPTION 'Ocupacion taller supera el cupo';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
CREATE TRIGGER before_insert_reparacion
    BEFORE INSERT ON reparacion
    FOR EACH ROW
    EXECUTE FUNCTION validar_ocupacion();

-- para prueba trigger
INSERT INTO reparacion(fecha_entrada, descripcion, id_automotor, id_mecanico, importe) VALUES
	(CURRENT_DATE, 'Prueba trigger before insert', 1, 2, 0);

/*Desarrollar un procedimiento almacenado o una función que
realice el cálculo del importe de la reparación, según las siguientes
consideraciones:
Si la diferencia de fechas es de menos de 30 días, el importe se calcula como:
cantidad de días x valor día.
Si la cantidad de días se encuentra entre 30 y 49, el importe es igual al caso
anterior con un incremento del 5%
Si la cantidad de días es mayor o igual a 50, el importe es igual al primer caso
+ 12%. 
En caso de ser tipo camión (id 1) se suma un 20%. 
En caso de ser Peugeot (id 3) o Renault (id 5) se suma un 6%.
Valor día es una variable que vale $ 1000
Aplicarla al modificar la fecha_salida de una reparación
*/
CREATE OR REPLACE FUNCTION calculo_importe_repa(fentrada DATE, fsalida DATE, idTipo INT, idMarca INT)
RETURNS REAL
LANGUAGE plpgsql
AS $$
DECLARE 
     resultado REAL;
	 valorDia REAL;
	 difDias INT;
BEGIN
    valorDia := 1000;
	difDias := fsalida - fentrada + 1;
	resultado := valorDia * difDias;
    CASE
        WHEN difDias >= 50 THEN resultado := resultado * 1.12;
		WHEN difDias >= 30 THEN resultado := resultado * 1.05;
		ELSE
    END CASE;
	IF idTipo = 1 THEN
	   resultado := resultado * 1.20;
	ELSIF idMarca = 3 OR idMarca = 5 THEN
	   resultado := resultado * 1.06;
	END IF;
	
    RETURN resultado;
END;
$$;

-- probar funcion
SELECT calculo_importe_repa(CURRENT_DATE, CURRENT_DATE, 2, 3)

CREATE OR REPLACE FUNCTION actualizar_importe_reparacion()
    RETURNS TRIGGER AS $$
	DECLARE
	   idMarca INT;
	   idTipo INT;
    BEGIN
	    SELECT a.id_tipo, a.id_marca INTO idTipo, idMarca
		FROM automotor a
		WHERE a.id_automotor = OLD.id_automotor;
		
	    NEW.importe := calculo_importe_repa(OLD.fecha_entrada, 
		                                    NEW.fecha_salida,
											idTipo, idMarca);
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

CREATE TRIGGER after_update_reparacion
    AFTER UPDATE ON reparacion
    FOR EACH ROW
    EXECUTE FUNCTION actualizar_importe_reparacion();



