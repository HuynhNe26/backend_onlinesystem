from flask import Blueprint, jsonify
from ...config.db_config import get_db_connection
from flask import request
import traceback
from datetime import datetime
import re

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

@admin_bp.route('/update/<int:id>', methods=['PUT'])
def updateAdmin(id):
    db = None
    cursor = None
    try:
        data = request.get_json()
        email = data.get("email")
        full_name = data.get("fullName")          
        date_of_birth = data.get("dateOfBirth")
        gender = data.get("gender")

        if not all([email, full_name, date_of_birth, gender]):
            return jsonify({"success": False, "msg": "Thiếu thông tin bắt buộc"}), 400

        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            return jsonify({"success": False, "msg": "Email không hợp lệ"}), 400
        
        if gender not in ['Nam', 'Nữ']:
            return jsonify({"success": False, "msg": "Giới tính không hợp lệ"}), 400
        
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE id_user=%s", (id,))
        admin = cursor.fetchone()
        
        if not admin:
            return jsonify({"success": False, "msg": "Không tìm thấy quản trị viên"}), 404

        cursor.execute("SELECT id FROM users WHERE email=%s AND id_user!=%s", (email, id))
        existing_email = cursor.fetchone()
        
        if existing_email:
            return jsonify({"success": False, "msg": "Email đã được sử dụng bởi tài khoản khác"}), 409

        try:
            birth_date = datetime.strptime(date_of_birth, '%Y-%m-%d')
            today = datetime.now()
            age = (today - birth_date).days / 365.25
            
            if age < 18:
                return jsonify({"success": False, "msg": "Quản trị viên phải từ 18 tuổi trở lên"}), 400
            
            if age > 100:
                return jsonify({"success": False, "msg": "Ngày sinh không hợp lệ"}), 400
                
        except ValueError:
            return jsonify({"success": False, "msg": "Định dạng ngày sinh không hợp lệ (YYYY-MM-DD)"}), 400
        
        if len(full_name.strip()) < 2:
            return jsonify({"success": False, "msg": "Họ tên phải có ít nhất 2 ký tự"}), 400
        
        if len(full_name) > 100:
            return jsonify({"success": False, "msg": "Họ tên không được quá 100 ký tự"}), 400

        update_query = """
            UPDATE users 
            SET email=%s, fullName=%s, dateOfBirth=%s, gender=%s 
            WHERE id_user=%s
        """
        cursor.execute(update_query, (email, full_name.strip(), date_of_birth, gender, id))
        db.commit()
        
        cursor.execute("SELECT * FROM users WHERE id_user=%s", (id,))
        updated_admin = cursor.fetchone()

        return jsonify({"success": True, "msg": "Cập nhật thành công", "data": updated_admin}), 200

    except Exception as e:
        if db:
            db.rollback()
        print("Lỗi cập nhật dữ liệu:", e)
        return jsonify({"success": False, "msg": "Lỗi server"}), 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()