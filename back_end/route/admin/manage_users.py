# src/back_end/routes/admin/manage_users.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from werkzeug.security import generate_password_hash
from ...config.db_config import get_db_connection

manage_users_bp = Blueprint('manage_users_bp', __name__)


def is_admin():
    """Kiểm tra quyền admin dựa trên JWT claims"""
    claims = get_jwt()
    return int(claims.get("level", 1)) >= 2  # chỉ admin level >=2


# ===== READ - Lấy danh sách user =====
@manage_users_bp.route('/all', methods=['GET'])
@jwt_required()
def list_users():
    if not is_admin():
        return jsonify({"msg": "Không có quyền"}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id_user, fullName, username, email, role, status, gender, level FROM users WHERE level=1 ORDER BY id_user DESC")
        users = cursor.fetchall()
        return jsonify({"data": users}), 200
    except Exception as e:
        print("List users error:", e)
        return jsonify({"msg": "Lỗi server"}), 500
    finally:
        cursor.close()
        conn.close()


# ===== UPDATE - Cập nhật user =====
@manage_users_bp.route('/update/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    if not is_admin():
        return jsonify({"msg": "Không có quyền"}), 403

    data = request.get_json() or {}
    fields, values = [], []

    if data.get("fullName"):
        fields.append("fullName=%s")
        values.append(data["fullName"])
    if data.get("email"):
        fields.append("email=%s")
        values.append(data["email"])
    if data.get("username"):
        fields.append("username=%s")
        values.append(data["username"])
    if data.get("password"):
        fields.append("password=%s")
        values.append(generate_password_hash(data["password"]))
    if data.get("role"):
        fields.append("role=%s")
        values.append(data["role"])
    if "status" in data:
        fields.append("status=%s")
        values.append(data["status"])

    if not fields:
        return jsonify({"msg": "Không có dữ liệu để cập nhật"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        sql = "UPDATE users SET " + ", ".join(fields) + " WHERE id_user=%s AND level=1"
        values.append(user_id)
        cursor.execute(sql, tuple(values))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"msg": "Không tìm thấy user"}), 404
        return jsonify({"msg": "Cập nhật thành công"}), 200
    except Exception as e:
        print("Update user error:", e)
        return jsonify({"msg": "Lỗi server"}), 500
    finally:
        cursor.close()
        conn.close()


# ===== DELETE - Xóa user =====
@manage_users_bp.route('/delete/<int:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    if not is_admin():
        return jsonify({"msg": "Không có quyền"}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id_user=%s AND level=1", (user_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"msg": "Không tìm thấy user hoặc không thể xóa"}), 404
        return jsonify({"msg": "Xóa thành công"}), 200
    except Exception as e:
        print("Delete user error:", e)
        return jsonify({"msg": "Lỗi server"}), 500
    finally:
        cursor.close()
        conn.close()
