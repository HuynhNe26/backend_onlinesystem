from flask import Blueprint, jsonify, request
from back_end.config.db_config import get_db_connection
import traceback

exam_bp = Blueprint('exam_bp', __name__)

def _close(cursor, db):
    if cursor:
        cursor.close()
    if db:
        db.close()

@exam_bp.route('/departments', methods=['GET'])
def get_departments():
    db = cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id_department, name_department FROM department")
        departments = cursor.fetchall()
        return jsonify({"success": True, "departments": departments})
    except Exception:
        print("Lỗi lấy departments:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)

@exam_bp.route('/classrooms', methods=['GET'])
def get_classrooms():
    db = cursor = None
    try:
        id_department = request.args.get("id_department")  # <- query param
        if not id_department:
            return jsonify({"success": False, "message": "Thiếu id_department"}), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        sql = "SELECT id_class, class_name FROM classroom WHERE id_department = %s"
        cursor.execute(sql, (id_department,))
        classes = cursor.fetchall()
        return jsonify({"success": True, "classes": classes})
    except Exception:
        print("Lỗi lấy classrooms:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)
