import os
import re
import tempfile
import oracledb
from dotenv import load_dotenv
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
from datetime import datetime, date

# Cargar variables de entorno desde el archivo .env (soporta ejecución desde cualquier directorio)
DIRECTORIO_APP = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(DIRECTORIO_APP, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)

# ==============================================================================
# PARSER ROBUSTO DE SCRIPTS SQL (SOPORTA ';' Y '/' DE PL/SQL)
# ==============================================================================
def limpiar_sql_fragmento(texto):
    """
    Elimina líneas de comentarios '--' y comentarios inline,
    retornando la sentencia SQL limpia.
    """
    lineas_limpias = []
    for l in texto.splitlines():
        l_str = l.strip()
        if not l_str or l_str.startswith("--"):
            continue
        en_comilla = False
        idx_comentario = -1
        for i in range(len(l)):
            if l[i] == "'":
                en_comilla = not en_comilla
            elif not en_comilla and l[i:i+2] == "--":
                idx_comentario = i
                break
        if idx_comentario != -1:
            l = l[:idx_comentario]
        if l.strip():
            lineas_limpias.append(l)
    return "\n".join(lineas_limpias).strip()

def parsear_script_sql(contenido):
    """
    Separa correctamente un script de Oracle que contiene:
    - Sentencias DDL/DML normales terminadas en ';'
    - Bloques PL/SQL (TRIGGER, PROCEDURE, FUNCTION) delimitados por '/'
    """
    # Eliminar comentarios multilínea /* ... */ para evitar ORA-01742 y ORA-00900
    contenido = re.sub(r'/\*.*?\*/', '', contenido, flags=re.DOTALL)

    bloques = []
    lineas = contenido.splitlines()
    buffer = []
    en_plsql = False

    for linea in lineas:
        linea_strip = linea.strip()

        linea_up = linea_strip.upper()

        # Ignorar comentarios y comandos de cliente SQL*Plus cuando no estamos dentro de un bloque PL/SQL
        if not en_plsql and (not linea_strip or linea_strip.startswith("--") or linea_up.startswith(("SET ", "PROMPT", "SHOW ", "SPOOL ", "WHENEVER "))):
            continue
        if any(linea_up.startswith(k) for k in [
            "CREATE OR REPLACE TRIGGER", "CREATE TRIGGER",
            "CREATE OR REPLACE PROCEDURE", "CREATE PROCEDURE",
            "CREATE OR REPLACE FUNCTION", "CREATE FUNCTION",
            "DECLARE", "BEGIN"
        ]):
            en_plsql = True

        if en_plsql:
            if linea_strip == "/":
                bloque_sql = "\n".join(buffer).strip()
                if bloque_sql:
                    bloques.append(bloque_sql)
                buffer = []
                en_plsql = False
            else:
                buffer.append(linea)
        else:
            buffer.append(linea)
            if ";" in linea:
                texto = "\n".join(buffer)
                partes = texto.split(";")
                for p in partes[:-1]:
                    p_limpio = limpiar_sql_fragmento(p)
                    if p_limpio:
                        bloques.append(p_limpio)
                resto = partes[-1].strip()
                buffer = [resto] if resto else []

    if buffer:
        resto_final = "\n".join(buffer).strip()
        if resto_final and resto_final != "/":
            for p in resto_final.split(";"):
                p_limpio = limpiar_sql_fragmento(p)
                if p_limpio:
                    bloques.append(p_limpio)

    return bloques

# ==============================================================================
# TRADUCTOR DE ERRORES DE ORACLE A LENGUAJE HUMANO (REGLAS DE NEGOCIO, CHECKS, FKs)
# ==============================================================================
def traducir_error_oracle(error, incluir_tecnico=False, contexto=None):
    """
    Analiza la excepción de Oracle y devuelve una explicación en lenguaje humano.
    Si incluir_tecnico es False (por defecto, para popups y cuadros de diálogo), únicamente muestra
    'REGLA DE NEGOCIO VIOLADA: <MOTIVO>' y la explicación humana sin nombres de triggers ni detalles técnicos.
    Si incluir_tecnico es True (para la terminal del front / log inferior), agrega el detalle técnico al final.
    """
    mensaje_original = str(error)
    codigo_oracle = None

    if isinstance(error, oracledb.DatabaseError):
        try:
            error_obj, = error.args
            codigo_oracle = error_obj.code
            mensaje_original = error_obj.message
        except Exception:
            pass

    mensaje_original = re.sub(r'\s*Help:\s*https?://\S+', '', mensaje_original, flags=re.IGNORECASE).strip()
    mensaje_mayus = mensaje_original.upper()

    titulo = None
    explicacion = None

    # --------------------------------------------------------------------------
    # 1. ERRORES LANZADOS POR TRIGGERS DEL PROYECTO (RAISE_APPLICATION_ERROR)
    # --------------------------------------------------------------------------
    if "20008" in mensaje_mayus or "AUTOATENCION" in mensaje_mayus or "AUTO-ATENCION" in mensaje_mayus or "AUTOATENCIÓN" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: UN MÉDICO NO PUEDE AUTO-ATENDERSE"
        explicacion = (
            "El médico asignado tiene el mismo número de DNI que el paciente internado.\n"
            "Por regla de ética y control médico del hospital, un médico no puede ser el profesional a cargo de su propia internación."
        )
    elif "20010" in mensaje_mayus or "UQ_PACIENTE_INT_ACTIVA" in mensaje_mayus or "INTERNACION_MULTIPLE" in mensaje_mayus or "INTERNACION ACTIVA" in mensaje_mayus or "INTERNACIÓN ACTIVA" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: PACIENTE CON INTERNACIÓN ACTIVA"
        explicacion = (
            "El paciente ya cuenta con una internación en curso sin fecha de alta médica.\n"
            "Por regla del hospital, no se puede registrar una nueva internación para un paciente que ya se encuentra actualmente internado."
        )
    elif "20054" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: INTERNACIÓN SUPERPUESTA CON OTRA DEL PACIENTE"
        explicacion = (
            "Las fechas ingresadas para la internación se superponen con otra internación ya registrada para ese paciente.\n"
            "Verificá que la fecha de inicio y de fin no invadan el período de otra internación existente."
        )
    elif "20055" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: DÍA DEL RECORRIDO NO COINCIDE CON LA RONDA"
        explicacion = (
            "La fecha ingresada para el recorrido corresponde a un día de la semana distinto al configurado en la ronda seleccionada.\n"
            "Seleccioná una fecha que coincida con el día de la ronda o elegí una ronda correspondiente a ese día."
        )
    elif "20056" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: RONDA CON RECORRIDOS EN OTRO DÍA"
        explicacion = (
            "No se puede cambiar el día de la semana de la ronda porque ya existen recorridos registrados en otra fecha/día para esa ronda."
        )
    elif "20011" in mensaje_mayus or "FECHA_INICIO" in mensaje_mayus or "VALIDAR_FECHA_INICIO" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: FECHA DE INICIO EN EL FUTURO"
        explicacion = (
            "La fecha de inicio de la internación no puede ser mayor a la fecha actual del sistema (SYSDATE).\n"
            "Por regla del hospital, no se pueden registrar internaciones con fecha futura."
        )
    elif "20012" in mensaje_mayus or "INTERNACIÓN FINALIZADA" in mensaje_mayus or "INTERNACION FINALIZADA" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: INTERNACIÓN FINALIZADA"
        explicacion = (
            "No se pueden agregar comentarios ni evoluciones médicas a una internación que ya ha sido finalizada con alta médica."
        )
    elif "20013" in mensaje_mayus or "SIN HABITACIÓN" in mensaje_mayus or "SIN HABITACION" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: PACIENTE SIN HABITACIÓN ASIGNADA"
        explicacion = (
            "La internación indicada no cuenta con un registro de habitación y cama asignada en POSEE."
        )
    elif "20014" in mensaje_mayus or "ESTÉN EN SU RONDA" in mensaje_mayus or "ESTEN EN SU RONDA" in mensaje_mayus or "RONDA DEL RECORRIDO" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: HABITACIÓN FUERA DE LA RONDA"
        explicacion = (
            "La habitación actual del paciente no forma parte de la ronda asignada a este recorrido médico.\n"
            "Por regla hospitalaria, solo se pueden registrar comentarios de internaciones cuyas habitaciones estén comprendidas en la ronda del recorrido."
        )
    elif "TRG_EVITAR_GUARDIA_SUPERPUESTA" in mensaje_mayus and (codigo_oracle == 1403 or "01403" in mensaje_mayus or "NO DATA FOUND" in mensaje_mayus or "NO SE HA ENCONTRADO" in mensaje_mayus):
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: ERROR EN CABECERA DE GUARDIA"
        explicacion = (
            "La transacción del disparador no pudo encontrar la cabecera de la guardia (ORA-01403: No se ha encontrado ningún dato).\n"
            "Esto ocurre cuando la cabecera de la guardia no está confirmada (COMMIT) en la BD antes de insertar en CUBIERTA_POR."
        )
    elif "20015" in mensaje_mayus or "GUARDIA_SUPERPUESTA" in mensaje_mayus or "GUARDIA EN LA MISMA FECHA" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: GUARDIA SUPERPUESTA PARA EL MÉDICO"
        explicacion = (
            "El médico ya tiene asignada otra guardia en la misma fecha y turno.\n"
            "Por regla hospitalaria y límite laboral, un médico no puede estar cubriendo dos guardias en el mismo turno del mismo día."
        )
    elif "20016" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: HABITACIÓN INEXISTENTE"
        explicacion = "La habitación seleccionada no existe en la base de datos del hospital."
    elif "20017" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: CAMA INEXISTENTE"
        explicacion = "La habitación o cama seleccionada no existe en la base de datos."
    elif "20018" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: INTERNACIÓN NO ENCONTRADA"
        explicacion = "El ID de internación ingresado no corresponde a ninguna internación registrada en el hospital."
    elif "20019" in mensaje_mayus or "YA SE ENCUENTRA OCUPADA" in mensaje_mayus or "NO ESTÁ DISPONIBLE" in mensaje_mayus or "NO ESTA DISPONIBLE" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: CAMA NO DISPONIBLE"
        explicacion = (
            "La cama seleccionada no se encuentra disponible (ya está asignada u ocupada por otro paciente).\n"
            "Por regla de gestión hospitalaria, no se puede internar ni trasladar a un paciente a una cama que no esté en estado LIBRE."
        )
    elif "20020" in mensaje_mayus or "MISMA CAMA" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: PACIENTE YA ASIGNADO A ESTA CAMA"
        explicacion = "El paciente ya se encuentra actualmente en esa misma habitación y cama. Selecciona una cama diferente para el traslado."
    elif "20049" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: MÉDICO CON GUARDIAS ASIGNADAS"
        explicacion = (
            "No se pueden registrar vacaciones para el médico porque tiene una o más guardias asignadas durante ese período.\n"
            "Debe reasignar o eliminar las guardias antes de iniciar su período de vacaciones."
        )
    elif "20052" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: MÉDICO DE VACACIONES EN FECHA DEL RECORRIDO"
        explicacion = (
            "El médico seleccionado se encuentra de vacaciones en la fecha del recorrido.\n"
            "No se puede asignar un recorrido médico durante su período de vacaciones."
        )
    elif "20053" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: MÉDICO CON RECORRIDOS ASIGNADOS"
        explicacion = (
            "No se pueden registrar vacaciones para el médico porque tiene uno o más recorridos asignados durante ese período.\n"
            "Debe reasignar o eliminar los recorridos antes de registrar su período de vacaciones."
        )
    elif "20021" in mensaje_mayus or "VACACIONES" in mensaje_mayus or "PERÍODO DE VACACIONES" in mensaje_mayus or "PERIODO DE VACACIONES" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: MÉDICO DE VACACIONES"
        explicacion = (
            "El médico seleccionado se encuentra de vacaciones en la fecha programada para la guardia.\n"
            "Por normativa laboral y descanso médico obligatorio, no se pueden asignar guardias a profesionales durante su período de vacaciones."
        )
    elif "20001" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: FECHA DE CAMA ANTERIOR A INTERNACIÓN"
        explicacion = (
            "La fecha y hora en que se asigna la cama no puede ser anterior a la fecha en que inició la internación."
        )
    elif "20002" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: FECHA DE CAMA POSTERIOR A ALTA"
        explicacion = (
            "La asignación de cama no puede tener una fecha posterior al momento en que el paciente recibió el alta médica."
        )
    elif "20003" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: MÉDICO NO DISPUESTO A GUARDIA"
        explicacion = (
            "En la tabla TIENE se registró que este médico NO está dispuesto a realizar guardias para esta especialidad."
        )
    elif "20047" in mensaje_mayus or ("TRG_MEDICO_DISPUESTO" in mensaje_mayus and (codigo_oracle == 1403 or "01403" in mensaje_mayus)) or "NO TIENE REGISTRADA" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: ESPECIALIDAD NO REGISTRADA PARA EL MÉDICO"
        explicacion = (
            "El médico seleccionado no tiene registrada esa especialidad en la tabla TIENE, por lo que no puede cubrirla en una guardia."
        )
    elif "20005" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: LÍMITE DE GUARDIAS MENSUALES SUPERADO"
        explicacion = (
            "El médico ya alcanzó o superó la cantidad máxima de guardias que indicó estar dispuesto a realizar en este mes."
        )
    elif "20006" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: ROL INVÁLIDO PARA GUARDIA MÉDICA"
        explicacion = (
            "No se puede asignar una guardia médica a una persona que en el sistema está registrada con el rol de 'PACIENTE'."
        )
    elif "20007" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: INFORMACIÓN PERSONAL DEL MÉDICO NO ENCONTRADA"
        explicacion = (
            "No se encontró la persona asociada a la matrícula médica al intentar validar la guardia."
        )
    elif "20060" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: DATOS OBLIGATORIOS DE ESPECIALIDAD"
        explicacion = "La matrícula del médico y la especialidad son obligatorias para registrar en la tabla TIENE."
    elif "20061" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: VALOR INVÁLIDO DE DISPONIBILIDAD"
        explicacion = "El campo 'dispuesto' solo puede tomar el valor 'Si' o 'No'."

    # --------------------------------------------------------------------------
    # 2. TRIGGER INVÁLIDO O ERROR DE COMPILACIÓN (ORA-04098)
    # --------------------------------------------------------------------------
    elif codigo_oracle == 4098 or "ORA-04098" in mensaje_mayus:
        titulo = "❌ ERROR EN DISPARADOR DE BASE DE DATOS"
        explicacion = (
            "Uno de los disparadores (triggers) de la base de datos se compiló con errores de sintaxis y quedó en estado INVÁLIDO.\n"
            "• Causa típica: El script SQL se ejecutó cortando el código por ';' en lugar de compilarse completo con la barra '/'.\n"
            "• Solución: Haz clic en el botón 'Crear/Reiniciar Tablas' para que la app recompile todos los triggers con el delimitador '/' correcto."
        )

    # --------------------------------------------------------------------------
    # 3. REGLAS CHECK ESPECÍFICAS (ORA-02290)
    # --------------------------------------------------------------------------
    elif "CHK_MEDICO_CUIL_DNI" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: EL CUIL NO COINCIDE CON EL DNI DEL MÉDICO"
        explicacion = (
            "Los 8 dígitos del medio del CUIL (posiciones 3 a 10) deben ser exactamente iguales al DNI del médico.\n"
            "• Ejemplo: Si el DNI es '38123456', el CUIL debe ser '20381234563' o '27381234564'."
        )
    elif "CHK_PERSONA_DNI_NUM" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: DNI CON FORMATO INVÁLIDO"
        explicacion = (
            "El número de DNI debe contener únicamente dígitos numéricos (7 u 8 dígitos).\n"
            "• Si tiene 7 dígitos, el sistema lo completa con un '0' adelante automáticamente."
        )
    elif "CHK_MEDICO_CUIL_NUM" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: CUIL CON FORMATO INVÁLIDO"
        explicacion = "El CUIL del médico debe contener exactamente 11 dígitos numéricos (sin guiones ni letras)."
    elif "CHK_TIENE_DISPUESTO" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: VALOR DE DISPONIBILIDAD INVÁLIDO"
        explicacion = "El campo 'dispuesto' de la especialidad solo puede tomar los valores 'Si' o 'No'."
    elif "CHK_PACIENTE_SEXO" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: SEXO DEL PACIENTE NO VÁLIDO"
        explicacion = "El sistema solo permite registrar los valores 'MASCULINO', 'FEMENINO' u 'OTRO'."
    elif "CHK_HABITACION_ORIENTACION" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: ORIENTACIÓN DE HABITACIÓN NO VÁLIDA"
        explicacion = "La orientación de la habitación solo puede ser 'Norte', 'Sur', 'Este' u 'Oeste'."
    elif "CHK_CAMA_NRO" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: NÚMERO DE CAMA INVÁLIDO"
        explicacion = "El número de cama debe ser un número entero mayor o igual a 1 (no se permiten números negativos ni la cama 0)."
    elif "CHK_CAMA_ESTADO" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: ESTADO DE CAMA INVÁLIDO"
        explicacion = "Una cama en el hospital solo puede estar en estado 'LIBRE' u 'OCUPADA'."
    elif "CHK_GUARDIAS_MAX" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: CANTIDAD DE GUARDIAS NO PERMITIDA"
        explicacion = "Las guardias máximas mensuales que un médico puede aceptar deben ser un número mayor o igual a 0."
    elif "CHK_RONDA_TURNO" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: TURNO DE RONDA NO VÁLIDO"
        explicacion = "El turno asignado no es válido. Los turnos permitidos son 1, 2, 3 o 4."
    elif "CHK_RONDA_DIA" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: DÍA DE LA SEMANA INVÁLIDO"
        explicacion = "El día de la ronda debe ser válido (LUNES a DOMINGO)."
    elif "CHK_INTERNACION_FECHAS" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: FECHAS DE INTERNACIÓN INCOHERENTES"
        explicacion = "La fecha de finalización del alta médica no puede ser anterior a la fecha en que el paciente fue internado."
    elif "CHK_VACACION_FECHAS" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: PERÍODO DE VACACIONES INVÁLIDO"
        explicacion = "La fecha de fin de vacaciones debe ser posterior a la fecha de inicio."
    elif "CHK_GUARDIA_TURNO" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: TURNO DE GUARDIA INVÁLIDO"
        explicacion = "Los turnos de guardia solo pueden ser 'MAÑANA', 'TARDE' o 'NOCHE'."

    # --------------------------------------------------------------------------
    # 4. CLAVES DUPLICADAS (ORA-00001)
    # --------------------------------------------------------------------------
    elif "PK_PERSONA" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: DNI YA REGISTRADO"
        explicacion = "Ya existe una persona registrada con ese mismo número de DNI."
    elif "PK_PACIENTE" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: PACIENTE YA REGISTRADO"
        explicacion = "Este paciente ya se encuentra dado de alta en la base de datos."
    elif "PK_MEDICO" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: MATRÍCULA MÉDICA DUPLICADA"
        explicacion = "Ya existe un médico registrado con esa misma matrícula profesional."
    elif "UQ_MEDICO_CUIL" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: CUIL DE MÉDICO DUPLICADO"
        explicacion = "Ya existe otro médico registrado con ese mismo número de CUIL."
    elif "UQ_MEDICO_DNI" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: DNI YA ASIGNADO A UN MÉDICO"
        explicacion = "Ese DNI ya está registrado como médico en el hospital."
    elif "PK_CAMA" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: CAMA YA EXISTENTE EN ESTA HABITACIÓN"
        explicacion = "Esa habitación ya tiene registrada una cama con ese mismo número."
    elif "UQ_SECTOR_NOMBRE" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: NOMBRE DE SECTOR REPETIDO"
        explicacion = "Ya existe un sector con ese mismo nombre en el hospital."
    elif "PK_COMPUESTA_POR" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: RONDA YA VINCULADA"
        explicacion = "Esta habitación ya tiene asignada esa ronda para ese día de la semana."
    elif "PK_CUBIERTA_POR" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: GUARDIA YA ASIGNADA AL MÉDICO"
        explicacion = "Este médico ya está asignado a esa guardia para esa misma especialidad."

    # --------------------------------------------------------------------------
    # 5. CLAVES FORÁNEAS (ORA-02291 - FOREIGN KEY INEXISTENTE)
    # --------------------------------------------------------------------------
    elif "FK_INTERNACION_PACIENTE" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: PACIENTE NO ENCONTRADO"
        explicacion = "El DNI ingresado no corresponde a ningún paciente registrado en la base de datos."
    elif "FK_INTERNACION_MEDICO" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: MÉDICO PRINCIPAL NO ENCONTRADO"
        explicacion = "La matrícula médica ingresada no existe en la base de datos."
    elif "FK_HABITACION_SECTOR" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: SECTOR NO ENCONTRADO"
        explicacion = "El sector seleccionado no existe en la base de datos."
    elif "FK_CAMA_HABITACION" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: HABITACIÓN NO ENCONTRADA"
        explicacion = "El ID de habitación ingresado no existe en el hospital."
    elif "FK_CUBIERTA_TIENE" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: MÉDICO SIN ESPECIALIDAD REGISTRADA"
        explicacion = "El médico seleccionado no tiene registrada esa especialidad en la tabla TIENE."
    elif "FK_CUBIERTA_GUARDIA" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: GUARDIA NO ENCONTRADA"
        explicacion = "La guardia seleccionada no existe en la base de datos."
    elif "FK_RECORRIDO_RONDA" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: RONDA NO ENCONTRADA"
        explicacion = "La ronda seleccionada para el recorrido no existe en la base de datos."
    elif "FK_RECORRIDO_MEDICO" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: MÉDICO DEL RECORRIDO NO ENCONTRADO"
        explicacion = "La matrícula médica asignada al recorrido no existe en la base de datos."
    elif "FK_COMENTARIO_INTERNACION" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: INTERNACIÓN NO ENCONTRADA"
        explicacion = "La internación indicada para el comentario no existe en la base de datos."
    elif "FK_COMENTARIO_RECORRIDO" in mensaje_mayus:
        titulo = "❌ REGLA DE NEGOCIO VIOLADA: RECORRIDO NO ENCONTRADO"
        explicacion = "El recorrido médico indicado para el comentario no existe en la base de datos."

    # --------------------------------------------------------------------------
    # 6. OTRAS REGLAS O TRIGGERS (RAISE_APPLICATION_ERROR GENÉRICO)
    # --------------------------------------------------------------------------
    elif (codigo_oracle and 20000 <= abs(codigo_oracle) <= 20999) or "ORA-20" in mensaje_mayus or "REGLA DE NEGOCIO" in mensaje_mayus:
        texto_limpio = mensaje_original
        texto_limpio = re.sub(r'ORA-20\d{3}:\s*', '', texto_limpio, flags=re.IGNORECASE)
        texto_limpio = texto_limpio.split("ORA-06512")[0].split("ORA-04088")[0].strip()
        if texto_limpio.lower().startswith("regla de negocio:"):
            texto_limpio = texto_limpio[len("regla de negocio:"):].strip()
        titulo = "❌ REGLA DE NEGOCIO VIOLADA"
        explicacion = f"{texto_limpio}"

    elif "PLS-00201" in mensaje_mayus or ("ORA-06550" in mensaje_mayus and ("SE DEBE DECLARAR" in mensaje_mayus or "MUST BE DECLARED" in mensaje_mayus)):
        m_ident = re.search(r"['\"]([a-zA-Z0-9_]+)['\"]", mensaje_original)
        nombre_obj = m_ident.group(1) if m_ident else "el procedimiento"
        titulo = "⚠️ PROCEDIMIENTO NO DECLARADO EN ORACLE"
        explicacion = (
            f"El Stored Procedure '{nombre_obj}' no está compilado en la base de datos o el usuario no tiene permisos de ejecución.\n\n"
            "Solución: Haz clic en el botón '⚡ RESET TOTAL (Tablas + Datos + Usuarios)' en la cabecera de la aplicación para compilar automáticamente todos los Stored Procedures y otorgar sus permisos."
        )

    # --------------------------------------------------------------------------
    # 7. ERRORES GENERALES
    # --------------------------------------------------------------------------
    else:
        traducciones_generales = {
            1: ("❌ REGLA DE NEGOCIO VIOLADA: DATO DUPLICADO", "Ya existe un registro con ese identificador en la base de datos."),
            2291: ("❌ REGLA DE NEGOCIO VIOLADA: DATO RELACIONADO NO ENCONTRADO", "Estás intentando asociar un dato a otra tabla que no existe previamente."),
            2292: ("❌ REGLA DE NEGOCIO VIOLADA: NO SE PUEDE ELIMINAR (REGISTROS DEPENDIENTES)", "No puedes borrar este registro porque otras tablas dependen de él."),
            2290: ("❌ REGLA DE NEGOCIO VIOLADA: REGLA DE VALIDACIÓN NO CUMPLIDA", "Uno de los valores ingresados no cumple con las restricciones permitidas del sistema."),
            1400: ("❌ REGLA DE NEGOCIO VIOLADA: CAMPO OBLIGATORIO VACÍO", "Intentaste guardar dejando en blanco un campo que es requerido obligatoriamente."),
            942: ("⚠️ TABLA NO ENCONTRADA", "La tabla especificada no existe en Oracle. Haz clic en 'Crear/Reiniciar Tablas'."),
            904: ("⚠️ COLUMNA NO VÁLIDA", "Escribiste un nombre de columna que no existe en la tabla consultada."),
            933: ("⚠️ ERROR DE SINTAXIS SQL", "La consulta SQL está mal redactada o tiene palabras clave fuera de lugar."),
            936: ("⚠️ FALTA UNA EXPRESIÓN EN EL SQL", "Falta especificar un valor, una columna o una condición en tu sentencia SQL."),
            1438: ("⚠️ NÚMERO DEMASIADO GRANDE", "El número ingresado supera los dígitos permitidos para esa columna."),
            1843: ("⚠️ FORMATO DE FECHA INCORRECTO", "El formato de fecha no es válido. Usa el formato estándar DD/MM/YYYY o YYYY-MM-DD."),
            1017: ("⚠️ ACCESO DENEGADO", "El usuario o contraseña configurado en el archivo .env es incorrecto."),
            12541: ("⚠️ BASE DE DATOS INALCANZABLE", "El servicio de Oracle no responde en el puerto 1521."),
            54: ("⚠️ RECURSO BLOQUEADO POR OTRA TRANSACCIÓN", "La fila seleccionada está siendo modificada por otra transacción activa en este momento.")
        }

        if codigo_oracle in traducciones_generales:
            titulo, explicacion = traducciones_generales[codigo_oracle]
        else:
            titulo = "⚠️ ERROR DE BASE DE DATOS"
            explicacion = f"Explicación: {mensaje_original}"

    salida = f"{titulo}:\n{explicacion}"
    if incluir_tecnico:
        salida += f"\n[Detalle técnico: {mensaje_original}]"
    return salida

