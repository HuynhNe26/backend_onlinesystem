from ...config.db_config import get_db_connection
import bcrypt
from mysql.connector import Error

def create_user(full_name, username, email, password, gender, avatar=None, birth_date=None):
    conn = get_db_connection()
    if not conn:
        return False, "Không thể kết nối đến cơ sở dữ liệu."

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s OR email=%s", (username, email))
        if cursor.fetchone():
            return False, "Tên đăng nhập hoặc email đã tồn tại!"

        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        query = """
            INSERT INTO users (fullName, username, email, password, role, status, gender, level, dateOfBirth, avatar, id_package)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            full_name,
            username,
            email,
            hashed_pw,
            'học sinh',
            'Đang hoạt động',
            gender,
            1,
            birth_date,
            avatar,
            1
        ))
        conn.commit()
        return True, "Đăng ký thành công!"
    except Error as e:
        return False, f"Lỗi CSDL: {e}"
    finally:
        cursor.close()
        conn.close()

def login_user(email, password):
    conn = get_db_connection()
    if not conn:
        return False, "Không thể kết nối đến cơ sở dữ liệu."

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s AND level = 1", (email,))
        user = cursor.fetchone()

        if not user:
            return False, "Email không tồn tại."

        if not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            return False, "Sai mật khẩu."

        return True, {
            "id": user['id_user'],
            "fullName": user['fullName'],
            "username": user['username'],
            "email": user['email'],
            "role": user['role'],
            "status": user['status'],
            "gender": user['gender'],
            "level": user['level']
        }
    except Exception as e:
        return False, str(e)
    finally:
        cursor.close()
        conn.close()

def get_user():
    try:
        store = JsonStore('user.json')
        user = store.get('user') if store.exists('user') else None
        return user
    except Exception as e:
        print(f"Error retrieving user: {e}")
        return None