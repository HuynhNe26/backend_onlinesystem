from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required

from ...config.db_config import get_db_connection
from ...models.users.user_model import create_user, login_user

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
    required_fields = ["fullName", "username", "email", "password", "gender"]
    if not all(field in data for field in required_fields):
        return jsonify({"success": False, "message": "Thiếu dữ liệu."}), 400

    success, message = create_user(
        data["fullName"],
        data["username"],
        data["email"],
        data["password"],
        data["gender"],
        data.get("avatar"),
        data.get("birth_date")
    )
    return jsonify({"success": success, "message": message}), 200 if success else 400


@users_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or "email" not in data or "password" not in data:
        return jsonify({"success": False, "message": "Thiếu email hoặc mật khẩu."}), 400

    success, result = login_user(data["email"], data["password"])
    if not success:
        return jsonify({"success": False, "message": result}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (data["email"],))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        return jsonify({"success": False, "message": "Không tìm thấy người dùng."}), 404

    access_token = create_access_token(identity=str(user['id_user']))

    return jsonify({
        "success": True,
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
            "level": user['level']
        }
    }), 200


@users_bp.route('/update_package', methods=['POST'])
@jwt_required()
def update_package():
    user_id = get_current_user_id()
    data = request.get_json()
    package_id = data.get('package_id')

    if not package_id:
        return jsonify({"success": False, "message": "Thiếu package_id."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE users
            SET package_id = %s, updated_at = NOW()
            WHERE id_user = %s
            """,
            (package_id, user_id)
        )
        conn.commit()
        return jsonify({"success": True, "message": "Cập nhật gói dịch vụ thành công!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@users_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    user_id = get_current_user_id()

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM users WHERE id_user = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"success": False, "message": "Không tìm thấy người dùng."}), 404

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
                "package_id": user.get('package_id'),
                "package_expiry_date": user.get('package_expiry_date').isoformat() if user.get(
                    'package_expiry_date') else None
            }
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

