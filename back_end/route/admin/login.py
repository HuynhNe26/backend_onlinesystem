from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from datetime import timedelta
from ...config.db_config import get_db_connection

login_bp = Blueprint('login', __name__)

@login_bp.route('/admin', methods=['POST'])
def login_admin():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"msg": "Thiếu thông tin!"}), 400

    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT id_user, fullName, role, level, password
            FROM users
            WHERE email = %s
        """, (email,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"msg": "Sai email hoặc mật khẩu!"}), 401

        if password != user["password"]:
            return jsonify({"msg": "Sai email hoặc mật khẩu!"}), 401

        if user["level"] not in (1):
            return jsonify({"msg": "Không có quyền truy cập!"}), 403

        cursor.execute(
            "UPDATE users SET login_time = NOW() WHERE id_user = %s",
            (user["id_user"],)
        )
        db.commit()

        access_token = create_access_token(
            identity=str(user["id_user"]),
            additional_claims={"role": user["role"], "level": user["level"]},
            expires_delta=timedelta(hours=3)
        )

        return jsonify({
            "msg": "Đăng nhập thành công!",
            "accessToken": access_token,
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
