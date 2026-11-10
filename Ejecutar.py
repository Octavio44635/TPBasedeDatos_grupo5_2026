import os
import oracledb
from dotenv import load_dotenv
# PONER EL NOMBRE DEL ARCHIVO .SQL COMO PARAMETRO DE LA FUNCION
load_dotenv(override=True)

def separar_sentencias_sql(contenido):
    """
    Separa sentencias SQL estándar (terminadas en ';') 
    y bloques PL/SQL como Triggers y Procedures (terminados en '/').
    """
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

        if not en_bloque_plsql and linea_strip.endswith(';'):
            buffer.append(linea[:linea.rfind(';')])
            stmt = '\n'.join(buffer).strip()
            if stmt:
                sentencias.append(stmt)
            buffer = []
            continue

        buffer.append(linea)

    if buffer:
        stmt = '\n'.join(buffer).strip().rstrip(';/')
        if stmt:
            sentencias.append(stmt)

    return sentencias


def ejecutar_script_sql(archivo_sql):

    # print(f"Conectando con Usuario='{os.getenv('DB_USER')}', Password='{os.getenv('DB_PASS')}', DSN='{os.getenv('DSN')}'")

    conn = oracledb.connect(
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASS'),
        dsn=os.getenv('DSN')
    )

    cursor = conn.cursor()

    with open(archivo_sql, 'r', encoding='utf-8') as f:
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