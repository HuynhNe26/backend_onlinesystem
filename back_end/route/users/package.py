from ...config.db_config import get_db_connection

def get_all_package():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM package")
    data = cursor.fetchall()

    cursor.close()
    conn.close()
    return data
