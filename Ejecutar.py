import os
import oracledb
from dotenv import load_dotenv
# PONER EL NOMBRE DEL ARCHIVO .SQL COMO PARAMETRO DE LA FUNCION
load_dotenv(override=True)

def ejecutar_script_sql(archivo_sql):

    print(f"Conectando con Usuario='{os.getenv('DB_USER')}', Password='{os.getenv('DB_PASS')}', DSN='{os.getenv('DSN')}'")

    conn = oracledb.connect(
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASS'),
        dsn=os.getenv('DSN')
    )

    cursor = conn.cursor()

    with open(archivo_sql, 'r', encoding='utf-8') as f:
        contenido = f.read()

    # Separar sentencias por punto y coma ';'
    sentencias = contenido.split(';')

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

    ejecutar_script_sql("CreateTablas_withDrop.sql")