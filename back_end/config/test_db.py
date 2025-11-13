from ..config.db_config import get_db_connection

conn = get_db_connection()
if conn:
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES;")
    print("Các bảng trong database:")
    for x in cursor.fetchall():
        print(x)
    conn.close()
