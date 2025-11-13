import os
import mysql.connector
from mysql.connector import Error

def get_db_connection():
    try:
        if os.environ.get('RENDER') == "true":
            # MySQL trên Render
            conn = mysql.connector.connect(
                host=os.getenv("DB_HOST"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASS"),
                database=os.getenv("DB_NAME"),
                port=os.getenv("DB_PORT", 3306)  # mặc định port 3306
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
