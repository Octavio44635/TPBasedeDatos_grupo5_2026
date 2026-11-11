import os
import re
import oracledb
from dotenv import load_dotenv

DIRECTORIO_APP = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(DIRECTORIO_APP, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)

def limpiar_sql_fragmento(texto):
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

def separar_sentencias_sql(contenido):
    """
    Separa sentencias SQL estándar (terminadas en ';') 
    y bloques PL/SQL como Triggers y Procedures (terminados en '/').
    """
    contenido = re.sub(r'/\*.*?\*/', '', contenido, flags=re.DOTALL)
    sentencias = []
    buffer = []
    en_bloque_plsql = False

    for linea in contenido.splitlines():
        linea_strip = linea.strip()
        if not buffer and (not linea_strip or linea_strip.startswith('--')):
            continue

        palabras = linea_strip.upper().split()
        if not en_bloque_plsql and palabras:
            if palabras[0] in ('DECLARE', 'BEGIN') or (
                len(palabras) >= 2 and palabras[0] == 'CREATE' and any(kw in palabras for kw in ('TRIGGER', 'PROCEDURE', 'FUNCTION', 'PACKAGE'))
            ):
                en_bloque_plsql = True

        if en_bloque_plsql and linea_strip == '/':
            stmt = '\n'.join(buffer).strip()
            if stmt:
                sentencias.append(stmt)
            buffer = []
            en_bloque_plsql = False
            continue

        if not en_bloque_plsql and ';' in linea:
            buffer.append(linea)
            texto = '\n'.join(buffer)
            partes = texto.split(';')
            for p in partes[:-1]:
                p_limpio = limpiar_sql_fragmento(p)
                if p_limpio:
                    sentencias.append(p_limpio)
            resto = partes[-1].strip()
            buffer = [resto] if resto else []
            continue

        buffer.append(linea)

    if buffer:
        stmt = '\n'.join(buffer).strip().rstrip(';/')
        if stmt:
            p_limpio = limpiar_sql_fragmento(stmt)
            if p_limpio:
                sentencias.append(p_limpio)

    return sentencias


def ejecutar_script_sql(archivo_sql):
    ruta = archivo_sql
    if not os.path.isabs(ruta):
        ruta_en_dir = os.path.join(DIRECTORIO_APP, archivo_sql)
        if os.path.exists(ruta_en_dir):
            ruta = ruta_en_dir

    conn = oracledb.connect(
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASS'),
        dsn=os.getenv('DSN')
    )

    cursor = conn.cursor()

    try:
        cursor.execute("ALTER SESSION SET ddl_lock_timeout = 10")
    except Exception:
        pass

    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()

    sentencias = separar_sentencias_sql(contenido)

    for sql in sentencias:
        sql = sql.strip()
        if sql:  # Evitar ejecutar bloques vacíos
            try:
                cursor.execute(sql)
            except oracledb.DatabaseError as e:
                # Opcional: ignorar error ORA-00942 (tabla no existe al hacer DROP)
                error_obj, = e.args
                if error_obj.code == 942:
                    pass
                else:
                    print(f"Error en: {sql[:40]}... -> {e}")

    conn.commit()
    cursor.close()
    conn.close()
    print("Script ejecutado exitosamente!")

if __name__ == "__main__":

    ejecutar_script_sql("create-table.sql")