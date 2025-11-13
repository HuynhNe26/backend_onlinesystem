import os
import mysql.connector
from mysql.connector import Error

def get_db_connection():
    try:
        if os.environ.get('RENDER') == "true":
            # MySQL trên Render
            conn = mysql.connector.connect(
                host=os.environ("DB_HOST"),
                user=os.environ("DB_USER"),
                password=os.environ("DB_PASS"),
                database=os.environ("DB_NAME"),
                port=os.environ("DB_PORT", 3306)  # mặc định port 3306
            )
        else:
            # Local MySQL
            conn = mysql.connector.connect(
                host="localhost",
                user="root",
                password="Huynh@2608",
                database="online_testing"
            )
        return conn
    except Error as e:
        print(f"Lỗi kết nối MySQL: {e}")
        return None
