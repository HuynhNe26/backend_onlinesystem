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

@exam_bp.route('/categories', methods=['GET'])
def get_categories():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id_category, name_category FROM categories")
        categories = cursor.fetchall()
        return jsonify({"success": True, "categories": categories}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@exam_bp.route('/difficulty', methods=['GET'])
def get_difficulty():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id_diff, difficulty FROM difficulty")
        difficulties = cursor.fetchall()
        return jsonify({"success": True, "difficulties": difficulties}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@exam_bp.route('/exam/create', methods=['POST'])
@jwt_required()
def create_exam():
    user_id = get_current_user_id()
    data = request.get_json()
    category_id = data.get('category_id')
    difficulty_id = data.get('difficulty_id')
    num_questions = data.get('num_questions', 10)

    if not category_id or not difficulty_id or not num_questions:
        return jsonify({"success": False, "message": "Thiếu thông tin"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id_ques, ques_text, ans_a, ans_b, ans_c, ans_d
            FROM questions
            WHERE id_category = %s AND id_diff = %s
            ORDER BY RAND()
            LIMIT %s
        """, (category_id, difficulty_id, num_questions))
        questions = cursor.fetchall()

        if len(questions) < num_questions:
            return jsonify({
                "success": False,
                "message": f"Chỉ có {len(questions)} câu hỏi phù hợp."
            }), 400

        duration_minutes = num_questions
        cursor.execute("SELECT name_category FROM categories WHERE id_category = %s", (category_id,))
        category_name = cursor.fetchone()['name_category']
        exam_name = f"Bài kiểm tra {category_name}"

        cursor.execute("""
            INSERT INTO exam (total_ques, duration, name_ex, id_user)
            VALUES (%s, %s, %s, %s)
        """, (num_questions, duration_minutes, exam_name, user_id))

        exam_id = cursor.lastrowid

        for q in questions:
            cursor.execute("INSERT INTO exam_question (id_ex, id_ques) VALUES (%s, %s)", (exam_id, q['id_ques']))

        conn.commit()

        return jsonify({
            "success": True,
            "message": "Tạo đề thi thành công",
            "exam": {
                "id_ex": exam_id,
                "name_ex": exam_name,
                "total_ques": num_questions,
                "duration": duration_minutes,
                "questions": questions
            }
        }), 200

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@exam_bp.route('/exam/<int:exam_id>/question/<int:question_index>', methods=['GET'])
@jwt_required()
def get_exam_question(exam_id, question_index):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id_ex, name_ex, total_ques, duration FROM exam WHERE id_ex = %s", (exam_id,))
        exam_info = cursor.fetchone()
        if not exam_info:
            return jsonify({"success": False, "message": "Không tìm thấy bài thi"}), 404

        cursor.execute("""
            SELECT q.id_ques, q.ques_text, q.ans_a, q.ans_b, q.ans_c, q.ans_d
            FROM exam_question eq
            JOIN questions q ON eq.id_ques = q.id_ques
            WHERE eq.id_ex = %s
            ORDER BY eq.id_inter ASC
        """, (exam_id,))
        questions = cursor.fetchall()
        if not questions or question_index < 0 or question_index >= len(questions):
            return jsonify({"success": False, "message": "Câu hỏi không hợp lệ"}), 400

        return jsonify({
            "success": True,
            "exam_info": exam_info,
            "current_index": question_index,
            "total_questions": len(questions),
            "question": questions[question_index],
            "is_last": question_index == len(questions) - 1
        }), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@exam_bp.route('/exam/submit', methods=['POST'])
@jwt_required()
def submit_exam():
    user_id = get_current_user_id()
    data = request.get_json()
    exam_id = data.get('exam_id')
    answers = data.get('answers', [])
    start_time = data.get('start_time')

    if not exam_id or not isinstance(answers, list):
        return jsonify({"success": False, "message": "Dữ liệu không hợp lệ"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT q.id_ques, q.correct_ans, eq.id_inter
            FROM questions q
            JOIN exam_question eq ON q.id_ques = eq.id_ques
            WHERE eq.id_ex = %s
        """, (exam_id,))
        correct_answers = cursor.fetchall()
        correct_dict = {q['id_ques']: {'correct_ans': q['correct_ans'], 'id_inter': q['id_inter']} for q in correct_answers}

        total_correct = 0
        for ans in answers:
            qid = ans.get('id_ques')
            user_ans = str(ans.get('answer', '')).strip().lower()
            if qid in correct_dict:
                correct = str(correct_dict[qid]['correct_ans']).strip().lower()
                is_correct = (user_ans == correct)
                if is_correct: total_correct += 1
                cursor.execute("""
                    INSERT INTO answer (id_ques, answer, id_ex, is_correct, id_user, id_inter, create_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """, (qid, ans.get('answer'), exam_id, is_correct, user_id, correct_dict[qid]['id_inter']))

        total_questions = len(correct_answers)
        score = round((total_correct / total_questions) * 100) if total_questions > 0 else 0
        cursor.execute("SELECT name_ex FROM exam WHERE id_ex = %s", (exam_id,))
        exam_name = cursor.fetchone()['name_ex']
        cursor.execute("""
            INSERT INTO results (id_user, id_ex, score, total_correct, start_time, completed_time, status, exam_cat)
            VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s)
        """, (user_id, exam_id, score, total_correct, start_time or datetime.now(), 'Hoàn thành', exam_name))
        conn.commit()

        return jsonify({
            "success": True,
            "message": "Nộp bài thành công!",
            "result": {"score": score, "total_correct": total_correct, "total_questions": total_questions, "exam_name": exam_name}
        }), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@exam_bp.route('/result/<int:result_id>', methods=['GET'])
@jwt_required()
def get_result_detail(result_id):
    user_id = get_current_user_id()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT r.*, e.name_ex, e.total_ques
            FROM results r
            JOIN exam e ON r.id_ex = e.id_ex
            WHERE r.id_result = %s AND r.id_user = %s
        """, (result_id, user_id))
        result = cursor.fetchone()
        if not result:
            return jsonify({"success": False, "message": "Không tìm thấy kết quả"}), 404
        cursor.execute("""
            SELECT a.id_ques, a.answer, a.is_correct, q.ques_text, q.correct_ans, q.explanation
            FROM answer a
            JOIN questions q ON a.id_ques = q.id_ques
            WHERE a.id_ex = %s AND a.id_user = %s
            ORDER BY a.create_at
        """, (result['id_ex'], user_id))
        answers = cursor.fetchall()
        return jsonify({"success": True, "result": result, "answers": answers}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@exam_bp.route('/exam/history', methods=['GET'])
@jwt_required()
def get_exam_history():
    user_id = get_current_user_id()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT r.id_result, r.score, r.total_correct, r.completed_time, r.exam_cat, e.name_ex, e.total_ques
            FROM results r
            JOIN exam e ON r.id_ex = e.id_ex
            WHERE r.id_user = %s
            ORDER BY r.completed_time DESC
        """, (user_id,))
        history = cursor.fetchall()
        return jsonify({"success": True, "history": history}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        cursor.close()
        conn.close()