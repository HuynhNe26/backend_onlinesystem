import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv("back_end/config/data.env")

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            database=os.getenv("DB_NAME"),
            port=int(os.getenv("DB_PORT", 3306)),
            unix_socket=None
        )
        print("✅ Kết nối MySQL thành công!")
        return conn
    except Error as e:
        print(f"❌ Lỗi kết nối MySQL: {e}")
        return None


if __name__ == "__main__":
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES;")
        print("Các bảng trong database:")
        for x in cursor.fetchall():
            print(x)
        conn.close()
