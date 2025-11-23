from flask import Blueprint, request, jsonify
from ...config.db_config import get_db_connection
import traceback
from datetime import datetime

exam_bp = Blueprint('exam_bp', __name__)

EXAM_CATEGORIES = [
    {"key": "draft", "label": "Luyện thi"},
    {"key": "scheduled", "label": "Đã lên lịch"},
    {"key": "published", "label": "Đã công bố"},
    {"key": "closed", "label": "Đã đóng"},
    {"key": "archived", "label": "Lưu trữ"}
]
ALLOWED_CATS = {c['key'] for c in EXAM_CATEGORIES}

def _close(cursor, db):
    if cursor: cursor.close()
    if db: db.close()

def _validate_datetime_str(dt_str):
    if not dt_str: raise ValueError("Empty datetime string")
    for fmt in ("%Y-%m-%d %H:%M:%S","%Y-%m-%d %H:%M"):
        try: return datetime.strptime(dt_str, fmt)
        except: continue
    try: return datetime.strptime(dt_str, "%Y-%m-%d")
    except: raise ValueError("Invalid datetime format. Use YYYY-MM-DD HH:MM[:SS]")

# ----------------- Dropdowns -----------------
@exam_bp.route('/departments', methods=['GET'])
def get_departments():
    db = cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id_department, name_department FROM department")
        return jsonify({"success": True, "data": cursor.fetchall()})
    except Exception:
        print("Lỗi lấy departments:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)

@exam_bp.route('/classrooms', methods=['GET'])
def get_classrooms():
    db = cursor = None
    try:
        id_dept = request.args.get("id_department")
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        if id_dept:
            cursor.execute("SELECT id_class, class_name, id_department FROM class WHERE id_department=%s", (id_dept,))
        else:
            cursor.execute("SELECT id_class, class_name, id_department FROM class")
        return jsonify({"success": True, "data": cursor.fetchall()})
    except Exception:
        print("Lỗi lấy classrooms:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)

@exam_bp.route('/difficulties', methods=['GET'])
def get_difficulties():
    db = cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id_diff, difficulty FROM difficulty")
        return jsonify({"success": True, "data": cursor.fetchall()})
    except Exception:
        print("Lỗi lấy difficulties:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)

@exam_bp.route('/categories', methods=['GET'])
def get_categories():
    try:
        return jsonify({"success": True, "data": EXAM_CATEGORIES})
    except Exception:
        print("Lỗi lấy categories:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500

# ----------------- Create question -----------------
@exam_bp.route('/question/create', methods=['POST'])
def create_question():
    db = cursor = None
    try:
        data = request.get_json() or {}
        ques_text = data.get('ques_text')
        ans_a = data.get('ans_a')
        ans_b = data.get('ans_b')
        ans_c = data.get('ans_c')
        ans_d = data.get('ans_d')
        correct_ans = data.get('correct_ans')
        point = data.get('point', 1)
        explanation = data.get('explanation', "")

        if not all([ques_text, ans_a, ans_b, ans_c, ans_d, correct_ans]):
            return jsonify({"success": False, "message": "Thiếu dữ liệu bắt buộc"}), 400

        db = get_db_connection()
        cursor = db.cursor()
        sql = """INSERT INTO question
                (ques_text, ans_a, ans_b, ans_c, ans_d, correct_ans, point, explanation)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"""
        cursor.execute(sql, (ques_text, ans_a, ans_b, ans_c, ans_d, correct_ans, point, explanation))
        db.commit()
        return jsonify({"success": True, "message": "Tạo câu hỏi thành công", "id_question": cursor.lastrowid}), 201
    except Exception:
        print("Lỗi tạo câu hỏi:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)

# ----------------- Create exam -----------------
@exam_bp.route('/create', methods=['POST'])
def create_exam():
    db = cursor = None
    try:
        data = request.get_json() or {}
        id_department = data.get('id_department')
        id_class = data.get('id_class')
        id_diff = data.get('id_diff')
        total_question = data.get('total_question')
        duration = data.get('duration')
        exam_cat = data.get('exam_cat', 'draft')
        start_time = data.get('start_time')
        end_time = data.get('end_time')

        if not all([id_department, id_class, id_diff, total_question, duration]):
            return jsonify({"success": False, "message": "Thiếu dữ liệu bắt buộc"}), 400
        if exam_cat not in ALLOWED_CATS:
            return jsonify({"success": False, "message": "exam_cat không hợp lệ"}), 400

        start_dt = _validate_datetime_str(start_time) if start_time else None
        end_dt = _validate_datetime_str(end_time) if end_time else None
        if start_dt and end_dt and start_dt >= end_dt:
            return jsonify({"success": False, "message": "start_time phải trước end_time"}), 400

        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("""INSERT INTO exam
                          (id_department, id_class, id_diff, total_ques, duration, exam_cat, start_time, end_time, create_at)
                          VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())""",
                       (
                           id_department, id_class, id_diff, total_question, duration,
                           exam_cat,
                           start_dt.strftime('%Y-%m-%d %H:%M:%S') if start_dt else None,
                           end_dt.strftime('%Y-%m-%d %H:%M:%S') if end_dt else None
                       ))
        db.commit()
        return jsonify({"success": True, "message": "Tạo đề thành công", "id_exam": cursor.lastrowid}), 201
    except Exception:
        print("Lỗi tạo đề:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)

# ----------------- Add questions -----------------
@exam_bp.route('/<int:id_exam>/add-questions', methods=['POST'])
def add_questions_to_exam(id_exam):
    db = cursor = None
    try:
        data = request.get_json() or {}
        questions = data.get('questions')
        if not questions or not isinstance(questions, list):
            return jsonify({"success": False, "message": "Danh sách questions phải là list"}), 400

        db = get_db_connection()
        cursor = db.cursor()
        cursor.execute("SELECT id_exam FROM exam WHERE id_exam=%s", (id_exam,))
        if not cursor.fetchone():
            return jsonify({"success": False, "message": "Exam không tồn tại"}), 404

        values = []
        placeholders = []
        for q_id in questions:
            placeholders.append("(%s,%s)")
            values.extend([id_exam, q_id])

        cursor.execute("INSERT INTO exam_question (id_exam, id_question) VALUES " + ",".join(placeholders), tuple(values))
        db.commit()
        return jsonify({"success": True, "message": "Thêm câu hỏi vào đề thành công"}), 201
    except Exception:
        print("Lỗi thêm câu hỏi:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)
