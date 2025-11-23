from flask import Blueprint, jsonify, request
from back_end.config.db_config import get_db_connection
import traceback

exam_bp = Blueprint('exam_bp', __name__)

def _close(cursor, db):
    if cursor:
        cursor.close()
    if db:
        db.close()

# Lấy danh sách phòng ban
@exam_bp.route('/departments', methods=['GET'])
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

# Lấy danh sách lớp theo id_department
@exam_bp.route('/classrooms', methods=['GET'])
def get_classrooms():
    db = cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Lấy cố định id_department = 1
        cursor.execute("SELECT id_class, class_name FROM classroom WHERE id_department = 1")
        classes = cursor.fetchall()
        return jsonify({"success": True, "data": classes})

    except Exception:
        print("Lỗi lấy classrooms:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)