from kivy.storage.jsonstore import JsonStore
from ...config.db_config import get_db_connection
from mysql.connector import Error

def get_all_package():
    conn = get_db_connection()
    if not conn:
        return "Lỗi kết nối server!"

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM package")
        data = cursor.fetchall()
        return data
    except Error as e:
        print(f"Error fetching packages: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def set_package(pkg):
    try:
        store = JsonStore('user.json')
        store.put('package', **pkg)
    except Exception as e:
        print(f"Error setting package: {e}")

def get_package():
    try:
        store = JsonStore('user.json')
        package = store.get('package') if store.exists('package') else None
        return package
    except Exception as e:
        print(f"Error retrieving package: {e}")
        return None

def clear_package():
    try:
        store = JsonStore('user.json')
        if store.exists('package'):
            store.delete('package')
    except Exception as e:
        print(f"Error clearing package: {e}")