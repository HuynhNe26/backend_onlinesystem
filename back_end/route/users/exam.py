from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ...config.db_config import get_db_connection
from datetime import datetime

exam_bp = Blueprint("exam_bp", __name__)

def get_current_user_id():
    identity = get_jwt_identity()

    if isinstance(identity, dict):
        return identity.get("id") or identity.get("user_id") or identity.get("id_user")

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
        return jsonify({"success": True, "departments": cursor.fetchall()}), 200
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
        return jsonify({"success": True, "classes": cursor.fetchall()}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ----------------------------------------------------------
# LẤY DANH SÁCH ĐỀ THEO LỚP
# ----------------------------------------------------------
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
        return jsonify({"success": True, "exams": cursor.fetchall()}), 200
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

        return jsonify({
            "success": True,
            "exam": exam_info,
            "questions": cursor.fetchall()
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
    finally:
        cursor.close()
        conn.close()

@exam_bp.route("/exams/<int:exam_id>/submit", methods=["POST"])
@jwt_required()
def submit_exam(exam_id):
    user_id = get_current_user_id()

    if not user_id:
        return jsonify({"success": False, "message": "User ID trong token không hợp lệ"}), 400

    data = request.get_json()
    answers = data.get("answers")
    start_time = data.get("start_time")

    if not answers or not start_time:
        return jsonify({"success": False, "message": "Dữ liệu gửi lên không hợp lệ"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id_ex, name_ex, total_ques FROM exam WHERE id_ex=%s", (exam_id,))
        exam = cursor.fetchone()

        if not exam:
            return jsonify({"success": False, "message": "Đề thi không tồn tại"}), 404

        total_questions = exam["total_ques"]
        total_correct = 0

        for ans in answers:
            qid = ans["id_ques"]
            user_answer = ans["answer"]

            cursor.execute("SELECT correct_ans FROM questions WHERE id_ques=%s", (qid,))
            q = cursor.fetchone()

            if q and q["correct_ans"] == user_answer:
                total_correct += 1

        score = round((total_correct / total_questions) * 100)
        now = datetime.now()

        cursor.execute("""
            INSERT INTO results
            (id_user, id_ex, score, total_correct, start_time, completed_time)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            user_id, exam_id, score, total_correct, start_time, now
        ))

        result_id = cursor.lastrowid

        for ans in answers:
            qid = ans["id_ques"]
            user_answer = ans["answer"]

            cursor.execute("SELECT correct_ans FROM questions WHERE id_ques=%s", (qid,))
            q = cursor.fetchone()
            is_correct = (q["correct_ans"] == user_answer)

            cursor.execute("""
                SELECT id_inter FROM exam_question WHERE id_ex=%s AND id_ques=%s
            """, (exam_id, qid))
            inter = cursor.fetchone()
            id_inter = inter["id_inter"] if inter else 0

            cursor.execute("""
                INSERT INTO answer 
                (id_ques, answer, id_ex, is_correct, id_user, id_inter, create_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (qid, user_answer, exam_id, is_correct, user_id, id_inter, now))

        conn.commit()

        return jsonify({
            "success": True,
            "result": {
                "id_result": result_id,
                "score": score,
                "total_correct": total_correct,
                "total_questions": total_questions,
                "exam_name": exam["name_ex"]
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
            SELECT r.id_result, e.name_ex AS exam_name,
                   r.score, r.total_correct,
                   r.start_time, r.completed_time
            FROM results r
            JOIN exam e ON e.id_ex = r.id_ex
            WHERE r.id_user = %s
            ORDER BY r.completed_time DESC
        """, (user_id,))

        return jsonify({
            "success": True,
            "history": cursor.fetchall()
        }), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()