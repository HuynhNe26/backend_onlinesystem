from flask import Blueprint, request, jsonify
from back_end.config.db_config import get_db_connection
import traceback
from werkzeug.security import generate_password_hash, check_password_hash

# Blueprint
profile_bp = Blueprint("profile_bp", __name__)

# Helper đóng kết nối
def _close(cursor, db):
    try:
        if cursor: cursor.close()
        if db: db.close()
    except Exception:
        pass

# =================== Xem thông tin cá nhân ===================
@profile_bp.route("/<int:id_user>", methods=["GET"])
def get_user(id_user):
    db = cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT id_user, fullName, dateOfBirth, email, role, status, gender, avatar, level
            FROM users WHERE id_user=%s
        """, (id_user,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"success": False, "message": "Không tìm thấy người dùng"}), 404

        # ✅ Chuẩn hóa dateOfBirth về dạng YYYY-MM-DD
        if user.get("dateOfBirth"):
            try:
                if hasattr(user["dateOfBirth"], "strftime"):
                    user["dateOfBirth"] = user["dateOfBirth"].strftime("%Y-%m-%d")
                else:
                    user["dateOfBirth"] = str(user["dateOfBirth"])[:10]
            except Exception:
                pass

        return jsonify({"success": True, "data": user})
    except Exception as e:
        print("❌ Lỗi get_user:", traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        _close(cursor, db)

# =================== Chỉnh sửa thông tin cá nhân ===================
@profile_bp.route("/update", methods=["PUT"])
def update_user():
    db = cursor = None
    try:
        data = request.get_json(silent=True) or {}
        id_user = data.get("id_user")
        if not id_user:
            return jsonify({"success": False, "message": "Thiếu id_user"}), 400

        # Chuẩn hóa dateOfBirth
        if "dateOfBirth" in data and data["dateOfBirth"]:
            try:
                dob = str(data["dateOfBirth"]).split(" ")[0]
                data["dateOfBirth"] = dob
            except Exception:
                pass

        fields = ["fullName", "dateOfBirth", "email", "gender", "avatar", "status", "level"]
        updates, values = [], []
        for f in fields:
            if f in data and data[f] is not None:
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

        # Trả lại thông tin mới
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT id_user, fullName, dateOfBirth, email, role, status, gender, avatar, level
            FROM users WHERE id_user=%s
        """, (id_user,))
        user = cursor.fetchone()
        if user and user.get("dateOfBirth"):
            try:
                if hasattr(user["dateOfBirth"], "strftime"):
                    user["dateOfBirth"] = user["dateOfBirth"].strftime("%Y-%m-%d")
                else:
                    user["dateOfBirth"] = str(user["dateOfBirth"])[:10]
            except Exception:
                pass

        return jsonify({"success": True, "message": "Cập nhật thông tin thành công", "data": user})
    except Exception as e:
        print("❌ Lỗi update_user:", traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        _close(cursor, db)

# =================== Đổi mật khẩu ===================
@profile_bp.route("/change_password", methods=["PUT"])
def change_password():
    db = cursor = None
    try:
        data = request.get_json(silent=True) or {}
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

        # ✅ Dùng check_password_hash để so sánh
        if not check_password_hash(user["password"], old_pass):
            return jsonify({"success": False, "message": "Mật khẩu cũ không đúng"}), 400

        # ✅ Hash mật khẩu mới bằng generate_password_hash
        new_hashed = generate_password_hash(new_pass)
        cursor.execute("UPDATE users SET password=%s WHERE id_user=%s", (new_hashed, id_user))
        db.commit()

        return jsonify({"success": True, "message": "Đổi mật khẩu thành công"})
    except Exception as e:
        print("❌ Lỗi change_password:", traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        _close(cursor, db)