from flask import Blueprint, jsonify, request
from back_end.config.db_config import get_db_connection
import traceback

exam_bp = Blueprint('exam_bp', __name__)

def _close(cursor, db):
    if cursor:
        cursor.close()
    if db:
        db.close()

# Departments
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

# Classrooms
@exam_bp.route('/classrooms/<int:id_department>', methods=['GET'])
def get_classrooms_by_department(id_department):
    db = cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT id_class, class_name FROM classroom WHERE id_department = %s",
            (id_department,)
        )
        classes = cursor.fetchall()

        if not classes:
            return jsonify({"msg": "Không tìm thấy lớp học"}), 404

        return jsonify({"success": True, "data": classes}), 200

    except Exception as e:
        print("Lỗi lấy classrooms:", traceback.format_exc())
        return jsonify({"msg": "Lỗi server"}), 500

    finally:
        _close(cursor, db)

