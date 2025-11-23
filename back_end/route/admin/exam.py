from flask import Blueprint, jsonify, request
from back_end.config.db_config import get_db_connection
import traceback
from datetime import datetime

exam_ad = Blueprint('exam_ad', __name__)

def _close(cursor, db):
    if cursor:
        cursor.close()
    if db:
        db.close()

# -------------------- Departments --------------------
@exam_ad.route('/departments', methods=['GET'])
def get_departments():
    db = cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id_department, name_department FROM department")
        departments = cursor.fetchall()
        return jsonify({"success": True, "data": departments})
    except Exception:
        print("Lỗi lấy departments:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)

# -------------------- Classrooms --------------------
@exam_ad.route('/classrooms', methods=['GET'])
def get_classrooms():
    db = cursor = None
    try:
        id_department = request.args.get("id_department")
        if not id_department:
            return jsonify({"success": False, "message": "Thiếu id_department"}), 400

        try:
            id_department = int(id_department)
        except ValueError:
            return jsonify({"success": False, "message": "id_department phải là số"}), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT id_class, class_name FROM classroom WHERE id_department = %s",
            (id_department,)
        )
        classes = cursor.fetchall()
        return jsonify({"success": True, "data": classes})
    except Exception:
        print("Lỗi lấy classrooms:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)

# -------------------- Difficulties --------------------
@exam_ad.route('/difficulties', methods=['GET'])
def get_difficulties():
    db = cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id_diff, difficulty FROM dificulty")
        diffs = cursor.fetchall()
        return jsonify({"success": True, "data": diffs})
    except Exception:
        print("Lỗi lấy difficulties:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)

# -------------------- Create exam --------------------
@exam_ad.route('/create', methods=['POST'])
def create_exam():
    db = cursor = None
    try:
        data = request.get_json()
        required_fields = ["id_department", "id_class", "id_diff", "total_ques", "duration", "name_ex"]
        for field in required_fields:
            if field not in data or data[field] in [None, ""]:
                return jsonify({"success": False, "message": f"Thiếu {field}"}), 400

        db = get_db_connection()
        cursor = db.cursor()

        sql = """
        INSERT INTO exam
        (id_department, id_class, id_diff, total_ques, duration, name_ex, exam_cat)
        VALUES (%s, %s, %s, %s, %s, %s, 'draft')
        """
        cursor.execute(sql, (
            int(data["id_department"]),
            int(data["id_class"]),
            int(data["id_diff"]),
            int(data["total_ques"]),
            int(data["duration"]),
            data["name_ex"]
        ))
        db.commit()
        return jsonify({"success": True, "message": "Tạo đề thành công"})
    except Exception:
        print("Lỗi tạo exam:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)
