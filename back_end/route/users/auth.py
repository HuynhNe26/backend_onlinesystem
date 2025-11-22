from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
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

@users_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    required_fields = ["fullName", "email", "password", "gender"]

    if not data or not all(field in data for field in required_fields):
        return jsonify({"success": False, "message": "Thiếu dữ liệu bắt buộc."}), 400

    fullName = data["fullName"].strip()
    email = data["email"].strip().lower()
    password = data["password"]
    gender = data["gender"]
    avatar = data.get("avatar")
    dateOfBirth = data.get("dateOfBirth")

    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not re.match(email_regex, email):
        return jsonify({"success": False, "message": "Email không hợp lệ."}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id_user FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return jsonify({"success": False, "message": "Email đã được sử dụng."}), 400

        hashed_password = generate_password_hash(password)

        cursor.execute(
            """
            INSERT INTO users 
            (fullName, email, password, gender, avatar, dateOfBirth, role, status, level, create_at)
            VALUES (%s, %s, %s, %s, %s, %s, 'user', 'active', 1, NOW())
            """,
            (fullName, email, hashed_password, gender, avatar, dateOfBirth)
        )
        conn.commit()

        return jsonify({"success": True, "message": "Đăng ký thành công!"}), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": "Lỗi hệ thống: " + str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@users_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or "email" not in data or "password" not in data:
        return jsonify({"success": False, "message": "Thiếu email hoặc mật khẩu."}), 400

    email = data["email"].strip().lower()
    password = data["password"]

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if not user or not check_password_hash(user['password'], password):
            return jsonify({"success": False, "message": "Email hoặc mật khẩu không đúng."}), 401

        access_token = create_access_token(identity=str(user['id_user']))
        login_time = datetime.now().isoformat()
        return jsonify({
            "success": True,
            "token": access_token,
            "login_time": login_time,
            "user": {
                "id_user": user['id_user'],
                "fullName": user['fullName'],
                "email": user['email'],
                "role": user['role'],
                "status": user['status'],
                "gender": user['gender'],
                "level": user['level'],
                "id_package": user.get('id_package'),
                "start_package": user.get('start_package').isoformat() if user.get('start_package') else None,
                "end_package": user.get('end_package').isoformat() if user.get('end_package') else None
            }
        }), 200

    except Exception as e:
        return jsonify({"success": False, "message": "Lỗi hệ thống: " + str(e)}), 500
    finally:
        cursor.close()
        conn.close()