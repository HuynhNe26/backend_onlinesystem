import mysql.connector
from mysql.connector import Error

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Huynh@2608",
            database="online_testing"
        )
        return conn
    except Error as e:
        print(f"Lỗi kết nối: {e}")
        return None

