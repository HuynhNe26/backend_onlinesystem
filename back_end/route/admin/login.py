from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from datetime import timedelta
import mysql.connector

login_bp = Blueprint('login', __name__)

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Anhkiet3307*",
        database="online_testing"
    )

@login_bp.route('', methods=['POST'])
def login_admin():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"msg": "Thiếu thông tin!"}), 400

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Kiểm tra user
        query = """
            SELECT id_user, username, password, fullName, role, level
            FROM users
            WHERE email = %s AND password = %s
        """
        cursor.execute(query, (email, password))
        user = cursor.fetchone()

        if not user:
            return jsonify({"msg": "Sai tài khoản hoặc mật khẩu!"}), 401

        level = int(user["level"])
        if level not in (2, 3):
            return jsonify({"msg": "Mày biến !!!"}), 403

        # Update login_time ngay khi login thành công
        update_login = """
            UPDATE users
            SET login_time = NOW()
            WHERE id_user = %s
        """
        cursor.execute(update_login, (user["id_user"],))
        db.commit()  # quan trọng: commit để DB update

        # Tạo token JWT
        access_token = create_access_token(
            identity=str(user["id_user"]),  # chỉ id_user
            additional_claims={"role": user["role"], "level": user["level"]}
        )

        return jsonify({
            "msg": "Đăng nhập thành công!",
            "token": access_token,
            "user": {
                "id": user["id_user"],
                "name": user["fullName"],
                "role": user["role"],
                "level": user["level"]
            }
        }), 200

    except Exception as e:
        print("Login error:", e)
        return jsonify({"msg": "Lỗi server"}), 500

    finally:
        cursor.close()
        db.close()
