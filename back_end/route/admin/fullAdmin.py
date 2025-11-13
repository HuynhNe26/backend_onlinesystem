from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from flask_cors import CORS
from werkzeug.security import generate_password_hash
import mysql.connector

admin_users_bp = Blueprint('admin_users', __name__)

# ===== CORS CHO BLUEPRINT - QUAN TRỌNG =====
CORS(admin_users_bp,
     origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"],
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])


def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Anhkiet3307*",
        database="online_testing"
    )


def is_admin_claims_or_abort():
    claims = get_jwt()
    level = claims.get("level")
    try:
        level = int(level)
    except:
        pass
    return level in (2, 3)


# ===== READ - LIST ALL ADMINS =====
@admin_users_bp.route('/all', methods=['GET', 'OPTIONS'])
@jwt_required(optional=True)
def list_admins():
    # Cho phép OPTIONS request không cần JWT
    if request.method == 'OPTIONS':
        return jsonify({"msg": "OK"}), 200

    if not is_admin_claims_or_abort():
        return jsonify({"msg": "Không có quyền"}), 403

    try:
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT id_user, username, fullName, role, level, login_time, logout_time FROM users WHERE level>=2 ORDER BY id_user DESC"
        )
        admins = cursor.fetchall()
        return jsonify({"data": admins}), 200
    except Exception as e:
        print("List admins error:", e)
        return jsonify({"msg": "Lỗi server"}), 500
    finally:
        cursor.close()
        db.close()


# ===== CREATE - CREATE ADMIN =====
@admin_users_bp.route('/create', methods=['POST', 'OPTIONS'])
@jwt_required(optional=True)
def create_admin():
    # Cho phép OPTIONS request không cần JWT
    if request.method == 'OPTIONS':
        return jsonify({"msg": "OK"}), 200

    if not is_admin_claims_or_abort():
        return jsonify({"msg": "Không có quyền"}), 403

    data = request.get_json() or {}
    username = data.get("username")
    password = data.get("password")
    fullName = data.get("fullName", "")
    role = data.get("role", "admin")
    level = data.get("level", 2)

    if not username or not password:
        return jsonify({"msg": "Thiếu username hoặc password"}), 400

    try:
        hashed = generate_password_hash(password)
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO users (username, password, fullName, role, level) VALUES (%s, %s, %s, %s, %s)",
            (username, hashed, fullName, role, level)
        )
        db.commit()
        new_id = cursor.lastrowid
        return jsonify({"msg": "Tạo admin thành công", "id_user": new_id}), 201
    except mysql.connector.IntegrityError:
        return jsonify({"msg": "Username đã tồn tại"}), 400
    except Exception as e:
        print("Create admin error:", e)
        return jsonify({"msg": "Lỗi server"}), 500
    finally:
        cursor.close()
        db.close()


# ===== UPDATE - UPDATE ADMIN =====
@admin_users_bp.route('/update/<int:user_id>', methods=['PUT', 'OPTIONS'])
@jwt_required(optional=True)
def update_admin(user_id):
    # Cho phép OPTIONS request không cần JWT
    if request.method == 'OPTIONS':
        return jsonify({"msg": "OK"}), 200

    if not is_admin_claims_or_abort():
        return jsonify({"msg": "Không có quyền"}), 403

    data = request.get_json() or {}
    fields, values = [], []

    if data.get("username"):
        fields.append("username=%s")
        values.append(data["username"])
    if data.get("password"):
        fields.append("password=%s")
        values.append(generate_password_hash(data["password"]))
    if "fullName" in data:
        fields.append("fullName=%s")
        values.append(data["fullName"])
    if data.get("role"):
        fields.append("role=%s")
        values.append(data["role"])
    if "level" in data:
        fields.append("level=%s")
        values.append(data["level"])

    if not fields:
        return jsonify({"msg": "Không có dữ liệu để cập nhật"}), 400

    try:
        db = get_db()
        cursor = db.cursor()
        sql = "UPDATE users SET " + ", ".join(fields) + " WHERE id_user=%s"
        values.append(user_id)
        cursor.execute(sql, tuple(values))
        db.commit()
        if cursor.rowcount == 0:
            return jsonify({"msg": "Không tìm thấy admin"}), 404
        return jsonify({"msg": "Cập nhật thành công"}), 200
    except mysql.connector.IntegrityError:
        return jsonify({"msg": "Lỗi dữ liệu (trùng username)"}), 400
    except Exception as e:
        print("Update admin error:", e)
        return jsonify({"msg": "Lỗi server"}), 500
    finally:
        cursor.close()
        db.close()


# ===== DELETE - DELETE ADMIN =====
@admin_users_bp.route('/delete/<int:user_id>', methods=['DELETE', 'OPTIONS'])
@jwt_required(optional=True)
def delete_admin(user_id):
    # Cho phép OPTIONS request không cần JWT
    if request.method == 'OPTIONS':
        return jsonify({"msg": "OK"}), 200

    if not is_admin_claims_or_abort():
        return jsonify({"msg": "Không có quyền"}), 403

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
                    DELETE a FROM answer a
                    LEFT JOIN questions q ON a.id_ques = q.id_ques
                    LEFT JOIN exam_question eq ON a.id_inter = eq.id_inter
                    WHERE a.id_user = %s OR q.id_user = %s
                """, (user_id, user_id))

        # ===== 2. XÓA exam_question liên quan đến questions của user =====
        cursor.execute("""
                    DELETE eq FROM exam_question eq
                    JOIN questions q ON eq.id_ques = q.id_ques
                    WHERE q.id_user = %s
                """, (user_id,))

        # ===== 3. XÓA questions của user =====
        cursor.execute("DELETE FROM questions WHERE id_user = %s", (user_id,))

        # ===== 4. XÓA categories của user =====
        cursor.execute("DELETE FROM categories WHERE id_user = %s", (user_id,))

        # ===== 5. XÓA exam của user =====
        cursor.execute("DELETE FROM exam WHERE id_user = %s", (user_id,))

        # ===== 6. XÓA results, violations, notification =====
        cursor.execute("DELETE FROM results WHERE id_user = %s", (user_id,))
        cursor.execute("DELETE FROM violations WHERE id_user = %s", (user_id,))
        cursor.execute("DELETE FROM notification WHERE id_user = %s", (user_id,))

        # ===== 7. XÓA payment =====
        cursor.execute("DELETE FROM payment WHERE id_user = %s", (user_id,))

        # ===== 8. XÓA department =====
        cursor.execute("DELETE FROM department WHERE id_user = %s", (user_id,))

        # ===== 9. Cuối cùng xóa user =====
        cursor.execute("DELETE FROM users WHERE id_user = %s AND level >= 2", (user_id,))

        db.commit()

        if cursor.rowcount == 0:
            return jsonify({"msg": "Không tìm thấy admin hoặc không thể xóa"}), 404

        return jsonify({"msg": "Xóa admin và toàn bộ dữ liệu liên quan thành công"}), 200

    except Exception as e:
        db.rollback()
        print("Delete admin error:", e)
        return jsonify({"msg": "Lỗi server"}), 500
    finally:
        cursor.close()
        db.close()