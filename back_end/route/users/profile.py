from flask import Blueprint, request, jsonify
from back_end.config.db_config import get_db_connection
import traceback
import hashlib
profile_bp = Blueprint("profile_bp", __name__)

def _close(cursor, db):
    if cursor: cursor.close()
    if db: db.close()

# =================== Xem thông tin cá nhân ===================
@profile_bp.route("/users/<int:id_user>", methods=["GET"])
def get_user(id_user):
    db = cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id_user, fullName, dateOfBirth, email, role, status, gender, avatar, level FROM users WHERE id_user=%s", (id_user,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"success": False, "message": "Không tìm thấy người dùng"}), 404
        return jsonify({"success": True, "data": user})
    except Exception as e:
        print("Lỗi get_user:", traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        _close(cursor, db)

# =================== Chỉnh sửa thông tin cá nhân ===================
@profile_bp.route("/users/update", methods=["PUT"])
def update_user():
    db = cursor = None
    try:
        data = request.get_json() or {}
        id_user = data.get("id_user")
        if not id_user:
            return jsonify({"success": False, "message": "Thiếu id_user"}), 400

        fields = ["fullName", "dateOfBirth", "email", "gender", "avatar", "status", "level"]
        updates = []
        values = []
        for f in fields:
            if f in data:
                updates.append(f"{f}=%s")
                values.append(data[f])

        if not updates:
            return jsonify({"success": False, "message": "Không có dữ liệu để cập nhật"}), 400

        values.append(id_user)
        sql = f"UPDATE users SET {', '.join(updates)} WHERE id_user=%s"

        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute(sql, tuple(values))
        db.commit()

        return jsonify({"success": True, "message": "Cập nhật thông tin thành công"})
    except Exception as e:
        print("Lỗi update_user:", traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        _close(cursor, db)

# =================== Đổi mật khẩu ===================
@profile_bp.route("/users/change_password", methods=["PUT"])
def change_password():
    db = cursor = None
    try:
        data = request.get_json() or {}
        id_user = data.get("id_user")
        old_pass = data.get("old_password")
        new_pass = data.get("new_password")

        if not id_user or not old_pass or not new_pass:
            return jsonify({"success": False, "message": "Thiếu dữ liệu"}), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT password FROM users WHERE id_user=%s", (id_user,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"success": False, "message": "Không tìm thấy người dùng"}), 404

        # So sánh mật khẩu cũ (ở đây demo, chưa mã hóa)
        if user["password"] != old_pass:
            return jsonify({"success": False, "message": "Mật khẩu cũ không đúng"}), 400

        cursor.execute("UPDATE users SET password=%s WHERE id_user=%s", (new_pass, id_user))
        db.commit()

        return jsonify({"success": True, "message": "Đổi mật khẩu thành công"})
    except Exception as e:
        print("Lỗi change_password:", traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        _close(cursor, db)