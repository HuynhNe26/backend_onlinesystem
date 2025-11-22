from flask import Blueprint, request, jsonify
from ...config.db_config import get_db_connection
import traceback
from datetime import datetime

exam_bp = Blueprint('exam_bp', __name__, url_prefix='/exam')

EXAM_CATEGORIES = [
    {"key": "draft", "label": "Bản nháp"},
    {"key": "scheduled", "label": "Đã lên lịch"},
    {"key": "published", "label": "Đã công bố"},
    {"key": "closed", "label": "Đã đóng"},
    {"key": "archived", "label": "Lưu trữ"}
]
ALLOWED_CATS = {c['key'] for c in EXAM_CATEGORIES}

def _close(cursor, db):
    try:
        if cursor:
            cursor.close()
    except:
        pass
    try:
        if db:
            db.close()
    except:
        pass


def _validate_datetime_str(dt_str):
    if not dt_str:
        raise ValueError("Empty datetime string")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(dt_str, fmt)
        except Exception:
            continue
    try:
        return datetime.strptime(dt_str, "%Y-%m-%d")
    except Exception:
        raise ValueError("Invalid datetime format. Use 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD HH:MM:SS'")

@exam_bp.route('/departments', methods=['GET'])
def get_departments():
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id_department, name_department FROM department")
        data = cursor.fetchall()
        return jsonify({"success": True, "data": data}), 200
    except Exception:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)

@exam_bp.route('/classrooms', methods=['GET'])
def get_classrooms():
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id_class, name_class FROM classroom")
        data = cursor.fetchall()
        return jsonify({"success": True, "data": data}), 200
    except Exception:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)

@exam_bp.route('/difficulties', methods=['GET'])
def get_difficulties():
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT id_diff, name_diff FROM difficult")
        data = cursor.fetchall()
        return jsonify({"success": True, "data": data}), 200
    except Exception:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)

@exam_bp.route('/categories', methods=['GET'])
def get_categories():
    # Return allowed categories so FE can render dropdown
    return jsonify({"success": True, "data": EXAM_CATEGORIES}), 200

@exam_bp.route('/create', methods=['POST'])
def create_exam():
    db = None
    cursor = None
    try:
        data = request.get_json() or {}

        id_department = data.get('id_department')
        id_class = data.get('id_class')
        id_diff = data.get('id_diff')
        total_question = data.get('total_question')
        duration = data.get('duration')
        exam_cat = data.get('exam_cat', 'draft')
        start_time = data.get('start_time')  # optional, string
        end_time = data.get('end_time')      # optional, string

        if not all([id_department, id_class, id_diff, total_question, duration]):
            return jsonify({"success": False, "message": "Thiếu dữ liệu bắt buộc"}), 400

        if exam_cat not in ALLOWED_CATS:
            return jsonify({"success": False, "message": "exam_cat không hợp lệ"}), 400

        start_dt = None
        end_dt = None
        if exam_cat == 'scheduled' or start_time or end_time:
            if not start_time or not end_time:
                return jsonify({"success": False, "message": "scheduled requires start_time and end_time"}), 400
            try:
                start_dt = _validate_datetime_str(start_time)
                end_dt = _validate_datetime_str(end_time)
            except ValueError as ve:
                return jsonify({"success": False, "message": str(ve)}), 400

            if start_dt >= end_dt:
                return jsonify({"success": False, "message": "start_time must be before end_time"}), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        query = """
            INSERT INTO exam
            (id_department, id_class, id_diff, total_ques, duration, exam_cat, start_time, end_time, create_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """

        cursor.execute(query, (
            id_department,
            id_class,
            id_diff,
            total_question,
            duration,
            exam_cat,
            start_dt.strftime('%Y-%m-%d %H:%M:%S') if start_dt else None,
            end_dt.strftime('%Y-%m-%d %H:%M:%S') if end_dt else None
        ))

        db.commit()
        new_id = cursor.lastrowid

        return jsonify({"success": True, "message": "Tạo đề thành công", "id_exam": new_id}), 201

    except Exception:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)


@exam_bp.route('/<int:id_exam>/add-questions', methods=['POST'])
def add_questions_to_exam(id_exam):
    db = None
    cursor = None
    try:
        data = request.get_json() or {}
        questions = data.get('questions')

        if not questions or not isinstance(questions, list):
            return jsonify({"success": False, "message": "Danh sách questions phải là list"}), 400

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("SELECT id_exam FROM exam WHERE id_exam = %s", (id_exam,))
        if cursor.fetchone() is None:
            return jsonify({"success": False, "message": "Exam không tồn tại"}), 404

        values = []
        placeholders = []
        for q_id in questions:
            placeholders.append("(%s, %s)")
            values.extend([id_exam, q_id])

        if not placeholders:
            return jsonify({"success": False, "message": "Không có câu hỏi để thêm"}), 400

        insert_sql = "INSERT INTO exam_question (id_exam, id_question) VALUES " + ",".join(placeholders)

        cursor.execute(insert_sql, tuple(values))
        db.commit()

        return jsonify({"success": True, "message": "Thêm câu hỏi vào đề thành công"}), 201

    except Exception:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)

