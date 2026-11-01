import oracledb
import os
from dotenv import load_dotenv
def conexion():

    load_dotenv(override=True)
    usuario = os.getenv('DB_USER')
    password = os.getenv('DB_PASS')
    dsn = os.getenv("DSN")

    try:
        conexion = oracledb.connect(user=usuario, password=password, dsn=dsn)
        print("Conexión establecida con éxito.")
    except oracledb.Error as error:
        print(f"Error al conectar: {error}")


def main():
    conexion()


main()



