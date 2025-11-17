from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ...config.db_config import get_db_connection
from datetime import datetime

exam_bp = Blueprint('exam_bp', __name__)

def get_current_user_id():
    identity = get_jwt_identity()
    if isinstance(identity, dict):
        return identity.get("id") or identity.get("id_user")
    try:
        return int(identity)
    except (ValueError, TypeError):
        return identity


@exam_bp.route("/departments", methods=["GET"])
def get_departments():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id_department, name_department 
            FROM department
            WHERE status = 'Đang hoạt động'
        """)
        data = cursor.fetchall()
        return jsonify({"success": True, "departments": data}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@exam_bp.route("/departments/<int:dept_id>/classes", methods=["GET"])
def get_classes(dept_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id_class, class_name
            FROM classroom
            WHERE id_department = %s
        """, (dept_id,))
        data = cursor.fetchall()
        return jsonify({"success": True, "classes": data}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@exam_bp.route("/classes/<int:class_id>/exams", methods=["GET"])
def get_exams_by_class(class_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id_ex, name_ex, total_ques, duration
            FROM exam
            WHERE id_class = %s
            ORDER BY id_ex DESC
        """, (class_id,))
        data = cursor.fetchall()
        return jsonify({"success": True, "exams": data}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@exam_bp.route("/exams/<int:exam_id>/detail", methods=["GET"])
@jwt_required()
def get_exam_detail(exam_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id_ex, name_ex, total_ques, duration FROM exam WHERE id_ex=%s", (exam_id,))
        exam_info = cursor.fetchone()
        if not exam_info:
            return jsonify({"success": False, "message": "Không tìm thấy đề thi"}), 404

        cursor.execute("""
            SELECT q.id_ques, q.ques_text, q.ans_a, q.ans_b, q.ans_c, q.ans_d,
                   q.correct_ans, q.explanation
            FROM exam_question eq
            JOIN questions q ON q.id_ques = eq.id_ques
            WHERE eq.id_ex = %s
            ORDER BY eq.id_inter ASC
        """, (exam_id,))
        questions = cursor.fetchall()

        return jsonify({"success": True, "exam": exam_info, "questions": questions}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@exam_bp.route("/exams/<int:exam_id>/submit", methods=["POST"])
@jwt_required()
def submit_exam(exam_id):
    user_id = get_current_user_id()
    data = request.get_json()
    answers = data.get("answers", [])
    start_time = data.get("start_time")

    if not answers or not start_time:
        return jsonify({"success": False, "message": "Dữ liệu không hợp lệ"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id_ex, name_ex, total_ques FROM exam WHERE id_ex=%s", (exam_id,))
        exam = cursor.fetchone()
        if not exam:
            return jsonify({"success": False, "message": "Đề thi không tồn tại"}), 404

        total_questions = exam['total_ques']
        total_correct = 0

        for ans in answers:
            question_id = ans['id_ques']
            user_answer = ans['answer']
            cursor.execute("SELECT correct_ans FROM questions WHERE id_ques=%s", (question_id,))
            q = cursor.fetchone()
            if q and q['correct_ans'] == user_answer:
                total_correct += 1

        score = round((total_correct / total_questions) * 100)
        now = datetime.now()

        cursor.execute("""
            INSERT INTO result 
            (user_id, exam_id, score, total_correct, total_questions, start_time, end_time, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (user_id, exam_id, score, total_correct, total_questions, start_time, now, now))
        result_id = cursor.lastrowid

        for ans in answers:
            cursor.execute("""
                INSERT INTO answer (result_id, question_id, user_answer)
                VALUES (%s, %s, %s)
            """, (result_id, ans['id_ques'], ans['answer']))

        conn.commit()
        return jsonify({
            "success": True,
            "result": {
                "id_result": result_id,
                "score": score,
                "total_correct": total_correct,
                "total_questions": total_questions,
                "exam_name": exam.get('name_ex', 'Đề thi')
            }
        }), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@exam_bp.route("/exam/history", methods=["GET"])
@jwt_required()
def exam_history():
    user_id = get_current_user_id()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT er.id_result, e.name_ex AS exam_name, er.score, er.total_correct, er.total_questions, er.created_at
            FROM exam_result er
            JOIN exam e ON e.id_ex = er.exam_id
            WHERE er.user_id = %s
            ORDER BY er.created_at DESC
        """, (user_id,))
        results = cursor.fetchall()
        return jsonify({"success": True, "history": results}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()