# ==============================================================================
# CONEXIÓN
# ==============================================================================
def obtener_conexion(user=None, password=None):
    u = user or os.getenv('DB_USER')
    p = password or os.getenv('DB_PASS')
    dsn = os.getenv('DSN')
    conn = oracledb.connect(user=u, password=p, dsn=dsn)

    dueno = os.getenv('DB_USER')
    if dueno and u.upper() != dueno.upper():
        cur = conn.cursor()
        try:
            cur.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {dueno.strip().upper()}")
        finally:
            cur.close()
    return conn

def invocar_sp(cursor, sp_name, params):
    """
    Invoca un Stored Procedure soportando sinónimos públicos o prefijo explícito de esquema (ej: HOSPITAL.<sp>).
    """
    try:
        return cursor.callproc(sp_name, params)
    except oracledb.DatabaseError as e:
        dueno = os.getenv('DB_USER')
        msg = str(e)
        if dueno and ("PLS-00201" in msg or ("ORA-06550" in msg and sp_name.upper() in msg.upper())):
            return cursor.callproc(f"{dueno.strip().upper()}.{sp_name}", params)
        raise

# ==============================================================================
# APLICACIÓN PRINCIPAL
# ==============================================================================
class HospitalApp(tk.Tk):
    def reportar_error(self, titulo_popup, error, prefijo_log=None, parent=None):
        """
        Registra el detalle técnico completo en la terminal inferior (pantalla de abajo)
        y despliega en el popup únicamente el mensaje humano sin triggers ni códigos técnicos.
        """
        msg_humano = traducir_error_oracle(error, incluir_tecnico=False)
        msg_tecnico = traducir_error_oracle(error, incluir_tecnico=True)
        texto_log = f"{prefijo_log}:\n{msg_tecnico}" if prefijo_log else msg_tecnico
        self.log_error(texto_log)
        if parent:
            messagebox.showerror(titulo_popup, msg_humano, parent=parent)
        else:
            messagebox.showerror(titulo_popup, msg_humano)

    def __init__(self):
        super().__init__()
        self.title("Sistema Hospitalario - Gestión de Internaciones y Consultas SQL (UNMDP)")
        self.geometry("1180x820")
        self.minsize(980, 650)

        self.usuario_guardias = None
        self.password_guardias = None
        self._app_iniciada = False
        self._pestana_altas_anterior = None

        self.configurar_estilos()

        # Cabecera fija
        self.crear_cabecera()

        # Panel divisor móvil (PanedWindow) para redimensionar los logs
        self.paned_principal = ttk.PanedWindow(self, orient=tk.VERTICAL)
        self.paned_principal.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

        self.frame_superior = ttk.Frame(self.paned_principal)
        self.paned_principal.add(self.frame_superior, weight=4)

        self.frame_inferior = ttk.Frame(self.paned_principal)
        self.paned_principal.add(self.frame_inferior, weight=1)

        # Panel de logs primero
        self.crear_panel_logs(self.frame_inferior)

        # Pestañas
        self.crear_pestanas(self.frame_superior)

        self.log_info(f"Sistema iniciado correctamente. Conectado a Oracle con credenciales de .env como usuario: '{os.getenv('DB_USER')}'.")
        self.cargar_camas_libres()
        self.actualizar_combo_internaciones()
        self._app_iniciada = True

    def configurar_estilos(self):
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.COLOR_FONDO = "#EDF2F7"
        self.configure(bg=self.COLOR_FONDO)
        self.style.configure(".", background=self.COLOR_FONDO, font=("Segoe UI", 10))
        self.style.configure("TNotebook", background=self.COLOR_FONDO)
        self.style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=[12, 6])
        self.style.configure("TFrame", background=self.COLOR_FONDO)
        self.style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground="#1A365D", background=self.COLOR_FONDO)
        self.style.configure("SubHeader.TLabel", font=("Segoe UI", 9), foreground="#4A5568", background=self.COLOR_FONDO)
        self.style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#E2E8F0")

    def crear_cabecera(self):
        frame_cabecera = ttk.Frame(self, padding="12 8")
        frame_cabecera.pack(fill=tk.X)

        frame_textos = ttk.Frame(frame_cabecera)
        frame_textos.pack(side=tk.LEFT, fill=tk.Y)

        lbl_titulo = ttk.Label(frame_textos, text="🏥 Sistema de Gestión Hospitalaria", style="Header.TLabel")
        lbl_titulo.pack(anchor="w")

        frame_botones_cab = ttk.Frame(frame_cabecera)
        frame_botones_cab.pack(side=tk.RIGHT)

        self.btn_reset_total = tk.Button(
            frame_botones_cab,
            text="⚡ RESET TOTAL (Tablas + Datos + Usuarios)",
            bg="#9B2C2C",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="groove",
            cursor="hand2",
            command=self.accion_reset_total_hospital
        )
        self.btn_reset_total.pack(side=tk.LEFT, padx=5, pady=5)

    def ejecutar_archivo_sql(self, archivo, nombre_descriptivo, mostrar_popup=True):
        if not os.path.exists(archivo):
            self.log_error(f"No se encontró el archivo '{archivo}' en la carpeta del proyecto.")
            if mostrar_popup:
                messagebox.showerror("Archivo no encontrado", f"No se encontró '{archivo}'.")
            return False

        conn = None
        cursor = None
        try:
            self.log_info(f"Procesando '{archivo}' ({nombre_descriptivo}) en Oracle...")
            conn = obtener_conexion()
            cursor = conn.cursor()

            with open(archivo, "r", encoding="utf-8") as f:
                contenido = f.read()

            sentencias = parsear_script_sql(contenido)
            errores = 0
            exitos = 0
            total = len(sentencias)

            for idx, sql in enumerate(sentencias, 1):
                sql = sql.strip()
                if sql:
                    try:
                        cursor.execute(sql)
                        exitos += 1
                    except oracledb.DatabaseError as e:
                        error_obj, = e.args
                        if error_obj.code in (942, 1918):  # ORA-00942: tabla no existe, ORA-01918: usuario no existe en DROP
                            pass
                        elif error_obj.code == 1031 and "DROP USER" in sql.upper():
                            # ORA-01031: privilegios insuficientes en DROP USER si no es DBA
                            pass
                        else:
                            errores += 1
                            self.log_error(f"Sentencia con aviso [{error_obj.code}]: {sql[:40]}... -> {traducir_error_oracle(e, incluir_tecnico=True)}")

                # Mantener la ventana viva y respondiendo a Windows en tiempo real
                if idx % 3 == 0 or idx == total:
                    try:
                        self.update()
                    except Exception:
                        pass

            conn.commit()
            msg = f"{nombre_descriptivo} finalizado.\n• Exitosas: {exitos}\n• Avisos no críticos: {errores}"
            self.log_exito(msg)
            if mostrar_popup:
                messagebox.showinfo("Operación Finalizada", msg)
            self.cargar_camas_libres()
            self.refrescar_panel_guardias()
            return True

        except Exception as e:
            self.log_error(f"Error crítico al procesar '{archivo}':\n{traducir_error_oracle(e, incluir_tecnico=True)}")
            if mostrar_popup:
                messagebox.showerror("Error", traducir_error_oracle(e))
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def accion_ejecutar_script_tablas(self):
        respuesta = messagebox.askyesno(
            "Confirmar Inicialización", 
            "¿Deseas ejecutar 'create-table.sql'?\nEsto borrará (DROP) y volverá a crear todas las tablas, triggers y stored procedures en Oracle.\n\n(Además se restaurarán automáticamente los usuarios y permisos de 'create-users.sql')."
        )
        if respuesta:
            ok = self.ejecutar_archivo_sql("create-table.sql", "Creación de Esquema y Triggers", mostrar_popup=False)
            if ok:
                msg_final = "✅ Tablas, triggers y procedimientos recreados con éxito."
                if os.path.exists("create-users.sql"):
                    self.log_info("Restaurando usuarios y permisos para guardias ('create-users.sql')...")
                    ok_u = self.ejecutar_archivo_sql("create-users.sql", "Usuarios y Permisos de Guardias", mostrar_popup=False)
                    if ok_u:
                        msg_final += "\n✅ Permisos de usuarios médicos ('33333333', '44444444') restaurados correctamente."
                messagebox.showinfo("Reinicio Completo", msg_final)
                self.cargar_camas_libres()
                self.refrescar_panel_guardias()

    def accion_ejecutar_script_usuarios(self):
        respuesta = messagebox.askyesno(
            "Restaurar Usuarios y Permisos",
            "¿Deseas ejecutar 'create-users.sql'?\nEsto volverá a otorgar permisos de lectura/edición a los usuarios médicos ('33333333' y '44444444')."
        )
        if respuesta:
            self.ejecutar_archivo_sql("create-users.sql", "Usuarios y Permisos de Guardias")

    def accion_cargar_datos_hospital(self):
        respuesta = messagebox.askyesno(
            "Cargar Datos de Prueba", 
            "¿Deseas ejecutar 'HOSPITAL.sql'?\nEsto insertará los datos de prueba oficiales (personas, pacientes, médicos, camas, internaciones y guardias)."
        )
        if respuesta:
            self.ejecutar_archivo_sql("HOSPITAL.sql", "Carga de Datos de Prueba (HOSPITAL.sql)")

    def refrescar_toda_la_interfaz(self):
        """Refresca todos los listados y combos de la interfaz tras una recarga de datos."""
        try:
            self.cargar_camas_libres()
        except Exception:
            pass
        try:
            self.refrescar_panel_guardias()
        except Exception:
            pass
        try:
            if hasattr(self, 'cargar_lista_pacientes'):
                self.cargar_lista_pacientes()
        except Exception:
            pass
        try:
            if hasattr(self, 'cargar_lista_medicos'):
                self.cargar_lista_medicos()
        except Exception:
            pass
        try:
            if hasattr(self, 'cargar_lista_habitaciones'):
                self.cargar_lista_habitaciones()
        except Exception:
            pass
        try:
            if hasattr(self, 'cargar_todas_las_camas'):
                self.cargar_todas_las_camas()
        except Exception:
            pass

    def accion_reset_total_hospital(self):
        respuesta = messagebox.askyesno(
            "⚡ Reset Total de Base de Datos",
            "¿Deseas realizar un RESET COMPLETO de la Base de Datos?\n\n"
            "Esta operación ejecutará en secuencia:\n"
            "1. 'create-table.sql' (Elimina tablas viejas, crea tablas nuevas, triggers y stored procedures).\n"
            "2. 'HOSPITAL.sql' (Carga todos los datos de prueba oficiales).\n"
            "3. 'create-users.sql' (Crea usuarios '33333333' y '44444444' y les otorga todos los permisos y sinónimos).\n\n"
            "¿Deseas continuar?"
        )
        if not respuesta:
            return

        if hasattr(self, 'btn_reset_total'):
            self.btn_reset_total.config(state="disabled", text="⏳ Ejecutando Reset Total...")
            self.update()

        try:
            self.log_info("Iniciando RESET COMPLETO del Hospital (Paso 1/3: create-table.sql)...")
            ok1 = self.ejecutar_archivo_sql("create-table.sql", "1/3 Creación de Esquema y Triggers", mostrar_popup=False)
            if not ok1:
                messagebox.showerror("Error en Reset", "Falló la creación de tablas en 'create-table.sql'. Se detuvo el proceso.")
                return

            self.log_info("Continuando RESET COMPLETO (Paso 2/3: HOSPITAL.sql)...")
            ok2 = self.ejecutar_archivo_sql("HOSPITAL.sql", "2/3 Carga de Datos de Prueba", mostrar_popup=False)
            if not ok2:
                self.log_error("Hubo advertencias al cargar datos en 'HOSPITAL.sql'. Continuando con usuarios...")

            self.log_info("Continuando RESET COMPLETO (Paso 3/3: create-users.sql)...")
            ok3 = self.ejecutar_archivo_sql("create-users.sql", "3/3 Creación de Usuarios y Permisos", mostrar_popup=False)

            self.refrescar_toda_la_interfaz()

            msg_exito = (
                "🎉 ¡RESET COMPLETO FINALIZADO CON ÉXITO!\n\n"
                "✅ 1. Tablas, triggers y procedimientos recreados (create-table.sql).\n"
                "✅ 2. Datos de prueba oficiales cargados (HOSPITAL.sql).\n"
                "✅ 3. Usuarios médicos ('33333333' y '44444444') creados con todos sus permisos y sinónimos (create-users.sql).\n\n"
                "La base de datos y la interfaz están 100% listas para usar."
            )
            self.log_exito("RESET COMPLETO finalizado exitosamente. Tablas, datos y usuarios listos.")
            messagebox.showinfo("Reset Completo Exitoso", msg_exito)

        finally:
            if hasattr(self, 'btn_reset_total'):
                self.btn_reset_total.config(state="normal", text="⚡ RESET TOTAL (Tablas + Datos + Usuarios)")
                self.update()

    # --------------------------------------------------------------------------
    # PESTAÑAS PRINCIPALES
    # --------------------------------------------------------------------------
    def crear_pestanas(self, contenedor):
        self.notebook = ttk.Notebook(contenedor)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Internación y Consultas Stored Procedures
        self.tab_transaccion = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_transaccion, text=" 🔄 Internación (Transacción y Stored Procedures) ")
        self.construir_tab_transaccion()

        # Tab 2: Altas de Datos
        self.tab_altas = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_altas, text=" ➕ Carga de Datos (Pacientes, Médicos, Camas) ")
        self.construir_tab_altas()

        # Tab 3: Consola SQL
        self.tab_sql = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_sql, text=" 💻 Consola SQL en Vivo")
        self.construir_tab_sql()

    # ==========================================================================
    # TAB 1: OPERACIÓN TRANSACCIONAL Y CONSULTAS DE STORED PROCEDURES
    # ==========================================================================
    def construir_tab_transaccion(self):
        # Columna izquierda: Operaciones de Internación, Traslado y Consultas
        columna_izq = ttk.Frame(self.tab_transaccion)
        columna_izq.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10))

        # 1. Formulario: Registrar Internación Nueva
        frame_internacion = ttk.LabelFrame(columna_izq, text=" 🏥 Registrar Nueva Internación con Cama ", padding=10)
        frame_internacion.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(frame_internacion, text="DNI Paciente:").grid(row=0, column=0, sticky="w", pady=3)
        self.txt_dni = ttk.Entry(frame_internacion, width=15)
        self.txt_dni.grid(row=0, column=1, pady=3, padx=(0, 6), sticky="w")

        ttk.Label(frame_internacion, text="Matrícula Méd.:").grid(row=0, column=2, sticky="w", pady=3)
        self.txt_matricula = ttk.Entry(frame_internacion, width=13)
        self.txt_matricula.grid(row=0, column=3, pady=3, sticky="w")

        ttk.Label(frame_internacion, text="ID Habitación:").grid(row=1, column=0, sticky="w", pady=3)
        self.txt_hab = ttk.Entry(frame_internacion, width=15)
        self.txt_hab.grid(row=1, column=1, pady=3, padx=(0, 6), sticky="w")

        ttk.Label(frame_internacion, text="Cama Nro:").grid(row=1, column=2, sticky="w", pady=3)
        self.txt_cama = ttk.Entry(frame_internacion, width=13)
        self.txt_cama.grid(row=1, column=3, pady=3, sticky="w")

        ttk.Label(frame_internacion, text="Fecha Inicio:").grid(row=2, column=0, sticky="w", pady=3)
        self.txt_fecha_inicio = ttk.Entry(frame_internacion, width=15)
        self.txt_fecha_inicio.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.txt_fecha_inicio.grid(row=2, column=1, pady=3, padx=(0, 6), sticky="w")

        ttk.Label(frame_internacion, text="Fecha Fin:").grid(row=2, column=2, sticky="w", pady=3)
        self.txt_fecha_fin = ttk.Entry(frame_internacion, width=13)
        self.txt_fecha_fin.grid(row=2, column=3, pady=3, sticky="w")

        ttk.Label(frame_internacion, text="Hora Ingreso:").grid(row=3, column=0, sticky="w", pady=3)
        self.txt_hora_inicio = ttk.Entry(frame_internacion, width=15)
        self.txt_hora_inicio.insert(0, datetime.now().strftime("%H:%M"))
        self.txt_hora_inicio.grid(row=3, column=1, pady=3, padx=(0, 6), sticky="w")

        ttk.Label(
            frame_internacion,
            text="Formato: HH:MM (ej. 14:30)",
            font=("Segoe UI", 8, "italic"),
            foreground="#4A5568"
        ).grid(row=3, column=2, columnspan=2, sticky="w", pady=3)

        lbl_ayuda_fechas = ttk.Label(
            frame_internacion,
            text="Formato fechas: DD/MM/AAAA (Fecha Fin vacía = internación activa)",
            font=("Segoe UI", 8, "italic"),
            foreground="#4A5568"
        )
        lbl_ayuda_fechas.grid(row=4, column=0, columnspan=4, sticky="w", pady=(1, 4))

        btn_ejecutar = tk.Button(
            frame_internacion, 
            text="⚡ Registrar Internación (COMMIT / ROLLBACK)", 
            bg="#2B6CB0", 
            fg="white", 
            font=("Segoe UI", 9, "bold"),
            relief="groove", 
            cursor="hand2",
            command=self.accion_registrar_internacion
        )
        btn_ejecutar.grid(row=5, column=0, columnspan=4, pady=(6, 2), sticky="ew")

        # 2. Formulario: Traslado / Cambio de Cama y Alta Médica
        frame_traslado = ttk.LabelFrame(columna_izq, text=" 🔄 Gestión de Internación (Traslado / Alta Médica) ", padding=10)
        frame_traslado.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(frame_traslado, text="ID Internación:").grid(row=0, column=0, sticky="w", pady=3)
        self.txt_traslado_id_int = ttk.Combobox(frame_traslado, width=32)
        self.txt_traslado_id_int.grid(row=0, column=1, pady=3, padx=(0, 4), sticky="w")
        self.txt_traslado_id_int.bind("<<ComboboxSelected>>", self.accion_consultar_cama_actual)
        self.txt_traslado_id_int.bind("<Return>", self.accion_consultar_cama_actual)

       

        self.lbl_traslado_info = ttk.Label(
            frame_traslado, 
            text="Selecciona o escribe el ID de internación activa.", 
            font=("Segoe UI", 8, "italic"), 
            foreground="#4A5568",
            wraplength=380,
            justify="left"
        )
        self.lbl_traslado_info.grid(row=1, column=0, columnspan=4, sticky="w", pady=(1, 5))

        ttk.Label(frame_traslado, text="Nueva Hab.:").grid(row=2, column=0, sticky="w", pady=3)
        self.txt_traslado_hab = ttk.Entry(frame_traslado, width=15)
        self.txt_traslado_hab.grid(row=2, column=1, pady=3, padx=(0, 6), sticky="w")

        ttk.Label(frame_traslado, text="Nueva Cama:").grid(row=2, column=2, sticky="w", pady=3)
        self.txt_traslado_cama = ttk.Entry(frame_traslado, width=13)
        self.txt_traslado_cama.grid(row=2, column=3, pady=3, sticky="w")

        frame_botones_traslado = ttk.Frame(frame_traslado)
        frame_botones_traslado.grid(row=3, column=0, columnspan=4, pady=(6, 4), sticky="ew")

        btn_usar_cama_sel = tk.Button(
            frame_botones_traslado,
            text="📋 Usar Cama de Tabla",
            bg="#E2E8F0",
            font=("Segoe UI", 8),
            cursor="hand2",
            command=self.accion_copiar_cama_seleccionada
        )
        btn_usar_cama_sel.pack(side=tk.LEFT, padx=(0, 6))

        btn_ejecutar_traslado = tk.Button(
            frame_botones_traslado,
            text="🔀 Trasladar Paciente",
            bg="#2C7A7B",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="groove",
            cursor="hand2",
            command=self.accion_trasladar_cama
        )
        btn_ejecutar_traslado.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        ttk.Separator(frame_traslado, orient="horizontal").grid(row=4, column=0, columnspan=4, sticky="ew", pady=(8, 6))

        btn_finalizar_internacion = tk.Button(
            frame_traslado,
            text="🏁 Finalizar Internación / Alta Médica (Libera Cama)",
            bg="#9B2C2C",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="groove",
            cursor="hand2",
            command=self.accion_finalizar_internacion
        )
        btn_finalizar_internacion.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(0, 2))

        # 3. Consultar Comentarios (Stored Procedure)
        frame_sp_comentarios = ttk.LabelFrame(columna_izq, text=" 💬 Visitas Médicas y Recorridos (SP) ", padding=8)
        frame_sp_comentarios.pack(fill=tk.X)

        frame_sp_row0 = ttk.Frame(frame_sp_comentarios)
        frame_sp_row0.pack(fill=tk.X, pady=(0, 4))

        ttk.Label(frame_sp_row0, text="ID Internación:").pack(side=tk.LEFT, padx=(0, 4))
        self.txt_id_int_comentario = ttk.Entry(frame_sp_row0, width=8)
        self.txt_id_int_comentario.insert(0, "1")
        self.txt_id_int_comentario.pack(side=tk.LEFT, padx=(0, 8))

        btn_ver_sp_comentarios = tk.Button(
            frame_sp_row0,
            text="💬 Ver Visitas Médicas (SP)",
            bg="#E2E8F0",
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
            command=self.accion_consultar_comentarios_sp
        )
        btn_ver_sp_comentarios.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        frame_sp_row1 = ttk.Frame(frame_sp_comentarios)
        frame_sp_row1.pack(fill=tk.X, pady=(2, 0))

        btn_ir_rec = tk.Button(
            frame_sp_row1,
            text="🔄 Cargar Recorrido",
            bg="#EBF8FF",
            fg="#2B6CB0",
            cursor="hand2",
            font=("Segoe UI", 8, "bold"),
            command=self.ir_a_tab_recorrido
        )
        btn_ir_rec.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_ir_com = tk.Button(
            frame_sp_row1,
            text="📝 Cargar Comentario",
            bg="#F0FFF4",
            fg="#276749",
            cursor="hand2",
            font=("Segoe UI", 8, "bold"),
            command=self.ir_a_tab_comentario
        )
        btn_ir_com.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        # Panel derecho: Camas libres (Resumen por Sector + Detalle)
        frame_der = ttk.Frame(self.tab_transaccion)
        frame_der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 1. Resumen: Cantidad de camas libres por sector (Requerimiento SP)
        frame_resumen = ttk.LabelFrame(frame_der, text=" 📊 Cantidad de Camas Disponibles por Sector (Stored Procedure) ", padding=6)
        frame_resumen.pack(fill=tk.X, pady=(0, 6))

        self.tabla_resumen_camas = ttk.Treeview(frame_resumen, columns=("Sector", "CamasLibres"), show="headings", height=4)
        self.tabla_resumen_camas.heading("Sector", text="Sector")
        self.tabla_resumen_camas.heading("CamasLibres", text="Camas Disponibles")
        self.tabla_resumen_camas.column("Sector", width=180, anchor="w")
        self.tabla_resumen_camas.column("CamasLibres", width=130, anchor="center")
        self.tabla_resumen_camas.pack(fill=tk.X, expand=True)

        # 2. Detalle: Cama por cama
        frame_detalle = ttk.LabelFrame(frame_der, text=" 🛏️ Detalle de Camas Disponibles (Habitación y Cama) ", padding=6)
        frame_detalle.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        self.tabla_camas = ttk.Treeview(frame_detalle, columns=("Sector", "Habitacion", "Piso", "Cama", "Estado"), show="headings", height=7)
        self.tabla_camas.heading("Sector", text="Sector")
        self.tabla_camas.heading("Habitacion", text="Habitación")
        self.tabla_camas.heading("Piso", text="Piso")
        self.tabla_camas.heading("Cama", text="Cama Nro")
        self.tabla_camas.heading("Estado", text="Estado")
        self.tabla_camas.column("Sector", width=140)
        self.tabla_camas.column("Habitacion", width=90, anchor="center")
        self.tabla_camas.column("Piso", width=70, anchor="center")
        self.tabla_camas.column("Cama", width=80, anchor="center")
        self.tabla_camas.column("Estado", width=80, anchor="center")
        self.tabla_camas.pack(fill=tk.BOTH, expand=True, pady=(2, 4))
        self.tabla_camas.bind("<Double-1>", self.on_doble_clic_cama)

        ttk.Label(frame_detalle, text=" Doble clic en una fila de la tabla carga la habitación y cama automáticamente.", font=("Segoe UI", 8, "italic"), foreground="#4A5568").pack(anchor="w", padx=4)

        btn_refrescar_camas = tk.Button(
            frame_der, text="🔄 Actualizar Camas y Resumen", bg="#E2E8F0", cursor="hand2", command=self.cargar_camas_libres
        )
        btn_refrescar_camas.pack(anchor="w", pady=(0, 2))

    def accion_registrar_internacion(self):
        dni = self.txt_dni.get().strip()
        matricula = self.txt_matricula.get().strip()
        hab_str = self.txt_hab.get().strip()
        cama_str = self.txt_cama.get().strip()
        fecha_inicio_str = self.txt_fecha_inicio.get().strip() if hasattr(self, 'txt_fecha_inicio') else ""
        hora_inicio_str = self.txt_hora_inicio.get().strip() if hasattr(self, 'txt_hora_inicio') else ""
        fecha_fin_str = self.txt_fecha_fin.get().strip() if hasattr(self, 'txt_fecha_fin') else ""

        if not (dni and matricula and hab_str and cama_str and fecha_inicio_str and hora_inicio_str):
            messagebox.showwarning("Campos Incompletos", "Por favor completa el DNI, Matrícula, Habitación, Cama, Fecha de Inicio y Hora de Ingreso.")
            return

        try:
            hab = int(hab_str)
            cama = int(cama_str)
        except ValueError:
            self.log_error("Habitación y Cama deben ser números enteros.")
            messagebox.showerror("Dato Inválido", "Habitación y Cama deben ser valores numéricos enteros.")
            return

        # Parsear fecha de inicio
        fecha_inicio_dt = None
        for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                fecha_inicio_dt = datetime.strptime(fecha_inicio_str, fmt)
                break
            except ValueError:
                pass
        if fecha_inicio_dt is None:
            self.log_error(f"Formato de Fecha de Inicio inválido: '{fecha_inicio_str}'. Use DD/MM/AAAA.")
            messagebox.showerror("Fecha Inválida", f"La Fecha de Inicio '{fecha_inicio_str}' no es válida.\nFormato esperado: DD/MM/AAAA (ej. {datetime.now().strftime('%d/%m/%Y')}).")
            return

        # Parsear hora de ingreso para POSEE.fechaHora
        hora_inicio_t = None
        for h_fmt in ("%H:%M", "%H:%M:%S"):
            try:
                hora_inicio_t = datetime.strptime(hora_inicio_str, h_fmt).time()
                break
            except ValueError:
                pass
        if hora_inicio_t is None:
            self.log_error(f"Formato de Hora de Ingreso inválido: '{hora_inicio_str}'. Use HH:MM.")
            messagebox.showerror("Hora Inválida", f"La Hora de Ingreso '{hora_inicio_str}' no es válida.\nFormato esperado: HH:MM (ej. {datetime.now().strftime('%H:%M')}).")
            return

        fecha_inicio_solo_fecha = datetime.combine(fecha_inicio_dt.date(), datetime.min.time())
        fecha_hora_posee = datetime.combine(fecha_inicio_dt.date(), hora_inicio_t)

        # Parsear fecha de fin (opcional)
        fecha_fin_solo_fecha = None
        if fecha_fin_str:
            fecha_fin_dt = None
            for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    fecha_fin_dt = datetime.strptime(fecha_fin_str, fmt)
                    break
                except ValueError:
                    pass
            if fecha_fin_dt is None:
                self.log_error(f"Formato de Fecha de Fin inválido: '{fecha_fin_str}'. Use DD/MM/AAAA.")
                messagebox.showerror("Fecha Inválida", f"La Fecha de Fin '{fecha_fin_str}' no es válida.\nFormato esperado: DD/MM/AAAA o dejar en blanco.")
                return

            fecha_fin_solo_fecha = datetime.combine(fecha_fin_dt.date(), datetime.min.time())
            if fecha_fin_solo_fecha < fecha_inicio_solo_fecha:
                self.log_error("Fecha de Fin anterior a Fecha de Inicio.")
                messagebox.showerror("Fechas Inconsistentes", "La Fecha de Fin (alta) no puede ser anterior a la Fecha de Inicio de la internación.")
                return

        conn = None
        cursor = None
        try:
            self.log_info(f"Iniciando transacción: Asignando Paciente DNI={dni} a Hab={hab}, Cama={cama} con Médico={matricula} (Inicio={fecha_inicio_str} {hora_inicio_str})...")
            conn = obtener_conexion()
            cursor = conn.cursor()

            # Ejecutar Stored Procedure transaccional 'sp_registrar_internacion' en la base de datos
            id_internacion_var = cursor.var(oracledb.NUMBER)
            invocar_sp(cursor, "sp_registrar_internacion", [
                dni, matricula, hab, cama, fecha_inicio_solo_fecha, fecha_fin_solo_fecha, id_internacion_var, fecha_hora_posee
            ])
            id_internacion = int(id_internacion_var.getvalue())

            if fecha_fin_solo_fecha:
                mensaje_exito = f"Transacción confirmada por Stored Procedure (COMMIT): Internación #{id_internacion} registrada como finalizada (Inicio: {fecha_inicio_str} {hora_inicio_str}, Fin: {fecha_fin_str}) sin modificar el estado actual de la Cama {cama} de Hab {hab}."
            else:
                mensaje_exito = f"Transacción confirmada por Stored Procedure (COMMIT): Internación #{id_internacion} creada con éxito (Inicio: {fecha_inicio_str} {hora_inicio_str}). Cama {cama} de Hab {hab} asignada y en estado OCUPADA."

            self.log_exito(mensaje_exito)
            messagebox.showinfo("Transacción Exitosa", mensaje_exito)

            self.txt_dni.delete(0, tk.END)
            self.txt_matricula.delete(0, tk.END)
            self.txt_hab.delete(0, tk.END)
            self.txt_cama.delete(0, tk.END)
            if hasattr(self, 'txt_fecha_inicio'):
                self.txt_fecha_inicio.delete(0, tk.END)
                self.txt_fecha_inicio.insert(0, datetime.now().strftime("%d/%m/%Y"))
            if hasattr(self, 'txt_hora_inicio'):
                self.txt_hora_inicio.delete(0, tk.END)
                self.txt_hora_inicio.insert(0, datetime.now().strftime("%H:%M"))
            if hasattr(self, 'txt_fecha_fin'):
                self.txt_fecha_fin.delete(0, tk.END)

            self.cargar_camas_libres()
            self.actualizar_combo_internaciones()

        except Exception as e:
            if conn:
                conn.rollback()
            self.reportar_error("Error en Transacción", e, prefijo_log="Transacción ABORTADA (ROLLBACK aplicado)")

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def on_doble_clic_cama(self, event):
        item = self.tabla_camas.selection()
        if not item:
            return
        valores = self.tabla_camas.item(item[0], "values")
        if valores and len(valores) >= 4:
            hab = valores[1]
            cama = valores[3]
            if hasattr(self, 'txt_traslado_hab') and hasattr(self, 'txt_traslado_cama'):
                self.txt_traslado_hab.delete(0, tk.END)
                self.txt_traslado_hab.insert(0, hab)
                self.txt_traslado_cama.delete(0, tk.END)
                self.txt_traslado_cama.insert(0, cama)
            if hasattr(self, 'txt_hab') and hasattr(self, 'txt_cama'):
                self.txt_hab.delete(0, tk.END)
                self.txt_hab.insert(0, hab)
                self.txt_cama.delete(0, tk.END)
                self.txt_cama.insert(0, cama)

    def accion_copiar_cama_seleccionada(self):
        item = self.tabla_camas.selection()
        if not item:
            messagebox.showinfo("Seleccionar Cama", "Por favor haz clic en una cama disponible de la tabla de la derecha.")
            return
        valores = self.tabla_camas.item(item[0], "values")
        if valores and len(valores) >= 4:
            hab = valores[1]
            cama = valores[3]
            self.txt_traslado_hab.delete(0, tk.END)
            self.txt_traslado_hab.insert(0, hab)
            self.txt_traslado_cama.delete(0, tk.END)
            self.txt_traslado_cama.insert(0, cama)
            self.log_info(f"Cama seleccionada para traslado: Habitación {hab}, Cama {cama}.")

    def actualizar_combo_internaciones(self):
        if not hasattr(self, 'txt_traslado_id_int'):
            return
        conn = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            cur_int = cursor.connection.cursor()
            invocar_sp(cursor, "sp_listar_internaciones_activas", [cur_int])
            filas = cur_int.fetchall()
            cur_int.close()
            cursor.close()
            opciones = [f"{f[0]} - {f[1]} {f[2]} (DNI {f[3]})" for f in filas]
            self.txt_traslado_id_int['values'] = opciones
            
            val_actual = self.txt_traslado_id_int.get().strip()
            if opciones:
                if not val_actual or not any(val_actual.startswith(f"{f[0]} ") or val_actual == str(f[0]) for f in filas):
                    self.txt_traslado_id_int.set(opciones[0])
                self.accion_consultar_cama_actual()
            else:
                self.txt_traslado_id_int.set("")
                if hasattr(self, 'lbl_traslado_info'):
                    self.lbl_traslado_info.config(
                        text="No hay internaciones activas en este momento.",
                        foreground="#4A5568"
                    )
        except Exception:
            pass
        finally:
            if conn:
                conn.close()
            if hasattr(self, 'actualizar_combo_internaciones_activas_com'):
                self.actualizar_combo_internaciones_activas_com()

    def accion_consultar_cama_actual(self, event=None):
        if not hasattr(self, 'txt_traslado_id_int'):
            return
        raw_val = self.txt_traslado_id_int.get().strip()
        if not raw_val:
            return
        try:
            id_int = int(raw_val.split()[0].replace("#", ""))
        except ValueError:
            self.lbl_traslado_info.config(text="⚠️ ID de internación debe ser numérico.", foreground="#C53030")
            return

        conn = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            cur_datos = cursor.connection.cursor()
            invocar_sp(cursor, "sp_consultar_cama_actual", [id_int, cur_datos])
            row = cur_datos.fetchone()
            cur_datos.close()
            cursor.close()
            if not row:
                self.lbl_traslado_info.config(text=f"❌ La internación #{id_int} no existe.", foreground="#C53030")
                return

            pac_nom, dni, hab_act, cama_act, estado_cama, sec_nom, fh_pos, f_ini, f_fin = row

            # Sincronizar también el ID en la caja de Visitas Médicas (Stored Procedure)
            if hasattr(self, 'txt_id_int_comentario'):
                self.txt_id_int_comentario.delete(0, tk.END)
                self.txt_id_int_comentario.insert(0, str(id_int))

            f_ini_str = f_ini.strftime('%d/%m/%Y') if f_ini else 'N/D'

            if f_fin is not None:
                self.lbl_traslado_info.config(
                    text=f"⚠️ Paciente {pac_nom} (DNI {dni}) - ALTA MÉDICA OTORGADA ({f_fin.strftime('%d/%m/%Y')}) | Ingreso: {f_ini_str}.",
                    foreground="#C53030"
                )
            elif hab_act is not None and cama_act is not None:
                self.lbl_traslado_info.config(
                    text=f"👤 {pac_nom} (DNI {dni}) | Ingreso: {f_ini_str} | Cama actual: Hab {hab_act}, Cama {cama_act}",
                    foreground="#2B6CB0"
                )
            else:
                self.lbl_traslado_info.config(
                    text=f"👤 {pac_nom} (DNI {dni}) | Ingreso: {f_ini_str} | Sin cama previa asignada",
                    foreground="#4A5568"
                )
        except Exception as e:
            self.lbl_traslado_info.config(text=f"Error al consultar: {str(e)[:60]}", foreground="#C53030")
        finally:
            if conn:
                conn.close()

    def accion_trasladar_cama(self):
        raw_val = self.txt_traslado_id_int.get().strip()
        hab_str = self.txt_traslado_hab.get().strip()
        cama_str = self.txt_traslado_cama.get().strip()

        if not (raw_val and hab_str and cama_str):
            messagebox.showwarning("Campos Incompletos", "Por favor completa el ID de Internación, Nueva Habitación y Nueva Cama.")
            return

        try:
            id_int = int(raw_val.split()[0].replace("#", ""))
            hab_nueva = int(hab_str)
            cama_nueva = int(cama_str)
        except ValueError:
            self.log_error("ID de Internación, Habitación y Cama deben ser valores numéricos enteros.")
            messagebox.showerror("Dato Inválido", "El ID de Internación, Habitación y Cama deben ser valores numéricos enteros.")
            return

        conn = None
        cursor = None
        try:
            self.log_info(f"Iniciando transacción de traslado: Internación #{id_int} -> Habitación={hab_nueva}, Cama={cama_nueva}...")
            conn = obtener_conexion()
            cursor = conn.cursor()

            # Consultar datos actuales del paciente y cama mediante Stored Procedure
            cur_datos = cursor.connection.cursor()
            invocar_sp(cursor, "sp_consultar_cama_actual", [id_int, cur_datos])
            row_cama_actual = cur_datos.fetchone()
            cur_datos.close()
            paciente_nombre = f"{row_cama_actual[0]} (DNI {row_cama_actual[1]})" if row_cama_actual else f"Internación #{id_int}"
            hab_anterior, cama_anterior = (row_cama_actual[2], row_cama_actual[3]) if row_cama_actual else (None, None)

            # Ejecutar el Stored Procedure transaccional 'sp_ocupar_cama_posee'
            # Valida internación activa, habitación válida y cama libre con bloqueo pesimista (FOR UPDATE).
            # Libera la cama anterior (si tenía), ocupa la nueva, inserta en POSEE y ejecuta COMMIT atómicamente.
            # Si algo falla, el procedure ejecuta ROLLBACK automático para que nada quede a mitad de hacer.
            invocar_sp(cursor, "sp_ocupar_cama_posee", [id_int, hab_nueva, cama_nueva])

            msg_exito = (
                f"Transacción confirmada por Stored Procedure (COMMIT):\n"
                f"• Paciente: {paciente_nombre}\n"
                f"• Internación #{id_int} trasladado a Habitación {hab_nueva}, Cama {cama_nueva} (Estado: OCUPADA).\n"
            )
            if hab_anterior is not None:
                msg_exito += f"• Cama anterior: Habitación {hab_anterior}, Cama {cama_anterior} liberada automáticamente a 'LIBRE'."

            self.log_exito(msg_exito)
            messagebox.showinfo("Traslado Exitoso", msg_exito)

            self.txt_traslado_hab.delete(0, tk.END)
            self.txt_traslado_cama.delete(0, tk.END)
            self.cargar_camas_libres()
            self.accion_consultar_cama_actual()
            if hasattr(self, 'cargar_todas_las_camas'):
                self.cargar_todas_las_camas()

        except Exception as e:
            if conn:
                conn.rollback()
            self.reportar_error("Error en Traslado", e, prefijo_log="Traslado ABORTADO (ROLLBACK aplicado)")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def accion_finalizar_internacion(self):
        raw_val = self.txt_traslado_id_int.get().strip()
        if not raw_val:
            messagebox.showwarning("Seleccionar Internación", "Por favor selecciona o ingresa el ID de la internación activa que deseas finalizar.")
            return

        try:
            id_int = int(raw_val.split()[0].replace("#", ""))
        except ValueError:
            self.log_error("ID de Internación debe ser un valor numérico entero.")
            messagebox.showerror("Dato Inválido", "El ID de internación debe ser un número entero.")
            return

        conn = None
        cursor = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()

            # 1. Consultar datos de internación mediante Stored Procedure 'sp_obtener_datos_alta'
            cur_datos = cursor.connection.cursor()
            invocar_sp(cursor, "sp_obtener_datos_alta", [id_int, cur_datos])
            row_int = cur_datos.fetchone()
            cur_datos.close()
            if not row_int:
                raise Exception(f"La internación #{id_int} no existe en la base de datos.")
            if row_int[7] is not None:
                raise Exception(f"La internación #{id_int} ya finalizó previamente (Alta médica otorgada el {row_int[7].strftime('%d/%m/%Y')}).")

            paciente_nombre = f"{row_int[1]} {row_int[2]} (DNI {row_int[3]})"
            hab_act, cama_act = row_int[4], row_int[5]
            cama_info = f"Habitación {hab_act}, Cama {cama_act}" if hab_act is not None else "Sin cama asignada"

            # 2. Cuadro de confirmación antes de proceder
            confirmar = messagebox.askyesno(
                "Confirmar Alta Médica",
                f"¿Deseas dar el Alta Médica y finalizar la internación #{id_int}?\n\n"
                f"• Paciente: {paciente_nombre}\n"
                f"• Cama actual a liberar: {cama_info}\n\n"
                f"Al confirmar, el Stored Procedure registrará la fecha de alta y liberará la cama automáticamente."
            )
            if not confirmar:
                return

            self.log_info(f"Procesando alta médica para Internación #{id_int} ({paciente_nombre})...")

            # 3. Invocar Stored Procedure transaccional 'sp_dar_alta_internacion' en la base de datos
            invocar_sp(cursor, "sp_dar_alta_internacion", [id_int])

            msg_exito = (
                f"Transacción confirmada (COMMIT):\n"
                f"• Internación #{id_int} FINALIZADA con éxito (Alta Médica otorgada).\n"
                f"• Paciente: {paciente_nombre}\n"
            )
            if hab_act is not None:
                msg_exito += f"• Cama liberada: Habitación {hab_act}, Cama {cama_act} (Estado: LIBRE mediante Trigger 'trg_liberar_cama_fin_int')."

            self.log_exito(msg_exito)
            messagebox.showinfo("Alta Médica Confirmada", msg_exito)

            # Refrescar la interfaz
            self.cargar_camas_libres()
            self.actualizar_combo_internaciones()
            self.accion_consultar_cama_actual()
            if hasattr(self, 'cargar_todas_las_camas'):
                self.cargar_todas_las_camas()

        except Exception as e:
            if conn:
                conn.rollback()
            self.reportar_error("Error en Alta Médica", e, prefijo_log="Alta médica ABORTADA (ROLLBACK aplicado)")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def cargar_camas_libres(self):
        if hasattr(self, 'tabla_resumen_camas'):
            for item in self.tabla_resumen_camas.get_children():
                self.tabla_resumen_camas.delete(item)

        if hasattr(self, 'tabla_camas'):
            for item in self.tabla_camas.get_children():
                self.tabla_camas.delete(item)

        conn = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()

            cur_res = cursor.connection.cursor()
            cur_det = cursor.connection.cursor()
            invocar_sp(cursor, "listar_camas_disponibles", [cur_res, cur_det])
            
            filas_resumen = cur_res.fetchall()
            if hasattr(self, 'tabla_resumen_camas'):
                for r in filas_resumen:
                    self.tabla_resumen_camas.insert("", tk.END, values=(r[0], f"{r[1]} libre(s)"))

            filas_detalle = cur_det.fetchall()
            if hasattr(self, 'tabla_camas'):
                for f in filas_detalle:
                    self.tabla_camas.insert("", tk.END, values=(f[0], f[1], f[2], f[3], f[4]))

            cur_res.close()
            cur_det.close()
            cursor.close()
        except Exception as e:
            traduccion = traducir_error_oracle(e)
            self.log_error(f"No se pudieron cargar las camas libres:\n{traducir_error_oracle(e, incluir_tecnico=True)}")
            if "942" in str(e) or "no existe" in str(e).lower():
                self.log_info("💡 TIP: Parece que las tablas aún no fueron creadas en Oracle. Usa el botón 'Crear/Reiniciar Tablas' arriba a la derecha.")
        finally:
            if conn:
                conn.close()
            self.actualizar_combo_internaciones()

    def accion_consultar_comentarios_sp(self):
        id_int_str = self.txt_id_int_comentario.get().strip()
        if not id_int_str:
            messagebox.showwarning("Atención", "Ingresa el ID de internación a consultar.")
            return

        try:
            id_int = int(id_int_str)
        except ValueError:
            messagebox.showerror("Error", "El ID de internación debe ser un número entero.")
            return

        conn = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()

            cur_pac = cursor.connection.cursor()
            cur_com = cursor.connection.cursor()
            invocar_sp(cursor, "listar_comentarios_internacion", [id_int, cur_pac, cur_com])

            paciente_info = cur_pac.fetchall()
            comentarios = cur_com.fetchall()

            cur_pac.close()
            cur_com.close()

            if not paciente_info:
                messagebox.showinfo("Sin Datos", f"No se encontró la internación #{id_int} en el sistema.")
                return

            pac = paciente_info[0]
            texto_resultado = f"📋 REPORTE DE INTERNACIÓN #{pac[0]}\n"
            texto_resultado += f"• Paciente: {pac[1]} (DNI: {pac[2]})\n"
            texto_resultado += "=" * 55 + "\n\n"

            if not comentarios:
                texto_resultado += "No se registran comentarios médicos de recorridos para esta internación."
            else:
                texto_resultado += f"VISITAS MÉDICAS REGISTRADAS ({len(comentarios)}):\n\n"
                for c in comentarios:
                    texto_resultado += f"📅 Fecha: {c[0]} | Turno: {c[1]} | Médico: {c[2]} (Mat: {c[3]})\n"
                    texto_resultado += f"💬 Comentario: \"{c[4]}\"\n"
                    texto_resultado += "-" * 55 + "\n"

            self.log_exito(f"Stored Procedure 'listar_comentarios_internacion' ejecutado con éxito para Internación #{id_int}.")
            messagebox.showinfo(f"Comentarios de Internación #{id_int}", texto_resultado)

        except Exception as e:
            self.reportar_error("Error Stored Procedure", e, prefijo_log="Error al ejecutar Stored Procedure de comentarios")
        finally:
            if conn:
                conn.close()

    # ==========================================================================
    # TAB 2: SECCIONES DE ALTAS (PACIENTES, MÉDICOS, SECTORES, HABITACIONES, CAMAS)
    # ==========================================================================
    def construir_tab_altas(self):
        self.notebook_altas = ttk.Notebook(self.tab_altas)
        self.notebook_altas.pack(fill=tk.BOTH, expand=True)

        tab_pac = ttk.Frame(self.notebook_altas, padding=12)
        self.notebook_altas.add(tab_pac, text=" 👤 Pacientes ")
        self.construir_subtab_paciente(tab_pac)

        tab_med = ttk.Frame(self.notebook_altas, padding=12)
        self.notebook_altas.add(tab_med, text=" 🩺 Médicos ")
        self.construir_subtab_medico(tab_med)

        tab_sec = ttk.Frame(self.notebook_altas, padding=12)
        self.notebook_altas.add(tab_sec, text=" 🏢 Sectores ")
        self.construir_subtab_sector(tab_sec)

        tab_hab = ttk.Frame(self.notebook_altas, padding=12)
        self.notebook_altas.add(tab_hab, text=" 🚪 Habitaciones ")
        self.construir_subtab_habitacion(tab_hab)

        tab_cama = ttk.Frame(self.notebook_altas, padding=12)
        self.notebook_altas.add(tab_cama, text=" 🛏️ Camas ")
        self.construir_subtab_cama(tab_cama)

        self.tab_guardia = ttk.Frame(self.notebook_altas, padding=12)
        self.notebook_altas.add(self.tab_guardia, text=" 🛡️ Guardias ")
        self.construir_subtab_guardia(self.tab_guardia)

        self.tab_recorrido = ttk.Frame(self.notebook_altas, padding=12)
        self.notebook_altas.add(self.tab_recorrido, text=" 🔄 Recorridos ")
        self.construir_subtab_recorrido(self.tab_recorrido)

        self.tab_comentario = ttk.Frame(self.notebook_altas, padding=12)
        self.notebook_altas.add(self.tab_comentario, text=" 💬 Comentarios ")
        self.construir_subtab_comentario(self.tab_comentario)

        self._pestana_altas_anterior = self.notebook_altas.select()
        self.notebook_altas.bind("<<NotebookTabChanged>>", self.on_cambio_pestana_altas)

    def ir_a_tab_recorrido(self):
        self.notebook.select(self.tab_altas)
        if hasattr(self, 'tab_recorrido'):
            self.notebook_altas.select(self.tab_recorrido)

    def ir_a_tab_comentario(self):
        self.notebook.select(self.tab_altas)
        if hasattr(self, 'tab_comentario'):
            self.notebook_altas.select(self.tab_comentario)

    def on_cambio_pestana_altas(self, event=None):
        if not getattr(self, '_app_iniciada', False):
            return
        pestana_actual = self.notebook_altas.select()
        if hasattr(self, 'tab_guardia') and pestana_actual == str(self.tab_guardia):
            if not self.usuario_guardias:
                exito = self.solicitar_login_guardias()
                if not exito:
                    if self._pestana_altas_anterior and self._pestana_altas_anterior != str(self.tab_guardia):
                        self.notebook_altas.select(self._pestana_altas_anterior)
                    return
        elif hasattr(self, 'tab_recorrido') and pestana_actual == str(self.tab_recorrido):
            self.refrescar_panel_recorridos()
        elif hasattr(self, 'tab_comentario') and pestana_actual == str(self.tab_comentario):
            self.refrescar_panel_comentarios()
        self._pestana_altas_anterior = pestana_actual

    # 1. Subtab Paciente
    def construir_subtab_paciente(self, parent):
        frame_form = ttk.LabelFrame(parent, text=" Datos del Paciente ", padding=10)
        frame_form.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        ttk.Label(frame_form, text="DNI (máx 8 dígitos):").grid(row=0, column=0, sticky="w", pady=4)
        self.pac_dni = ttk.Entry(frame_form, width=22)
        self.pac_dni.grid(row=0, column=1, pady=4)

        ttk.Label(frame_form, text="Nombre:").grid(row=1, column=0, sticky="w", pady=4)
        self.pac_nombre = ttk.Entry(frame_form, width=22)
        self.pac_nombre.grid(row=1, column=1, pady=4)

        ttk.Label(frame_form, text="Apellido:").grid(row=2, column=0, sticky="w", pady=4)
        self.pac_apellido = ttk.Entry(frame_form, width=22)
        self.pac_apellido.grid(row=2, column=1, pady=4)

        ttk.Label(frame_form, text="Sexo:").grid(row=3, column=0, sticky="w", pady=4)
        self.pac_sexo = ttk.Combobox(frame_form, values=["MASCULINO", "FEMENINO", "OTRO"], state="readonly", width=20)
        self.pac_sexo.set("MASCULINO")
        self.pac_sexo.grid(row=3, column=1, pady=4)

        ttk.Label(frame_form, text="Fecha Nacimiento (DD/MM/YYYY):").grid(row=4, column=0, sticky="w", pady=4)
        self.pac_fnac = ttk.Entry(frame_form, width=22)
        self.pac_fnac.insert(0, "15/05/1995")
        self.pac_fnac.grid(row=4, column=1, pady=4)

        btn_guardar = tk.Button(
            frame_form, text="💾 Registrar Paciente", bg="#276749", fg="white", font=("Segoe UI", 9, "bold"),
            relief="groove", cursor="hand2", command=self.accion_insertar_paciente
        )
        btn_guardar.grid(row=5, column=0, columnspan=2, pady=12, sticky="ew")

        frame_lista = ttk.LabelFrame(parent, text=" Pacientes Registrados ", padding=10)
        frame_lista.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.tabla_pacientes = ttk.Treeview(frame_lista, columns=("DNI", "Apellido", "Nombre", "Sexo", "FechaNac"), show="headings")
        self.tabla_pacientes.heading("DNI", text="DNI")
        self.tabla_pacientes.heading("Apellido", text="Apellido")
        self.tabla_pacientes.heading("Nombre", text="Nombre")
        self.tabla_pacientes.heading("Sexo", text="Sexo")
        self.tabla_pacientes.heading("FechaNac", text="Fecha Nacimiento")
        for col in ("DNI", "Apellido", "Nombre", "Sexo", "FechaNac"):
            self.tabla_pacientes.column(col, width=105, anchor="center")
        self.tabla_pacientes.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        btn_refrescar = tk.Button(frame_lista, text="🔄 Refrescar Lista", bg="#E2E8F0", cursor="hand2", command=self.cargar_lista_pacientes)
        btn_refrescar.pack(anchor="w")
        self.cargar_lista_pacientes()

    def accion_insertar_paciente(self):
        dni = self.pac_dni.get().strip()
        nom = self.pac_nombre.get().strip()
        ape = self.pac_apellido.get().strip()
        sex = self.pac_sexo.get().strip()
        fnac = self.pac_fnac.get().strip()

        if not (dni and nom and ape and sex and fnac):
            messagebox.showwarning("Atención", "Todos los campos de paciente son requeridos.")
            return

        fnac_dt = None
        for f_fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                fnac_dt = datetime.strptime(fnac, f_fmt).date()
                break
            except ValueError:
                pass
        if not fnac_dt:
            messagebox.showerror("Error", "Formato de fecha de nacimiento inválido. Use DD/MM/AAAA o AAAA-MM-DD.")
            return

        conn = None
        cursor = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            # Invocar Stored Procedure transaccional 'sp_registrar_paciente'
            invocar_sp(cursor, "sp_registrar_paciente", [dni, nom, ape, sex, fnac_dt])
            self.log_exito(f"Paciente DNI {dni} ({ape}, {nom}) registrado exitosamente.")
            messagebox.showinfo("Éxito", f"Paciente {nom} {ape} registrado correctamente.")
            self.pac_dni.delete(0, tk.END)
            self.pac_nombre.delete(0, tk.END)
            self.pac_apellido.delete(0, tk.END)
            self.cargar_lista_pacientes()

        except Exception as e:
            if conn:
                conn.rollback()
            self.reportar_error("Error", e, prefijo_log="Error al registrar paciente")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def cargar_lista_pacientes(self):
        for item in self.tabla_pacientes.get_children():
            self.tabla_pacientes.delete(item)
        conn = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            cur_pac = cursor.connection.cursor()
            invocar_sp(cursor, "sp_listar_pacientes", [cur_pac])
            for row in cur_pac.fetchall():
                self.tabla_pacientes.insert("", tk.END, values=row)
            cur_pac.close()
            cursor.close()
        except Exception as e:
            self.log_error(f"No se pudieron cargar los pacientes: {traducir_error_oracle(e, incluir_tecnico=True)}")
        finally:
            if conn:
                conn.close()

    # 2. Subtab Médico
    def construir_subtab_medico(self, parent):
        frame_form = ttk.LabelFrame(parent, text=" Datos del Médico ", padding=10)
        frame_form.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        ttk.Label(frame_form, text="DNI (8 dígitos):").grid(row=0, column=0, sticky="w", pady=4)
        self.med_dni = ttk.Entry(frame_form, width=22)
        self.med_dni.grid(row=0, column=1, pady=4)

        ttk.Label(frame_form, text="Nombre:").grid(row=1, column=0, sticky="w", pady=4)
        self.med_nombre = ttk.Entry(frame_form, width=22)
        self.med_nombre.grid(row=1, column=1, pady=4)

        ttk.Label(frame_form, text="Apellido:").grid(row=2, column=0, sticky="w", pady=4)
        self.med_apellido = ttk.Entry(frame_form, width=22)
        self.med_apellido.grid(row=2, column=1, pady=4)

        ttk.Label(frame_form, text="Matrícula (máx 10 car.):").grid(row=3, column=0, sticky="w", pady=4)
        self.med_matricula = ttk.Entry(frame_form, width=22)
        self.med_matricula.grid(row=3, column=1, pady=4)

        ttk.Label(frame_form, text="CUIL (11 dígitos, ej 20...3):").grid(row=4, column=0, sticky="w", pady=4)
        self.med_cuil = ttk.Entry(frame_form, width=22)
        self.med_cuil.grid(row=4, column=1, pady=4)

        ttk.Label(frame_form, text="Guardias Máx. (mes):").grid(row=5, column=0, sticky="w", pady=4)
        self.med_guardias = ttk.Entry(frame_form, width=22)
        self.med_guardias.insert(0, "4")
        self.med_guardias.grid(row=5, column=1, pady=4)

        # Foto del médico (BLOB)
        ttk.Label(frame_form, text="Foto (BLOB):").grid(row=6, column=0, sticky="w", pady=4)
        frame_foto = ttk.Frame(frame_form)
        frame_foto.grid(row=6, column=1, pady=4, sticky="w")
        self.med_ruta_foto = None
        self.lbl_foto_nombre = ttk.Label(frame_foto, text="Sin foto", font=("Segoe UI", 8, "italic"))
        btn_sel_foto = tk.Button(
            frame_foto, text="📁 Seleccionar...", bg="#E2E8F0", cursor="hand2", font=("Segoe UI", 8),
            command=self.accion_seleccionar_foto_medico
        )
        btn_sel_foto.pack(side=tk.LEFT, padx=(0, 4))
        self.lbl_foto_nombre.pack(side=tk.LEFT)

        btn_guardar = tk.Button(
            frame_form, text="💾 Registrar Médico", bg="#276749", fg="white", font=("Segoe UI", 9, "bold"),
            relief="groove", cursor="hand2", command=self.accion_insertar_medico
        )
        btn_guardar.grid(row=7, column=0, columnspan=2, pady=12, sticky="ew")

        # Lista de médicos
        frame_lista = ttk.LabelFrame(parent, text=" Médicos Registrados ", padding=10)
        frame_lista.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.tabla_medicos = ttk.Treeview(frame_lista, columns=("Matricula", "DNI", "Apellido", "Nombre", "CUIL", "GuardiasMax", "TieneFoto"), show="headings")
        self.tabla_medicos.heading("Matricula", text="Matrícula")
        self.tabla_medicos.heading("DNI", text="DNI")
        self.tabla_medicos.heading("Apellido", text="Apellido")
        self.tabla_medicos.heading("Nombre", text="Nombre")
        self.tabla_medicos.heading("CUIL", text="CUIL")
        self.tabla_medicos.heading("GuardiasMax", text="Guardias")
        self.tabla_medicos.heading("TieneFoto", text="Foto (BLOB)")
        for col in ("Matricula", "DNI", "Apellido", "Nombre", "CUIL", "GuardiasMax", "TieneFoto"):
            self.tabla_medicos.column(col, width=85, anchor="center")
        self.tabla_medicos.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        frame_botones_medicos = ttk.Frame(frame_lista)
        frame_botones_medicos.pack(fill=tk.X)

        btn_refrescar = tk.Button(frame_botones_medicos, text="🔄 Refrescar Lista", bg="#E2E8F0", cursor="hand2", command=self.cargar_lista_medicos)
        btn_refrescar.pack(side=tk.LEFT, padx=(0, 5))

        btn_ver_foto = tk.Button(frame_botones_medicos, text="🖼️ Ver Foto", bg="#E2E8F0", cursor="hand2", command=self.accion_ver_foto_medico)
        btn_ver_foto.pack(side=tk.LEFT, padx=(0, 5))

        btn_gestionar_esp = tk.Button(
            frame_botones_medicos, text="🩺 Gestionar Especialidades...", bg="#2B6CB0", fg="white",
            font=("Segoe UI", 9, "bold"), cursor="hand2", command=self.accion_gestionar_especialidades_medico
        )
        btn_gestionar_esp.pack(side=tk.LEFT)

        self.cargar_lista_medicos()

    def accion_seleccionar_foto_medico(self):
        archivo = filedialog.askopenfilename(
            title="Seleccionar foto del médico",
            filetypes=[("Imágenes", "*.jpg;*.jpeg;*.png;*.bmp;*.gif"), ("Todos los archivos", "*.*")]
        )
        if archivo:
            self.med_ruta_foto = archivo
            nombre = os.path.basename(archivo)
            if len(nombre) > 16:
                nombre = nombre[:13] + "..."
            self.lbl_foto_nombre.config(text=nombre)
            self.log_info(f"Foto seleccionada: {archivo}")

    def accion_ver_foto_medico(self):
        seleccion = self.tabla_medicos.selection()
        if not seleccion:
            messagebox.showinfo("Seleccionar Médico", "Por favor selecciona un médico de la lista para ver su foto.")
            return
        item = self.tabla_medicos.item(seleccion[0])
        matricula = item['values'][0]
        nombre_completo = f"{item['values'][2]}, {item['values'][3]}"

        conn = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            cur_foto = cursor.connection.cursor()
            invocar_sp(cursor, "sp_obtener_foto_medico", [matricula, cur_foto])
            res = cur_foto.fetchone()
            cur_foto.close()
            cursor.close()
            if not res or not res[0]:
                messagebox.showinfo("Sin Foto", f"El médico Dr. {nombre_completo} no tiene una foto registrada.")
                return

            lob = res[0]
            foto_data = lob.read() if hasattr(lob, 'read') else lob

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            temp_file.write(foto_data)
            temp_file.close()

            os.startfile(temp_file.name)
            self.log_info(f"Visualizando foto del médico Dr. {nombre_completo} (recuperada del BLOB de Oracle).")

        except Exception as e:
            self.reportar_error("Error", e, prefijo_log="Error al abrir la foto del médico")
        finally:
            if conn:
                conn.close()

    def accion_gestionar_especialidades_medico(self):
        seleccion = self.tabla_medicos.selection()
        if not seleccion:
            messagebox.showinfo("Seleccionar Médico", "Por favor selecciona un médico de la lista para gestionar sus especialidades.")
            return

        item = self.tabla_medicos.item(seleccion[0])
        matricula = str(item['values'][0])
        apellido = str(item['values'][2])
        nombre = str(item['values'][3])

        modal = tk.Toplevel(self)
        modal.title(f"Especialidades - Dr. {apellido}, {nombre} ({matricula})")
        modal.geometry("640x520")
        modal.transient(self)
        modal.grab_set()

        # Encabezado
        frame_top = ttk.Frame(modal, padding=12)
        frame_top.pack(fill=tk.X)
        ttk.Label(
            frame_top,
            text=f"🩺 Especialidades del Dr. {apellido}, {nombre} (Matrícula: {matricula})",
            font=("Segoe UI", 11, "bold"),
            foreground="#2B6CB0"
        ).pack(anchor="w")
        ttk.Label(
            frame_top,
            text="Asigne especialidades al médico e indique si está dispuesto a realizar guardias (tabla TIENE).",
            font=("Segoe UI", 8, "italic")
        ).pack(anchor="w", pady=(2, 0))

        # Tabla de especialidades
        frame_tabla = ttk.LabelFrame(modal, text=" Especialidades Registradas ", padding=8)
        frame_tabla.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        tree_esp = ttk.Treeview(frame_tabla, columns=("ID", "Especialidad", "Tiene", "Dispuesto"), show="headings", height=8)
        tree_esp.heading("ID", text="ID")
        tree_esp.heading("Especialidad", text="Especialidad")
        tree_esp.heading("Tiene", text="Tiene Especialidad")
        tree_esp.heading("Dispuesto", text="Dispuesto a Guardia")
        tree_esp.column("ID", width=45, anchor="center")
        tree_esp.column("Especialidad", width=220, anchor="w")
        tree_esp.column("Tiene", width=130, anchor="center")
        tree_esp.column("Dispuesto", width=180, anchor="center")
        tree_esp.pack(fill=tk.BOTH, expand=True)

        # Formulario de asignación / modificación
        frame_form = ttk.LabelFrame(modal, text=" Asignar o Modificar Especialidad ", padding=10)
        frame_form.pack(fill=tk.X, padx=12, pady=(4, 12))

        ttk.Label(frame_form, text="Especialidad:").grid(row=0, column=0, sticky="w", pady=4)
        cb_esp_modal = ttk.Combobox(frame_form, state="readonly", width=28)
        cb_esp_modal.grid(row=0, column=1, sticky="w", padx=6, pady=4)

        var_dispuesto = tk.StringVar(value="Si")
        chk_disp = ttk.Checkbutton(
            frame_form, text="Dispuesto a guardias (Si/No)",
            variable=var_dispuesto, onvalue="Si", offvalue="No"
        )
        chk_disp.grid(row=0, column=2, sticky="w", padx=10, pady=4)

        def refrescar_datos():
            tree_esp.delete(*tree_esp.get_children())
            opciones_combo = []
            conn = None
            cur_sp = None
            try:
                conn = obtener_conexion()
                cursor = conn.cursor()
                cur_sp = cursor.connection.cursor()
                invocar_sp(cursor, "sp_listar_especialidades_medico", [matricula, cur_sp])
                filas = cur_sp.fetchall()
                cur_sp.close()
                cur_sp = None
                cursor.close()

                for f in filas:
                    id_e, nom_e, disp = f[0], f[1], f[2]
                    tiene_str = "✅ Sí" if disp is not None else "❌ No"
                    if disp is not None:
                        disp_str = "🟢 Sí (Disponible)" if str(disp).strip().upper() == "SI" else "🔴 No (No disponible)"
                    else:
                        disp_str = "—"
                    tree_esp.insert("", tk.END, values=(id_e, nom_e, tiene_str, disp_str))
                    opciones_combo.append(f"{id_e} - {nom_e}")

                cb_esp_modal['values'] = opciones_combo
                if opciones_combo and not cb_esp_modal.get():
                    cb_esp_modal.current(0)
            except Exception as ex:
                self.reportar_error("Error", ex, prefijo_log="Error al listar especialidades del médico")
            finally:
                if cur_sp:
                    try:
                        cur_sp.close()
                    except Exception:
                        pass
                if conn:
                    conn.close()

        def on_tree_select(event=None):
            sel = tree_esp.selection()
            if sel:
                vals = tree_esp.item(sel[0])['values']
                id_sel = vals[0]
                disp_val = str(vals[3])
                for v in cb_esp_modal['values']:
                    if v.startswith(f"{id_sel} - "):
                        cb_esp_modal.set(v)
                        break
                if "No" in disp_val:
                    var_dispuesto.set("No")
                else:
                    var_dispuesto.set("Si")

        tree_esp.bind("<<TreeviewSelect>>", on_tree_select)

        def accion_guardar_esp():
            sel_val = cb_esp_modal.get()
            if not sel_val:
                messagebox.showwarning("Atención", "Seleccione una especialidad de la lista.", parent=modal)
                return
            id_esp = int(sel_val.split(" - ")[0])
            disp = var_dispuesto.get()

            conn = None
            try:
                conn = obtener_conexion()
                cursor = conn.cursor()
                invocar_sp(cursor, "sp_asignar_especialidad_medico", [matricula, id_esp, disp])
                cursor.close()
                self.log_exito(f"Especialidad {sel_val} asignada al Dr. {apellido} ({matricula}) con dispuesto='{disp}'.")
                refrescar_datos()
                self.cargar_combos_guardia()
                messagebox.showinfo("Éxito", f"Especialidad guardada correctamente para el Dr. {apellido}.", parent=modal)
            except Exception as ex:
                self.reportar_error("Error", ex, prefijo_log="Error al asignar especialidad")
            finally:
                if conn:
                    conn.close()

        def accion_quitar_esp():
            sel_tree = tree_esp.selection()
            if not sel_tree:
                messagebox.showinfo("Seleccionar", "Seleccione una especialidad de la lista para quitarla.", parent=modal)
                return
            item_vals = tree_esp.item(sel_tree[0])['values']
            id_esp = int(item_vals[0])
            nom_esp = str(item_vals[1])
            tiene_esp = str(item_vals[2])

            if "No" in tiene_esp:
                messagebox.showinfo("Atención", f"El médico ya no tiene asignada la especialidad '{nom_esp}'.", parent=modal)
                return

            if not messagebox.askyesno("Confirmar", f"¿Desea quitar la especialidad '{nom_esp}' del Dr. {apellido}?", parent=modal):
                return

            conn = None
            try:
                conn = obtener_conexion()
                cursor = conn.cursor()
                invocar_sp(cursor, "sp_quitar_especialidad_medico", [matricula, id_esp])
                cursor.close()
                self.log_exito(f"Especialidad {nom_esp} quitada del Dr. {apellido} ({matricula}).")
                refrescar_datos()
                self.cargar_combos_guardia()
                messagebox.showinfo("Éxito", f"Especialidad quitada exitosamente.", parent=modal)
            except Exception as ex:
                self.reportar_error("Error", ex, prefijo_log="Error al quitar especialidad")
            finally:
                if conn:
                    conn.close()

        frame_btn_form = ttk.Frame(frame_form)
        frame_btn_form.grid(row=1, column=0, columnspan=3, pady=(10, 0), sticky="ew")

        btn_guardar_esp = tk.Button(
            frame_btn_form, text="💾 Asignar / Guardar", bg="#276749", fg="white",
            font=("Segoe UI", 9, "bold"), cursor="hand2", command=accion_guardar_esp
        )
        btn_guardar_esp.pack(side=tk.LEFT, padx=(0, 6))

        btn_quitar = tk.Button(
            frame_btn_form, text="🗑️ Quitar Especialidad", bg="#9B2C2C", fg="white",
            font=("Segoe UI", 9), cursor="hand2", command=accion_quitar_esp
        )
        btn_quitar.pack(side=tk.LEFT, padx=(0, 6))

        btn_cerrar = tk.Button(
            frame_btn_form, text="Cerrar", bg="#E2E8F0", cursor="hand2", command=modal.destroy
        )
        btn_cerrar.pack(side=tk.RIGHT)

        refrescar_datos()

    def accion_insertar_medico(self):
        dni = self.med_dni.get().strip()
        nom = self.med_nombre.get().strip()
        ape = self.med_apellido.get().strip()
        mat = self.med_matricula.get().strip()
        cuil = self.med_cuil.get().strip()
        guardias_str = self.med_guardias.get().strip()

        if not (dni and nom and ape and mat and cuil):
            messagebox.showwarning("Atención", "DNI, Nombre, Apellido, Matrícula y CUIL son obligatorios.")
            return

        try:
            guardias = int(guardias_str) if guardias_str else 0
        except ValueError:
            messagebox.showerror("Error", "Guardias máximas debe ser un número entero.")
            return

        conn = None
        cursor = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()

            foto_bytes = None
            if self.med_ruta_foto and os.path.exists(self.med_ruta_foto):
                with open(self.med_ruta_foto, "rb") as f:
                    foto_bytes = f.read()

            # Invocar Stored Procedure transaccional 'sp_registrar_medico' (foto opcional)
            if foto_bytes:
                invocar_sp(cursor, "sp_registrar_medico", [dni, nom, ape, mat, cuil, guardias, foto_bytes])
            else:
                invocar_sp(cursor, "sp_registrar_medico", [dni, nom, ape, mat, cuil, guardias])
            
            self.log_exito(f"Médico Matrícula {mat} - Dr. {ape}, {nom} registrado exitosamente.")
            self.med_dni.delete(0, tk.END)
            self.med_nombre.delete(0, tk.END)
            self.med_apellido.delete(0, tk.END)
            self.med_matricula.delete(0, tk.END)
            self.med_cuil.delete(0, tk.END)
            self.med_ruta_foto = None
            self.lbl_foto_nombre.config(text="Sin foto")
            self.cargar_lista_medicos()
            self.cargar_combos_guardia()

            if messagebox.askyesno("Médico Registrado", f"Dr. {ape} registrado con éxito.\n\n¿Deseas asignarle especialidades médicas (tabla TIENE) ahora mismo?"):
                for item_id in self.tabla_medicos.get_children():
                    if str(self.tabla_medicos.item(item_id)['values'][0]) == mat:
                        self.tabla_medicos.selection_set(item_id)
                        self.tabla_medicos.focus(item_id)
                        self.accion_gestionar_especialidades_medico()
                        break

        except Exception as e:
            if conn:
                conn.rollback()
            self.reportar_error("Error", e, prefijo_log="Error al registrar médico")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def cargar_lista_medicos(self):
        for item in self.tabla_medicos.get_children():
            self.tabla_medicos.delete(item)
        conn = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            cur_med = cursor.connection.cursor()
            invocar_sp(cursor, "sp_listar_medicos", [cur_med])
            for row in cur_med.fetchall():
                self.tabla_medicos.insert("", tk.END, values=row)
            cur_med.close()
            cursor.close()
        except Exception as e:
            self.log_error(f"No se pudieron cargar los médicos: {traducir_error_oracle(e, incluir_tecnico=True)}")
        finally:
            if conn:
                conn.close()

    # 3. Subtab Sector
    def construir_subtab_sector(self, parent):
        frame_form = ttk.LabelFrame(parent, text=" Crear Nuevo Sector ", padding=10)
        frame_form.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        ttk.Label(frame_form, text="Nombre del Sector (máx 20 car.):").grid(row=0, column=0, sticky="w", pady=4)
        self.txt_sec_nombre = ttk.Entry(frame_form, width=24)
        self.txt_sec_nombre.grid(row=1, column=0, pady=4, sticky="w")

        lbl_ayuda = ttk.Label(
            frame_form, 
            text="Ejemplos:\n• Maternidad\n• Neonatología\n• Traumatología\n• Terapia Intensiva\n• Pediatría\n• Guardia",
            font=("Segoe UI", 8),
            foreground="#4A5568",
            justify="left"
        )
        lbl_ayuda.grid(row=2, column=0, sticky="w", pady=8)

        btn_guardar = tk.Button(
            frame_form, text="💾 Crear Sector", bg="#276749", fg="white", font=("Segoe UI", 9, "bold"),
            relief="groove", cursor="hand2", command=self.accion_insertar_sector
        )
        btn_guardar.grid(row=3, column=0, pady=10, sticky="ew")

        # Lista de sectores
        frame_lista = ttk.LabelFrame(parent, text=" Sectores del Hospital ", padding=10)
        frame_lista.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.tabla_sectores = ttk.Treeview(frame_lista, columns=("ID", "Nombre", "Habitaciones"), show="headings")
        self.tabla_sectores.heading("ID", text="ID Sector")
        self.tabla_sectores.heading("Nombre", text="Nombre del Sector")
        self.tabla_sectores.heading("Habitaciones", text="Habitaciones Asociadas")
        self.tabla_sectores.column("ID", width=80, anchor="center")
        self.tabla_sectores.column("Nombre", width=160, anchor="w")
        self.tabla_sectores.column("Habitaciones", width=140, anchor="center")
        self.tabla_sectores.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        btn_refrescar = tk.Button(frame_lista, text="🔄 Refrescar Sectores", bg="#E2E8F0", cursor="hand2", command=self.actualizar_todos_los_sectores)
        btn_refrescar.pack(anchor="w")

        self.actualizar_todos_los_sectores()

    def accion_insertar_sector(self):
        nombre = self.txt_sec_nombre.get().strip()
        if self.insertar_sector_bd(nombre):
            self.txt_sec_nombre.delete(0, tk.END)

    def accion_dialogo_nuevo_sector(self):
        nombre = simpledialog.askstring("Nuevo Sector", "Ingresa el nombre del nuevo sector (máximo 20 caracteres):")
        if nombre:
            self.insertar_sector_bd(nombre)

    def insertar_sector_bd(self, nombre):
        nombre = nombre.strip()
        if not nombre:
            messagebox.showwarning("Atención", "El nombre del sector no puede estar vacío.")
            return False
        if len(nombre) > 20:
            messagebox.showwarning("Atención", "El nombre del sector no puede superar los 20 caracteres permitidos por la base de datos.")
            return False

        conn = None
        cursor = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            id_sec_var = cursor.var(oracledb.NUMBER)
            invocar_sp(cursor, "sp_crear_sector", [nombre, id_sec_var])
            nuevo_id = int(id_sec_var.getvalue())
            self.log_exito(f"Sector #{nuevo_id} '{nombre}' creado exitosamente en la base de datos.")
            messagebox.showinfo("Éxito", f"Sector '{nombre}' (ID #{nuevo_id}) creado correctamente.")
            self.actualizar_todos_los_sectores()
            if hasattr(self, 'hab_sector_cb'):
                self.hab_sector_cb.set(f"{nuevo_id} - {nombre}")
            return True
        except Exception as e:
            if conn:
                conn.rollback()
            self.reportar_error("Error al Crear Sector", e, prefijo_log="Error al crear sector")
            return False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def actualizar_todos_los_sectores(self):
        conn = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            cur_sec_combo = cursor.connection.cursor()
            invocar_sp(cursor, "sp_listar_sectores_combo", [cur_sec_combo])
            sectores = cur_sec_combo.fetchall()
            cur_sec_combo.close()

            valores_sectores = [f"{s[0]} - {s[1]}" for s in sectores]
            if hasattr(self, 'hab_sector_cb'):
                sel_actual = self.hab_sector_cb.get()
                self.hab_sector_cb["values"] = valores_sectores
                if sel_actual in valores_sectores:
                    self.hab_sector_cb.set(sel_actual)
                elif valores_sectores:
                    self.hab_sector_cb.current(0)

            if hasattr(self, 'tabla_sectores'):
                for item in self.tabla_sectores.get_children():
                    self.tabla_sectores.delete(item)
                cur_sec_tabla = cursor.connection.cursor()
                invocar_sp(cursor, "sp_listar_sectores", [cur_sec_tabla])
                for row in cur_sec_tabla.fetchall():
                    self.tabla_sectores.insert("", tk.END, values=(row[0], row[1], f"{row[2]} habitaciones"))
                cur_sec_tabla.close()

            cursor.close()
        except Exception as e:
            self.log_error(f"Error al actualizar sectores: {traducir_error_oracle(e, incluir_tecnico=True)}")
        finally:
            if conn:
                conn.close()

    # 4. Subtab Habitación
    def construir_subtab_habitacion(self, parent):
        frame_form = ttk.LabelFrame(parent, text=" Crear Habitación y Asignar Rondas ", padding=10)
        frame_form.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        ttk.Label(frame_form, text="Piso (ej: 1, 2, PB):").grid(row=0, column=0, sticky="w", pady=3)
        self.hab_piso = ttk.Entry(frame_form, width=20)
        self.hab_piso.insert(0, "1")
        self.hab_piso.grid(row=0, column=1, pady=3)

        ttk.Label(frame_form, text="Orientación:").grid(row=1, column=0, sticky="w", pady=3)
        self.hab_orientacion = ttk.Combobox(frame_form, values=["Norte", "Sur", "Este", "Oeste", "NORTE", "SUR", "ESTE", "OESTE"], state="readonly", width=18)
        self.hab_orientacion.set("Norte")
        self.hab_orientacion.grid(row=1, column=1, pady=3)

        ttk.Label(frame_form, text="Sector:").grid(row=2, column=0, sticky="w", pady=3)
        frame_sec_sel = ttk.Frame(frame_form)
        frame_sec_sel.grid(row=2, column=1, pady=3, sticky="w")
        self.hab_sector_cb = ttk.Combobox(frame_sec_sel, state="readonly", width=14)
        self.hab_sector_cb.pack(side=tk.LEFT, padx=(0, 4))
        btn_crear_sec_rapido = tk.Button(
            frame_sec_sel, text="➕", bg="#E2E8F0", cursor="hand2", font=("Segoe UI", 8, "bold"),
            command=self.accion_dialogo_nuevo_sector
        )
        btn_crear_sec_rapido.pack(side=tk.LEFT)

        # Asignar Rondas para los 7 días
        frame_rondas = ttk.LabelFrame(frame_form, text=" Asignar Rondas (Turnos 1 a 4) para los 7 días ", padding=6)
        frame_rondas.grid(row=3, column=0, columnspan=2, pady=8, sticky="ew")

        self.dias_semana = [
            ("LUNES", "Lunes"),
            ("MARTES", "Martes"),
            ("MIERCOLES", "Miércoles"),
            ("JUEVES", "Jueves"),
            ("VIERNES", "Viernes"),
            ("SABADO", "Sábado"),
            ("DOMINGO", "Domingo")
        ]
        self.cb_turnos_dias = {}

        for idx, (dia_cod, dia_nombre) in enumerate(self.dias_semana):
            ttk.Label(frame_rondas, text=f"{dia_nombre}:", font=("Segoe UI", 9)).grid(row=idx, column=0, sticky="w", pady=2, padx=(2, 8))
            cb = ttk.Combobox(frame_rondas, values=["Turno 1", "Turno 2", "Turno 3", "Turno 4"], state="readonly", width=10)
            cb.set("Turno 1")
            cb.grid(row=idx, column=1, pady=2)
            self.cb_turnos_dias[dia_cod] = cb

        btn_guardar = tk.Button(
            frame_form, text="💾 Crear Habitación y Guardar Rondas", bg="#276749", fg="white", font=("Segoe UI", 9, "bold"),
            relief="groove", cursor="hand2", command=self.accion_insertar_habitacion
        )
        btn_guardar.grid(row=4, column=0, columnspan=2, pady=10, sticky="ew")

        # Lista de habitaciones
        frame_lista = ttk.LabelFrame(parent, text=" Habitaciones y Rondas Asignadas ", padding=10)
        frame_lista.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.tabla_habitaciones = ttk.Treeview(frame_lista, columns=("ID", "Piso", "Orientacion", "Sector", "CantRondas"), show="headings")
        self.tabla_habitaciones.heading("ID", text="ID Habitación")
        self.tabla_habitaciones.heading("Piso", text="Piso")
        self.tabla_habitaciones.heading("Orientacion", text="Orientación")
        self.tabla_habitaciones.heading("Sector", text="Sector")
        self.tabla_habitaciones.heading("CantRondas", text="Rondas Vinculadas")
        for col in ("ID", "Piso", "Orientacion", "Sector", "CantRondas"):
            self.tabla_habitaciones.column(col, width=95, anchor="center")
        self.tabla_habitaciones.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        frame_botones_hab = ttk.Frame(frame_lista)
        frame_botones_hab.pack(fill=tk.X)

        btn_refrescar = tk.Button(frame_botones_hab, text="🔄 Refrescar Lista", bg="#E2E8F0", cursor="hand2", command=self.cargar_lista_habitaciones)
        btn_refrescar.pack(side=tk.LEFT, padx=(0, 6))

        btn_ver_rondas = tk.Button(frame_botones_hab, text="📅 Ver Rondas de los 7 Días", bg="#E2E8F0", cursor="hand2", command=self.accion_ver_rondas_habitacion)
        btn_ver_rondas.pack(side=tk.LEFT)

        self.cargar_lista_habitaciones()

    def accion_ver_rondas_habitacion(self):
        seleccion = self.tabla_habitaciones.selection()
        if not seleccion:
            messagebox.showinfo("Seleccionar Habitación", "Por favor selecciona una habitación de la lista.")
            return
        item = self.tabla_habitaciones.item(seleccion[0])
        id_hab = item['values'][0]

        conn = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            cur_ron = cursor.connection.cursor()
            invocar_sp(cursor, "sp_obtener_rondas_habitacion", [id_hab, cur_ron])
            filas = cur_ron.fetchall()
            cur_ron.close()
            cursor.close()
            if not filas:
                messagebox.showinfo("Rondas", f"La habitación #{id_hab} no tiene rondas asignadas aún.")
                return

            detalle = f"📅 RONDAS ASIGNADAS - HABITACIÓN #{id_hab}:\n\n"
            for dia, turno, id_ronda in filas:
                turno_fmt = f"Turno {turno}" if str(turno).isdigit() else str(turno)
                detalle += f"• {dia:<10} ➔ {turno_fmt:<10} (Ronda ID #{id_ronda})\n"

            messagebox.showinfo(f"Rondas de Habitación #{id_hab}", detalle)
        except Exception as e:
            self.reportar_error("Error", e, prefijo_log="Error al consultar rondas")
        finally:
            if conn:
                conn.close()

    def accion_insertar_habitacion(self):
        piso = self.hab_piso.get().strip()
        ori = self.hab_orientacion.get().strip()
        sector_seleccion = self.hab_sector_cb.get().strip()

        if not (piso and ori and sector_seleccion):
            messagebox.showwarning("Atención", "Completa piso, orientación y sector.")
            return

        id_sector = sector_seleccion.split(" - ")[0]

        conn = None
        cursor = None
        try:
            self.log_info(f"Iniciando creación de Habitación (Piso {piso}, {ori}) y asignación de rondas...")
            conn = obtener_conexion()
            cursor = conn.cursor()

            # Ejecutar Stored Procedure transaccional 'sp_crear_habitacion_con_rondas'
            turnos = [int(self.cb_turnos_dias[dia_cod].get().replace("Turno", "").strip()) for dia_cod, _ in self.dias_semana]
            id_hab_var = cursor.var(oracledb.NUMBER)
            invocar_sp(cursor, "sp_crear_habitacion_con_rondas", [
                str(piso), ori, int(id_sector),
                turnos[0], turnos[1], turnos[2], turnos[3], turnos[4], turnos[5], turnos[6],
                id_hab_var
            ])
            nueva_hab = int(id_hab_var.getvalue())
            msg_exito = f"Habitación #{nueva_hab} creada y asociada a las rondas de los 7 días con éxito (COMMIT)."
            self.log_exito(msg_exito)
            messagebox.showinfo("Éxito", msg_exito)
            self.cargar_lista_habitaciones()

        except Exception as e:
            if conn:
                conn.rollback()
            self.reportar_error("Error en Creación", e, prefijo_log="Error al crear habitación y rondas")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def cargar_lista_habitaciones(self):
        self.actualizar_todos_los_sectores()

        for item in self.tabla_habitaciones.get_children():
            self.tabla_habitaciones.delete(item)
        conn = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            cur_hab = cursor.connection.cursor()
            invocar_sp(cursor, "sp_listar_habitaciones", [cur_hab])
            for row in cur_hab.fetchall():
                cant_texto = f"{row[4]} días asignados" if row[4] > 0 else "Sin rondas"
                self.tabla_habitaciones.insert("", tk.END, values=(row[0], row[1], row[2], row[3], cant_texto))
            cur_hab.close()
            cursor.close()
        except Exception as e:
            self.log_error(f"No se pudieron cargar habitaciones: {traducir_error_oracle(e, incluir_tecnico=True)}")
        finally:
            if conn:
                conn.close()

    # 5. Subtab Cama
    def construir_subtab_cama(self, parent):
        frame_form = ttk.LabelFrame(parent, text=" Crear Cama en Habitación ", padding=10)
        frame_form.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        ttk.Label(frame_form, text="ID de Habitación:").grid(row=0, column=0, sticky="w", pady=4)
        self.cama_id_hab = ttk.Entry(frame_form, width=22)
        self.cama_id_hab.grid(row=0, column=1, pady=4)

        ttk.Label(frame_form, text="Número de Cama (>= 1):").grid(row=1, column=0, sticky="w", pady=4)
        self.cama_nro = ttk.Entry(frame_form, width=22)
        self.cama_nro.insert(0, "1")
        self.cama_nro.grid(row=1, column=1, pady=4)

        ttk.Label(frame_form, text="Estado:").grid(row=2, column=0, sticky="w", pady=4)
        self.cama_estado = ttk.Combobox(frame_form, values=["LIBRE", "OCUPADA"], state="readonly", width=20)
        self.cama_estado.set("LIBRE")
        self.cama_estado.grid(row=2, column=1, pady=4)

        btn_guardar = tk.Button(
            frame_form, text="💾 Crear Cama", bg="#276749", fg="white", font=("Segoe UI", 9, "bold"),
            relief="groove", cursor="hand2", command=self.accion_insertar_cama
        )
        btn_guardar.grid(row=3, column=0, columnspan=2, pady=12, sticky="ew")

        # Lista de todas las camas
        frame_lista = ttk.LabelFrame(parent, text=" Camas en el Hospital ", padding=10)
        frame_lista.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.tabla_todas_camas = ttk.Treeview(frame_lista, columns=("Habitacion", "Cama", "Estado", "Sector"), show="headings")
        self.tabla_todas_camas.heading("Habitacion", text="ID Habitación")
        self.tabla_todas_camas.heading("Cama", text="Cama Nro")
        self.tabla_todas_camas.heading("Estado", text="Estado")
        self.tabla_todas_camas.heading("Sector", text="Sector")
        for col in ("Habitacion", "Cama", "Estado", "Sector"):
            self.tabla_todas_camas.column(col, width=110, anchor="center")
        self.tabla_todas_camas.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        btn_refrescar = tk.Button(frame_lista, text="🔄 Refrescar Camas", bg="#E2E8F0", cursor="hand2", command=self.cargar_todas_las_camas)
        btn_refrescar.pack(anchor="w")
        self.cargar_todas_las_camas()

    def accion_insertar_cama(self):
        id_hab_str = self.cama_id_hab.get().strip()
        nro_cama_str = self.cama_nro.get().strip()
        estado = self.cama_estado.get().strip().upper()

        if not (id_hab_str and nro_cama_str and estado):
            messagebox.showwarning("Atención", "Todos los campos de cama son requeridos.")
            return

        try:
            id_hab = int(id_hab_str)
            nro_cama = int(nro_cama_str)
        except ValueError:
            messagebox.showerror("Error", "Habitación y Cama deben ser valores numéricos enteros.")
            return

        conn = None
        cursor = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            invocar_sp(cursor, "sp_crear_cama", [id_hab, nro_cama, estado])
            self.log_exito(f"Cama {nro_cama} creada en Habitación #{id_hab} con estado '{estado}'.")
            messagebox.showinfo("Éxito", f"Cama {nro_cama} creada con éxito.")
            self.cargar_todas_las_camas()
            self.cargar_camas_libres()
        except Exception as e:
            if conn:
                conn.rollback()
            self.reportar_error("Error", e, prefijo_log="Error al crear cama")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def cargar_todas_las_camas(self):
        for item in self.tabla_todas_camas.get_children():
            self.tabla_todas_camas.delete(item)
        conn = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            cur_cam = cursor.connection.cursor()
            invocar_sp(cursor, "sp_listar_todas_camas", [cur_cam])
            for row in cur_cam.fetchall():
                self.tabla_todas_camas.insert("", tk.END, values=row)
            cur_cam.close()
            cursor.close()
        except Exception as e:
            self.log_error(f"No se pudieron cargar las camas: {traducir_error_oracle(e, incluir_tecnico=True)}")
        finally:
            if conn:
                conn.close()

    # 6. Gestión de Sesión de BD para Guardias
    def obtener_conexion_guardias_o_default(self):
        """Devuelve conexión con el usuario de guardias si está autenticado, o con el usuario por defecto de .env."""
        if self.usuario_guardias and self.password_guardias:
            return obtener_conexion(self.usuario_guardias, self.password_guardias)
        return obtener_conexion()

    def obtener_conexion_guardias(self):
        """Devuelve una conexión exigiendo usuario autenticado para guardias. Si no hay sesión, pide login."""
        if not self.usuario_guardias or not self.password_guardias:
            if not self.solicitar_login_guardias():
                return None
        try:
            return obtener_conexion(self.usuario_guardias, self.password_guardias)
        except Exception as e:
            self.usuario_guardias = None
            self.password_guardias = None
            self.actualizar_banner_usuario_guardias()
            messagebox.showerror("Error de Autenticación", f"Falló la conexión con el usuario de guardias:\n{traducir_error_oracle(e)}")
            if self.solicitar_login_guardias():
                return obtener_conexion(self.usuario_guardias, self.password_guardias)
            return None

    def solicitar_login_guardias(self, forzar=False):
        """Abre un diálogo modal para iniciar sesión o cambiar a otro usuario de BD para gestionar guardias."""
        resultado = {"exito": False}

        dialogo = tk.Toplevel(self)
        dialogo.title("🔐 Login de Usuario - Gestión de Guardias")
        dialogo.configure(bg=self.COLOR_FONDO)
        dialogo.geometry("440x290")
        dialogo.minsize(420, 270)
        dialogo.transient(self)
        dialogo.grab_set()

        try:
            x = self.winfo_x() + (self.winfo_width() // 2) - 220
            y = self.winfo_y() + (self.winfo_height() // 2) - 145
            dialogo.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        frame = ttk.Frame(dialogo, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text="🔐 Autenticación de Usuario para Guardias",
            font=("Segoe UI", 11, "bold"),
            foreground="#1A365D"
        ).pack(anchor="w", pady=(0, 4))

        ttk.Label(
            frame,
            text="Para gestionar guardias debe ingresar con un usuario de la base de datos con permisos.",
            font=("Segoe UI", 9),
            foreground="#4A5568",
            wraplength=390,
            justify="left"
        ).pack(anchor="w", pady=(0, 10))

        grid_frame = ttk.Frame(frame)
        grid_frame.pack(fill=tk.X, pady=(0, 10))
        grid_frame.columnconfigure(1, weight=1)

        ttk.Label(grid_frame, text="Usuario BD:").grid(row=0, column=0, sticky="w", pady=5)
        entry_user = ttk.Entry(grid_frame, width=24)
        entry_user.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=5)
        usuario_sugerido = self.usuario_guardias or "44444444"
        entry_user.insert(0, usuario_sugerido)

        ttk.Label(grid_frame, text="Contraseña:").grid(row=1, column=0, sticky="w", pady=5)
        entry_pass = ttk.Entry(grid_frame, width=24, show="*")
        entry_pass.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=5)

        lbl_error = ttk.Label(frame, text="", font=("Segoe UI", 8), foreground="#C53030", wraplength=390)
        lbl_error.pack(fill=tk.X, pady=(0, 6))

        def intentar_login(event=None):
            u = entry_user.get().strip()
            p = entry_pass.get()
            if not u:
                lbl_error.config(text="⚠️ Por favor ingrese el nombre de usuario.")
                entry_user.focus_set()
                return
            if not p:
                lbl_error.config(text="⚠️ Por favor ingrese la contraseña.")
                entry_pass.focus_set()
                return

            try:
                test_conn = obtener_conexion(user=u, password=p)
                test_conn.close()

                self.usuario_guardias = u
                self.password_guardias = p
                resultado["exito"] = True
                self.log_exito(f"Sesión activa para gestión de guardias: '{u.upper()}'.")
                self.actualizar_banner_usuario_guardias()
                self.refrescar_panel_guardias()
                dialogo.destroy()
            except Exception as e:
                msg = traducir_error_oracle(e)
                lbl_error.config(text=f"❌ Error al conectar:\n{msg[:130]}...")
                self.log_error(f"Fallo de login para guardias ({u}):\n{msg}")

        entry_pass.bind("<Return>", intentar_login)
        entry_user.bind("<Return>", lambda _e: entry_pass.focus_set())

        frame_btns = ttk.Frame(frame)
        frame_btns.pack(fill=tk.X, pady=(6, 0))

        btn_conectar = tk.Button(
            frame_btns,
            text="🔓 Conectar e Ingresar",
            bg="#2B6CB0",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="groove",
            cursor="hand2",
            command=intentar_login
        )
        btn_conectar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        btn_cancelar = tk.Button(
            frame_btns,
            text="Cancelar",
            bg="#E2E8F0",
            cursor="hand2",
            command=dialogo.destroy
        )
        btn_cancelar.pack(side=tk.RIGHT)

        entry_pass.focus_set()
        self.wait_window(dialogo)
        return resultado["exito"]

    def actualizar_banner_usuario_guardias(self):
        if hasattr(self, 'lbl_usuario_guardia'):
            if self.usuario_guardias:
                self.lbl_usuario_guardia.config(
                    text=f"👤 Usuario BD conectado: {self.usuario_guardias.upper()}",
                    foreground="#276749"
                )
            else:
                self.lbl_usuario_guardia.config(
                    text="⚠️ Sesión no iniciada (Requiere login de BD)",
                    foreground="#C53030"
                )

    def restablecer_usuario_guardias(self):
        self.usuario_guardias = None
        self.password_guardias = None
        self.actualizar_banner_usuario_guardias()
        self.log_info(f"Sesión de guardias restablecida a credenciales de ('{os.getenv('DB_USER')}').")
        self.refrescar_panel_guardias()

    # Subtab Guardia
    def construir_subtab_guardia(self, parent):
        """Construye el panel de alta directa, listado, modificación y baja de guardias."""
        columna_izq = ttk.Frame(parent)
        columna_izq.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Banner de Sesión de Base de Datos para Guardias
        frame_sesion = ttk.LabelFrame(columna_izq, text=" 🔐 Sesión de Base de Datos (Guardias) ", padding=8)
        frame_sesion.pack(fill=tk.X, pady=(0, 8))
        frame_sesion.columnconfigure(0, weight=1)

        self.lbl_usuario_guardia = ttk.Label(
            frame_sesion,
            text="👤 Usuario BD: [Sin iniciar sesión]",
            font=("Segoe UI", 9, "bold"),
            foreground="#C53030"
        )
        self.lbl_usuario_guardia.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

        frame_btns_sesion = ttk.Frame(frame_sesion)
        frame_btns_sesion.grid(row=1, column=0, columnspan=2, sticky="ew")

        btn_cambiar_user = tk.Button(
            frame_btns_sesion,
            text="🔑 Cambiar Usuario BD",
            bg="#2B6CB0",
            fg="white",
            font=("Segoe UI", 8, "bold"),
            relief="groove",
            cursor="hand2",
            command=lambda: self.solicitar_login_guardias(forzar=True)
        )
        btn_cambiar_user.pack(side=tk.LEFT, padx=(0, 4))

        btn_reset_user = tk.Button(
            frame_btns_sesion,
            text="🔄 Cerrar Sesion",
            bg="#E2E8F0",
            font=("Segoe UI", 8),
            cursor="hand2",
            command=self.restablecer_usuario_guardias
        )
        btn_reset_user.pack(side=tk.LEFT, padx=(0, 4))

        btn_reaplicar_permisos = tk.Button(
            frame_btns_sesion,
            text="🛡️ Reaplicar Permisos BD",
            bg="#E2E8F0",
            font=("Segoe UI", 8),
            cursor="hand2",
            command=self.accion_ejecutar_script_usuarios
        )
        btn_reaplicar_permisos.pack(side=tk.LEFT)

        frame_form = ttk.LabelFrame(columna_izq, text=" ➕ Crear Nueva Guardia (con Médico Asignado) ", padding=10)
        frame_form.pack(fill=tk.X, pady=(0, 10))
        frame_form.columnconfigure(1, weight=1)

        ttk.Label(frame_form, text="Fecha (DD/MM/YYYY):").grid(row=0, column=0, sticky="w", pady=4)
        self.guardia_fecha = ttk.Entry(frame_form, width=34)
        self.guardia_fecha.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.guardia_fecha.grid(row=0, column=1, pady=4, padx=(6, 0), sticky="ew")

        ttk.Label(frame_form, text="Turno:").grid(row=1, column=0, sticky="w", pady=4)
        self.guardia_turno = ttk.Combobox(
            frame_form,
            values=["MAÑANA", "TARDE", "NOCHE"],
            state="readonly",
            width=32
        )
        self.guardia_turno.set("MAÑANA")
        self.guardia_turno.grid(row=1, column=1, pady=4, padx=(6, 0), sticky="ew")

        ttk.Label(frame_form, text="Médico:").grid(row=2, column=0, sticky="w", pady=4)
        self.cb_guardia_medico = ttk.Combobox(frame_form, state="readonly", width=32)
        self.cb_guardia_medico.grid(row=2, column=1, pady=4, padx=(6, 0), sticky="ew")
        self.cb_guardia_medico.bind(
            "<<ComboboxSelected>>",
            lambda _e: self._cargar_especialidades_para_combo(
                self.cb_guardia_medico, self.cb_guardia_especialidad, self.lbl_guardia_esp_info
            )
        )

        ttk.Label(frame_form, text="Especialidad:").grid(row=3, column=0, sticky="w", pady=4)
        self.cb_guardia_especialidad = ttk.Combobox(frame_form, state="readonly", width=32)
        self.cb_guardia_especialidad.grid(row=3, column=1, pady=4, padx=(6, 0), sticky="ew")
        self.cb_guardia_especialidad.bind(
            "<<ComboboxSelected>>",
            lambda _e: self._actualizar_label_esp_guardia(self.cb_guardia_especialidad, self.lbl_guardia_esp_info)
        )

        self.lbl_guardia_esp_info = ttk.Label(
            frame_form,
            text="",
            font=("Segoe UI", 8, "italic"),
            foreground="#4A5568"
        )
        self.lbl_guardia_esp_info.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 4))

        btn_guardar = tk.Button(
            frame_form,
            text="💾 Crear Guardia con Médico",
            bg="#276749",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="groove",
            cursor="hand2",
            command=self.accion_insertar_guardia
        )
        btn_guardar.grid(row=5, column=0, columnspan=2, pady=(8, 6), sticky="ew")

        ttk.Label(
            frame_form,
            text="ℹ️ Toda guardia requiere al menos un médico asignado al crearse.",
            font=("Segoe UI", 8, "italic"),
            foreground="#4A5568",
            wraplength=310,
            justify="left"
        ).grid(row=6, column=0, columnspan=2, sticky="w")

        frame_lista = ttk.LabelFrame(parent, text=" Guardias Programadas ", padding=10)
        frame_lista.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.tabla_guardias = ttk.Treeview(frame_lista, columns=("ID", "Fecha", "Turno", "Medicos"), show="headings")
        self.tabla_guardias.heading("ID", text="ID Guardia")
        self.tabla_guardias.heading("Fecha", text="Fecha")
        self.tabla_guardias.heading("Turno", text="Turno")
        self.tabla_guardias.heading("Medicos", text="Médicos Asignados")
        self.tabla_guardias.column("ID", width=75, anchor="center")
        self.tabla_guardias.column("Fecha", width=95, anchor="center")
        self.tabla_guardias.column("Turno", width=85, anchor="center")
        self.tabla_guardias.column("Medicos", width=270, anchor="w")
        self.tabla_guardias.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        self.tabla_guardias.bind("<Double-1>", lambda _e: self.abrir_dialogo_modificar_guardia())

        ttk.Label(
            frame_lista,
            text=" Selecciona una guardia para modificar o eliminar (doble clic abre Modificar).",
            font=("Segoe UI", 8, "italic"),
            foreground="#4A5568"
        ).pack(anchor="w", pady=(0, 6))

        frame_botones_guardia = ttk.Frame(frame_lista)
        frame_botones_guardia.pack(fill=tk.X)

        btn_refrescar = tk.Button(
            frame_botones_guardia,
            text="🔄 Refrescar Guardias",
            bg="#E2E8F0",
            cursor="hand2",
            command=self.refrescar_panel_guardias
        )
        btn_refrescar.pack(side=tk.LEFT, padx=(0, 6))

        btn_modificar = tk.Button(
            frame_botones_guardia,
            text="✏️ Modificar Guardia",
            bg="#2B6CB0",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="groove",
            cursor="hand2",
            command=self.abrir_dialogo_modificar_guardia
        )
        btn_modificar.pack(side=tk.LEFT, padx=(0, 6))

        btn_eliminar = tk.Button(
            frame_botones_guardia,
            text="🗑️ Eliminar Guardia",
            bg="#9B2C2C",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="groove",
            cursor="hand2",
            command=self.accion_eliminar_guardia
        )
        btn_eliminar.pack(side=tk.LEFT)

        self.actualizar_banner_usuario_guardias()
        self.refrescar_panel_guardias()

    @staticmethod
    def _parsear_clave_combo(valor):
        return valor.split(" - ", 1)[0].strip()

    def _obtener_opciones_medicos(self, cursor):
        cur_med = cursor.connection.cursor()
        invocar_sp(cursor, "sp_listar_medicos_combo", [cur_med])
        opciones = [f"{m[0]} - {m[1]}, {m[2]}" for m in cur_med.fetchall()]
        cur_med.close()
        return opciones

    def _cargar_especialidades_para_combo(self, cb_medico, cb_esp, lbl_info=None, cursor=None):
        """Carga especialidades ordenadas por disponibilidad para el médico del combo."""
        med_sel = cb_medico.get().strip()
        if not med_sel:
            cb_esp["values"] = []
            cb_esp.set("")
            self._actualizar_label_esp_guardia(cb_esp, lbl_info)
            return

        matricula = self._parsear_clave_combo(med_sel)
        conn_propia = None
        cursor_local = cursor
        try:
            if cursor_local is None:
                conn_propia = self.obtener_conexion_guardias_o_default()
                cursor_local = conn_propia.cursor()

            cur_esp = cursor_local.connection.cursor()
            invocar_sp(cursor_local, "sp_listar_especialidades_medico", [matricula, cur_esp])
            filas_esp = cur_esp.fetchall()
            cur_esp.close()

            opciones_esp = []
            for id_esp, nombre, dispuesto in filas_esp:
                estado = f"Disp: {dispuesto}" if dispuesto is not None else "No reg."
                opciones_esp.append(f"{id_esp} - {nombre} ({estado})")

            cb_esp["values"] = opciones_esp
            if opciones_esp:
                cb_esp.current(0)
            else:
                cb_esp.set("")
            self._actualizar_label_esp_guardia(cb_esp, lbl_info)

        except Exception as e:
            self.log_error(f"No se pudieron cargar las especialidades del médico: {traducir_error_oracle(e, incluir_tecnico=True)}")
        finally:
            if conn_propia:
                if cursor_local:
                    cursor_local.close()
                conn_propia.close()

    @staticmethod
    def _actualizar_label_esp_guardia(cb_esp, lbl_info):
        """Actualiza la etiqueta descriptiva de disponibilidad de la especialidad seleccionada."""
        if lbl_info is None:
            return
        esp_sel = cb_esp.get().strip()
        esp_up = esp_sel.upper()
        if not esp_sel:
            lbl_info.config(text="", foreground="#4A5568")
        elif "(DISP: SI)" in esp_up:
            lbl_info.config(text="✅ Médico dispuesto a cubrir esta especialidad.", foreground="#276749")
        elif "(DISP: NO)" in esp_up:
            lbl_info.config(text="⚠️ Figura NO dispuesto en TIENE para esta especialidad.", foreground="#C53030")
        else:
            lbl_info.config(text="⚠️ Especialidad sin registrar en TIENE para este médico.", foreground="#C53030")

    def _verificar_medico_tiene_especialidad(self, matricula, id_especialidad):
        """
        Verifica en la base de datos si el médico tiene registrada la especialidad en la tabla TIENE
        y si está dispuesto ('SI') a realizar guardias en ella.
        Retorna (valido: bool, motivo: str).
        Motivo puede ser 'ok', 'no_registrada' o 'no_dispuesto'.
        """
        conn = None
        cur = None
        try:
            conn = self.obtener_conexion_guardias_o_default()
            cur = conn.cursor()
            p_res = cur.var(oracledb.DB_TYPE_VARCHAR)
            invocar_sp(cur, "sp_verificar_medico_especialidad", [matricula, id_especialidad, p_res])
            resultado = (p_res.getvalue() or "").strip().lower()
            if resultado == "ok":
                return True, "ok"
            elif resultado == "no_dispuesto":
                return False, "no_dispuesto"
            else:
                return False, "no_registrada"
        except Exception as e:
            self.log_error(f"Error al verificar especialidad del médico: {e}")
            return False, "error_db"
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

    def refrescar_panel_guardias(self):
        """Actualiza la tabla de guardias y los selectores de médicos/especialidades."""
        self.cargar_lista_guardias()
        self.cargar_combos_guardia()

    def cargar_combos_guardia(self):
        """Carga la lista de médicos y sus especialidades para el alta directa de guardias."""
        if not hasattr(self, 'cb_guardia_medico'):
            return

        conn = None
        cursor = None
        try:
            conn = self.obtener_conexion_guardias_o_default()
            cursor = conn.cursor()
            opciones_medicos = self._obtener_opciones_medicos(cursor)
            sel_medico = self.cb_guardia_medico.get()
            self.cb_guardia_medico["values"] = opciones_medicos
            if sel_medico in opciones_medicos:
                self.cb_guardia_medico.set(sel_medico)
            elif opciones_medicos:
                self.cb_guardia_medico.current(0)
            else:
                self.cb_guardia_medico.set("")

            self._cargar_especialidades_para_combo(
                self.cb_guardia_medico, self.cb_guardia_especialidad, self.lbl_guardia_esp_info, cursor=cursor
            )
        except Exception as e:
            self.log_error(f"No se pudieron cargar los médicos para guardias: {traducir_error_oracle(e, incluir_tecnico=True)}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def accion_insertar_guardia(self):
        """Crea una guardia y la asigna directamente a un médico en una sola transacción."""
        conn = self.obtener_conexion_guardias()
        if not conn:
            return

        fecha_str = self.guardia_fecha.get().strip()
        turno = self.guardia_turno.get().strip().upper()
        med_sel = self.cb_guardia_medico.get().strip()
        esp_sel = self.cb_guardia_especialidad.get().strip()

        if not (fecha_str and turno):
            messagebox.showwarning("Atención", "Fecha y turno son obligatorios.")
            conn.close()
            return
        if not (med_sel and esp_sel):
            messagebox.showwarning(
                "Médico Obligatorio",
                "No puede existir una guardia sin un médico asignado. Selecciona un médico y una especialidad."
            )
            conn.close()
            return

        try:
            matricula = self._parsear_clave_combo(med_sel)
            id_especialidad = int(self._parsear_clave_combo(esp_sel))
        except ValueError:
            messagebox.showerror("Dato Inválido", "La especialidad seleccionada no tiene un ID válido.")
            conn.close()
            return

        fecha_dt = None
        for f_fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                fecha_dt = datetime.strptime(fecha_str, f_fmt).date()
                break
            except ValueError:
                pass
        if not fecha_dt:
            messagebox.showerror("Error", "Formato de fecha inválido. Use DD/MM/AAAA o AAAA-MM-DD.")
            conn.close()
            return

        # Verificar que el médico tenga la especialidad registrada en TIENE y esté dispuesto
        valido, motivo = self._verificar_medico_tiene_especialidad(matricula, id_especialidad)
        if not valido:
            conn.close()
            if motivo == "no_registrada":
                messagebox.showerror(
                    "Especialidad No Registrada",
                    f"❌ REGLA DE NEGOCIO VIOLADA:\n\n"
                    f"El médico {med_sel} no tiene registrada esa especialidad en la tabla TIENE."
                )
            else:
                messagebox.showerror(
                    "Médico No Dispuesto",
                    f"❌ REGLA DE NEGOCIO VIOLADA:\n\n"
                    f"El médico {med_sel} figura como NO DISPUESTO a realizar guardias para esa especialidad."
                )
            return

        cursor = None
        nuevo_id = None
        try:
            cursor = conn.cursor()
            id_guardia_var = cursor.var(oracledb.NUMBER)

            invocar_sp(cursor, "sp_crear_y_asignar_guardia", [
                turno, fecha_dt, matricula, id_especialidad, id_guardia_var
            ])
            nuevo_id = int(id_guardia_var.getvalue())

            msg = f"Guardia #{nuevo_id} ({turno} del {fecha_str}) creada y asignada a '{med_sel}' por usuario '{self.usuario_guardias.upper()}'."
            self.log_exito(msg)
            messagebox.showinfo("Éxito", msg)
            self.refrescar_panel_guardias()

        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            self.reportar_error("Error", e, prefijo_log="Error al crear y asignar guardia (ROLLBACK aplicado)")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def cargar_lista_guardias(self):
        if not hasattr(self, 'tabla_guardias'):
            return
        for item in self.tabla_guardias.get_children():
            self.tabla_guardias.delete(item)

        conn = None
        try:
            conn = self.obtener_conexion_guardias_o_default()
            cursor = conn.cursor()
            cur_grd = cursor.connection.cursor()
            invocar_sp(cursor, "sp_listar_guardias", [cur_grd])
            for row in cur_grd.fetchall():
                self.tabla_guardias.insert("", tk.END, values=row)
            cur_grd.close()
            cursor.close()
        except Exception as e:
            self.log_error(f"No se pudieron cargar las guardias: {traducir_error_oracle(e, incluir_tecnico=True)}")
        finally:
            if conn:
                conn.close()

    def abrir_dialogo_modificar_guardia(self):
        """Abre un diálogo modal para editar una guardia y sus médicos (mínimo 1 obligatorio)."""
        seleccion = self.tabla_guardias.selection()
        if not seleccion:
            messagebox.showinfo("Seleccionar Guardia", "Por favor selecciona una guardia de la lista para modificar.")
            return

        conn = self.obtener_conexion_guardias()
        if not conn:
            return

        try:
            valores = self.tabla_guardias.item(seleccion[0], "values")
        except Exception:
            valores = None

        if not valores:
            if conn:
                conn.close()
            messagebox.showwarning("Atención", "No se pudo obtener la guardia seleccionada.")
            return
        id_guardia = int(valores[0])

        cursor = None
        try:
            cursor = conn.cursor()
            cur_g = cursor.connection.cursor()
            cur_m = cursor.connection.cursor()
            invocar_sp(cursor, "sp_obtener_datos_guardia", [id_guardia, cur_g, cur_m])
            row_g = cur_g.fetchone()
            asignaciones_actuales = cur_m.fetchall()
            cur_g.close()
            cur_m.close()
            if not row_g:
                cursor.close()
                messagebox.showerror("No Encontrada", f"La guardia #{id_guardia} ya no existe en la base de datos.")
                self.refrescar_panel_guardias()
                return

            fecha_actual, turno_actual = row_g
            opciones_medicos = self._obtener_opciones_medicos(cursor)
        except Exception as e:
            self.reportar_error("Error", e, prefijo_log=f"Error al cargar guardia #{id_guardia}")
            return
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        asignaciones = [
            {
                "mat": r[0],
                "med_txt": f"{r[0]} - {r[1]}, {r[2]}",
                "id_esp": r[3],
                "esp_txt": r[4],
            }
            for r in asignaciones_actuales
        ]

        modal = tk.Toplevel(self)
        modal.title(f"Modificar Guardia #{id_guardia} (Usuario: {self.usuario_guardias.upper() if self.usuario_guardias else ''})")
        modal.configure(bg=self.COLOR_FONDO)
        modal.transient(self)
        modal.grab_set()
        modal.resizable(False, False)

        cont = ttk.Frame(modal, padding=12)
        cont.pack(fill=tk.BOTH, expand=True)

        frame_datos = ttk.LabelFrame(cont, text=f" Datos de la Guardia #{id_guardia} ", padding=10)
        frame_datos.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(frame_datos, text="Fecha (DD/MM/YYYY):").grid(row=0, column=0, sticky="w", pady=4)
        entry_fecha = ttk.Entry(frame_datos, width=18)
        entry_fecha.insert(0, fecha_actual)
        entry_fecha.grid(row=0, column=1, padx=(6, 14), pady=4, sticky="w")

        ttk.Label(frame_datos, text="Turno:").grid(row=0, column=2, sticky="w", pady=4)
        cb_turno = ttk.Combobox(frame_datos, values=["MAÑANA", "TARDE", "NOCHE"], state="readonly", width=15)
        cb_turno.set(turno_actual)
        cb_turno.grid(row=0, column=3, padx=(6, 0), pady=4, sticky="w")

        frame_meds = ttk.LabelFrame(cont, text=" Médicos Asignados (mínimo 1 obligatorio) ", padding=10)
        frame_meds.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        frame_meds.columnconfigure(1, weight=1)

        tree_asig = ttk.Treeview(frame_meds, columns=("Matricula", "Medico", "Especialidad"), show="headings", height=4)
        tree_asig.heading("Matricula", text="Matrícula")
        tree_asig.heading("Medico", text="Médico")
        tree_asig.heading("Especialidad", text="Especialidad")
        tree_asig.column("Matricula", width=90, anchor="center")
        tree_asig.column("Medico", width=190, anchor="w")
        tree_asig.column("Especialidad", width=160, anchor="w")
        tree_asig.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        def refrescar_tree_asig():
            tree_asig.delete(*tree_asig.get_children())
            for idx, item in enumerate(asignaciones):
                tree_asig.insert("", tk.END, iid=str(idx), values=(item["mat"], item["med_txt"], item["esp_txt"]))

        refrescar_tree_asig()
        if asignaciones:
            tree_asig.selection_set("0")

        ttk.Label(frame_meds, text="Médico:").grid(row=1, column=0, sticky="w", pady=3)
        cb_mod_med = ttk.Combobox(frame_meds, values=opciones_medicos, state="readonly", width=38)
        cb_mod_med.grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=3)
        if opciones_medicos:
            cb_mod_med.current(0)

        ttk.Label(frame_meds, text="Especialidad:").grid(row=2, column=0, sticky="w", pady=3)
        cb_mod_esp = ttk.Combobox(frame_meds, state="readonly", width=38)
        cb_mod_esp.grid(row=2, column=1, sticky="ew", padx=(6, 0), pady=3)

        lbl_mod_esp_info = ttk.Label(frame_meds, text="", font=("Segoe UI", 8, "italic"), foreground="#4A5568")
        lbl_mod_esp_info.grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 6))

        cb_mod_med.bind(
            "<<ComboboxSelected>>",
            lambda _e: self._cargar_especialidades_para_combo(cb_mod_med, cb_mod_esp, lbl_mod_esp_info)
        )
        cb_mod_esp.bind(
            "<<ComboboxSelected>>",
            lambda _e: self._actualizar_label_esp_guardia(cb_mod_esp, lbl_mod_esp_info)
        )
        self._cargar_especialidades_para_combo(cb_mod_med, cb_mod_esp, lbl_mod_esp_info)

        def obtener_par_seleccionado():
            med_sel = cb_mod_med.get().strip()
            esp_sel = cb_mod_esp.get().strip()
            if not (med_sel and esp_sel):
                messagebox.showwarning("Atención", "Selecciona un médico y una especialidad.", parent=modal)
                return None
            mat = self._parsear_clave_combo(med_sel)
            id_esp = int(self._parsear_clave_combo(esp_sel))
            esp_nombre = esp_sel.split(" - ", 1)[1].rsplit(" (", 1)[0].strip()
            return {"mat": mat, "med_txt": med_sel, "id_esp": id_esp, "esp_txt": esp_nombre}

        def agregar_medico_lista():
            nuevo = obtener_par_seleccionado()
            if not nuevo:
                return

            # Verificar que el médico tenga la especialidad registrada en TIENE y esté dispuesto
            valido, motivo = self._verificar_medico_tiene_especialidad(nuevo["mat"], nuevo["id_esp"])
            if not valido:
                if motivo == "no_registrada":
                    msg_error = (
                        f"❌ REGLA DE NEGOCIO VIOLADA:\n\n"
                        f"El médico {nuevo['med_txt']} no tiene registrada la especialidad '{nuevo['esp_txt']}' en la tabla TIENE."
                    )
                elif motivo == "no_dispuesto":
                    msg_error = (
                        f"❌ REGLA DE NEGOCIO VIOLADA:\n\n"
                        f"El médico {nuevo['med_txt']} figura como NO DISPUESTO a realizar guardias para la especialidad '{nuevo['esp_txt']}'."
                    )
                else:
                    msg_error = "Ocurrió un error al verificar la especialidad del médico en la base de datos."

                messagebox.showerror("Especialidad No Permitida", msg_error, parent=modal)
                return

            if any(a["mat"] == nuevo["mat"] and a["id_esp"] == nuevo["id_esp"] for a in asignaciones):
                messagebox.showinfo("Ya Asignado", "Ese médico ya está asignado a la guardia con esa especialidad.", parent=modal)
                return
            asignaciones.append(nuevo)
            refrescar_tree_asig()
            tree_asig.selection_set(str(len(asignaciones) - 1))

        def reemplazar_medico_lista():
            sel = tree_asig.selection()
            if not sel:
                if len(asignaciones) == 1:
                    idx = 0
                else:
                    messagebox.showinfo("Seleccionar Fila", "Selecciona de la tabla el médico que deseas reemplazar.", parent=modal)
                    return
            else:
                idx = int(sel[0])

            med_anterior = asignaciones[idx]
            mat_anterior = med_anterior["mat"]
            id_esp_anterior = med_anterior["id_esp"]
            med_txt_anterior = med_anterior["med_txt"]
            esp_txt_anterior = med_anterior["esp_txt"]

            nuevo = obtener_par_seleccionado()
            if not nuevo:
                return

            mat_nueva = nuevo["mat"]
            med_txt_nueva = nuevo["med_txt"]
            id_esp_nueva = nuevo["id_esp"]
            esp_txt_nueva = nuevo["esp_txt"]

            if mat_nueva == mat_anterior and id_esp_nueva == id_esp_anterior:
                messagebox.showinfo("Mismo Médico y Especialidad", "Has seleccionado al mismo médico y especialidad que ya están asignados.", parent=modal)
                return

            # Regla de negocio: El médico no puede reemplazar al seleccionado si no tiene esa especialidad registrada (y dispuesta) en TIENE
            valido, motivo = self._verificar_medico_tiene_especialidad(mat_nueva, id_esp_nueva)
            if not valido:
                if motivo == "no_registrada":
                    msg_error = (
                        f"❌ REGLA DE NEGOCIO VIOLADA:\n\n"
                        f"El médico {med_txt_nueva} no tiene registrada la especialidad '{esp_txt_nueva}' en el sistema (tabla TIENE).\n\n"
                        f"No se puede realizar el reemplazo. Se mantiene el médico que estaba anteriormente:\n"
                        f"• {med_txt_anterior} ({esp_txt_anterior})"
                    )
                elif motivo == "no_dispuesto":
                    msg_error = (
                        f"❌ REGLA DE NEGOCIO VIOLADA:\n\n"
                        f"El médico {med_txt_nueva} figura como NO DISPUESTO a realizar guardias para la especialidad '{esp_txt_nueva}'.\n\n"
                        f"No se puede realizar el reemplazo. Se mantiene el médico que estaba anteriormente:\n"
                        f"• {med_txt_anterior} ({esp_txt_anterior})"
                    )
                else:
                    msg_error = "Ocurrió un error al verificar la especialidad del médico en la base de datos."

                messagebox.showerror("Reemplazo No Permitido", msg_error, parent=modal)
                # Debe quedar el médico que estaba anteriormente: no modificamos asignaciones[idx]
                refrescar_tree_asig()
                tree_asig.selection_set(str(idx))
                return

            # Verificar que no quede duplicado en otra fila de la guardia
            if any(i != idx and a["mat"] == mat_nueva and a["id_esp"] == id_esp_nueva for i, a in enumerate(asignaciones)):
                messagebox.showinfo("Duplicado", f"El médico {med_txt_nueva} ya figura asignado a esta guardia en la especialidad '{esp_txt_nueva}'.", parent=modal)
                return

            # Reemplazar al médico (puede ser con la misma especialidad o con cualquier especialidad que el médico tenga dispuesta)
            asignaciones[idx] = nuevo
            refrescar_tree_asig()
            tree_asig.selection_set(str(idx))
            self.log_info(f"Médico reemplazado en guardia: '{med_txt_anterior}' ({esp_txt_anterior}) por '{med_txt_nueva}' ({esp_txt_nueva}).")

        def quitar_medico_lista():
            if len(asignaciones) <= 1:
                messagebox.showwarning(
                    "Regla de Negocio",
                    "Una guardia no puede quedar sin médicos asignados.\n"
                    "Para cambiar el único médico usa 'Reemplazar', o para darla de baja usa 'Eliminar Guardia'.",
                    parent=modal
                )
                return
            sel = tree_asig.selection()
            if not sel:
                messagebox.showinfo("Seleccionar Fila", "Selecciona el médico que deseas quitar de la guardia.", parent=modal)
                return
            del asignaciones[int(sel[0])]
            refrescar_tree_asig()

        frame_btns_med = ttk.Frame(frame_meds)
        frame_btns_med.grid(row=4, column=0, columnspan=2, sticky="ew")

        tk.Button(
            frame_btns_med, text="➕ Agregar Médico", bg="#E2E8F0", cursor="hand2", command=agregar_medico_lista
        ).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(
            frame_btns_med, text="🔄 Reemplazar Seleccionado", bg="#E2E8F0", cursor="hand2", command=reemplazar_medico_lista
        ).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(
            frame_btns_med, text="➖ Quitar Seleccionado", bg="#FED7D7", cursor="hand2", command=quitar_medico_lista
        ).pack(side=tk.LEFT)

        def guardar_modificacion():
            fecha_nueva = entry_fecha.get().strip()
            turno_nuevo = cb_turno.get().strip().upper()
            if not (fecha_nueva and turno_nuevo):
                messagebox.showwarning("Campos Incompletos", "Fecha y turno son obligatorios.", parent=modal)
                return
            if len(asignaciones) < 1:
                messagebox.showerror(
                    "Operación Prohibida",
                    "Una guardia no puede quedar sin médicos asignados. Asigna al menos un médico.",
                    parent=modal
                )
                return

            fecha_dt = None
            for f_fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                try:
                    fecha_dt = datetime.strptime(fecha_nueva, f_fmt).date()
                    break
                except ValueError:
                    pass
            if not fecha_dt:
                messagebox.showerror("Error", "Formato de fecha inválido. Use DD/MM/AAAA o AAAA-MM-DD.", parent=modal)
                return

            conn_save = self.obtener_conexion_guardias()
            if not conn_save:
                return

            asignaciones_str = ",".join(f"{a['mat']}:{a['id_esp']}" for a in asignaciones)

            cur_save = None
            try:
                cur_save = conn_save.cursor()

                # Modificar fecha, turno y asignaciones en una única transacción atómica (SP)
                invocar_sp(cur_save, "sp_modificar_guardia", [id_guardia, fecha_dt, turno_nuevo, asignaciones_str])

                msg = f"Guardia #{id_guardia} modificada con éxito ({turno_nuevo} del {fecha_nueva}) por usuario '{self.usuario_guardias.upper()}'."
                self.log_exito(msg)
                messagebox.showinfo("Modificación Exitosa", msg, parent=modal)
                modal.destroy()
                self.refrescar_panel_guardias()
            except Exception as e:
                if conn_save:
                    conn_save.rollback()
                self.reportar_error("Error al Modificar Guardia", e, prefijo_log=f"Error al modificar guardia #{id_guardia} (ROLLBACK aplicado)", parent=modal)
            finally:
                if cur_save:
                    cur_save.close()
                if conn_save:
                    conn_save.close()

        frame_acciones = ttk.Frame(cont)
        frame_acciones.pack(fill=tk.X)

        tk.Button(
            frame_acciones,
            text="💾 Guardar Cambios",
            bg="#276749",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="groove",
            cursor="hand2",
            command=guardar_modificacion
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))

        tk.Button(
            frame_acciones,
            text="Cancelar",
            bg="#E2E8F0",
            cursor="hand2",
            command=modal.destroy
        ).pack(side=tk.RIGHT)

    def accion_eliminar_guardia(self):
        """Da de baja la guardia seleccionada (elimina GUARDIA y en cascada CUBIERTA_POR)."""
        seleccion = self.tabla_guardias.selection()
        if not seleccion:
            messagebox.showinfo("Seleccionar Guardia", "Por favor selecciona una guardia de la lista para eliminar.")
            return

        conn = self.obtener_conexion_guardias()
        if not conn:
            return

        try:
            valores = self.tabla_guardias.item(seleccion[0], "values")
        except Exception:
            valores = None

        if not valores or len(valores) < 4:
            conn.close()
            messagebox.showwarning("Atención", "No se pudo obtener la guardia seleccionada.")
            return
        id_guardia, fecha, turno, medicos = int(valores[0]), valores[1], valores[2], valores[3]

        confirmar = messagebox.askyesno(
            "Confirmar Baja de Guardia",
            f"¿Deseas eliminar definitivamente la Guardia #{id_guardia}?\n\n"
            f"• Fecha: {fecha}\n"
            f"• Turno: {turno}\n"
            f"• Médicos asignados: {medicos}\n"
            f"• Operador BD: {self.usuario_guardias.upper()}\n\n"
            "Esta acción dará de baja la guardia y sus asignaciones en CUBIERTA_POR."
        )
        if not confirmar:
            conn.close()
            return

        cursor = None
        try:
            cursor = conn.cursor()
            invocar_sp(cursor, "sp_eliminar_guardia", [id_guardia])

            msg = f"Guardia #{id_guardia} ({turno} del {fecha}) eliminada correctamente por usuario '{self.usuario_guardias.upper()}'."
            self.log_exito(msg)
            messagebox.showinfo("Guardia Eliminada", msg)
            self.refrescar_panel_guardias()
        except Exception as e:
            if conn:
                conn.rollback()
            self.reportar_error("Error al Eliminar Guardia", e, prefijo_log=f"Error al eliminar guardia #{id_guardia}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # --------------------------------------------------------------------------
    # MÉTODOS AUXILIARES: RECORRIDOS Y RONDAS
    # --------------------------------------------------------------------------
    def _obtener_opciones_rondas(self, cursor):
        cur_ron = cursor.connection.cursor()
        invocar_sp(cursor, "sp_listar_rondas_combo", [cur_ron])
        filas = cur_ron.fetchall()
        cur_ron.close()
        return [f"Ronda #{r[0]} | {r[2]} (Turno {r[1]})" for r in filas]

    def _parsear_fecha_recorrido(self, fecha_str):
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(fecha_str, fmt).date()
            except ValueError:
                pass
        return None

    # ==========================================================================
    # SUBTAB: RECORRIDOS (Carga de Datos)
    # ==========================================================================
    def construir_subtab_recorrido(self, parent):
        columna_izq = ttk.Frame(parent)
        columna_izq.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        frame_form = ttk.LabelFrame(columna_izq, text=" 🔄 Registrar Nuevo Recorrido ", padding=12)
        frame_form.pack(fill=tk.X, pady=(0, 10))

        # Médico
        ttk.Label(frame_form, text="Médico a Cargo:", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", pady=(2, 2))
        self.rec_cb_medico = ttk.Combobox(frame_form, state="readonly", width=34)
        self.rec_cb_medico.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        # Ronda
        ttk.Label(frame_form, text="Ronda Hospitalaria:", font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w", pady=(2, 2))
        self.rec_cb_ronda = ttk.Combobox(frame_form, state="readonly", width=34)
        self.rec_cb_ronda.grid(row=3, column=0, sticky="ew", pady=(0, 8))

        # Fecha
        ttk.Label(frame_form, text="Fecha del Recorrido:", font=("Segoe UI", 9, "bold")).grid(row=4, column=0, sticky="w", pady=(2, 2))
        self.rec_txt_fecha = ttk.Entry(frame_form, width=34)
        self.rec_txt_fecha.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.rec_txt_fecha.grid(row=5, column=0, sticky="ew", pady=(0, 2))
        ttk.Label(frame_form, text="Formato: DD/MM/AAAA", font=("Segoe UI", 8, "italic"), foreground="#4A5568").grid(row=6, column=0, sticky="w", pady=(0, 10))

        btn_guardar_rec = tk.Button(
            frame_form,
            text="🔄 Registrar Recorrido (INSERT)",
            bg="#2B6CB0",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="groove",
            cursor="hand2",
            command=self.accion_insertar_recorrido
        )
        btn_guardar_rec.grid(row=7, column=0, sticky="ew", pady=(4, 6))

        btn_ir_comentarios = tk.Button(
            frame_form,
            text="💬 Ir a Agregar Comentarios ➔",
            bg="#E2E8F0",
            font=("Segoe UI", 9),
            cursor="hand2",
            command=self.ir_a_tab_comentario
        )
        btn_ir_comentarios.grid(row=8, column=0, sticky="ew", pady=(0, 2))

        # Columna derecha: Listado de Recorridos
        columna_der = ttk.Frame(parent)
        columna_der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        frame_tabla = ttk.LabelFrame(columna_der, text=" 📋 Listado de Recorridos Realizados ", padding=10)
        frame_tabla.pack(fill=tk.BOTH, expand=True)

        cols = ("id_recorrido", "fecha", "matricula", "medico", "id_ronda", "turno", "dia", "cant_com")
        self.tabla_recorridos = ttk.Treeview(frame_tabla, columns=cols, show="headings", height=14)
        self.tabla_recorridos.heading("id_recorrido", text="ID Recorrido")
        self.tabla_recorridos.heading("fecha", text="Fecha")
        self.tabla_recorridos.heading("matricula", text="Matrícula")
        self.tabla_recorridos.heading("medico", text="Médico")
        self.tabla_recorridos.heading("id_ronda", text="Ronda")
        self.tabla_recorridos.heading("turno", text="Turno")
        self.tabla_recorridos.heading("dia", text="Día")
        self.tabla_recorridos.heading("cant_com", text="Comentarios")

        self.tabla_recorridos.column("id_recorrido", width=85, anchor="center")
        self.tabla_recorridos.column("fecha", width=125, anchor="center")
        self.tabla_recorridos.column("matricula", width=80, anchor="center")
        self.tabla_recorridos.column("medico", width=160)
        self.tabla_recorridos.column("id_ronda", width=65, anchor="center")
        self.tabla_recorridos.column("turno", width=60, anchor="center")
        self.tabla_recorridos.column("dia", width=90, anchor="center")
        self.tabla_recorridos.column("cant_com", width=85, anchor="center")

        scroll_y = ttk.Scrollbar(frame_tabla, orient=tk.VERTICAL, command=self.tabla_recorridos.yview)
        self.tabla_recorridos.configure(yscrollcommand=scroll_y.set)
        self.tabla_recorridos.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        frame_btns_tabla = ttk.Frame(columna_der)
        frame_btns_tabla.pack(fill=tk.X, pady=(6, 0))

        tk.Button(
            frame_btns_tabla,
            text="🔄 Actualizar Lista",
            bg="#E2E8F0",
            cursor="hand2",
            font=("Segoe UI", 9),
            command=self.cargar_lista_recorridos
        ).pack(side=tk.LEFT, padx=(0, 6))

        
    def accion_insertar_recorrido(self):
        med_sel = self.rec_cb_medico.get().strip()
        ronda_sel = self.rec_cb_ronda.get().strip()
        fecha_str = self.rec_txt_fecha.get().strip()

        if not med_sel or " - " not in med_sel:
            messagebox.showwarning("Médico Requerido", "Por favor selecciona un médico de la lista.")
            return
        if not ronda_sel or "Ronda #" not in ronda_sel:
            messagebox.showwarning("Ronda Requerida", "Por favor selecciona una ronda de la lista.")
            return
        if not fecha_str:
            messagebox.showwarning("Fecha Requerida", "Por favor ingresa la fecha del recorrido.")
            return

        fecha_dt = self._parsear_fecha_recorrido(fecha_str)
        if fecha_dt is None:
            messagebox.showerror("Fecha Inválida", f"El formato de fecha '{fecha_str}' no es válido.\nFormatos soportados: DD/MM/AAAA o AAAA-MM-DD")
            return

        matricula = med_sel.split(" - ")[0].strip()
        try:
            id_ronda = int(ronda_sel.split("|")[0].replace("Ronda #", "").strip())
        except ValueError:
            messagebox.showerror("Error", "No se pudo interpretar el identificador de la ronda.")
            return

        conn = None
        cursor = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            id_rec_var = cursor.var(oracledb.NUMBER)
            invocar_sp(cursor, "sp_registrar_recorrido", [fecha_dt, id_ronda, matricula, id_rec_var])
            nuevo_id = int(id_rec_var.getvalue())

            msg = f"Recorrido #{nuevo_id} registrado con éxito para el Dr./Dra. {med_sel} en Ronda #{id_ronda} ({fecha_str})."
            self.log_exito(msg)
            messagebox.showinfo("Recorrido Registrado", msg)

            self.rec_txt_fecha.delete(0, tk.END)
            self.rec_txt_fecha.insert(0, datetime.now().strftime("%d/%m/%Y"))
            self.cargar_lista_recorridos()

            if hasattr(self, 'com_cb_medico') and self.com_cb_medico.get() == med_sel:
                self.cargar_recorridos_de_medico_com(matricula)

        except Exception as e:
            if conn:
                conn.rollback()
            self.reportar_error("Error al Registrar Recorrido", e, prefijo_log="Error al registrar recorrido")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def cargar_lista_recorridos(self):
        if not hasattr(self, 'tabla_recorridos'):
            return
        for item in self.tabla_recorridos.get_children():
            self.tabla_recorridos.delete(item)

        conn = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            cur_rec = cursor.connection.cursor()
            invocar_sp(cursor, "sp_listar_recorridos", [cur_rec])
            for row in cur_rec.fetchall():
                self.tabla_recorridos.insert("", tk.END, values=row)
            cur_rec.close()
            cursor.close()
        except Exception as e:
            self.log_error(f"Error al cargar listado de recorridos: {e}")
        finally:
            if conn:
                conn.close()

    def refrescar_panel_recorridos(self):
        conn = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            medicos = self._obtener_opciones_medicos(cursor)
            rondas = self._obtener_opciones_rondas(cursor)
            cursor.close()

            if hasattr(self, 'rec_cb_medico'):
                self.rec_cb_medico['values'] = medicos
                if medicos and not self.rec_cb_medico.get():
                    self.rec_cb_medico.set(medicos[0])

            if hasattr(self, 'rec_cb_ronda'):
                self.rec_cb_ronda['values'] = rondas
                if rondas and not self.rec_cb_ronda.get():
                    self.rec_cb_ronda.set(rondas[0])

            self.cargar_lista_recorridos()
        except Exception as e:
            self.log_error(f"Error al refrescar panel de recorridos: {e}")
        finally:
            if conn:
                conn.close()

    def accion_eliminar_recorrido(self):
        sel = self.tabla_recorridos.selection()
        if not sel:
            messagebox.showinfo("Selección", "Por favor selecciona un recorrido de la tabla para eliminar.")
            return
        vals = self.tabla_recorridos.item(sel[0], "values")
        id_rec = int(vals[0])
        fecha = vals[1]
        medico = vals[3]
        cant_com = int(vals[7])

        if cant_com > 0:
            messagebox.showerror(
                "No se puede eliminar",
                f"El recorrido #{id_rec} tiene {cant_com} comentario(s) médico(s) asociado(s).\n\n"
                "Por integridad referencial (FK_COMENTARIO_RECORRIDO), debes eliminar primero los comentarios en la solapa 'Comentarios'."
            )
            return

        if not messagebox.askyesno("Confirmar Eliminación", f"¿Estás seguro de eliminar el Recorrido #{id_rec} ({fecha} - {medico})?"):
            return

        conn = None
        cursor = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            invocar_sp(cursor, "sp_eliminar_recorrido", [id_rec])
            self.log_exito(f"Recorrido #{id_rec} eliminado exitosamente.")
            messagebox.showinfo("Éxito", f"Recorrido #{id_rec} eliminado correctamente.")
            self.cargar_lista_recorridos()
        except Exception as e:
            if conn:
                conn.rollback()
            self.reportar_error("Error al Eliminar Recorrido", e, prefijo_log=f"Error al eliminar recorrido #{id_rec}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # ==========================================================================
    # SUBTAB: COMENTARIOS (Carga de Datos)
    # ==========================================================================
    def construir_subtab_comentario(self, parent):
        columna_izq = ttk.Frame(parent)
        columna_izq.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        frame_form = ttk.LabelFrame(columna_izq, text=" 📝 Registro de Comentarios / Evoluciones Médicas ", padding=12)
        frame_form.pack(fill=tk.X, pady=(0, 8))

        # Paso 1: Seleccionar Médico
        ttk.Label(frame_form, text="1. Seleccionar Médico:", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", pady=(2, 2))
        self.com_cb_medico = ttk.Combobox(frame_form, state="readonly", width=42)
        self.com_cb_medico.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.com_cb_medico.bind("<<ComboboxSelected>>", self.on_com_medico_seleccionado)

        # Paso 2: Seleccionar Recorrido del Médico
        ttk.Label(frame_form, text="2. Seleccionar Recorrido del Médico:", font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w", pady=(2, 2))
        self.com_cb_recorrido = ttk.Combobox(frame_form, state="readonly", width=42)
        self.com_cb_recorrido.grid(row=3, column=0, sticky="ew", pady=(0, 2))
        self.com_cb_recorrido.bind("<<ComboboxSelected>>", self.on_com_recorrido_seleccionado)

        self.lbl_aviso_recorridos_med = ttk.Label(
            frame_form,
            text="Selecciona un médico arriba para ver sus recorridos.",
            font=("Segoe UI", 8, "italic"),
            foreground="#4A5568"
        )
        self.lbl_aviso_recorridos_med.grid(row=4, column=0, sticky="w", pady=(0, 8))

        # Paso 3: Seleccionar Internación (SOLO NO FINALIZADAS)
        # Paso 3: Seleccionar Internación (SOLO de habitaciones en la ronda del recorrido)
        frame_lbl_int = ttk.Frame(frame_form)
        frame_lbl_int.grid(row=5, column=0, sticky="ew", pady=(2, 2))
        ttk.Label(frame_lbl_int, text="3. Internación en Ronda del Recorrido:", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        btn_refrescar_ints = tk.Button(
            frame_lbl_int,
            text="🔄",
            bg="#E2E8F0",
            font=("Segoe UI", 8),
            cursor="hand2",
            command=self.on_com_recorrido_seleccionado
        )
        btn_refrescar_ints.pack(side=tk.RIGHT)

        self.com_cb_internacion = ttk.Combobox(frame_form, state="readonly", width=42)
        self.com_cb_internacion.grid(row=6, column=0, sticky="ew", pady=(0, 2))

        self.lbl_info_ronda_int = ttk.Label(
            frame_form,
            text="🟢 Solo internaciones activas cuyas habitaciones pertenezcan a la ronda del recorrido",
            font=("Segoe UI", 8, "italic"),
            foreground="#276749",
            wraplength=310
        )
        self.lbl_info_ronda_int.grid(row=7, column=0, sticky="w", pady=(0, 8))

        # Paso 4: Contenido del Comentario (máx 200 car.)
        ttk.Label(frame_form, text="4. Comentario / Evolución Clínica (máx 200 car.):", font=("Segoe UI", 9, "bold")).grid(row=8, column=0, sticky="w", pady=(2, 2))
        self.com_txt_contenido = scrolledtext.ScrolledText(frame_form, height=4, width=40, font=("Segoe UI", 9), wrap=tk.WORD)
        self.com_txt_contenido.grid(row=9, column=0, sticky="ew", pady=(0, 2))
        self.com_txt_contenido.bind("<KeyRelease>", self.actualizar_contador_comentario)

        self.com_lbl_contador = ttk.Label(frame_form, text="Caracteres: 0 / 200", font=("Segoe UI", 8, "italic"), foreground="#4A5568")
        self.com_lbl_contador.grid(row=10, column=0, sticky="w", pady=(0, 8))

        # Botón Guardar Comentario
        btn_guardar_com = tk.Button(
            frame_form,
            text="📝 Registrar Comentario (INSERT)",
            bg="#276749",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="groove",
            cursor="hand2",
            command=self.accion_insertar_comentario_desde_tab
        )
        btn_guardar_com.grid(row=11, column=0, sticky="ew", pady=(4, 4))

        # Panel Derecho: Visualización
        columna_der = ttk.Frame(parent)
        columna_der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        frame_recs_med = ttk.LabelFrame(columna_der, text=" 🔄 Recorridos del Médico Seleccionado (Clic para seleccionar) ", padding=8)
        frame_recs_med.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        cols_rec = ("id_recorrido", "fecha", "ronda", "dia", "turno", "cant_comentarios")
        self.com_tabla_recorridos_med = ttk.Treeview(frame_recs_med, columns=cols_rec, show="headings", height=6)
        self.com_tabla_recorridos_med.heading("id_recorrido", text="ID Recorrido")
        self.com_tabla_recorridos_med.heading("fecha", text="Fecha")
        self.com_tabla_recorridos_med.heading("ronda", text="Ronda")
        self.com_tabla_recorridos_med.heading("dia", text="Día")
        self.com_tabla_recorridos_med.heading("turno", text="Turno")
        self.com_tabla_recorridos_med.heading("cant_comentarios", text="Evoluciones")

        self.com_tabla_recorridos_med.column("id_recorrido", width=85, anchor="center")
        self.com_tabla_recorridos_med.column("fecha", width=120, anchor="center")
        self.com_tabla_recorridos_med.column("ronda", width=65, anchor="center")
        self.com_tabla_recorridos_med.column("dia", width=90, anchor="center")
        self.com_tabla_recorridos_med.column("turno", width=60, anchor="center")
        self.com_tabla_recorridos_med.column("cant_comentarios", width=80, anchor="center")

        scroll_rec_y = ttk.Scrollbar(frame_recs_med, orient=tk.VERTICAL, command=self.com_tabla_recorridos_med.yview)
        self.com_tabla_recorridos_med.configure(yscrollcommand=scroll_rec_y.set)
        self.com_tabla_recorridos_med.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_rec_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.com_tabla_recorridos_med.bind("<<TreeviewSelect>>", self.on_com_recorrido_tabla_click)

        # Abajo: Comentarios del Recorrido Seleccionado
        frame_coms = ttk.LabelFrame(columna_der, text=" 💬 Comentarios / Evoluciones Registradas en el Recorrido Seleccionado ", padding=8)
        frame_coms.pack(fill=tk.BOTH, expand=True)

        cols_com = ("id_comentario", "id_internacion", "paciente", "contenido")
        self.com_tabla_comentarios = ttk.Treeview(frame_coms, columns=cols_com, show="headings", height=6)
        self.com_tabla_comentarios.heading("id_comentario", text="ID Comentario")
        self.com_tabla_comentarios.heading("id_internacion", text="ID Int.")
        self.com_tabla_comentarios.heading("paciente", text="Paciente")
        self.com_tabla_comentarios.heading("contenido", text="Contenido (Evolución Clínica)")

        self.com_tabla_comentarios.column("id_comentario", width=90, anchor="center")
        self.com_tabla_comentarios.column("id_internacion", width=70, anchor="center")
        self.com_tabla_comentarios.column("paciente", width=150)
        self.com_tabla_comentarios.column("contenido", width=300)

        scroll_com_y = ttk.Scrollbar(frame_coms, orient=tk.VERTICAL, command=self.com_tabla_comentarios.yview)
        self.com_tabla_comentarios.configure(yscrollcommand=scroll_com_y.set)
        self.com_tabla_comentarios.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_com_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.com_tabla_comentarios.bind("<Double-1>", self.mostrar_detalle_comentario)

        frame_coms_btns = ttk.Frame(frame_coms)
        frame_coms_btns.pack(fill=tk.X, pady=(6, 0))

        tk.Button(
            frame_coms_btns,
            text="🔍 Ver Comentario Completo",
            bg="#E2E8F0",
            cursor="hand2",
            font=("Segoe UI", 8),
            command=self.mostrar_detalle_comentario
        ).pack(side=tk.LEFT, padx=(0, 6))

        
    def on_com_medico_seleccionado(self, event=None):
        med_sel = self.com_cb_medico.get().strip()
        if not med_sel or " - " not in med_sel:
            return
        matricula = med_sel.split(" - ")[0].strip()
        self.cargar_recorridos_de_medico_com(matricula)

    def cargar_recorridos_de_medico_com(self, matricula):
        if not hasattr(self, 'com_cb_recorrido') or not hasattr(self, 'com_tabla_recorridos_med'):
            return
        for item in self.com_tabla_recorridos_med.get_children():
            self.com_tabla_recorridos_med.delete(item)
        for item in self.com_tabla_comentarios.get_children():
            self.com_tabla_comentarios.delete(item)

        conn = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            cur_rec_med = cursor.connection.cursor()
            invocar_sp(cursor, "sp_listar_recorridos_medico", [matricula, cur_rec_med])
            recorridos = cur_rec_med.fetchall()
            cur_rec_med.close()
            cursor.close()

            opciones_combo = []
            for r in recorridos:
                self.com_tabla_recorridos_med.insert("", tk.END, values=(r[0], r[1], r[2], r[3], r[4], r[5]))
                opciones_combo.append(f"Recorrido #{r[0]} | Fecha: {r[1]} | Ronda #{r[2]} ({r[3]} T{r[4]})")

            self.com_cb_recorrido['values'] = opciones_combo
            if opciones_combo:
                self.com_cb_recorrido.set(opciones_combo[0])
                self.lbl_aviso_recorridos_med.config(
                    text=f"✓ {len(opciones_combo)} recorrido(s) encontrado(s) para este médico.",
                    foreground="#276749"
                )
                self.on_com_recorrido_seleccionado()
            else:
                self.com_cb_recorrido.set("(Este médico no tiene recorridos registrados)")
                self.lbl_aviso_recorridos_med.config(
                    text="⚠️ Este médico no tiene recorridos. Puedes registrar uno en la pestaña 'Recorridos'.",
                    foreground="#C53030"
                )
        except Exception as e:
            self.log_error(f"Error al cargar recorridos del médico {matricula}: {e}")
        finally:
            if conn:
                conn.close()

    def on_com_recorrido_seleccionado(self, event=None):
        rec_sel = self.com_cb_recorrido.get().strip()
        if not rec_sel or not rec_sel.startswith("Recorrido #"):
            if hasattr(self, 'com_cb_internacion'):
                self.com_cb_internacion['values'] = []
                self.com_cb_internacion.set("(Primero selecciona un recorrido)")
            if hasattr(self, 'lbl_info_ronda_int'):
                self.lbl_info_ronda_int.config(
                    text="Selecciona un recorrido arriba para cargar las internaciones de su ronda.",
                    foreground="#4A5568"
                )
            return
        try:
            id_rec = int(rec_sel.split("|")[0].replace("Recorrido #", "").strip())
        except ValueError:
            return
        self.cargar_comentarios_de_recorrido(id_rec)
        self.cargar_internaciones_de_recorrido(id_rec)

    def on_com_recorrido_tabla_click(self, event=None):
        sel = self.com_tabla_recorridos_med.selection()
        if not sel:
            return
        vals = self.com_tabla_recorridos_med.item(sel[0], "values")
        if not vals:
            return
        id_rec = int(vals[0])
        for opc in self.com_cb_recorrido['values']:
            if opc.startswith(f"Recorrido #{id_rec} "):
                self.com_cb_recorrido.set(opc)
                break
        self.cargar_comentarios_de_recorrido(id_rec)
        self.cargar_internaciones_de_recorrido(id_rec)

    def cargar_comentarios_de_recorrido(self, id_recorrido):
        if not hasattr(self, 'com_tabla_comentarios'):
            return
        for item in self.com_tabla_comentarios.get_children():
            self.com_tabla_comentarios.delete(item)

        conn = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            cur_com = cursor.connection.cursor()
            invocar_sp(cursor, "sp_listar_comentarios_recorrido", [id_recorrido, cur_com])
            for row in cur_com.fetchall():
                self.com_tabla_comentarios.insert("", tk.END, values=row)
            cur_com.close()
            cursor.close()
        except Exception as e:
            self.log_error(f"Error al cargar comentarios del recorrido #{id_recorrido}: {e}")
        finally:
            if conn:
                conn.close()

    def cargar_internaciones_de_recorrido(self, id_recorrido):
        """
        Filtra y carga en el desplegable ÚNICAMENTE las internaciones activas (fecha_fin IS NULL)
        cuyas habitaciones actuales formen parte de la ronda del recorrido seleccionado.
        """
        if not hasattr(self, 'com_cb_internacion'):
            return

        conn = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()

            # Consultar internaciones y datos de la ronda mediante Stored Procedure
            cur_ronda = cursor.connection.cursor()
            cur_ints = cursor.connection.cursor()
            invocar_sp(cursor, "sp_internaciones_de_recorrido", [id_recorrido, cur_ronda, cur_ints])
            row_rec = cur_ronda.fetchone()
            if not row_rec:
                cur_ronda.close()
                cur_ints.close()
                cursor.close()
                return

            id_ronda = row_rec[0]
            dia_ronda = row_rec[1] or "N/A"
            turno_ronda = row_rec[2] or "N/A"
            habs_str = row_rec[3] if len(row_rec) > 3 and row_rec[3] else None

            filas_int = cur_ints.fetchall()
            cur_ronda.close()
            cur_ints.close()
            cursor.close()

            opciones = [
                f"Int #{f[0]} | Pac: {f[2]}, {f[1]} (DNI {f[3]}) | Hab: {f[4]} Cama: {f[5]} ({f[6]})"
                for f in filas_int
            ]
            self.com_cb_internacion['values'] = opciones

            if opciones:
                self.com_cb_internacion.set(opciones[0])
                if hasattr(self, 'lbl_info_ronda_int'):
                    self.lbl_info_ronda_int.config(
                        text=f"✓ Ronda #{id_ronda} ({dia_ronda} T{turno_ronda}) incluye: {habs_str or f'Habitaciones de Ronda #{id_ronda}'}\n  {len(opciones)} internación(es) activa(s) en sus habitaciones.",
                        foreground="#276749"
                    )
            else:
                if habs_str:
                    self.com_cb_internacion.set("(No hay internaciones activas en las habitaciones de esta ronda)")
                    if hasattr(self, 'lbl_info_ronda_int'):
                        self.lbl_info_ronda_int.config(
                            text=f"⚠️ Ronda #{id_ronda} cubre: {habs_str}, pero actualmente no hay pacientes internados en esas habitaciones.",
                            foreground="#C53030"
                        )
                else:
                    self.com_cb_internacion.set("(Esta ronda no tiene habitaciones asignadas)")
                    if hasattr(self, 'lbl_info_ronda_int'):
                        self.lbl_info_ronda_int.config(
                            text=f"⚠️ Ronda #{id_ronda} no tiene habitaciones asignadas.",
                            foreground="#C53030"
                        )

        except Exception as e:
            self.log_error(f"Error al cargar internaciones de la ronda para recorrido #{id_recorrido}: {e}")
        finally:
            if conn:
                conn.close()

    def actualizar_combo_internaciones_activas_com(self):
        """Redirige al filtrado por el recorrido seleccionado actualmente."""
        self.on_com_recorrido_seleccionado()

    def actualizar_contador_comentario(self, event=None):
        if not hasattr(self, 'com_txt_contenido') or not hasattr(self, 'com_lbl_contador'):
            return
        texto = self.com_txt_contenido.get("1.0", tk.END).strip()
        n = len(texto)
        if n > 200:
            self.com_lbl_contador.config(
                text=f"⚠️ {n} / 200 caracteres (¡Excede el límite de 200 de Oracle!)",
                foreground="#C53030"
            )
        else:
            self.com_lbl_contador.config(
                text=f"Caracteres: {n} / 200",
                foreground="#4A5568" if n < 180 else "#DD6B20"
            )

    def accion_insertar_comentario_desde_tab(self):
        med_sel = self.com_cb_medico.get().strip()
        rec_sel = self.com_cb_recorrido.get().strip()
        int_sel = self.com_cb_internacion.get().strip()
        contenido = self.com_txt_contenido.get("1.0", tk.END).strip()

        if not med_sel or " - " not in med_sel:
            messagebox.showwarning("Médico Requerido", "Por favor selecciona un médico de la lista.")
            return

        if not rec_sel or not rec_sel.startswith("Recorrido #"):
            messagebox.showwarning("Recorrido Requerido", "Por favor selecciona un recorrido válido del médico.\nSi el médico no tiene recorridos, créalo primero en la solapa 'Recorridos'.")
            return

        if not int_sel or not int_sel.startswith("Int #"):
            messagebox.showwarning("Internación Requerida", "Por favor selecciona una internación activa de la lista.")
            return

        if not contenido:
            messagebox.showwarning("Contenido Vacío", "Por favor ingresa el comentario o evolución clínica para el paciente.")
            return

        if len(contenido) > 200:
            messagebox.showerror("Texto Demasiado Largo", f"El comentario tiene {len(contenido)} caracteres. El máximo permitido por la base de datos es de 200 caracteres.")
            return

        try:
            id_rec = int(rec_sel.split("|")[0].replace("Recorrido #", "").strip())
        except ValueError:
            messagebox.showerror("Error", "No se pudo identificar el ID del recorrido.")
            return

        try:
            id_int = int(int_sel.split("|")[0].replace("Int #", "").strip())
        except ValueError:
            messagebox.showerror("Error", "No se pudo identificar el ID de la internación.")
            return

        conn = None
        cursor = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()

            # Invocar Stored Procedure transaccional 'sp_registrar_comentario' en la base de datos
            id_comentario_var = cursor.var(oracledb.NUMBER)
            invocar_sp(cursor, "sp_registrar_comentario", [id_int, id_rec, contenido, id_comentario_var])
            nuevo_id_com = int(id_comentario_var.getvalue())

            msg = f"Comentario #{nuevo_id_com} registrado con éxito para la Internación activa #{id_int} en el Recorrido #{id_rec}."
            self.log_exito(msg)
            messagebox.showinfo("Comentario Registrado", msg)

            self.com_txt_contenido.delete("1.0", tk.END)
            self.actualizar_contador_comentario()

            self.cargar_comentarios_de_recorrido(id_rec)
            self.cargar_internaciones_de_recorrido(id_rec)
            matricula = med_sel.split(" - ")[0].strip()
            self.cargar_recorridos_de_medico_com(matricula)

            if hasattr(self, 'txt_id_int_comentario'):
                self.txt_id_int_comentario.delete(0, tk.END)
                self.txt_id_int_comentario.insert(0, str(id_int))

        except Exception as e:
            if conn:
                conn.rollback()
            self.reportar_error("Error al Guardar Comentario", e, prefijo_log="Error al registrar comentario médico")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def mostrar_detalle_comentario(self, event=None):
        sel = self.com_tabla_comentarios.selection()
        if not sel:
            messagebox.showinfo("Selección", "Por favor selecciona un comentario de la tabla.")
            return
        vals = self.com_tabla_comentarios.item(sel[0], "values")
        id_com, id_int, pac, contenido = vals[0], vals[1], vals[2], vals[3]

        modal = tk.Toplevel(self)
        modal.title(f"Comentario #{id_com} - Internación #{id_int}")
        modal.geometry("520x340")
        modal.transient(self)
        modal.grab_set()

        f = ttk.Frame(modal, padding=14)
        f.pack(fill=tk.BOTH, expand=True)

        ttk.Label(f, text=f"📋 Evolución Médica #{id_com}", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 4))
        ttk.Label(f, text=f"• Internación: #{id_int} | Paciente: {pac}", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 8))

        txt = scrolledtext.ScrolledText(f, height=8, wrap=tk.WORD, font=("Segoe UI", 10))
        txt.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        txt.insert(tk.END, contenido)
        txt.config(state="disabled")

        tk.Button(f, text="Cerrar", bg="#E2E8F0", cursor="hand2", command=modal.destroy).pack(anchor="e")

    def accion_eliminar_comentario(self):
        sel = self.com_tabla_comentarios.selection()
        if not sel:
            messagebox.showinfo("Selección", "Por favor selecciona un comentario de la tabla para eliminar.")
            return
        vals = self.com_tabla_comentarios.item(sel[0], "values")
        id_com, id_int, pac = int(vals[0]), vals[1], vals[2]

        if not messagebox.askyesno("Confirmar Eliminación", f"¿Deseas eliminar el Comentario #{id_com} de la Internación #{id_int} ({pac})?"):
            return

        conn = None
        cursor = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            invocar_sp(cursor, "sp_eliminar_comentario", [id_com])
            self.log_exito(f"Comentario #{id_com} eliminado correctamente.")
            messagebox.showinfo("Éxito", f"Comentario #{id_com} eliminado correctamente.")

            rec_sel = self.com_cb_recorrido.get().strip()
            if rec_sel and rec_sel.startswith("Recorrido #"):
                id_rec = int(rec_sel.split("|")[0].replace("Recorrido #", "").strip())
                self.cargar_comentarios_de_recorrido(id_rec)
                med_sel = self.com_cb_medico.get().strip()
                if med_sel and " - " in med_sel:
                    matricula = med_sel.split(" - ")[0].strip()
                    self.cargar_recorridos_de_medico_com(matricula)
        except Exception as e:
            if conn:
                conn.rollback()
            self.reportar_error("Error al Eliminar", e, prefijo_log=f"Error al eliminar comentario #{id_com}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def accion_ver_sp_desde_comentarios(self):
        sel = self.com_tabla_comentarios.selection()
        if sel:
            vals = self.com_tabla_comentarios.item(sel[0], "values")
            id_int = vals[1]
        else:
            int_sel = self.com_cb_internacion.get().strip()
            if int_sel and int_sel.startswith("Int #"):
                id_int = int_sel.split("|")[0].replace("Int #", "").strip()
            else:
                messagebox.showinfo("Selección", "Por favor selecciona un comentario de la tabla o una internación.")
                return

        if hasattr(self, 'txt_id_int_comentario'):
            self.txt_id_int_comentario.delete(0, tk.END)
            self.txt_id_int_comentario.insert(0, str(id_int))
        self.accion_consultar_comentarios_sp()

    def refrescar_panel_comentarios(self):
        conn = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            medicos = self._obtener_opciones_medicos(cursor)
            cursor.close()

            if hasattr(self, 'com_cb_medico'):
                self.com_cb_medico['values'] = medicos
                if medicos:
                    if not self.com_cb_medico.get() or self.com_cb_medico.get() not in medicos:
                        self.com_cb_medico.set(medicos[0])
                    self.on_com_medico_seleccionado()
                else:
                    self.com_cb_medico.set("")
                    if hasattr(self, 'com_cb_recorrido'):
                        self.com_cb_recorrido['values'] = []
                        self.com_cb_recorrido.set("")
                    if hasattr(self, 'com_cb_internacion'):
                        self.com_cb_internacion['values'] = []
                        self.com_cb_internacion.set("(No hay médicos registrados)")
        except Exception as e:
            self.log_error(f"Error al refrescar panel de comentarios: {e}")
        finally:
            if conn:
                conn.close()

    # ==========================================================================
    # TAB 3: CONSOLA SQL
    # ==========================================================================
    def construir_tab_sql(self):
        frame_editor = ttk.LabelFrame(self.tab_sql, text=" Editor de Consultas SQL en Vivo ", padding=10)
        frame_editor.pack(fill=tk.X, padx=5, pady=(0, 6))

        self.txt_sql = scrolledtext.ScrolledText(
            frame_editor, 
            height=4, 
            font=("Consolas", 11),
            bg="#1A202C", 
            fg="#63B3ED", 
            insertbackground="white"
        )
        self.txt_sql.pack(fill=tk.X, expand=True, pady=(0, 6))
        self.txt_sql.insert(tk.END, "SELECT * FROM PACIENTE;")

        frame_botones_sql = ttk.Frame(frame_editor)
        frame_botones_sql.pack(fill=tk.X)

        btn_run = tk.Button(
            frame_botones_sql,
            text="▶ Ejecutar SQL (F5)",
            bg="#276749",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="groove",
            cursor="hand2",
            command=self.accion_ejecutar_sql
        )
        btn_run.pack(side=tk.LEFT, padx=(0, 10))

        self.bind("<F5>", lambda event: self.accion_ejecutar_sql())

        ttk.Label(frame_botones_sql, text="Consultas rápidas:").pack(side=tk.LEFT, padx=(5, 3))

        consultas_rapidas = [
            ("Pacientes", "SELECT * FROM PACIENTE;"),
            ("Médicos", "SELECT * FROM MEDICO;"),
            ("Camas por Sector", "SELECT s.nombre AS sector, COUNT(c.nro_cama) AS camas_libres FROM SECTOR s LEFT JOIN HABITACION h ON s.id_sector = h.id_sector LEFT JOIN CAMA c ON h.id_habitacion = c.id_habitacion AND UPPER(c.estado) = 'LIBRE' GROUP BY s.nombre ORDER BY camas_libres DESC;"),
            ("Camas Libres", "SELECT s.nombre, h.id_habitacion, h.piso, c.nro_cama FROM CAMA c JOIN HABITACION h ON c.id_habitacion = h.id_habitacion JOIN SECTOR s ON h.id_sector = s.id_sector WHERE UPPER(c.estado) = 'LIBRE';"),
            ("Auditoría Guardias", "SELECT * FROM AUDITORIA_GUARDIAS ORDER BY fecha_operacion DESC;"),
            ("Guardias", "SELECT g.id_guardia, g.fecha, g.turno, cp.numero_de_matricula FROM GUARDIA g LEFT JOIN CUBIERTA_POR cp ON g.id_guardia = cp.id_guardia ORDER BY g.fecha DESC;"),
            ("Comentarios Recorridos", "SELECT * FROM COMENTARIO;"),
            ("Internaciones", "SELECT * FROM INTERNACION ORDER BY id_internacion DESC;"),
            ("Historial POSEE", "SELECT * FROM POSEE ORDER BY fechaHora DESC;"),
            ("Vacaciones", "SELECT v.numero_de_matricula, p.nombre || ' ' || p.apellido AS medico, TO_CHAR(v.fecha_inicio_vac, 'DD/MM/YYYY') AS inicio, TO_CHAR(v.fecha_fin_vac, 'DD/MM/YYYY') AS fin FROM VACACION v JOIN MEDICO m ON v.numero_de_matricula = m.numero_de_matricula JOIN PERSONA p ON m.numero_de_DNI = p.numero_de_DNI ORDER BY v.fecha_inicio_vac DESC;")
        ]

        for texto, sql in consultas_rapidas:
            b = tk.Button(
                frame_botones_sql, 
                text=texto, 
                bg="#E2E8F0", 
                font=("Segoe UI", 8),
                cursor="hand2",
                command=lambda s=sql: self.pegar_sql(s)
            )
            b.pack(side=tk.LEFT, padx=2)

        frame_resultados = ttk.LabelFrame(self.tab_sql, text=" Resultados de la Consulta ", padding=8)
        frame_resultados.pack(fill=tk.BOTH, expand=True, padx=5)

        self.frame_tabla_contenedor = ttk.Frame(frame_resultados)
        self.frame_tabla_contenedor.pack(fill=tk.BOTH, expand=True)

        self.tabla_sql = ttk.Treeview(self.frame_tabla_contenedor, show="headings")
        self.scrollbar_y = ttk.Scrollbar(self.frame_tabla_contenedor, orient=tk.VERTICAL, command=self.tabla_sql.yview)
        self.scrollbar_x = ttk.Scrollbar(self.frame_tabla_contenedor, orient=tk.HORIZONTAL, command=self.tabla_sql.xview)
        self.tabla_sql.configure(yscrollcommand=self.scrollbar_y.set, xscrollcommand=self.scrollbar_x.set)

        self.scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tabla_sql.pack(fill=tk.BOTH, expand=True)

        self.lbl_filas_resultado = ttk.Label(frame_resultados, text="0 filas devueltas.", font=("Segoe UI", 9, "italic"))
        self.lbl_filas_resultado.pack(anchor="w", pady=(2, 0))

    def pegar_sql(self, sql):
        self.txt_sql.delete("1.0", tk.END)
        self.txt_sql.insert(tk.END, sql)

    @staticmethod
    def _validar_sql_consola(sql):
        """
        Valida que desde la consola SQL del frontend no se ejecuten sentencias que:
        - Creen/modifiquen internaciones (INTERNACION, sp_registrar_internacion, sp_dar_alta_internacion)
        - Muevan pacientes de cama o alteren camas (POSEE, CAMA, sp_ocupar_cama_posee)
        - Modifiquen la tabla de auditoría (AUDITORIA_GUARDIAS / AUDITORIA*)
        Las consultas de solo lectura (SELECT / WITH) están permitidas.
        Retorna (permitido: bool, motivo: str | None).
        """
        # Eliminar comentarios /* ... */ y -- ...
        limpio = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
        limpio = re.sub(r'--[^\r\n]*', ' ', limpio)
        limpio_up = re.sub(r'\s+', ' ', limpio).strip().upper()

        if not limpio_up:
            return True, None

        # Verificar si es una consulta de solo lectura pura (SELECT o WITH sin palabras de modificación/PLSQL)
        es_lectura = limpio_up.startswith("SELECT ") or limpio_up.startswith("SELECT\n") or limpio_up.startswith("WITH ")
        tiene_modificacion = bool(re.search(
            r'\b(INSERT|UPDATE|DELETE|MERGE|TRUNCATE|DROP|ALTER|CREATE|GRANT|REVOKE|REPLACE|CALL|EXEC|EXECUTE|BEGIN|DECLARE)\b',
            limpio_up
        ))

        if es_lectura and not tiene_modificacion:
            return True, None

        if tiene_modificacion:
            if re.search(r'\b([A-Z0-9_]+\.)?AUDITORIA[A-Z0-9_]*\b', limpio_up):
                return False, (
                    "🚫 Operación bloqueada en la consola SQL:\n\n"
                    "No está permitido insertar, modificar ni eliminar registros de la tabla de auditoría."
                )
            if re.search(r'\b([A-Z0-9_]+\.)?(INTERNACION|SP_REGISTRAR_INTERNACION|SP_DAR_ALTA_INTERNACION)\b', limpio_up):
                return False, (
                    "🚫 Operación bloqueada en la consola SQL:\n\n"
                    "No está permitido crear ni modificar internaciones desde la consola SQL.\n"
                    "Por favor, utiliza la pestaña '🏥 Internación y Camas'."
                )
            if re.search(r'\b([A-Z0-9_]+\.)?(POSEE|CAMA|SP_OCUPAR_CAMA_POSEE)\b', limpio_up):
                return False, (
                    "🚫 Operación bloqueada en la consola SQL:\n\n"
                    "No está permitido mover pacientes de cama ni modificar camas desde la consola SQL.\n"
                    "Por favor, utiliza la pestaña '🏥 Internación y Camas'."
                )

        return True, None

    def accion_ejecutar_sql(self):
        sql_input = self.txt_sql.get("1.0", tk.END).strip()
        if not sql_input:
            return

        # Filtrar comandos de cliente SQL*Plus
        lineas_validas = []
        for l in sql_input.splitlines():
            l_up = l.strip().upper()
            if not l_up.startswith(("SET ", "PROMPT", "SHOW ", "SPOOL ", "WHENEVER ")):
                lineas_validas.append(l)
        sql_limpio = "\n".join(lineas_validas).strip()

        if not sql_limpio:
            messagebox.showinfo("Consola SQL", "La entrada solo contenía directivas de cliente SQL*Plus (SET/PROMPT).")
            return

        bloques = parsear_script_sql(sql_limpio)
        if not bloques:
            bloques = [sql_limpio.rstrip(';').strip()]

        conn = None
        cursor = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            try:
                cursor.callproc("dbms_output.enable")
            except Exception:
                pass

            # Caso 1: Una única consulta de lectura pura (SELECT / WITH)
            if len(bloques) == 1 and (bloques[0].upper().startswith("SELECT ") or bloques[0].upper().startswith("SELECT\n") or bloques[0].upper().startswith("WITH ")):
                b = bloques[0].rstrip(';').strip()
                permitido, motivo_bloqueo = self._validar_sql_consola(b)
                if not permitido:
                    self.log_error(f"Sentencia bloqueada en consola SQL: '{b[:60]}...'")
                    messagebox.showwarning("Operación No Permitida", motivo_bloqueo)
                    return

                cursor.execute(b)
                self.tabla_sql.delete(*self.tabla_sql.get_children())
                if cursor.description:
                    columnas_ids = [f"c{i}" for i in range(len(cursor.description))]
                    self.tabla_sql["columns"] = columnas_ids
                    for i, col in enumerate(cursor.description):
                        titulo_limpio = col[0].replace('_', ' ')
                        self.tabla_sql.heading(columnas_ids[i], text=titulo_limpio)
                        self.tabla_sql.column(columnas_ids[i], width=130, anchor="w")

                    filas = cursor.fetchall()
                    for fila in filas:
                        valores = []
                        for v in fila:
                            if v is None:
                                texto = ""
                            elif isinstance(v, (bytes, bytearray)):
                                texto = f"[Foto BLOB: {len(v)} bytes]"
                            elif hasattr(v, 'read'):
                                texto = "[Foto BLOB]"
                            elif isinstance(v, (datetime, date)):
                                if hasattr(v, 'hour') and (v.hour != 0 or v.minute != 0 or v.second != 0):
                                    texto = v.strftime("%d/%m/%Y %H:%M:%S")
                                else:
                                    texto = v.strftime("%d/%m/%Y")
                            else:
                                texto = str(v)
                            valores.append(texto)
                        self.tabla_sql.insert("", tk.END, values=valores)

                    self.lbl_filas_resultado.config(text=f"✅ {len(filas)} fila(s) retornada(s).")
                    self.log_exito(f"Consulta SQL ejecutada: '{b[:45]}...' -> {len(filas)} filas.")
                    return

            # Caso 2: Una o más sentencias DML / Bloques PL/SQL / Scripts de prueba
            salida_mensajes = []
            total_ejecutadas = 0

            for idx, b in enumerate(bloques):
                b_run = b.rstrip(';').strip() if not (b.upper().startswith("BEGIN") or b.upper().startswith("DECLARE")) else b
                permitido, motivo_bloqueo = self._validar_sql_consola(b_run)
                if not permitido:
                    salida_mensajes.append(f"⚠️ [Bloque #{idx+1} omitido]: {motivo_bloqueo}")
                    continue

                try:
                    cursor.execute(b_run)
                    total_ejecutadas += 1
                except Exception as ex_b:
                    salida_mensajes.append(f"❌ [Error en bloque #{idx+1}]: {traducir_error_oracle(ex_b, incluir_tecnico=True)}")

            conn.commit()

            # Capturar líneas generadas por DBMS_OUTPUT.PUT_LINE
            try:
                line_var = cursor.var(str)
                status_var = cursor.var(int)
                while True:
                    cursor.callproc("dbms_output.get_line", (line_var, status_var))
                    if status_var.getvalue() != 0:
                        break
                    val = line_var.getvalue()
                    if val is not None:
                        salida_mensajes.append(str(val))
            except Exception:
                pass

            self.tabla_sql.delete(*self.tabla_sql.get_children())
            self.tabla_sql["columns"] = ("Mensaje",)
            self.tabla_sql.heading("Mensaje", text="Salida de Ejecución / DBMS_OUTPUT")
            self.tabla_sql.column("Mensaje", width=650, anchor="w")

            if salida_mensajes:
                for msg in salida_mensajes:
                    self.tabla_sql.insert("", tk.END, values=(msg,))
                self.lbl_filas_resultado.config(text=f"✅ {len(salida_mensajes)} línea(s) de salida.")
                self.log_exito(f"Script SQL ejecutado con éxito ({total_ejecutadas} sentencia/s procesada/s).")
            else:
                self.tabla_sql.insert("", tk.END, values=(f"Sentencia(s) ejecutada(s) exitosamente. Total procesadas: {total_ejecutadas}",))
                self.lbl_filas_resultado.config(text=f"✅ {total_ejecutadas} sentencia(s) ejecutada(s).")
                self.log_exito(f"Ejecución finalizada: {total_ejecutadas} sentencia(s) procesadas.")

        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            self.reportar_error("Error al Ejecutar Consulta", e, prefijo_log="Error al ejecutar SQL")

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # ==========================================================================
    # PANEL INFERIOR MÓVIL
    # ==========================================================================
    def crear_panel_logs(self, contenedor):
        frame_logs = ttk.LabelFrame(contenedor, text=" 📋 Registro de Eventos y Errores (Redimensionable - Arrastra hacia arriba/abajo) ", padding=6)
        frame_logs.pack(fill=tk.BOTH, expand=True)

        self.txt_logs = scrolledtext.ScrolledText(
            frame_logs, 
            height=5, 
            font=("Segoe UI", 9),
            bg="#2D3748", 
            fg="#E2E8F0"
        )
        self.txt_logs.pack(fill=tk.BOTH, expand=True)

        self.txt_logs.tag_config("INFO", foreground="#63B3ED")
        self.txt_logs.tag_config("EXITO", foreground="#68D391")
        self.txt_logs.tag_config("ERROR", foreground="#FC8181")

    def _agregar_log(self, texto, tag):
        timestamp = datetime.now().strftime("%H:%M:%S")
        linea_completa = f"[{timestamp}] {texto}"
        print(linea_completa)
        if hasattr(self, 'txt_logs'):
            self.txt_logs.insert(tk.END, f"{linea_completa}\n", tag)
            self.txt_logs.see(tk.END)

    def log_info(self, mensaje):
        self._agregar_log(f"ℹ️ {mensaje}", "INFO")

    def log_exito(self, mensaje):
        self._agregar_log(f"✅ {mensaje}", "EXITO")

    def log_error(self, mensaje):
        msg_str = str(mensaje).strip()
        if not msg_str.startswith("❌") and not msg_str.startswith("⚠️"):
            msg_str = f"❌ {msg_str}"
        self._agregar_log(msg_str, "ERROR")

# ==============================================================================
# PUNTO DE ENTRADA
# ==============================================================================
if __name__ == "__main__":
    app = HospitalApp()
    app.mainloop()