@exam_bp.route('/<int:id_exam>', methods=['GET'])
def get_exam_detail(id_exam):
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM exam WHERE id_exam = %s", (id_exam,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "message": "Không tìm thấy đề"}), 404

        cursor.execute("SELECT eq.id_question, q.title as question_title FROM exam_question eq LEFT JOIN question q ON q.id_question = eq.id_question WHERE eq.id_exam = %s", (id_exam,))
        qs = cursor.fetchall()
        row['questions'] = qs

        return jsonify({"success": True, "data": row}), 200
    except Exception:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)


@exam_bp.route('/list', methods=['GET'])
def list_exams():
    # Optional filters via query params: department, class, diff, cat
    id_department = request.args.get('id_department')
    id_class = request.args.get('id_class')
    id_diff = request.args.get('id_diff')
    exam_cat = request.args.get('exam_cat')

    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        base = "SELECT * FROM exam"
        where = []
        params = []
        if id_department:
            where.append("id_department = %s")
            params.append(id_department)
        if id_class:
            where.append("id_class = %s")
            params.append(id_class)
        if id_diff:
            where.append("id_diff = %s")
            params.append(id_diff)
        if exam_cat:
            where.append("exam_cat = %s")
            params.append(exam_cat)

        if where:
            base = base + " WHERE " + " AND ".join(where)

        cursor.execute(base, tuple(params))
        rows = cursor.fetchall()
        return jsonify({"success": True, "data": rows}), 200

    except Exception:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)


@exam_bp.route('/<int:id_exam>', methods=['PUT'])
def update_exam(id_exam):
    db = None
    cursor = None
    try:
        data = request.get_json() or {}

        # Allow update of several fields: exam_cat, start_time, end_time, total_ques, duration
        exam_cat = data.get('exam_cat')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        total_question = data.get('total_question')
        duration = data.get('duration')

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("SELECT * FROM exam WHERE id_exam = %s", (id_exam,))
        if cursor.fetchone() is None:
            return jsonify({"success": False, "message": "Exam không tồn tại"}), 404

        updates = []
        params = []

        if exam_cat:
            if exam_cat not in ALLOWED_CATS:
                return jsonify({"success": False, "message": "exam_cat không hợp lệ"}), 400
            updates.append("exam_cat = %s")
            params.append(exam_cat)

        if start_time:
            try:
                s_dt = _validate_datetime_str(start_time)
                updates.append("start_time = %s")
                params.append(s_dt.strftime('%Y-%m-%d %H:%M:%S'))
            except ValueError as ve:
                return jsonify({"success": False, "message": str(ve)}), 400

        if end_time:
            try:
                e_dt = _validate_datetime_str(end_time)
                updates.append("end_time = %s")
                params.append(e_dt.strftime('%Y-%m-%d %H:%M:%S'))
            except ValueError as ve:
                return jsonify({"success": False, "message": str(ve)}), 400

        if total_question is not None:
            updates.append("total_ques = %s")
            params.append(total_question)

        if duration is not None:
            updates.append("duration = %s")
            params.append(duration)

        if not updates:
            return jsonify({"success": False, "message": "Không có dữ liệu để cập nhật"}), 400

        sql = "UPDATE exam SET " + ", ".join(updates) + " WHERE id_exam = %s"
        params.append(id_exam)

        cursor.execute(sql, tuple(params))
        db.commit()

        return jsonify({"success": True, "message": "Cập nhật exam thành công"}), 200

    except Exception:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)


@exam_bp.route('/<int:id_exam>', methods=['DELETE'])
def delete_exam(id_exam):
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor()

        # delete exam_question first to maintain FK
        cursor.execute("DELETE FROM exam_question WHERE id_exam = %s", (id_exam,))
        cursor.execute("DELETE FROM exam WHERE id_exam = %s", (id_exam,))
        db.commit()

        return jsonify({"success": True, "message": "Xóa exam thành công"}), 200
    except Exception:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)

# --- FULL UPDATED BACKEND WITH QUESTION CREATION + EXAM LINKING ---
from flask import Blueprint, request, jsonify
from ...config.db_config import get_db_connection
import traceback
from datetime import datetime

exam_bp = Blueprint('exam_bp', __name__, url_prefix='/exam')

