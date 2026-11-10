import os
import tempfile
import oracledb
from dotenv import load_dotenv
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
from datetime import datetime, date

# Cargar variables de entorno desde el archivo .env
load_dotenv(override=True)

def traducir_error_oracle(error, contexto=None):
    """
    obtenemos detalle de los errores de manera mas especifica para su entendimiento desde consola segun la restriccion violada
    """
    mensaje_original = str(error)
    mensaje_mayus = mensaje_original.upper()
    codigo_oracle = None

    if isinstance(error, oracledb.DatabaseError):
        try:
            error_obj, = error.args
            codigo_oracle = error_obj.code
            mensaje_original = error_obj.message
            mensaje_mayus = mensaje_original.upper()
        except Exception:
            pass

    #reglas check especificas
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
            "Explicación humana: Una cama en el hospital solo puede estar en estado 'Libre' u 'Ocupada'.\n"
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
            "Explicación humana: El turno asignado no es válido. Los turnos de ronda deben ser 1, 2, 3 o 4 (o Mañana, Tarde, Noche).\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "CHK_RONDA_DIA" in mensaje_mayus:
        return (
            "❌ DÍA DE LA SEMANA INVÁLIDO (Regla CHECK):\n"
            "Explicación humana: El día de la ronda debe ser un día válido (LUNES, MARTES, MIERCOLES, JUEVES, VIERNES, SABADO o DOMINGO).\n"
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
    if "CHK_PERSONA_ROL" in mensaje_mayus:
        return (
            "❌ ROL DE PERSONA INVÁLIDO (Regla CHECK):\n"
            "Explicación humana: El rol asignado a la persona no cumple con las opciones permitidas en la base de datos.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )

    #claves duplicadas (UNIQUE)
    if "PK_PERSONA" in mensaje_mayus:
        return (
            "❌ DNI DE PERSONA YA EXISTENTE (Dato Duplicado):\n"
            "Explicación humana: Ya existe una persona registrada en el hospital con ese mismo número de DNI. "
            "No se puede registrar dos veces a la misma persona.\n"
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
            "Explicación humana: Ya existe un médico registrado con esa misma matrícula profesional. "
            "Cada matrícula debe ser única.\n"
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
            "❌ DNI YA REGISTRADO COMO MÉDICO (Dato Duplicado):\n"
            "Explicación humana: Ya existe un médico en el sistema con ese número de DNI.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "PK_CAMA" in mensaje_mayus:
        return (
            "❌ CAMA YA EXISTENTE EN ESTA HABITACIÓN (Dato Duplicado):\n"
            "Explicación humana: Esa habitación ya tiene registrada una cama con ese mismo número. "
            "Elige otro número de cama o cárgala en una habitación diferente.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "UQ_SECTOR_NOMBRE" in mensaje_mayus:
        return (
            "❌ NOMBRE DE SECTOR REPETIDO (Dato Duplicado):\n"
            "Explicación humana: Ya existe un sector con ese mismo nombre en el hospital. "
            "Los nombres de los sectores no pueden repetirse.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "PK_COMPUESTA_POR" in mensaje_mayus:
        return (
            "❌ RONDA YA VINCULADA (Dato Duplicado):\n"
            "Explicación humana: Esta habitación ya tiene asignada esa ronda para ese día de la semana.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )

    #claves foraneas inexistentes
    if "FK_INTERNACION_PACIENTE" in mensaje_mayus:
        return (
            "❌ PACIENTE NO ENCONTRADO:\n"
            "Explicación humana: El DNI ingresado no corresponde a ningún paciente registrado. "
            "Primero debes registrar al paciente en la pestaña 'Carga de Datos' antes de poder internarlo.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "FK_INTERNACION_MEDICO" in mensaje_mayus:
        return (
            "❌ MÉDICO PRINCIPAL NO ENCONTRADO:\n"
            "Explicación humana: La matrícula médica ingresada no existe en la base de datos. "
            "Primero debes registrar al médico antes de asignarlo a una internación.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "FK_HABITACION_SECTOR" in mensaje_mayus:
        return (
            "❌ SECTOR NO ENCONTRADO:\n"
            "Explicación humana: El sector seleccionado no existe en la base de datos. "
            "Por favor crea el sector antes de asociarle una habitación.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )
    if "FK_CAMA_HABITACION" in mensaje_mayus:
        return (
            "❌ HABITACIÓN NO ENCONTRADA PARA ESTA CAMA:\n"
            "Explicación humana: El ID de habitación ingresado no existe en el hospital. "
            "Verifica el ID en la lista de habitaciones existentes.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )

    # campos obligatorios faltantes (NOT NULL)
    if codigo_oracle == 1400:
        columna_afectada = ""
        if '"NOMBRE"' in mensaje_mayus:
            columna_afectada = "el NOMBRE"
        elif '"APELLIDO"' in mensaje_mayus:
            columna_afectada = "el APELLIDO"
        elif '"CUIL"' in mensaje_mayus:
            columna_afectada = "el CUIL"
        elif '"FECHA"' in mensaje_mayus or '"FECHA_DE_NACIMIENTO"' in mensaje_mayus:
            columna_afectada = "la FECHA"
        elif '"PISO"' in mensaje_mayus:
            columna_afectada = "el PISO"
        else:
            columna_afectada = "uno de los campos obligatorios"

        return (
            f"❌ CAMPO REQUERIDO VACÍO (Restricción NOT NULL):\n"
            f"Explicación humana: Intentaste guardar un registro dejando en blanco {columna_afectada}. "
            "Por favor completa todos los campos del formulario.\n"
            f"[Detalle técnico: {mensaje_original}]"
        )

    #codigos especificos explicados
    traducciones_generales = {
        1: (
            "DATO DUPLICADO (Clave Única o Primaria)",
            "Ya existe un registro con ese identificador único (DNI, Matrícula, CUIL, etc.) en la base de datos."
        ),
        2291: (
            "DATO RELACIONADO NO ENCONTRADO (Foreign Key)",
            "Estás intentando asociar un dato a otra tabla que no existe previamente (ej: Paciente, Médico, Habitación o Sector no cargado)."
        ),
        2292: (
            "NO SE PUEDE ELIMINAR (Registros dependientes)",
            "No puedes borrar este registro porque tiene otros datos asociados en otras tablas del hospital."
        ),
        2290: (
            "REGLA DE VALIDACIÓN NO CUMPLIDA (Violación de CHECK)",
            "Uno de los valores ingresados no cumple con las restricciones permitidas por la base de datos."
        ),
        1400: (
            "CAMPO OBLIGATORIO VACÍO (NOT NULL)",
            "Intentaste guardar dejando en blanco un campo que es requerido obligatoriamente."
        ),
        942: (
            "TABLA NO ENCONTRADA",
            "La tabla especificada no existe en Oracle. Haz clic en 'Crear/Reiniciar Tablas' para inicializar la base de datos."
        ),
        904: (
            "COLUMNA NO VÁLIDA",
            "Escribiste un nombre de columna que no existe en la tabla consultada."
        ),
        933: (
            "ERROR DE SINTAXIS SQL",
            "La consulta SQL está mal redactada o tiene palabras clave fuera de lugar."
        ),
        936: (
            "FALTA UNA EXPRESIÓN EN EL SQL",
            "Falta especificar un valor, una columna o una condición en tu sentencia SQL."
        ),
        1438: (
            "NÚMERO DEMASIADO GRANDE",
            "El número ingresado supera los dígitos permitidos para esa columna (ej: un DNI con más de 8 dígitos o cama mayor a 9)."
        ),
        1843: (
            "FORMATO DE FECHA INCORRECTO",
            "El formato de fecha no es válido. Usa el formato estándar DD/MM/YYYY o YYYY-MM-DD."
        ),
        1017: (
            "ACCESO DENEGADO",
            "El usuario o contraseña configurado en el archivo .env es incorrecto."
        ),
        12541: (
            "BASE DE DATOS INALCANZABLE (Listener caído)",
            "El servicio de Oracle no responde en el puerto 1521. Verifica que el servicio de Oracle esté iniciado."
        ),
        54: (
            "RECURSO BLOQUEADO POR OTRA TRANSACCIÓN",
            "La fila seleccionada está siendo modificada por otra transacción activa en este momento."
        )
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

# CONEXIÓN A LA BASE DE DATOS
def obtener_conexion():
    return oracledb.connect(
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASS'),
        dsn=os.getenv('DSN')
    )

# APLICACIÓN PRINCIPAL (GUI CON TKINTER)
class HospitalApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sistema Hospitalario - Gestión de Internaciones y Consultas SQL (UNMDP)")
        self.geometry("1180x820")
        self.minsize(980, 650)

        # Configuración de estilos visuales
        self.configurar_estilos()

        # 1. Cabecera superior fija
        self.crear_cabecera()

        # 2. Panel divisor móvil (PanedWindow) para permitir agrandar/achicar logs
        self.paned_principal = ttk.PanedWindow(self, orient=tk.VERTICAL)
        self.paned_principal.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

        # Marco superior: Pestañas de la aplicación
        self.frame_superior = ttk.Frame(self.paned_principal)
        self.paned_principal.add(self.frame_superior, weight=4)

        # Marco inferior: Logs móviles (redimensionables arrastrando la barra)
        self.frame_inferior = ttk.Frame(self.paned_principal)
        self.paned_principal.add(self.frame_inferior, weight=1)

        # 3. Construir panel de logs primero (para capturar cualquier evento de inicio)
        self.crear_panel_logs(self.frame_inferior)

        # 4. Construir pestañas dentro del marco superior
        self.crear_pestanas(self.frame_superior)

        self.log_info(f"Sistema iniciado correctamente. Conectado a Oracle como usuario: '{os.getenv('DB_USER')}'.")
        self.cargar_camas_libres()

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

    # --------------------------------------------------------------------------
    # CABECERA SUPERIOR
    # --------------------------------------------------------------------------
    def crear_cabecera(self):
        frame_cabecera = ttk.Frame(self, padding="12 8")
        frame_cabecera.pack(fill=tk.X)

        frame_textos = ttk.Frame(frame_cabecera)
        frame_textos.pack(side=tk.LEFT, fill=tk.Y)

        lbl_titulo = ttk.Label(frame_textos, text="🏥 Sistema de Gestión Hospitalaria", style="Header.TLabel")
        lbl_titulo.pack(anchor="w")

        lbl_subtitulo = ttk.Label(
            frame_textos, 
            text="Diseño de Bases de Datos - Universidad Nacional de Mar del Plata", 
            style="SubHeader.TLabel"
        )
        lbl_subtitulo.pack(anchor="w")

        btn_init_db = tk.Button(
            frame_cabecera,
            text="🛠️ Crear/Reiniciar Tablas",
            bg="#DD6B20",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="groove",
            cursor="hand2",
            command=self.accion_ejecutar_script_tablas
        )
        btn_init_db.pack(side=tk.RIGHT, padx=5, pady=5)

    def accion_ejecutar_script_tablas(self):
        archivo = "create-table.sql"
        if not os.path.exists(archivo):
            self.log_error(f"No se encontró el archivo '{archivo}' en la carpeta del proyecto.")
            messagebox.showerror("Archivo no encontrado", f"No se encontró '{archivo}'.")
            return

        respuesta = messagebox.askyesno(
            "Confirmar Inicialización", 
            "¿Deseas ejecutar 'create-table.sql'?\nEsto borrará (DROP) y volverá a crear todas las tablas en Oracle."
        )
        if not respuesta:
            return

        conn = None
        cursor = None
        try:
            self.log_info(f"Ejecutando script de tablas '{archivo}' en Oracle...")
            conn = obtener_conexion()
            cursor = conn.cursor()

            with open(archivo, "r", encoding="utf-8") as f:
                contenido = f.read()

            sentencias = contenido.split(";")
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
                        if error_obj.code == 942:  # ORA-00942: tabla no existe en el DROP
                            pass
                        else:
                            errores += 1
                            self.log_error(f"Error en sentencia: {sql[:35]}... -> {traducir_error_oracle(e)}")

            conn.commit()
            msg = f"Script finalizado. Sentencias exitosas: {exitos} (Sentencias con error no crítico: {errores})."
            self.log_exito(msg)
            messagebox.showinfo("Tablas Inicializadas", msg)
            self.cargar_camas_libres()

        except Exception as e:
            self.log_error(f"Error crítico al ejecutar script de tablas:\n{traducir_error_oracle(e)}")
            messagebox.showerror("Error", traducir_error_oracle(e))
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # --------------------------------------------------------------------------
    # PESTAÑAS PRINCIPALES
    # --------------------------------------------------------------------------
    def crear_pestanas(self, contenedor):
        self.notebook = ttk.Notebook(contenedor)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Operación Transaccional
        self.tab_transaccion = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_transaccion, text=" 🔄 Internación")
        self.construir_tab_transaccion()

        # Tab 2: Altas de Datos (Pacientes, Médicos, Habitaciones, Camas)
        self.tab_altas = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_altas, text=" ➕ Carga de Datos (Pacientes, Médicos, Camas) ")
        self.construir_tab_altas()

        # Tab 3: Consola SQL para el Parcial
        self.tab_sql = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_sql, text=" 💻 Consola SQL en Vivo")
        self.construir_tab_sql()

    # ==========================================================================
    # TAB 1: OPERACIÓN TRANSACCIONAL DE INTERNACIÓN
    # ==========================================================================
    def construir_tab_transaccion(self):
        frame_izq = ttk.LabelFrame(self.tab_transaccion, text=" Registrar Internación con Cama ", padding=12)
        frame_izq.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10))

        ttk.Label(frame_izq, text="DNI del Paciente:").grid(row=0, column=0, sticky="w", pady=4)
        self.txt_dni = ttk.Entry(frame_izq, width=22)
        self.txt_dni.grid(row=0, column=1, pady=4)

        ttk.Label(frame_izq, text="Matrícula del Médico:").grid(row=1, column=0, sticky="w", pady=4)
        self.txt_matricula = ttk.Entry(frame_izq, width=22)
        self.txt_matricula.grid(row=1, column=1, pady=4)

        ttk.Label(frame_izq, text="ID de Habitación:").grid(row=2, column=0, sticky="w", pady=4)
        self.txt_hab = ttk.Entry(frame_izq, width=22)
        self.txt_hab.grid(row=2, column=1, pady=4)

        ttk.Label(frame_izq, text="Número de Cama:").grid(row=3, column=0, sticky="w", pady=4)
        self.txt_cama = ttk.Entry(frame_izq, width=22)
        self.txt_cama.grid(row=3, column=1, pady=4)

        btn_ejecutar = tk.Button(
            frame_izq, 
            text="Ejecutar Transacción", 
            bg="#2B6CB0", 
            fg="white", 
            font=("Segoe UI", 10, "bold"),
            relief="groove",
            cursor="hand2",
            command=self.accion_registrar_internacion
        )
        btn_ejecutar.grid(row=4, column=0, columnspan=2, pady=12, sticky="ew")

        
        # Panel derecho: Camas libres (Resumen por Sector + Detalle)
        frame_der = ttk.Frame(self.tab_transaccion)
        frame_der.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 1. Resumen: Cantidad de camas libres por sector (Requerimiento del TP)
        frame_resumen = ttk.LabelFrame(frame_der, text=" 📊 Cantidad de Camas Disponibles por Sector ", padding=6)
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

        btn_refrescar_camas = tk.Button(
            frame_der, text="🔄 Actualizar Camas y Resumen", bg="#E2E8F0", cursor="hand2", command=self.cargar_camas_libres
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
            #USO DE TRANSACCIONES: INTERNACION 
            self.log_info(f"Iniciando transacción: Asignando Paciente DNI={dni} a Hab={hab}, Cama={cama}...")
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
            if fila_cama[0] != 'Libre':
                raise Exception(f"La cama {cama} de la habitación {hab} no está disponible (Estado actual: '{fila_cama[0]}').")

            # 2. Inserción de la Internación
            id_internacion_var = cursor.var(oracledb.NUMBER)
            cursor.execute("""
                INSERT INTO INTERNACION (fecha_inicio, numero_de_DNI, numero_de_matricula)
                VALUES (TRUNC(SYSDATE), :1, :2)
                RETURNING id_internacion INTO :3
            """, [dni, matricula, id_internacion_var])
            
            id_internacion = int(id_internacion_var.getvalue()[0])

            # 3. Ocupar la cama
            cursor.execute("""
                UPDATE CAMA 
                SET estado = 'Ocupada' 
                WHERE id_habitacion = :1 AND nro_cama = :2
            """, [hab, cama])

            # 4. Insertar en POSEE
            cursor.execute("""
                INSERT INTO POSEE (id_internacion, id_habitacion, nro_cama, fechaHora)
                VALUES (:1, :2, :3, SYSTIMESTAMP)
            """, [id_internacion, hab, cama])

            # Confirmar transacción
            conn.commit()
            mensaje_exito = f"Transacción confirmada (COMMIT): Internación #{id_internacion} creada con éxito. Cama {cama} de Hab {hab} quedó OCUPADA."
            self.log_exito(mensaje_exito)
            messagebox.showinfo("Transacción Exitosa", mensaje_exito)

            self.txt_dni.delete(0, tk.END)
            self.txt_matricula.delete(0, tk.END)
            self.txt_hab.delete(0, tk.END)
            self.txt_cama.delete(0, tk.END)
            self.cargar_camas_libres()

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

            # 1. Consulta agrupada: Cantidad de camas disponibles por sector
            cursor.execute("""
                SELECT s.nombre AS sector, COUNT(c.nro_cama) AS disponibles
                FROM SECTOR s
                LEFT JOIN HABITACION h ON s.id_sector = h.id_sector
                LEFT JOIN CAMA c ON h.id_habitacion = c.id_habitacion AND c.estado = 'Libre'
                GROUP BY s.nombre
                ORDER BY s.nombre
            """)
            filas_resumen = cursor.fetchall()
            if hasattr(self, 'tabla_resumen_camas'):
                for r in filas_resumen:
                    self.tabla_resumen_camas.insert("", tk.END, values=(r[0], f"{r[1]} libre(s)"))

            # 2. Consulta detallada: Cama por cama
            cursor.execute("""
                SELECT s.nombre AS sector, h.id_habitacion, h.piso, c.nro_cama, c.estado
                FROM CAMA c
                JOIN HABITACION h ON c.id_habitacion = h.id_habitacion
                JOIN SECTOR s ON h.id_sector = s.id_sector
                WHERE c.estado = 'Libre'
                ORDER BY s.nombre, h.id_habitacion, c.nro_cama
            """)
            filas_detalle = cursor.fetchall()
            if hasattr(self, 'tabla_camas'):
                for f in filas_detalle:
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

    # ==========================================================================
    # TAB 2: SECCIONES DE ALTAS (PACIENTES, MÉDICOS, HABITACIONES, CAMAS)
    # ==========================================================================
    def construir_tab_altas(self):
        notebook_altas = ttk.Notebook(self.tab_altas)
        notebook_altas.pack(fill=tk.BOTH, expand=True)

        # Sub-pestaña 1: Paciente
        tab_pac = ttk.Frame(notebook_altas, padding=12)
        notebook_altas.add(tab_pac, text=" 👤 Pacientes ")
        self.construir_subtab_paciente(tab_pac)

        # Sub-pestaña 2: Médico
        tab_med = ttk.Frame(notebook_altas, padding=12)
        notebook_altas.add(tab_med, text=" 🩺 Médicos ")
        self.construir_subtab_medico(tab_med)

        # Sub-pestaña 3: Sector
        tab_sec = ttk.Frame(notebook_altas, padding=12)
        notebook_altas.add(tab_sec, text=" 🏢 Sectores ")
        self.construir_subtab_sector(tab_sec)

        # Sub-pestaña 4: Habitación
        tab_hab = ttk.Frame(notebook_altas, padding=12)
        notebook_altas.add(tab_hab, text=" 🚪 Habitaciones ")
        self.construir_subtab_habitacion(tab_hab)

        # Sub-pestaña 5: Cama
        tab_cama = ttk.Frame(notebook_altas, padding=12)
        notebook_altas.add(tab_cama, text=" 🛏️ Camas ")
        self.construir_subtab_cama(tab_cama)

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

        # Lista de pacientes
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
            # 1. Insert en PERSONA (rol PACIENTE)
            cursor.execute("""
                INSERT INTO PERSONA (numero_de_DNI, nombre, apellido, rol)
                VALUES (:1, :2, :3, 'PACIENTE')
            """, [dni, nom, ape])

            # 2. Insert en PACIENTE (sin hora, solo fecha)
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

            # Guardar en archivo temporal y abrir en Windows
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

            # 1. Verificar o insertar PERSONA
            cursor.execute("SELECT numero_de_DNI FROM PERSONA WHERE numero_de_DNI = :1", [dni])
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO PERSONA (numero_de_DNI, nombre, apellido, rol)
                    VALUES (:1, :2, :3, 'PACIENTE')
                """, [dni, nom, ape])

            # Leer bytes de la foto si fue seleccionada (tipo BLOB en Oracle)
            foto_bytes = None
            if self.med_ruta_foto and os.path.exists(self.med_ruta_foto):
                with open(self.med_ruta_foto, "rb") as f:
                    foto_bytes = f.read()

            # 2. Insertar en MEDICO (con foto BLOB)
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

    # --------------------------------------------------------------------------
    # SUBTAB SECTOR
    # --------------------------------------------------------------------------
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

            # 1. Actualizar el combobox desplegable de la pestaña Habitación
            valores_sectores = [f"{s[0]} - {s[1]}" for s in sectores]
            if hasattr(self, 'hab_sector_cb'):
                sel_actual = self.hab_sector_cb.get()
                self.hab_sector_cb["values"] = valores_sectores
                if sel_actual in valores_sectores:
                    self.hab_sector_cb.set(sel_actual)
                elif valores_sectores:
                    self.hab_sector_cb.current(0)

            # 2. Actualizar la tabla de sectores si está inicializada
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
        self.hab_orientacion = ttk.Combobox(frame_form, values=["Norte", "Sur", "Este", "Oeste"], state="readonly", width=18)
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

        # Marco para la asignación de rondas de los 7 días de la semana
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
            self.log_info(f"Iniciando creación de Habitación (Piso {piso}, {ori}) y asignación de rondas para los 7 días...")
            conn = obtener_conexion()
            cursor = conn.cursor()

            # Asegurar que el CHECK constraint en RONDA permita turnos 1, 2, 3, 4
            try:
                cursor.execute("ALTER TABLE RONDA DROP CONSTRAINT chk_ronda_turno")
                cursor.execute("ALTER TABLE RONDA ADD CONSTRAINT chk_ronda_turno CHECK (turno IN ('1', '2', '3', '4', 'MAÑANA', 'TARDE', 'NOCHE'))")
            except Exception:
                pass

            # 1. Insertar Habitación y obtener su ID
            id_hab_var = cursor.var(oracledb.NUMBER)
            cursor.execute("""
                INSERT INTO HABITACION (piso, orientacion, id_sector)
                VALUES (:1, :2, :3)
                RETURNING id_habitacion INTO :4
            """, [piso, ori, id_sector, id_hab_var])
            nueva_hab = int(id_hab_var.getvalue()[0])

            # 2. Asignar la ronda de cada uno de los 7 días (en COMPUESTA_POR)
            rondas_asignadas = []
            for dia_cod, _ in self.dias_semana:
                turno_seleccionado = self.cb_turnos_dias[dia_cod].get()  # ej: "Turno 1"
                nro_turno = turno_seleccionado.replace("Turno", "").strip() # ej: "1"

                # Buscar si ya existe una RONDA para ese día y turno
                cursor.execute("""
                    SELECT id_ronda FROM RONDA 
                    WHERE dia_semana = :1 AND turno = :2
                """, [dia_cod, nro_turno])
                fila_ronda = cursor.fetchone()

                if fila_ronda:
                    id_ronda = fila_ronda[0]
                else:
                    # Si no existe, crear la ronda
                    id_ronda_var = cursor.var(oracledb.NUMBER)
                    cursor.execute("""
                        INSERT INTO RONDA (dia_semana, turno)
                        VALUES (:1, :2)
                        RETURNING id_ronda INTO :3
                    """, [dia_cod, nro_turno, id_ronda_var])
                    id_ronda = int(id_ronda_var.getvalue()[0])

                # Asociar la habitación a la ronda en COMPUESTA_POR
                cursor.execute("""
                    INSERT INTO COMPUESTA_POR (id_ronda, id_habitacion)
                    VALUES (:1, :2)
                """, [id_ronda, nueva_hab])
                rondas_asignadas.append(f"{dia_cod}: Turno {nro_turno}")

            # Confirmar transacción atómica completa
            conn.commit()
            msg_exito = f"Habitación #{nueva_hab} creada y asociada a las rondas de los 7 días con éxito (COMMIT)."
            self.log_exito(msg_exito)
            self.log_info(f"Rondas asignadas a Habitación #{nueva_hab}: {', '.join(rondas_asignadas)}")
            messagebox.showinfo("Éxito", msg_exito)
            self.cargar_lista_habitaciones()

        except Exception as e:
            if conn:
                conn.rollback()
            self.log_error(f"Error al crear habitación y rondas (ROLLBACK ejecutado):\n{traducir_error_oracle(e)}")
            messagebox.showerror("Error en Creación", traducir_error_oracle(e))
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def cargar_lista_habitaciones(self):
        # Actualizar siempre el combobox de sectores con lo que exista en la BD
        self.actualizar_todos_los_sectores()

        for item in self.tabla_habitaciones.get_children():
            self.tabla_habitaciones.delete(item)
        conn = None
        try:
            conn = obtener_conexion()
            cursor = conn.cursor()

            # Cargar habitaciones junto con la cantidad de rondas asignadas
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
        self.cama_estado = ttk.Combobox(frame_form, values=["Libre", "Ocupada"], state="readonly", width=20)
        self.cama_estado.set("Libre")
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
        estado = self.cama_estado.get().strip()

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
            ("Ver Pacientes", "SELECT * FROM PACIENTE;"),
            ("Ver Médicos", "SELECT * FROM MEDICO;"),
            ("Camas por Sector", "SELECT s.nombre AS sector, COUNT(c.nro_cama) AS camas_libres FROM SECTOR s LEFT JOIN HABITACION h ON s.id_sector = h.id_sector LEFT JOIN CAMA c ON h.id_habitacion = c.id_habitacion AND c.estado = 'Libre' GROUP BY s.nombre ORDER BY camas_libres DESC;"),
            ("Ver Camas Libres", "SELECT s.nombre, h.id_habitacion, h.piso, c.nro_cama FROM CAMA c JOIN HABITACION h ON c.id_habitacion = h.id_habitacion JOIN SECTOR s ON h.id_sector = s.id_sector WHERE c.estado = 'Libre';"),
            ("Ver Habitaciones", "SELECT * FROM HABITACION;"),
            ("Ver Internaciones", "SELECT * FROM INTERNACION ORDER BY id_internacion DESC;"),
            ("Ver Historial POSEE", "SELECT * FROM POSEE ORDER BY fechaHora DESC;")
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
                # Quitar guiones bajos de los títulos de columna
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
                            # Si es fecha (como nacimiento) o no tiene hora, mostrar solo la fecha sin hora
                            if hasattr(v, 'hour') and (v.hour != 0 or v.minute != 0 or v.second != 0):
                                texto = v.strftime("%d/%m/%Y %H:%M:%S")
                            else:
                                texto = v.strftime("%d/%m/%Y")
                        else:
                            texto = str(v)
                        valores.append(texto)
                    self.tabla_sql.insert("", tk.END, values=valores)

                self.lbl_filas_resultado.config(text=f"✅ {len(filas)} fila(s) retornada(s).")
                self.log_exito(f"Consulta SQL ejecutada: '{sql[:45]}...' -> {len(filas)} filas retornadas.")
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
    # PANEL INFERIOR MÓVIL (PANEDWINDOW) Y LOGS SIMULTÁNEOS CONSOLA + UI
    # ==========================================================================
    def crear_panel_logs(self, contenedor):
        frame_logs = ttk.LabelFrame(contenedor, text=" 📋 Registro de Eventos y Errores ", padding=6)
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

        # 1. IMPRIMIR SIEMPRE EN LA CONSOLA / TERMINAL
        print(linea_completa)

        # 2. INSERTAR EN EL VISOR VISUAL (SI YA FUE INICIALIZADO)
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
