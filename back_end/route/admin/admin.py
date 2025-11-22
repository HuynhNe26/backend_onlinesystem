from flask import Blueprint, jsonify
from ...config.db_config import get_db_connection
from flask import request
import traceback

admin_bp = Blueprint('admin_bp', __name__)

@admin_bp.route('/admin', methods=['GET'])
def getAdllAdmin():
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute('SELECT * FROM users WHERE level >= 2')
        admins = cursor.fetchall()

        if not admins:
            return jsonify({"msg": "Không có dữ liệu quản trị viên"}), 404

        return jsonify({"success": True, "data": admins}), 200

    except Exception as e:
        print("Lỗi lấy dữ liệu:", e)
        return jsonify({"msg": "Lỗi server"}), 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

@admin_bp.route('/<int:id>', methods=['GET'])
def getAdminDetail(id):
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE id_user = %s", (id,))
        admin = cursor.fetchone()

        if not admin:
            return jsonify({"msg": "Không tìm thấy quản trị viên"}), 404

        return jsonify({"success": True, "data": admin}), 200

    except Exception as e:
        print("Lỗi lấy dữ liệu:", e)
        return jsonify({"msg": "Lỗi server"}), 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

admin_bp = Blueprint("admin_bp", __name__)

@admin_bp.route('/create', methods=['POST'])
def create_admin():
    db = None
    cursor = None
    try:
        data = request.get_json()

        email = data.get("email")
        full_name = data.get("fullName")          
        date_of_birth = data.get("dateOfBirth")
        password = data.get("password")
        gender = data.get("gender")
        level_raw = data.get("level")

        if not all([email, full_name, date_of_birth, password, gender, level_raw]):
            return jsonify({"success": False, "message": "Thiếu dữ liệu bắt buộc"}), 400

        try:
            level = int(level_raw)
        except:
            return jsonify({"success": False, "message": "Level không hợp lệ"}), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing = cursor.fetchone()
        if existing:
            return jsonify({"success": False, "message": "Email đã tồn tại"}), 400

        role = "Quản trị viên" if level == 2 else "Quản trị viên cấp cao"

        status = "Tài khoản mới"
        
        query = """
            INSERT INTO users 
            (email, fullName, dateOfBirth, password, level, gender, status, role, create_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        cursor.execute(query, (
            email,
            full_name,
            date_of_birth,
            password,
            level,
            gender,
            status,
            role
        ))

        db.commit()

        return jsonify({"success": True, "message": "Tạo quản trị viên thành công"}), 201

    except Exception as e:
        print("Lỗi tạo quản trị viên:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()