EXAM_CATEGORIES = [
    {"key": "draft", "label": "Luyện thi"},
    {"key": "scheduled", "label": "Đã lên lịch"},
    {"key": "published", "label": "Đã công bố"},
    {"key": "closed", "label": "Đã đóng"},
    {"key": "archived", "label": "Lưu trữ"}
]
ALLOWED_CATS = {c['key'] for c in EXAM_CATEGORIES}


def _close(cursor, db):
    try:
        if cursor:
            cursor.close()
    except:
        pass
    try:
        if db:
            db.close()
    except:
        pass


def _validate_datetime_str(dt_str):
    if not dt_str:
        raise ValueError("Empty datetime string")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(dt_str, fmt)
        except Exception:
            continue
    try:
        return datetime.strptime(dt_str, "%Y-%m-%d")
    except Exception:
        raise ValueError("Invalid datetime format. Use 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD HH:MM:SS'")


# ------------------------------------------------------------
# 1) Tạo câu hỏi — lưu vào bảng question
# ------------------------------------------------------------
@exam_bp.route('/question/create', methods=['POST'])
def create_question():
    db = None
    cursor = None
    try:
        data = request.get_json() or {}

        ques_text = data.get('ques_text')
        ans_a = data.get('ans_a')
        ans_b = data.get('ans_b')
        ans_c = data.get('ans_c')
        ans_d = data.get('ans_d')
        correct_ans = data.get('correct_ans')
        point = data.get('point')
        explanation = data.get('explanation')

        if not all([ques_text, ans_a, ans_b, ans_c, ans_d, correct_ans]):
            return jsonify({"success": False, "message": "Thiếu dữ liệu bắt buộc"}), 400

        db = get_db_connection()
        cursor = db.cursor()

        sql = """
            INSERT INTO question
            (ques_text, ans_a, ans_b, ans_c, ans_d, correct_ans, point, explanation)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (
            ques_text, ans_a, ans_b, ans_c, ans_d, correct_ans, point, explanation
        ))
        db.commit()
        new_qid = cursor.lastrowid

        return jsonify({"success": True, "message": "Tạo câu hỏi thành công", "id_question": new_qid}), 201

    except Exception:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500

    finally:
        _close(cursor, db)


# ------------------------------------------------------------
# 2) Tạo đề thi — chỉ lưu bảng exam
# ------------------------------------------------------------
@exam_bp.route('/create', methods=['POST'])
def create_exam():
    db = None
    cursor = None
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

        start_dt = None
        end_dt = None

        if exam_cat == 'scheduled' or start_time or end_time:
            if not start_time or not end_time:
                return jsonify({"success": False, "message": "scheduled requires start_time and end_time"}), 400
            try:
                start_dt = _validate_datetime_str(start_time)
                end_dt = _validate_datetime_str(end_time)
            except ValueError as ve:
                return jsonify({"success": False, "message": str(ve)}), 400

            if start_dt >= end_dt:
                return jsonify({"success": False, "message": "start_time must be before end_time"}), 400

        db = get_db_connection()
        cursor = db.cursor()

        query = """
            INSERT INTO exam
            (id_department, id_class, id_diff, total_ques, duration, exam_cat, start_time, end_time, create_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """

        cursor.execute(query, (
            id_department, id_class, id_diff, total_question, duration,
            exam_cat,
            start_dt.strftime('%Y-%m-%d %H:%M:%S') if start_dt else None,
            end_dt.strftime('%Y-%m-%d %H:%M:%S') if end_dt else None
        ))

        db.commit()
        new_id = cursor.lastrowid

        return jsonify({"success": True, "message": "Tạo đề thành công", "id_exam": new_id}), 201

    except Exception:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)


# ------------------------------------------------------------
# 3) Gán danh sách câu hỏi vào đề thi — lưu exam_question
# ------------------------------------------------------------
@exam_bp.route('/<int:id_exam>/add-questions', methods=['POST'])
def add_questions_to_exam(id_exam):
    db = None
    cursor = None
    try:
        data = request.get_json() or {}
        questions = data.get('questions')

        if not questions or not isinstance(questions, list):
            return jsonify({"success": False, "message": "Danh sách questions phải là list"}), 400

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("SELECT id_exam FROM exam WHERE id_exam = %s", (id_exam,))
        if cursor.fetchone() is None:
            return jsonify({"success": False, "message": "Exam không tồn tại"}), 404

        values = []
        placeholders = []
        for q_id in questions:
            placeholders.append("(%s, %s)")
            values.extend([id_exam, q_id])

        if not placeholders:
            return jsonify({"success": False, "message": "Không có câu hỏi để thêm"}), 400

        insert_sql = "INSERT INTO exam_question (id_exam, id_question) VALUES " + ",".join(placeholders)

        cursor.execute(insert_sql, tuple(values))
        db.commit()

        return jsonify({"success": True, "message": "Thêm câu hỏi vào đề thành công"}), 201

    except Exception:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)
