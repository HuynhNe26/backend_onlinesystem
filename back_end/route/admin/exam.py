from flask import Blueprint, jsonify
from ...config.db_config import get_db_connection

exam_bp = Blueprint('exam_bp', __name__)

# --- 1. Tạo đề thi ---
@exam_bp.route('/admin/exam', methods=['POST'])
def create_exam():
    """
    Admin tạo đề thi mới
    """
    from flask import request
    db = None
    cursor = None
    try:
        data = request.get_json()
        # Nhận dữ liệu từ frontend
        name_ex = data['name_ex']
        total_ques = data['total_ques']
        duration = data['duration']   # phút
        id_user = data['id_user']     # admin tạo đề

        db = get_db_connection()
        cursor = db.cursor()

        sql = "INSERT INTO exam (name_ex, total_ques, duration, id_user) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql, (name_ex, total_ques, duration, id_user))
        db.commit()

        exam_id = cursor.lastrowid
        return jsonify({"msg": "Tạo đề thành công", "exam_id": exam_id}), 201

    except Exception as e:
        print("Lỗi tạo đề:", e)
        return jsonify({"msg": "Lỗi server"}), 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

# --- 2. Thêm câu hỏi ---
@exam_bp.route('/admin/question', methods=['POST'])
def add_question():
    """
    Admin thêm câu hỏi mới
    """
    from flask import request
    db = None
    cursor = None
    try:
        data = request.get_json()
        id_category = data['id_category']
        ques_text = data['ques_text']
        ans_a = data['ans_a']
        ans_b = data['ans_b']
        ans_c = data.get('ans_c')
        ans_d = data.get('ans_d')
        correct_ans = data['correct_ans']
        point = data['point']
        explanation = data['explanation']
        id_diff = data['id_diff']
        id_user = data['id_user']

        db = get_db_connection()
        cursor = db.cursor()

        sql = """INSERT INTO questions (id_category, ques_text, ans_a, ans_b, ans_c, ans_d, correct_ans, point, explanation, id_diff, id_user)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
        cursor.execute(sql, (id_category, ques_text, ans_a, ans_b, ans_c, ans_d, correct_ans, point, explanation, id_diff, id_user))
        db.commit()
        question_id = cursor.lastrowid

        return jsonify({"msg": "Thêm câu hỏi thành công", "question_id": question_id}), 201

    except Exception as e:
        print("Lỗi thêm câu hỏi:", e)
        return jsonify({"msg": "Lỗi server"}), 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

# --- 3. Chọn câu hỏi vào đề ---
@exam_bp.route('/admin/exam/<int:exam_id>/questions', methods=['POST'])
def add_questions_to_exam(exam_id):
    """
    Admin tick chọn các câu hỏi cho đề thi
    """
    from flask import request
    db = None
    cursor = None
    try:
        data = request.get_json()
        question_ids = data['question_ids']  # list of question IDs

        db = get_db_connection()
        cursor = db.cursor()

        for qid in question_ids:
            sql = "INSERT INTO exam_question (id_ex, id_ques) VALUES (%s, %s)"
            cursor.execute(sql, (exam_id, qid))
        db.commit()

        return jsonify({"msg": "Thêm câu hỏi vào đề thành công"}), 201

    except Exception as e:
        print("Lỗi thêm câu vào đề:", e)
        return jsonify({"msg": "Lỗi server"}), 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()

# --- 4. Lấy danh sách câu hỏi trong đề ---
@exam_bp.route('/admin/exam/<int:exam_id>/questions', methods=['GET'])
def get_exam_questions(exam_id):
    """
    Lấy danh sách câu hỏi của đề thi
    """
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        sql = """SELECT q.* 
                 FROM questions q
                 JOIN exam_question eq ON q.id_ques = eq.id_ques
                 WHERE eq.id_ex = %s"""
        cursor.execute(sql, (exam_id,))
        questions = cursor.fetchall()

        return jsonify({"questions": questions}), 200

    except Exception as e:
        print("Lỗi lấy câu hỏi:", e)
        return jsonify({"msg": "Lỗi server"}), 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()
