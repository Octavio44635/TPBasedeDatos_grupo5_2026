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

        # Ignorar comentarios de una sola línea cuando no estamos dentro de un bloque
        if not en_plsql and (not linea_strip or linea_strip.startswith("--")):
            continue

        linea_up = linea_strip.upper()
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
# TRADUCTOR DE ERRORES DE ORACLE A LENGUAJE HUMANO (TRIGGERS, CHECKS, FKs)
# ==============================================================================
def traducir_error_oracle(error, contexto=None):
    """
    Analiza la excepción de Oracle y devuelve una explicación en lenguaje humano
    súper detallista, mapeando cada código de Trigger (-20001 a -20010),
    restricciones CHECK, UNIQUE, FK, NOT NULL y errores de compilación.
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

    # --------------------------------------------------------------------------
    # 1. ERRORES LANZADOS POR TRIGGERS DEL PROYECTO (RAISE_APPLICATION_ERROR)
    # --------------------------------------------------------------------------
    if "20008" in mensaje_mayus or "AUTOATENCION" in mensaje_mayus or "AUTO-ATENCION" in mensaje_mayus or "AUTOATENCIÓN" in mensaje_mayus:
        return (
            "❌ REGLA DE NEGOCIO VIOLADA: UN MÉDICO NO PUEDE AUTO-ATENDERSE (Trigger trg_evitar_autoatencion):\n"
            "Explicación humana: El médico asignado tiene el mismo número de DNI que el paciente internado.\n"
            "Por regla de ética y control médico del hospital, un médico no puede ser el profesional a cargo de su propia internación.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "20010" in mensaje_mayus or "INTERNACION_MULTIPLE" in mensaje_mayus or "INTERNACION ACTIVA" in mensaje_mayus or "INTERNACIÓN ACTIVA" in mensaje_mayus:
        return (
            "❌ REGLA DE NEGOCIO VIOLADA: PACIENTE CON INTERNACIÓN ACTIVA (Trigger trg_evitar_internacion_multiple):\n"
            "Explicación humana: El paciente ya cuenta con una internación en curso sin fecha de alta médica.\n"
            "Por regla del hospital, no se puede registrar una nueva internación para un paciente que ya se encuentra actualmente internado.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "20001" in mensaje_mayus:
        return (
            "❌ FECHA DE CAMA ANTERIOR A INTERNACIÓN (Trigger trg_posee_fecha):\n"
            "Explicación humana: La fecha y hora en que se asigna la cama no puede ser anterior a la fecha en que inició la internación.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "20002" in mensaje_mayus:
        return (
            "❌ FECHA DE CAMA POSTERIOR A ALTA (Trigger trg_posee_fecha):\n"
            "Explicación humana: La asignación de cama no puede tener una fecha posterior al momento en que el paciente recibió el alta médica.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "20003" in mensaje_mayus:
        return (
            "❌ MÉDICO NO DISPUESTO A GUARDIA (Trigger trg_medico_dispuesto):\n"
            "Explicación humana: En la tabla TIENE se registró que este médico NO está dispuesto a realizar guardias para esta especialidad.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "TRG_MEDICO_DISPUESTO" in mensaje_mayus and (codigo_oracle == 1403 or "01403" in mensaje_mayus):
        return (
            "❌ ESPECIALIDAD NO REGISTRADA PARA EL MÉDICO (Trigger trg_medico_dispuesto):\n"
            "Explicación humana: El médico seleccionado no tiene registrada esa especialidad en la tabla TIENE, por lo que no puede cubrirla en una guardia.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "20005" in mensaje_mayus:
        return (
            "❌ LÍMITE DE GUARDIAS MENSUALES SUPERADO (Trigger trg_limite_guardias):\n"
            "Explicación humana: El médico ya alcanzó o superó la cantidad máxima de guardias que indicó estar dispuesto a realizar en este mes.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "20006" in mensaje_mayus:
        return (
            "❌ ROL DE PACIENTE ASIGNADO A GUARDIA (Trigger trg_validar_rol_guardia):\n"
            "Explicación humana: No se puede asignar una guardia médica a una persona que en el sistema está registrada con el rol de 'PACIENTE'.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "20007" in mensaje_mayus:
        return (
            "❌ INFORMACIÓN PERSONAL DEL MÉDICO NO ENCONTRADA (Trigger trg_validar_rol_guardia):\n"
            "Explicación humana: No se encontró la persona asociada a la matrícula médica al intentar validar la guardia.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "20009" in mensaje_mayus:
        return (
            "❌ FECHA DE INICIO INVÁLIDA (Trigger trg_validar_fecha_inicio):\n"
            "Explicación humana: La fecha de inicio de la internación no puede ser una fecha futura posterior a la fecha actual del sistema.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )

    # --------------------------------------------------------------------------
    # 2. TRIGGER INVÁLIDO O ERROR DE COMPILACIÓN (ORA-04098)
    # --------------------------------------------------------------------------
    if codigo_oracle == 4098 or "ORA-04098" in mensaje_mayus:
        return (
            "❌ DISPARADOR (TRIGGER) INVÁLIDO EN ORACLE:\n"
            "Explicación humana: Uno de los triggers de la base de datos se compiló con errores de sintaxis y quedó en estado INVÁLIDO.\n"
            "• Causa típica: El script SQL se ejecutó cortando el código por ';' en lugar de compilarse completo con la barra '/'.\n"
            "• Solución: Haz clic en el botón 'Crear/Reiniciar Tablas' para que la app recompile todos los triggers con el delimitador '/' correcto.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )

    # --------------------------------------------------------------------------
    # 3. REGLAS CHECK ESPECÍFICAS (ORA-02290)
    # --------------------------------------------------------------------------
    if "CHK_MEDICO_CUIL_DNI" in mensaje_mayus:
        return (
            "❌ EL CUIL NO COINCIDE CON EL DNI DEL MÉDICO (Regla de Integridad):\n"
            "Explicación humana: Los 8 dígitos del medio del CUIL (posiciones 3 a 10) deben ser "
            "exactamente iguales al DNI del médico.\n"
            "• Ejemplo: Si el DNI es '38123456', el CUIL debe ser '20381234563' o '27381234564'.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "CHK_PACIENTE_SEXO" in mensaje_mayus:
        return (
            "❌ SEXO DEL PACIENTE NO VÁLIDO (Regla CHECK):\n"
            "Explicación humana: El sistema solo permite registrar los valores 'MASCULINO', 'FEMENINO' u 'OTRO'.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "CHK_HABITACION_ORIENTACION" in mensaje_mayus:
        return (
            "❌ ORIENTACIÓN DE HABITACIÓN NO VÁLIDA (Regla CHECK):\n"
            "Explicación humana: La orientación de la habitación solo puede ser 'Norte', 'Sur', 'Este' u 'Oeste'.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "CHK_CAMA_NRO" in mensaje_mayus:
        return (
            "❌ NÚMERO DE CAMA INVÁLIDO (Regla CHECK):\n"
            "Explicación humana: El número de cama debe ser un número entero mayor o igual a 1 (no se permiten números negativos ni la cama 0).\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "CHK_CAMA_ESTADO" in mensaje_mayus:
        return (
            "❌ ESTADO DE CAMA INVÁLIDO (Regla CHECK):\n"
            "Explicación humana: Una cama en el hospital solo puede estar en estado 'LIBRE' u 'OCUPADA'.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "CHK_GUARDIAS_MAX" in mensaje_mayus:
        return (
            "❌ CANTIDAD DE GUARDIAS NO PERMITIDA (Regla CHECK):\n"
            "Explicación humana: Las guardias máximas mensuales que un médico puede aceptar deben ser un número mayor o igual a 0.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "CHK_RONDA_TURNO" in mensaje_mayus:
        return (
            "❌ TURNO DE RONDA NO VÁLIDO (Regla CHECK):\n"
            "Explicación humana: El turno asignado no es válido. Los turnos permitidos son 1, 2, 3 o 4.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "CHK_RONDA_DIA" in mensaje_mayus:
        return (
            "❌ DÍA DE LA SEMANA INVÁLIDO (Regla CHECK):\n"
            "Explicación humana: El día de la ronda debe ser válido (LUNES a DOMINGO).\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "CHK_INTERNACION_FECHAS" in mensaje_mayus:
        return (
            "❌ FECHAS DE INTERNACIÓN INCOHERENTES (Regla CHECK):\n"
            "Explicación humana: La fecha de finalización del alta médica no puede ser anterior a la fecha en que el paciente fue internado.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "CHK_VACACION_FECHAS" in mensaje_mayus:
        return (
            "❌ PERÍODO DE VACACIONES INVÁLIDO (Regla CHECK):\n"
            "Explicación humana: La fecha de fin de vacaciones debe ser posterior a la fecha de inicio.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "CHK_GUARDIA_TURNO" in mensaje_mayus:
        return (
            "❌ TURNO DE GUARDIA INVÁLIDO (Regla CHECK):\n"
            "Explicación humana: Los turnos de guardia solo pueden ser 'MAÑANA', 'TARDE' o 'NOCHE'.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )

    # --------------------------------------------------------------------------
    # 4. CLAVES DUPLICADAS (ORA-00001)
    # --------------------------------------------------------------------------
    if "PK_PERSONA" in mensaje_mayus:
        return (
            "❌ DNI YA REGISTRADO (Dato Duplicado):\n"
            "Explicación humana: Ya existe una persona registrada con ese mismo número de DNI.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "PK_PACIENTE" in mensaje_mayus:
        return (
            "❌ PACIENTE YA REGISTRADO (Dato Duplicado):\n"
            "Explicación humana: Este paciente ya se encuentra dado de alta en la base de datos.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "PK_MEDICO" in mensaje_mayus:
        return (
            "❌ MATRÍCULA MÉDICA DUPLICADA (Dato Duplicado):\n"
            "Explicación humana: Ya existe un médico registrado con esa misma matrícula profesional.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "UQ_MEDICO_CUIL" in mensaje_mayus:
        return (
            "❌ CUIL DE MÉDICO DUPLICADO (Dato Duplicado):\n"
            "Explicación humana: Ya existe otro médico registrado con ese mismo número de CUIL.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "UQ_MEDICO_DNI" in mensaje_mayus:
        return (
            "❌ DNI YA ASIGNADO A UN MÉDICO (Dato Duplicado):\n"
            "Explicación humana: Ese DNI ya está registrado como médico en el hospital.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "PK_CAMA" in mensaje_mayus:
        return (
            "❌ CAMA YA EXISTENTE EN ESTA HABITACIÓN (Dato Duplicado):\n"
            "Explicación humana: Esa habitación ya tiene registrada una cama con ese mismo número.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "UQ_SECTOR_NOMBRE" in mensaje_mayus:
        return (
            "❌ NOMBRE DE SECTOR REPETIDO (Dato Duplicado):\n"
            "Explicación humana: Ya existe un sector con ese mismo nombre en el hospital.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "PK_COMPUESTA_POR" in mensaje_mayus:
        return (
            "❌ RONDA YA VINCULADA (Dato Duplicado):\n"
            "Explicación humana: Esta habitación ya tiene asignada esa ronda para ese día de la semana.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "PK_CUBIERTA_POR" in mensaje_mayus:
        return (
            "❌ GUARDIA YA ASIGNADA AL MÉDICO (Dato Duplicado):\n"
            "Explicación humana: Este médico ya está asignado a esa guardia para esa misma especialidad.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )

    # --------------------------------------------------------------------------
    # 5. CLAVES FORÁNEAS (ORA-02291 - FOREIGN KEY INEXISTENTE)
    # --------------------------------------------------------------------------
    if "FK_INTERNACION_PACIENTE" in mensaje_mayus:
        return (
            "❌ PACIENTE NO ENCONTRADO:\n"
            "Explicación humana: El DNI ingresado no corresponde a ningún paciente registrado en la base de datos.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "FK_INTERNACION_MEDICO" in mensaje_mayus:
        return (
            "❌ MÉDICO PRINCIPAL NO ENCONTRADO:\n"
            "Explicación humana: La matrícula médica ingresada no existe en la base de datos.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "FK_HABITACION_SECTOR" in mensaje_mayus:
        return (
            "❌ SECTOR NO ENCONTRADO:\n"
            "Explicación humana: El sector seleccionado no existe en la base de datos.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "FK_CAMA_HABITACION" in mensaje_mayus:
        return (
            "❌ HABITACIÓN NO ENCONTRADA:\n"
            "Explicación humana: El ID de habitación ingresado no existe en el hospital.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "FK_CUBIERTA_MEDICO" in mensaje_mayus:
        return (
            "❌ MÉDICO NO ENCONTRADO:\n"
            "Explicación humana: La matrícula médica seleccionada no existe en la base de datos.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "FK_CUBIERTA_ESPECIALIDAD" in mensaje_mayus:
        return (
            "❌ ESPECIALIDAD NO ENCONTRADA:\n"
            "Explicación humana: La especialidad seleccionada no existe en la base de datos.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "FK_CUBIERTA_GUARDIA" in mensaje_mayus:
        return (
            "❌ GUARDIA NO ENCONTRADA:\n"
            "Explicación humana: La guardia seleccionada no existe en la base de datos.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )

    # --------------------------------------------------------------------------
    # 6. ERRORES GENERALES
    # --------------------------------------------------------------------------
    traducciones_generales = {
        1: ("DATO DUPLICADO (Clave Única o Primaria)", "Ya existe un registro con ese identificador en la base de datos."),
        2291: ("DATO RELACIONADO NO ENCONTRADO (Foreign Key)", "Estás intentando asociar un dato a otra tabla que no existe previamente."),
        2292: ("NO SE PUEDE ELIMINAR (Registros dependientes)", "No puedes borrar este registro porque otras tablas dependen de él."),
        2290: ("REGLA DE VALIDACIÓN NO CUMPLIDA (Violación de CHECK)", "Uno de los valores ingresados no cumple con las restricciones permitidas."),
        1400: ("CAMPO OBLIGATORIO VACÍO (NOT NULL)", "Intentaste guardar dejando en blanco un campo que es requerido obligatoriamente."),
        942: ("TABLA NO ENCONTRADA", "La tabla especificada no existe en Oracle. Haz clic en 'Crear/Reiniciar Tablas'."),
        904: ("COLUMNA NO VÁLIDA", "Escribiste un nombre de columna que no existe en la tabla consultada."),
        933: ("ERROR DE SINTAXIS SQL", "La consulta SQL está mal redactada o tiene palabras clave fuera de lugar."),
        936: ("FALTA UNA EXPRESIÓN EN EL SQL", "Falta especificar un valor, una columna o una condición en tu sentencia SQL."),
        1438: ("NÚMERO DEMASIADO GRANDE", "El número ingresado supera los dígitos permitidos para esa columna."),
        1843: ("FORMATO DE FECHA INCORRECTO", "El formato de fecha no es válido. Usa el formato estándar DD/MM/YYYY o YYYY-MM-DD."),
        1017: ("ACCESO DENEGADO", "El usuario o contraseña configurado en el archivo .env es incorrecto."),
        12541: ("BASE DE DATOS INALCANZABLE (Listener caído)", "El servicio de Oracle no responde en el puerto 1521."),
        54: ("RECURSO BLOQUEADO POR OTRA TRANSACCIÓN", "La fila seleccionada está siendo modificada por otra transacción activa en este momento.")
    }

    if codigo_oracle in traducciones_generales:
        titulo, explicacion = traducciones_generales[codigo_oracle]
        return (
            f"⚠️ {titulo}:\n"
            f"Explicación humana: {explicacion}\n"
            f"[Detalle técnico Oracle: ORA-{codigo_oracle:05d}: {mensaje_original}]"
        )
    else:
        return (
            f"⚠️ ERROR DE BASE DE DATOS:\n"
            f"Explicación: {mensaje_original}"
        )

# ==============================================================================
# CONEXIÓN
# ==============================================================================
def obtener_conexion():
    return oracledb.connect(
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASS'),
        dsn=os.getenv('DSN')
    )

# ==============================================================================
# APLICACIÓN PRINCIPAL
# ==============================================================================
class HospitalApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sistema Hospitalario - Gestión de Internaciones y Consultas SQL (UNMDP)")
        self.geometry("1180x820")
        self.minsize(980, 650)

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

        self.log_info(f"Sistema iniciado correctamente. Conectado a Oracle como usuario: '{os.getenv('DB_USER')}'.")
        self.cargar_camas_libres()
        self.actualizar_combo_internaciones()

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

        lbl_subtitulo = ttk.Label(
            frame_textos, 
            text="Diseño de Bases de Datos - Universidad Nacional de Mar del Plata | Demostración de Transacciones ACID y Stored Procedures", 
            style="SubHeader.TLabel"
        )
        lbl_subtitulo.pack(anchor="w")

        frame_botones_cab = ttk.Frame(frame_cabecera)
        frame_botones_cab.pack(side=tk.RIGHT)

        btn_cargar_datos = tk.Button(
            frame_botones_cab,
            text="📥 Cargar Datos de Prueba (HOSPITAL.sql)",
            bg="#2B6CB0",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="groove",
            cursor="hand2",
            command=self.accion_cargar_datos_hospital
        )
        btn_cargar_datos.pack(side=tk.LEFT, padx=5, pady=5)

        btn_init_db = tk.Button(
            frame_botones_cab,
            text="🛠️ Crear/Reiniciar Tablas (create-table.sql)",
            bg="#DD6B20",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="groove",
            cursor="hand2",
            command=self.accion_ejecutar_script_tablas
        )
        btn_init_db.pack(side=tk.LEFT, padx=5, pady=5)

    def ejecutar_archivo_sql(self, archivo, nombre_descriptivo):
        if not os.path.exists(archivo):
            self.log_error(f"No se encontró el archivo '{archivo}' en la carpeta del proyecto.")
            messagebox.showerror("Archivo no encontrado", f"No se encontró '{archivo}'.")
            return

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

            for sql in sentencias:
                sql = sql.strip()
                if sql:
                    try:
                        cursor.execute(sql)
                        exitos += 1
                    except oracledb.DatabaseError as e:
                        error_obj, = e.args
                        if error_obj.code == 942:  # ORA-00942: tabla no existe en DROP
                            pass
                        else:
                            errores += 1
                            self.log_error(f"Sentencia con aviso [{error_obj.code}]: {sql[:40]}... -> {traducir_error_oracle(e)}")

            conn.commit()
            msg = f"{nombre_descriptivo} finalizado.\n• Exitosas: {exitos}\n• Avisos no críticos: {errores}"
            self.log_exito(msg)
            messagebox.showinfo("Operación Finalizada", msg)
            self.cargar_camas_libres()
            self.refrescar_panel_guardias()

        except Exception as e:
            self.log_error(f"Error crítico al procesar '{archivo}':\n{traducir_error_oracle(e)}")
            messagebox.showerror("Error", traducir_error_oracle(e))
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def accion_ejecutar_script_tablas(self):
        respuesta = messagebox.askyesno(
            "Confirmar Inicialización", 
            "¿Deseas ejecutar 'create-table.sql'?\nEsto borrará (DROP) y volverá a crear todas las tablas, triggers y stored procedures en Oracle."
        )
        if respuesta:
            self.ejecutar_archivo_sql("create-table.sql", "Creación de Esquema y Triggers")

    def accion_cargar_datos_hospital(self):
        respuesta = messagebox.askyesno(
            "Cargar Datos de Prueba", 
            "¿Deseas ejecutar 'HOSPITAL.sql'?\nEsto insertará los datos de prueba oficiales (personas, pacientes, médicos, camas, internaciones y guardias)."
        )
        if respuesta:
            self.ejecutar_archivo_sql("HOSPITAL.sql", "Carga de Datos de Prueba (HOSPITAL.sql)")

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
        self.notebook.add(self.tab_sql, text=" 💻 Consola SQL en Vivo (Para el Parcial) ")
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
        btn_ejecutar.grid(row=2, column=0, columnspan=4, pady=(8, 2), sticky="ew")

        # 2. Formulario: Traslado / Cambio de Cama y Alta Médica
        frame_traslado = ttk.LabelFrame(columna_izq, text=" 🔄 Gestión de Internación (Traslado / Alta Médica) ", padding=10)
        frame_traslado.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(frame_traslado, text="ID Internación:").grid(row=0, column=0, sticky="w", pady=3)
        self.txt_traslado_id_int = ttk.Combobox(frame_traslado, width=15)
        self.txt_traslado_id_int.grid(row=0, column=1, pady=3, padx=(0, 4), sticky="w")
        self.txt_traslado_id_int.bind("<<ComboboxSelected>>", self.accion_consultar_cama_actual)
        self.txt_traslado_id_int.bind("<Return>", self.accion_consultar_cama_actual)

        btn_info_paciente = tk.Button(
            frame_traslado,
            text="🔍 Info Cama Actual",
            bg="#EDF2F7",
            font=("Segoe UI", 8),
            cursor="hand2",
            command=self.accion_consultar_cama_actual
        )
        btn_info_paciente.grid(row=0, column=2, columnspan=2, sticky="ew", pady=3)

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
            text="🔀 Trasladar Paciente (COMMIT)",
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
        frame_sp_comentarios = ttk.LabelFrame(columna_izq, text=" 💬 Visitas Médicas (Stored Procedure) ", padding=8)
        frame_sp_comentarios.pack(fill=tk.X)

        ttk.Label(frame_sp_comentarios, text="ID Internación:").grid(row=0, column=0, sticky="w", pady=2)
        self.txt_id_int_comentario = ttk.Entry(frame_sp_comentarios, width=10)
        self.txt_id_int_comentario.insert(0, "1")
        self.txt_id_int_comentario.grid(row=0, column=1, pady=2, padx=(0, 8), sticky="w")

        btn_ver_sp_comentarios = tk.Button(
            frame_sp_comentarios,
            text="💬 Ver Visitas Médicas (SP)",
            bg="#E2E8F0",
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
            command=self.accion_consultar_comentarios_sp
        )
        btn_ver_sp_comentarios.grid(row=0, column=2, pady=2, sticky="ew")

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
            frame_der, text="🔄 Actualizar Camas y Resumen (Invocar SP)", bg="#E2E8F0", cursor="hand2", command=self.cargar_camas_libres
        )
        btn_refrescar_camas.pack(anchor="w", pady=(0, 2))

    def accion_registrar_internacion(self):
        dni = self.txt_dni.get().strip()
        matricula = self.txt_matricula.get().strip()
        hab_str = self.txt_hab.get().strip()
        cama_str = self.txt_cama.get().strip()

        if not (dni and matricula and hab_str and cama_str):
            messagebox.showwarning("Campos Incompletos", "Por favor completa todos los campos del formulario.")
            return

        try:
            hab = int(hab_str)
            cama = int(cama_str)
        except ValueError:
            self.log_error("Habitación y Cama deben ser números enteros.")
            messagebox.showerror("Dato Inválido", "Habitación y Cama deben ser valores numéricos enteros.")
            return

        conn = None
        cursor = None
        try:
            self.log_info(f"Iniciando transacción: Asignando Paciente DNI={dni} a Hab={hab}, Cama={cama} con Médico={matricula}...")
            conn = obtener_conexion()
            cursor = conn.cursor()

            # 1. Bloqueo y verificación de la cama
            cursor.execute("""
                SELECT estado 
                FROM CAMA 
                WHERE id_habitacion = :1 AND nro_cama = :2 
                FOR UPDATE 
            """, [hab, cama]) 
            
            fila_cama = cursor.fetchone()
            if not fila_cama:
                raise Exception(f"La cama {cama} de la habitación {hab} no existe en la base de datos.")
            if fila_cama[0].upper() != 'LIBRE':
                raise Exception(f"La cama {cama} de la habitación {hab} no está disponible (Estado actual: '{fila_cama[0]}').")

            # 1.5. Validar regla médica de autoatención
            cursor.execute("SELECT numero_de_DNI FROM MEDICO WHERE numero_de_matricula = :1", [matricula])
            fila_med = cursor.fetchone()
            if fila_med and str(fila_med[0]).strip() == str(dni).strip():
                raise Exception("Regla médica de negocio: Un médico no puede ser el profesional a cargo de su propia internación (el DNI del paciente coincide con el DNI del médico).")

            # 2. Inserción de la Internación
            id_internacion_var = cursor.var(oracledb.NUMBER)
            cursor.execute("""
                INSERT INTO INTERNACION (fecha_inicio, numero_de_DNI, numero_de_matricula)
                VALUES (TRUNC(SYSDATE), :1, :2)
                RETURNING id_internacion INTO :3
            """, [dni, matricula, id_internacion_var])
            
            id_internacion = int(id_internacion_var.getvalue()[0])

            # 3. Ocupar la cama (respetando si la tabla usa 'OCUPADA' u 'Ocupada')
            estado_ocupado = "OCUPADA" if fila_cama[0].isupper() else "Ocupada"
            cursor.execute("""
                UPDATE CAMA 
                SET estado = :1 
                WHERE id_habitacion = :2 AND nro_cama = :3
            """, [estado_ocupado, hab, cama])

            # 4. Insertar en POSEE (historial con timestamp)
            cursor.execute("""
                INSERT INTO POSEE (id_internacion, id_habitacion, nro_cama, fechaHora)
                VALUES (:1, :2, :3, SYSTIMESTAMP)
            """, [id_internacion, hab, cama])

            # Confirmar transacción completa
            conn.commit()
            mensaje_exito = f"Transacción confirmada (COMMIT): Internación #{id_internacion} creada con éxito. Cama {cama} de Hab {hab} quedó OCUPADA."
            self.log_exito(mensaje_exito)
            messagebox.showinfo("Transacción Exitosa", mensaje_exito)

            self.txt_dni.delete(0, tk.END)
            self.txt_matricula.delete(0, tk.END)
            self.txt_hab.delete(0, tk.END)
            self.txt_cama.delete(0, tk.END)
            self.cargar_camas_libres()
            self.actualizar_combo_internaciones()

        except Exception as e:
            if conn:
                conn.rollback()
            self.log_error(f"Transacción ABORTADA (ROLLBACK aplicado):\n{traducir_error_oracle(e)}")
            messagebox.showerror("Error en Transacción", traducir_error_oracle(e))

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
            cursor.execute("""
                SELECT i.id_internacion, p.nombre, p.apellido, i.numero_de_DNI
                FROM INTERNACION i
                JOIN PERSONA p ON i.numero_de_DNI = p.numero_de_DNI
                WHERE i.fecha_fin IS NULL
                ORDER BY i.id_internacion DESC
            """)
            filas = cursor.fetchall()
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
            cursor.execute("""
                SELECT i.id_internacion, p.nombre, p.apellido, i.numero_de_DNI, i.fecha_fin
                FROM INTERNACION i
                JOIN PERSONA p ON i.numero_de_DNI = p.numero_de_DNI
                WHERE i.id_internacion = :1
            """, [id_int])
            row = cursor.fetchone()
            if not row:
                self.lbl_traslado_info.config(text=f"❌ La internación #{id_int} no existe.", foreground="#C53030")
                cursor.close()
                return

            id_i, nom, ape, dni, f_fin = row

            cursor.execute("""
                SELECT id_habitacion, nro_cama
                FROM POSEE
                WHERE id_internacion = :1
                ORDER BY fechaHora DESC
                FETCH FIRST 1 ROW ONLY
            """, [id_int])
            row_cama = cursor.fetchone()
            cursor.close()

            # Sincronizar también el ID en la caja de Visitas Médicas (Stored Procedure)
            if hasattr(self, 'txt_id_int_comentario'):
                self.txt_id_int_comentario.delete(0, tk.END)
                self.txt_id_int_comentario.insert(0, str(id_int))

            if f_fin is not None:
                self.lbl_traslado_info.config(
                    text=f"⚠️ Paciente {nom} {ape} (DNI {dni}) - ALTA MÉDICA OTORGADA ({f_fin.strftime('%d/%m/%Y')}).",
                    foreground="#C53030"
                )
            elif row_cama:
                hab_act, cama_act = row_cama
                self.lbl_traslado_info.config(
                    text=f"👤 {nom} {ape} (DNI {dni}) | Cama actual: Hab {hab_act}, Cama {cama_act}",
                    foreground="#2B6CB0"
                )
            else:
                self.lbl_traslado_info.config(
                    text=f"👤 {nom} {ape} (DNI {dni}) | Sin cama previa asignada",
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

            # 1. Validar existencia y estado de la internación
            cursor.execute("""
                SELECT i.id_internacion, i.fecha_inicio, i.fecha_fin, i.numero_de_DNI, p.nombre, p.apellido
                FROM INTERNACION i
                JOIN PERSONA p ON i.numero_de_DNI = p.numero_de_DNI
                WHERE i.id_internacion = :1
            """, [id_int])
            row_int = cursor.fetchone()
            if not row_int:
                raise Exception(f"La internación #{id_int} no existe en la base de datos.")
            if row_int[2] is not None:
                raise Exception(f"La internación #{id_int} ya finalizó (alta médica otorgada el {row_int[2].strftime('%d/%m/%Y')}). No se puede cambiar de cama a un paciente con alta.")

            paciente_nombre = f"{row_int[4]} {row_int[5]} (DNI {row_int[3]})"

            # 2. Consultar cama actual del paciente en POSEE
            cursor.execute("""
                SELECT id_habitacion, nro_cama
                FROM POSEE
                WHERE id_internacion = :1
                ORDER BY fechaHora DESC
                FETCH FIRST 1 ROW ONLY
            """, [id_int])
            row_cama_actual = cursor.fetchone()
            hab_anterior, cama_anterior = (row_cama_actual[0], row_cama_actual[1]) if row_cama_actual else (None, None)

            if hab_anterior == hab_nueva and cama_anterior == cama_nueva:
                raise Exception(f"El paciente {paciente_nombre} ya se encuentra actualmente en la Habitación {hab_nueva}, Cama {cama_nueva}. Por favor selecciona una cama diferente para el traslado.")

            # 3. Bloqueo y verificación de la nueva cama
            cursor.execute("""
                SELECT estado 
                FROM CAMA 
                WHERE id_habitacion = :1 AND nro_cama = :2 
                FOR UPDATE
            """, [hab_nueva, cama_nueva])
            fila_cama = cursor.fetchone()
            if not fila_cama:
                raise Exception(f"La cama {cama_nueva} de la habitación {hab_nueva} no existe en la base de datos.")
            if fila_cama[0].upper() != 'LIBRE':
                raise Exception(f"La cama {cama_nueva} de la habitación {hab_nueva} no está disponible (Estado actual: '{fila_cama[0]}').")

            # 4. Ocupar la nueva cama (respetando si la tabla usa 'OCUPADA' u 'Ocupada')
            estado_ocupado = "OCUPADA" if fila_cama[0].isupper() else "Ocupada"
            cursor.execute("""
                UPDATE CAMA
                SET estado = :1
                WHERE id_habitacion = :2 AND nro_cama = :3
            """, [estado_ocupado, hab_nueva, cama_nueva])

            # 5. Insertar en POSEE (el Trigger 'trg_liberar_cama_cambio' liberará automáticamente la cama anterior)
            cursor.execute("""
                INSERT INTO POSEE (id_internacion, id_habitacion, nro_cama, fechaHora)
                VALUES (:1, :2, :3, SYSTIMESTAMP)
            """, [id_int, hab_nueva, cama_nueva])

            # Confirmar transacción completa
            conn.commit()

            msg_exito = (
                f"Transacción confirmada (COMMIT):\n"
                f"• Paciente: {paciente_nombre}\n"
                f"• Internación #{id_int} trasladado a Habitación {hab_nueva}, Cama {cama_nueva} (Estado: OCUPADA).\n"
            )
            if hab_anterior is not None:
                msg_exito += f"• Cama anterior: Habitación {hab_anterior}, Cama {cama_anterior} liberada automáticamente por el Trigger 'trg_liberar_cama_cambio'."

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
            self.log_error(f"Traslado ABORTADO (ROLLBACK aplicado):\n{traducir_error_oracle(e)}")
            messagebox.showerror("Error en Traslado", traducir_error_oracle(e))
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

            # 1. Validar existencia y estado de la internación
            cursor.execute("""
                SELECT i.id_internacion, i.fecha_inicio, i.fecha_fin, i.numero_de_DNI, p.nombre, p.apellido
                FROM INTERNACION i
                JOIN PERSONA p ON i.numero_de_DNI = p.numero_de_DNI
                WHERE i.id_internacion = :1
            """, [id_int])
            row_int = cursor.fetchone()
            if not row_int:
                raise Exception(f"La internación #{id_int} no existe en la base de datos.")
            if row_int[2] is not None:
                raise Exception(f"La internación #{id_int} ya finalizó previamente (Alta médica otorgada el {row_int[2].strftime('%d/%m/%Y')}).")

            paciente_nombre = f"{row_int[4]} {row_int[5]} (DNI {row_int[3]})"
            fecha_inicio = row_int[1]

            # 2. Consultar cama actual del paciente en POSEE
            cursor.execute("""
                SELECT id_habitacion, nro_cama
                FROM POSEE
                WHERE id_internacion = :1
                ORDER BY fechaHora DESC
                FETCH FIRST 1 ROW ONLY
            """, [id_int])
            row_cama = cursor.fetchone()
            hab_act, cama_act = (row_cama[0], row_cama[1]) if row_cama else (None, None)
            cama_info = f"Habitación {hab_act}, Cama {cama_act}" if hab_act is not None else "Sin cama asignada"

            # 3. Cuadro de confirmación antes de proceder
            confirmar = messagebox.askyesno(
                "Confirmar Alta Médica",
                f"¿Deseas dar el Alta Médica y finalizar la internación #{id_int}?\n\n"
                f"• Paciente: {paciente_nombre}\n"
                f"• Cama actual a liberar: {cama_info}\n\n"
                f"Al confirmar, se actualizará la fecha de alta y el disparador 'trg_liberar_cama_fin_int' liberará la cama automáticamente."
            )
            if not confirmar:
                return

            self.log_info(f"Procesando alta médica para Internación #{id_int} ({paciente_nombre})...")

            # 4. Actualizar fecha_fin en INTERNACION.
            # En Oracle, el Trigger 'trg_liberar_cama_fin_int' se dispara:
            # AFTER UPDATE OF fecha_fin ON INTERNACION WHEN (OLD.fecha_fin IS NULL AND NEW.fecha_fin IS NOT NULL)
            # y ejecuta: UPDATE CAMA SET estado = 'LIBRE' WHERE id_habitacion = v_id_hab AND nro_cama = v_nro_cama;
            cursor.execute("""
                UPDATE INTERNACION
                SET fecha_fin = GREATEST(TRUNC(SYSDATE), fecha_inicio)
                WHERE id_internacion = :1 AND fecha_fin IS NULL
            """, [id_int])

            if cursor.rowcount == 0:
                raise Exception(f"No se pudo actualizar la internación #{id_int}. Verifique si ya estaba finalizada.")

            # Como resguardo si el trigger no estuviera activo en la base:
            if hab_act is not None and cama_act is not None:
                cursor.execute("""
                    UPDATE CAMA
                    SET estado = 'LIBRE'
                    WHERE id_habitacion = :1 AND nro_cama = :2 AND estado != 'LIBRE'
                """, [hab_act, cama_act])

            # Confirmar la transacción
            conn.commit()

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
            self.log_error(f"Alta médica ABORTADA (ROLLBACK aplicado):\n{traducir_error_oracle(e)}")
            messagebox.showerror("Error en Alta Médica", traducir_error_oracle(e))
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

            # Intentar invocar el Stored Procedure listar_camas_disponibles
            usar_sp = False
            try:
                cur_res = cursor.connection.cursor()
                cur_det = cursor.connection.cursor()
                cursor.callproc("listar_camas_disponibles", [cur_res, cur_det])
                
                filas_resumen = cur_res.fetchall()
                if hasattr(self, 'tabla_resumen_camas'):
                    for r in filas_resumen:
                        nom = r[1] if len(r) >= 2 else str(r[0])
                        cant = r[2] if len(r) >= 3 else r[1]
                        self.tabla_resumen_camas.insert("", tk.END, values=(nom, f"{cant} libre(s)"))

                filas_detalle = cur_det.fetchall()
                if hasattr(self, 'tabla_camas'):
                    for f in filas_detalle:
                        self.tabla_camas.insert("", tk.END, values=(f[0], f[1], "-", f[2], "LIBRE"))

                cur_res.close()
                cur_det.close()
                usar_sp = True
            except Exception:
                usar_sp = False

            # Si el SP no está compilado, usar consulta directa con soporte mayúsculas/minúsculas
            if not usar_sp:
                cursor.execute("""
                    SELECT s.nombre AS sector, COUNT(c.nro_cama) AS disponibles
                    FROM SECTOR s
                    LEFT JOIN HABITACION h ON s.id_sector = h.id_sector
                    LEFT JOIN CAMA c ON h.id_habitacion = c.id_habitacion AND UPPER(c.estado) = 'LIBRE'
                    GROUP BY s.nombre
                    ORDER BY s.nombre
                """)
                for r in cursor.fetchall():
                    if hasattr(self, 'tabla_resumen_camas'):
                        self.tabla_resumen_camas.insert("", tk.END, values=(r[0], f"{r[1]} libre(s)"))

                cursor.execute("""
                    SELECT s.nombre AS sector, h.id_habitacion, h.piso, c.nro_cama, c.estado
                    FROM CAMA c
                    JOIN HABITACION h ON c.id_habitacion = h.id_habitacion
                    JOIN SECTOR s ON h.id_sector = s.id_sector
                    WHERE UPPER(c.estado) = 'LIBRE'
                    ORDER BY s.nombre, h.id_habitacion, c.nro_cama
                """)
                for f in cursor.fetchall():
                    if hasattr(self, 'tabla_camas'):
                        self.tabla_camas.insert("", tk.END, values=(f[0], f[1], f[2], f[3], f[4]))

            cursor.close()
        except Exception as e:
            traduccion = traducir_error_oracle(e)
            self.log_error(f"No se pudieron cargar las camas libres:\n{traduccion}")
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
            cursor.callproc("listar_comentarios_internacion", [id_int, cur_pac, cur_com])

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
                    texto_resultado += f"📅 Fecha: {c[0]} | Médico: {c[1]} (Mat: {c[2]})\n"
                    texto_resultado += f"💬 Comentario: \"{c[3]}\"\n"
                    texto_resultado += "-" * 55 + "\n"

            self.log_exito(f"Stored Procedure 'listar_comentarios_internacion' ejecutado con éxito para Internación #{id_int}.")
            messagebox.showinfo(f"Comentarios de Internación #{id_int}", texto_resultado)

        except Exception as e:
            self.log_error(f"Error al ejecutar Stored Procedure de comentarios:\n{traducir_error_oracle(e)}")
            messagebox.showerror("Error Stored Procedure", traducir_error_oracle(e))
        finally:
            if conn:
                conn.close()

    # ==========================================================================
    # TAB 2: SECCIONES DE ALTAS (PACIENTES, MÉDICOS, SECTORES, HABITACIONES, CAMAS)
    # ==========================================================================
    def construir_tab_altas(self):
        notebook_altas = ttk.Notebook(self.tab_altas)
        notebook_altas.pack(fill=tk.BOTH, expand=True)

        tab_pac = ttk.Frame(notebook_altas, padding=12)
        notebook_altas.add(tab_pac, text=" 👤 Pacientes ")
        self.construir_subtab_paciente(tab_pac)

        tab_med = ttk.Frame(notebook_altas, padding=12)
        notebook_altas.add(tab_med, text=" 🩺 Médicos ")
        self.construir_subtab_medico(tab_med)

        tab_sec = ttk.Frame(notebook_altas, padding=12)
        notebook_altas.add(tab_sec, text=" 🏢 Sectores ")
        self.construir_subtab_sector(tab_sec)

        tab_hab = ttk.Frame(notebook_altas, padding=12)
        notebook_altas.add(tab_hab, text=" 🚪 Habitaciones ")
        self.construir_subtab_habitacion(tab_hab)

        tab_cama = ttk.Frame(notebook_altas, padding=12)
        notebook_altas.add(tab_cama, text=" 🛏️ Camas ")
        self.construir_subtab_cama(tab_cama)

        tab_guardia = ttk.Frame(notebook_altas, padding=12)
        notebook_altas.add(tab_guardia, text=" 🛡️ Guardias ")
        self.construir_subtab_guardia(tab_guardia)

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

        fmt = 'YYYY-MM-DD' if '-' in fnac else 'DD/MM/YYYY'

        conn = None
        cursor = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            # 1. Insert en PERSONA
            cursor.execute("""
                INSERT INTO PERSONA (numero_de_DNI, nombre, apellido, rol)
                VALUES (:1, :2, :3, 'PACIENTE')
            """, [dni, nom, ape])

            # 2. Insert en PACIENTE
            cursor.execute(f"""
                INSERT INTO PACIENTE (numero_de_DNI, sexo, fecha_de_nacimiento)
                VALUES (:1, :2, TO_DATE(:3, '{fmt}'))
            """, [dni, sex, fnac])

            conn.commit()
            self.log_exito(f"Paciente DNI {dni} ({ape}, {nom}) registrado exitosamente.")
            messagebox.showinfo("Éxito", f"Paciente {nom} {ape} registrado correctamente.")
            self.pac_dni.delete(0, tk.END)
            self.pac_nombre.delete(0, tk.END)
            self.pac_apellido.delete(0, tk.END)
            self.cargar_lista_pacientes()

        except Exception as e:
            if conn:
                conn.rollback()
            self.log_error(f"Error al registrar paciente:\n{traducir_error_oracle(e)}")
            messagebox.showerror("Error", traducir_error_oracle(e))
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
            cursor.execute("""
                SELECT p.numero_de_DNI, pr.apellido, pr.nombre, p.sexo, TO_CHAR(p.fecha_de_nacimiento, 'DD/MM/YYYY')
                FROM PACIENTE p
                JOIN PERSONA pr ON p.numero_de_DNI = pr.numero_de_DNI
                ORDER BY pr.apellido, pr.nombre
            """)
            for row in cursor.fetchall():
                self.tabla_pacientes.insert("", tk.END, values=row)
            cursor.close()
        except Exception as e:
            self.log_error(f"No se pudieron cargar los pacientes: {traducir_error_oracle(e)}")
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

        btn_ver_foto = tk.Button(frame_botones_medicos, text="🖼️ Ver Foto del Médico Seleccionado", bg="#E2E8F0", cursor="hand2", command=self.accion_ver_foto_medico)
        btn_ver_foto.pack(side=tk.LEFT)

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
            cursor.execute("SELECT foto FROM MEDICO WHERE numero_de_matricula = :1", [matricula])
            res = cursor.fetchone()
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
            self.log_error(f"Error al abrir la foto del médico: {traducir_error_oracle(e)}")
            messagebox.showerror("Error", traducir_error_oracle(e))
        finally:
            if conn:
                conn.close()

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

            # 1. Verificar o insertar PERSONA (rol NULL para no chocar con el trigger de guardias)
            cursor.execute("SELECT numero_de_DNI FROM PERSONA WHERE numero_de_DNI = :1", [dni])
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO PERSONA (numero_de_DNI, nombre, apellido, rol)
                    VALUES (:1, :2, :3, NULL)
                """, [dni, nom, ape])

            foto_bytes = None
            if self.med_ruta_foto and os.path.exists(self.med_ruta_foto):
                with open(self.med_ruta_foto, "rb") as f:
                    foto_bytes = f.read()

            # 2. Insertar en MEDICO con foto BLOB
            cursor.execute("""
                INSERT INTO MEDICO (numero_de_matricula, CUIL, foto, guardias_max, fecha_ingreso, numero_de_DNI)
                VALUES (:1, :2, :3, :4, SYSDATE, :5)
            """, [mat, cuil, foto_bytes, guardias, dni])

            conn.commit()
            texto_foto = "con foto adjunta" if foto_bytes else "sin foto"
            self.log_exito(f"Médico Matrícula {mat} - Dr. {ape}, {nom} ({texto_foto}) registrado exitosamente.")
            messagebox.showinfo("Éxito", f"Médico Dr. {ape} registrado con éxito ({texto_foto}).")
            self.med_dni.delete(0, tk.END)
            self.med_nombre.delete(0, tk.END)
            self.med_apellido.delete(0, tk.END)
            self.med_matricula.delete(0, tk.END)
            self.med_cuil.delete(0, tk.END)
            self.med_ruta_foto = None
            self.lbl_foto_nombre.config(text="Sin foto")
            self.cargar_lista_medicos()
            self.cargar_combos_guardia()

        except Exception as e:
            if conn:
                conn.rollback()
            self.log_error(f"Error al registrar médico:\n{traducir_error_oracle(e)}")
            messagebox.showerror("Error", traducir_error_oracle(e))
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
            cursor.execute("""
                SELECT m.numero_de_matricula, m.numero_de_DNI, pr.apellido, pr.nombre, m.CUIL, m.guardias_max,
                       CASE WHEN m.foto IS NOT NULL THEN 'Sí' ELSE 'No' END AS tiene_foto
                FROM MEDICO m
                JOIN PERSONA pr ON m.numero_de_DNI = pr.numero_de_DNI
                ORDER BY pr.apellido, pr.nombre
            """)
            for row in cursor.fetchall():
                self.tabla_medicos.insert("", tk.END, values=row)
            cursor.close()
        except Exception as e:
            self.log_error(f"No se pudieron cargar los médicos: {traducir_error_oracle(e)}")
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
            cursor.execute("""
                INSERT INTO SECTOR (nombre)
                VALUES (:1)
                RETURNING id_sector INTO :2
            """, [nombre, id_sec_var])
            conn.commit()
            nuevo_id = int(id_sec_var.getvalue()[0])
            self.log_exito(f"Sector #{nuevo_id} '{nombre}' creado exitosamente en la base de datos.")
            messagebox.showinfo("Éxito", f"Sector '{nombre}' (ID #{nuevo_id}) creado correctamente.")
            self.actualizar_todos_los_sectores()
            if hasattr(self, 'hab_sector_cb'):
                self.hab_sector_cb.set(f"{nuevo_id} - {nombre}")
            return True
        except Exception as e:
            if conn:
                conn.rollback()
            self.log_error(f"Error al crear sector:\n{traducir_error_oracle(e)}")
            messagebox.showerror("Error al Crear Sector", traducir_error_oracle(e))
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
            cursor.execute("SELECT id_sector, nombre FROM SECTOR ORDER BY id_sector")
            sectores = cursor.fetchall()

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
                cursor.execute("""
                    SELECT s.id_sector, s.nombre,
                           (SELECT COUNT(*) FROM HABITACION h WHERE h.id_sector = s.id_sector) AS cant_habs
                    FROM SECTOR s
                    ORDER BY s.id_sector
                """)
                for row in cursor.fetchall():
                    self.tabla_sectores.insert("", tk.END, values=(row[0], row[1], f"{row[2]} habitaciones"))

            cursor.close()
        except Exception as e:
            self.log_error(f"Error al actualizar sectores: {traducir_error_oracle(e)}")
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
            cursor.execute("""
                SELECT r.dia_semana, r.turno, r.id_ronda
                FROM COMPUESTA_POR cp
                JOIN RONDA r ON cp.id_ronda = r.id_ronda
                WHERE cp.id_habitacion = :1
                ORDER BY CASE r.dia_semana 
                    WHEN 'LUNES' THEN 1 
                    WHEN 'MARTES' THEN 2 
                    WHEN 'MIERCOLES' THEN 3 
                    WHEN 'JUEVES' THEN 4 
                    WHEN 'VIERNES' THEN 5 
                    WHEN 'SABADO' THEN 6 
                    WHEN 'DOMINGO' THEN 7 
                    ELSE 8 END
            """, [id_hab])
            filas = cursor.fetchall()
            if not filas:
                messagebox.showinfo("Rondas", f"La habitación #{id_hab} no tiene rondas asignadas aún.")
                return

            detalle = f"📅 RONDAS ASIGNADAS - HABITACIÓN #{id_hab}:\n\n"
            for dia, turno, id_ronda in filas:
                turno_fmt = f"Turno {turno}" if str(turno).isdigit() else str(turno)
                detalle += f"• {dia:<10} ➔ {turno_fmt:<10} (Ronda ID #{id_ronda})\n"

            messagebox.showinfo(f"Rondas de Habitación #{id_hab}", detalle)
        except Exception as e:
            self.log_error(f"Error al consultar rondas: {traducir_error_oracle(e)}")
            messagebox.showerror("Error", traducir_error_oracle(e))
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

            # 1. Insertar Habitación y obtener su ID
            id_hab_var = cursor.var(oracledb.NUMBER)
            cursor.execute("""
                INSERT INTO HABITACION (piso, orientacion, id_sector)
                VALUES (:1, :2, :3)
                RETURNING id_habitacion INTO :4
            """, [piso, ori, id_sector, id_hab_var])
            nueva_hab = int(id_hab_var.getvalue()[0])

            # 2. Asignar la ronda de cada uno de los 7 días
            rondas_asignadas = []
            for dia_cod, _ in self.dias_semana:
                turno_sel = self.cb_turnos_dias[dia_cod].get()
                nro_turno = turno_sel.replace("Turno", "").strip()

                cursor.execute("""
                    SELECT id_ronda FROM RONDA 
                    WHERE dia_semana = :1 AND turno = :2
                """, [dia_cod, nro_turno])
                fila_ronda = cursor.fetchone()

                if fila_ronda:
                    id_ronda = fila_ronda[0]
                else:
                    id_ronda_var = cursor.var(oracledb.NUMBER)
                    cursor.execute("""
                        INSERT INTO RONDA (dia_semana, turno)
                        VALUES (:1, :2)
                        RETURNING id_ronda INTO :3
                    """, [dia_cod, nro_turno, id_ronda_var])
                    id_ronda = int(id_ronda_var.getvalue()[0])

                cursor.execute("""
                    INSERT INTO COMPUESTA_POR (id_ronda, id_habitacion)
                    VALUES (:1, :2)
                """, [id_ronda, nueva_hab])
                rondas_asignadas.append(f"{dia_cod}: Turno {nro_turno}")

            conn.commit()
            msg_exito = f"Habitación #{nueva_hab} creada y asociada a las rondas de los 7 días con éxito (COMMIT)."
            self.log_exito(msg_exito)
            messagebox.showinfo("Éxito", msg_exito)
            self.cargar_lista_habitaciones()

        except Exception as e:
            if conn:
                conn.rollback()
            self.log_error(f"Error al crear habitación y rondas:\n{traducir_error_oracle(e)}")
            messagebox.showerror("Error en Creación", traducir_error_oracle(e))
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

            cursor.execute("""
                SELECT h.id_habitacion, h.piso, h.orientacion, s.nombre,
                       (SELECT COUNT(*) FROM COMPUESTA_POR cp WHERE cp.id_habitacion = h.id_habitacion) AS cant_rondas
                FROM HABITACION h
                JOIN SECTOR s ON h.id_sector = s.id_sector
                ORDER BY h.id_habitacion
            """)
            for row in cursor.fetchall():
                cant_texto = f"{row[4]} días asignados" if row[4] > 0 else "Sin rondas"
                self.tabla_habitaciones.insert("", tk.END, values=(row[0], row[1], row[2], row[3], cant_texto))
            cursor.close()
        except Exception as e:
            self.log_error(f"No se pudieron cargar habitaciones: {traducir_error_oracle(e)}")
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
            cursor.execute("""
                INSERT INTO CAMA (id_habitacion, nro_cama, estado)
                VALUES (:1, :2, :3)
            """, [id_hab, nro_cama, estado])
            conn.commit()
            self.log_exito(f"Cama {nro_cama} creada en Habitación #{id_hab} con estado '{estado}'.")
            messagebox.showinfo("Éxito", f"Cama {nro_cama} creada con éxito.")
            self.cargar_todas_las_camas()
            self.cargar_camas_libres()
        except Exception as e:
            if conn:
                conn.rollback()
            self.log_error(f"Error al crear cama:\n{traducir_error_oracle(e)}")
            messagebox.showerror("Error", traducir_error_oracle(e))
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
            cursor.execute("""
                SELECT c.id_habitacion, c.nro_cama, c.estado, s.nombre
                FROM CAMA c
                JOIN HABITACION h ON c.id_habitacion = h.id_habitacion
                JOIN SECTOR s ON h.id_sector = s.id_sector
                ORDER BY c.id_habitacion, c.nro_cama
            """)
            for row in cursor.fetchall():
                self.tabla_todas_camas.insert("", tk.END, values=row)
            cursor.close()
        except Exception as e:
            self.log_error(f"No se pudieron cargar las camas: {traducir_error_oracle(e)}")
        finally:
            if conn:
                conn.close()

    # 6. Subtab Guardia
    def construir_subtab_guardia(self, parent):
        """Construye el panel de alta directa, listado, modificación y baja de guardias."""
        frame_form = ttk.LabelFrame(parent, text=" ➕ Crear Nueva Guardia (con Médico Asignado) ", padding=10)
        frame_form.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
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

        self.refrescar_panel_guardias()

    @staticmethod
    def _parsear_clave_combo(valor):
        return valor.split(" - ", 1)[0].strip()

    def _obtener_opciones_medicos(self, cursor):
        cursor.execute("""
            SELECT m.numero_de_matricula, p.apellido, p.nombre
            FROM MEDICO m
            JOIN PERSONA p ON m.numero_de_DNI = p.numero_de_DNI
            ORDER BY p.apellido, p.nombre
        """)
        return [f"{m[0]} - {m[1]}, {m[2]}" for m in cursor.fetchall()]

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
                conn_propia = obtener_conexion()
                cursor_local = conn_propia.cursor()

            cursor_local.execute("""
                SELECT e.id_especialidad, e.nombre, t.dispuesto
                FROM ESPECIALIDAD e
                LEFT JOIN TIENE t
                       ON e.id_especialidad = t.id_especialidad
                      AND t.numero_de_matricula = :1
                ORDER BY CASE
                             WHEN UPPER(t.dispuesto) = 'SI' THEN 0
                             WHEN UPPER(t.dispuesto) = 'NO' THEN 1
                             ELSE 2
                         END,
                         e.nombre
            """, [matricula])

            opciones_esp = []
            for id_esp, nombre, dispuesto in cursor_local.fetchall():
                estado = f"Disp: {dispuesto}" if dispuesto is not None else "No reg."
                opciones_esp.append(f"{id_esp} - {nombre} ({estado})")

            cb_esp["values"] = opciones_esp
            if opciones_esp:
                cb_esp.current(0)
            else:
                cb_esp.set("")
            self._actualizar_label_esp_guardia(cb_esp, lbl_info)

        except Exception as e:
            self.log_error(f"No se pudieron cargar las especialidades del médico: {traducir_error_oracle(e)}")
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
            conn = obtener_conexion()
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
            self.log_error(f"No se pudieron cargar los médicos para guardias: {traducir_error_oracle(e)}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def accion_insertar_guardia(self):
        """Crea una guardia y la asigna directamente a un médico en una sola transacción."""
        fecha_str = self.guardia_fecha.get().strip()
        turno = self.guardia_turno.get().strip().upper()
        med_sel = self.cb_guardia_medico.get().strip()
        esp_sel = self.cb_guardia_especialidad.get().strip()

        if not (fecha_str and turno):
            messagebox.showwarning("Atención", "Fecha y turno son obligatorios.")
            return
        if not (med_sel and esp_sel):
            messagebox.showwarning(
                "Médico Obligatorio",
                "No puede existir una guardia sin un médico asignado. Selecciona un médico y una especialidad."
            )
            return

        try:
            matricula = self._parsear_clave_combo(med_sel)
            id_especialidad = int(self._parsear_clave_combo(esp_sel))
        except ValueError:
            messagebox.showerror("Dato Inválido", "La especialidad seleccionada no tiene un ID válido.")
            return

        fmt = 'YYYY-MM-DD' if '-' in fecha_str else 'DD/MM/YYYY'

        conn = None
        cursor = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            id_guardia_var = cursor.var(oracledb.NUMBER)

            cursor.execute(f"""
                INSERT INTO GUARDIA (turno, fecha)
                VALUES (:1, TO_DATE(:2, '{fmt}'))
                RETURNING id_guardia INTO :3
            """, [turno, fecha_str, id_guardia_var])
            nuevo_id = int(id_guardia_var.getvalue()[0])

            cursor.execute("""
                INSERT INTO CUBIERTA_POR (numero_de_matricula, id_especialidad, id_guardia)
                VALUES (:1, :2, :3)
            """, [matricula, id_especialidad, nuevo_id])

            conn.commit()
            msg = f"Guardia #{nuevo_id} ({turno} del {fecha_str}) creada y asignada a '{med_sel}'."
            self.log_exito(msg)
            messagebox.showinfo("Éxito", msg)
            self.refrescar_panel_guardias()

        except Exception as e:
            if conn:
                conn.rollback()
            self.log_error(f"Error al crear y asignar guardia (ROLLBACK aplicado):\n{traducir_error_oracle(e)}")
            messagebox.showerror("Error", traducir_error_oracle(e))
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
            conn = obtener_conexion()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT g.id_guardia,
                       TO_CHAR(g.fecha, 'DD/MM/YYYY'),
                       g.turno,
                       COALESCE(
                           (SELECT LISTAGG(p.apellido || ' (' || cp.numero_de_matricula || ' - ' || e.nombre || ')', ', ')
                                   WITHIN GROUP (ORDER BY p.apellido, e.nombre)
                            FROM CUBIERTA_POR cp
                            JOIN MEDICO m ON cp.numero_de_matricula = m.numero_de_matricula
                            JOIN PERSONA p ON m.numero_de_DNI = p.numero_de_DNI
                            JOIN ESPECIALIDAD e ON cp.id_especialidad = e.id_especialidad
                            WHERE cp.id_guardia = g.id_guardia),
                           'Sin asignar'
                       ) AS medicos_asignados
                FROM GUARDIA g
                ORDER BY g.fecha DESC, g.id_guardia DESC
            """)
            for row in cursor.fetchall():
                self.tabla_guardias.insert("", tk.END, values=row)
            cursor.close()
        except Exception as e:
            self.log_error(f"No se pudieron cargar las guardias: {traducir_error_oracle(e)}")
        finally:
            if conn:
                conn.close()

    def abrir_dialogo_modificar_guardia(self):
        """Abre un diálogo modal para editar una guardia y sus médicos (mínimo 1 obligatorio)."""
        seleccion = self.tabla_guardias.selection()
        if not seleccion:
            messagebox.showinfo("Seleccionar Guardia", "Por favor selecciona una guardia de la lista para modificar.")
            return

        valores = self.tabla_guardias.item(seleccion[0], "values")
        if not valores:
            return
        id_guardia = int(valores[0])

        conn = None
        cursor = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT TO_CHAR(fecha, 'DD/MM/YYYY'), turno
                FROM GUARDIA
                WHERE id_guardia = :1
            """, [id_guardia])
            row_g = cursor.fetchone()
            if not row_g:
                messagebox.showerror("No Encontrada", f"La guardia #{id_guardia} ya no existe en la base de datos.")
                self.refrescar_panel_guardias()
                return

            fecha_actual, turno_actual = row_g

            cursor.execute("""
                SELECT cp.numero_de_matricula, p.apellido, p.nombre, cp.id_especialidad, e.nombre
                FROM CUBIERTA_POR cp
                JOIN MEDICO m ON cp.numero_de_matricula = m.numero_de_matricula
                JOIN PERSONA p ON m.numero_de_DNI = p.numero_de_DNI
                JOIN ESPECIALIDAD e ON cp.id_especialidad = e.id_especialidad
                WHERE cp.id_guardia = :1
                ORDER BY p.apellido, e.nombre
            """, [id_guardia])
            asignaciones_actuales = cursor.fetchall()
            opciones_medicos = self._obtener_opciones_medicos(cursor)
        except Exception as e:
            self.log_error(f"Error al cargar guardia #{id_guardia}: {traducir_error_oracle(e)}")
            messagebox.showerror("Error", traducir_error_oracle(e))
            return
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        asignaciones_originales = {(r[0], r[3]) for r in asignaciones_actuales}
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
        modal.title(f"Modificar Guardia #{id_guardia}")
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
            if any(a["mat"] == nuevo["mat"] and a["id_esp"] == nuevo["id_esp"] for a in asignaciones):
                messagebox.showinfo("Ya Asignado", "Ese médico ya está asignado a la guardia con esa especialidad.", parent=modal)
                return
            asignaciones.append(nuevo)
            refrescar_tree_asig()

        def reemplazar_medico_lista():
            nuevo = obtener_par_seleccionado()
            if not nuevo:
                return
            sel = tree_asig.selection()
            if not sel:
                if len(asignaciones) == 1:
                    idx = 0
                else:
                    messagebox.showinfo("Seleccionar Fila", "Selecciona de la tabla el médico que deseas reemplazar.", parent=modal)
                    return
            else:
                idx = int(sel[0])

            if any(
                i != idx and a["mat"] == nuevo["mat"] and a["id_esp"] == nuevo["id_esp"]
                for i, a in enumerate(asignaciones)
            ):
                messagebox.showinfo("Duplicado", "Ese médico ya figura en otra fila con la misma especialidad.", parent=modal)
                return
            asignaciones[idx] = nuevo
            refrescar_tree_asig()

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

            fmt = 'YYYY-MM-DD' if '-' in fecha_nueva else 'DD/MM/YYYY'
            nuevo_set = {(a["mat"], a["id_esp"]) for a in asignaciones}
            a_eliminar = asignaciones_originales - nuevo_set
            a_insertar = nuevo_set - asignaciones_originales

            conn_save = None
            cur_save = None
            try:
                conn_save = obtener_conexion()
                cur_save = conn_save.cursor()

                cur_save.execute(f"""
                    UPDATE GUARDIA
                    SET fecha = TO_DATE(:1, '{fmt}'), turno = :2
                    WHERE id_guardia = :3
                """, [fecha_nueva, turno_nuevo, id_guardia])

                for mat_del, esp_del in a_eliminar:
                    cur_save.execute("""
                        DELETE FROM CUBIERTA_POR
                        WHERE id_guardia = :1 AND numero_de_matricula = :2 AND id_especialidad = :3
                    """, [id_guardia, mat_del, esp_del])

                for mat_ins, esp_ins in a_insertar:
                    cur_save.execute("""
                        INSERT INTO CUBIERTA_POR (numero_de_matricula, id_especialidad, id_guardia)
                        VALUES (:1, :2, :3)
                    """, [mat_ins, esp_ins, id_guardia])

                cur_save.execute("SELECT COUNT(*) FROM CUBIERTA_POR WHERE id_guardia = :1", [id_guardia])
                if cur_save.fetchone()[0] < 1:
                    raise Exception("Una guardia no puede quedar sin médicos asignados.")

                conn_save.commit()
                msg = f"Guardia #{id_guardia} modificada con éxito ({turno_nuevo} del {fecha_nueva})."
                self.log_exito(msg)
                messagebox.showinfo("Modificación Exitosa", msg, parent=modal)
                modal.destroy()
                self.refrescar_panel_guardias()
            except Exception as e:
                if conn_save:
                    conn_save.rollback()
                self.log_error(f"Error al modificar guardia #{id_guardia} (ROLLBACK aplicado):\n{traducir_error_oracle(e)}")
                messagebox.showerror("Error al Modificar Guardia", traducir_error_oracle(e), parent=modal)
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

        valores = self.tabla_guardias.item(seleccion[0], "values")
        if not valores or len(valores) < 4:
            return
        id_guardia, fecha, turno, medicos = int(valores[0]), valores[1], valores[2], valores[3]

        confirmar = messagebox.askyesno(
            "Confirmar Baja de Guardia",
            f"¿Deseas eliminar definitivamente la Guardia #{id_guardia}?\n\n"
            f"• Fecha: {fecha}\n"
            f"• Turno: {turno}\n"
            f"• Médicos asignados: {medicos}\n\n"
            "Esta acción dará de baja la guardia y sus asignaciones en CUBIERTA_POR."
        )
        if not confirmar:
            return

        conn = None
        cursor = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM GUARDIA WHERE id_guardia = :1", [id_guardia])
            if cursor.rowcount == 0:
                raise Exception(f"No se encontró la guardia #{id_guardia} en la base de datos.")
            conn.commit()

            msg = f"Guardia #{id_guardia} ({turno} del {fecha}) eliminada correctamente."
            self.log_exito(msg)
            messagebox.showinfo("Guardia Eliminada", msg)
            self.refrescar_panel_guardias()
        except Exception as e:
            if conn:
                conn.rollback()
            self.log_error(f"Error al eliminar guardia #{id_guardia}:\n{traducir_error_oracle(e)}")
            messagebox.showerror("Error al Eliminar Guardia", traducir_error_oracle(e))
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # ==========================================================================
    # TAB 3: CONSOLA SQL PARA EL PARCIAL
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
            ("Historial POSEE", "SELECT * FROM POSEE ORDER BY fechaHora DESC;")
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

    def accion_ejecutar_sql(self):
        sql = self.txt_sql.get("1.0", tk.END).strip()
        if not sql:
            return

        if sql.endswith(';'):
            sql = sql[:-1].strip()

        conn = None
        cursor = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()
            cursor.execute(sql)

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
                self.log_exito(f"Consulta SQL ejecutada: '{sql[:45]}...' -> {len(filas)} filas.")
            else:
                conn.commit()
                afectadas = cursor.rowcount
                self.tabla_sql["columns"] = ("Resultado",)
                self.tabla_sql.heading("Resultado", text="Estado de Ejecución")
                self.tabla_sql.column("Resultado", width=400)
                self.tabla_sql.insert("", tk.END, values=(f"Operación realizada exitosamente. Filas afectadas: {afectadas}",))
                self.lbl_filas_resultado.config(text=f"✅ Filas afectadas: {afectadas}")
                self.log_exito(f"Sentencia ejecutada: '{sql[:45]}...' (Filas afectadas: {afectadas})")

        except Exception as e:
            traduccion = traducir_error_oracle(e)
            self.log_error(f"Error al ejecutar SQL:\n{traduccion}")
            messagebox.showerror("Error al Ejecutar Consulta", traduccion)

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
        self._agregar_log(f"❌ {mensaje}", "ERROR")

# ==============================================================================
# PUNTO DE ENTRADA
# ==============================================================================
if __name__ == "__main__":
    app = HospitalApp()
    app.mainloop()
