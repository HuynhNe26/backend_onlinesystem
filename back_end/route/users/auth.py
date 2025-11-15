from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from werkzeug.security import generate_password_hash, check_password_hash
import re

from ...config.db_config import get_db_connection

users_bp = Blueprint('users_bp', __name__)


def get_current_user_id():
    identity = get_jwt_identity()

    if isinstance(identity, dict):
        return identity.get("id") or identity.get("id_user")

    try:
        return int(identity)
    except (ValueError, TypeError):
        return identity


def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password(password):
    if len(password) < 8:
        return False, "Mật khẩu phải có ít nhất 8 ký tự."
    if not re.search(r"[A-Z]", password):
        return False, "Mật khẩu phải chứa ít nhất một chữ cái viết hoa."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Mật khẩu phải chứa ít nhất một ký tự đặc biệt."
    return True, ""


def create_user(fullName, username, email, password, gender, avatar=None, birth_date=None):
    conn = None
    cursor = None

    try:
        if not validate_email(email):
            return False, "Định dạng email không hợp lệ."

        is_valid, error_msg = validate_password(password)
        if not is_valid:
            return False, error_msg

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT id_user FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return False, "Email đã được sử dụng."

        cursor.execute("SELECT id_user FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            return False, "Tên đăng nhập đã tồn tại."

        hashed_password = generate_password_hash(password)

        if not avatar:
            avatar = "src/assets/Avt/nam.png" if gender == "Nam" else "src/assets/Avt/nu.png"

        insert_query = """
            INSERT INTO users (fullName, username, email, password, gender, avatar, birth_date, 
                             role, status, level, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'user', 'active', 1, NOW(), NOW())
        """

        cursor.execute(insert_query, (
            fullName,
            username,
            email,
            hashed_password,
            gender,
            avatar,
            birth_date
        ))

        conn.commit()
        return True, "Đăng ký thành công!"

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error creating user: {str(e)}")
        return False, f"Đã xảy ra lỗi khi tạo tài khoản: {str(e)}"

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@users_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()

    # Validate required fields
    required_fields = ["fullName", "username", "email", "password", "gender"]
    missing_fields = [field for field in required_fields if field not in data or not data[field]]

    if missing_fields:
        return jsonify({
            "success": False,
            "message": f"Thiếu dữ liệu: {', '.join(missing_fields)}"
        }), 400

    success, message = create_user(
        data["fullName"],
        data["username"],
        data["email"],
        data["password"],
        data["gender"],
        data.get("avatar"),
        data.get("birth_date")
    )

    status_code = 201 if success else 400
    return jsonify({"success": success, "message": message}), status_code


@users_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data or "email" not in data or "password" not in data:
        return jsonify({
            "success": False,
            "message": "Thiếu email hoặc mật khẩu."
        }), 400

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE email = %s", (data["email"],))
        user = cursor.fetchone()

        if not user:
            return jsonify({
                "success": False,
                "message": "Email hoặc mật khẩu không đúng."
            }), 401

        if not check_password_hash(user['password'], data["password"]):
            return jsonify({
                "success": False,
                "message": "Email hoặc mật khẩu không đúng."
            }), 401

        if user.get('status') != 'active':
            return jsonify({
                "success": False,
                "message": "Tài khoản đã bị khóa. Vui lòng liên hệ quản trị viên."
            }), 403

        access_token = create_access_token(identity=str(user['id_user']))

        return jsonify({
            "success": True,
            "message": "Đăng nhập thành công!",
            "token": access_token,
            "user": {
                "id": user['id_user'],
                "id_user": user['id_user'],
                "fullName": user['fullName'],
                "username": user['username'],
                "email": user['email'],
                "role": user['role'],
                "status": user['status'],
                "gender": user['gender'],
                "level": user['level'],
                "avatar": user.get('avatar')
            }
        }), 200

    except Exception as e:
        print(f"Login error: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Đã xảy ra lỗi khi đăng nhập."
        }), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@users_bp.route('/update_package', methods=['POST'])
@jwt_required()
def update_package():
    user_id = get_current_user_id()
    data = request.get_json()
    package_id = data.get('package_id')

    if not package_id:
        return jsonify({"success": False, "message": "Thiếu package_id."}), 400

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE users
            SET package_id = %s, updated_at = NOW()
            WHERE id_user = %s
            """,
            (package_id, user_id)
        )
        conn.commit()

        return jsonify({
            "success": True,
            "message": "Cập nhật gói dịch vụ thành công!"
        }), 200

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Update package error: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Đã xảy ra lỗi khi cập nhật gói dịch vụ."
        }), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@users_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    user_id = get_current_user_id()

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE id_user = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({
                "success": False,
                "message": "Không tìm thấy người dùng."
            }), 404

        return jsonify({
            "success": True,
            "user": {
                "id": user['id_user'],
                "fullName": user['fullName'],
                "username": user['username'],
                "email": user['email'],
                "role": user['role'],
                "status": user['status'],
                "gender": user['gender'],
                "level": user['level'],
                "avatar": user.get('avatar'),
                "birth_date": user.get('birth_date').isoformat() if user.get('birth_date') else None,
                "package_id": user.get('package_id'),
                "package_expiry_date": user.get('package_expiry_date').isoformat() if user.get(
                    'package_expiry_date') else None
            }
        }), 200

    except Exception as e:
        print(f"Get profile error: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Đã xảy ra lỗi khi lấy thông tin người dùng."
        }), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()