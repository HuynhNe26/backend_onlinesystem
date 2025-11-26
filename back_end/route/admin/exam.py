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
        cursor.execute("SELECT id_diff, difficulty FROM difficulty")  # chọn rõ cột
        diffs = cursor.fetchall()
        return jsonify({"success": True, "data": diffs})
    except Exception:
        import traceback
        print("Lỗi lấy difficulties:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()
# -------------------- Create exam --------------------
@exam_ad.route('/create', methods=['POST'])
def create_exam():
    db = cursor = None
    try:
        data = request.get_json()

        required_fields = ["id_class", "id_diff", "total_ques", "duration", "name_ex"]
        for field in required_fields:
            if field not in data or data[field] in [None, ""]:
                return jsonify({"success": False, "message": f"Thiếu {field}"}), 400

        db = get_db_connection()
        cursor = db.cursor()

        sql = """
            INSERT INTO exam (id_class, id_diff, total_ques, duration, name_ex, exam_cat)
            VALUES (%s, %s, %s, %s, %s, 'draft')
        """
        cursor.execute(sql, (
            int(data["id_class"]),
            int(data["id_diff"]),
            int(data["total_ques"]),
            int(data["duration"]),
            data["name_ex"]
        ))

        db.commit()
        new_exam_id = cursor.lastrowid

        return jsonify({
            "success": True,
            "message": "Tạo đề thành công",
            "id_ex": new_exam_id
        })

    except Exception:
        print("Lỗi:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)
@exam_ad.route('/add_question', methods=['POST'])
def add_question():
    db = cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "Không nhận được dữ liệu"}), 400

        # Các trường bắt buộc
        required_fields = ["ques_text", "ans_a", "ans_b", "ans_c", "ans_d", "correct_ans", "point"]
        for f in required_fields:
            if f not in data or str(data[f]).strip() == "":
                return jsonify({"success": False, "message": f"Thiếu {f}"}), 400

        # Convert point sang float
        try:
            point = float(data["point"])
        except ValueError:
            return jsonify({"success": False, "message": "point phải là số"}), 400

        db = get_db_connection()
        cursor = db.cursor()

        sql = """
            INSERT INTO questions
            (ques_text, ans_a, ans_b, ans_c, ans_d, correct_ans, point, explanation)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (
            data["ques_text"].strip(),
            data["ans_a"].strip(),
            data["ans_b"].strip(),
            data["ans_c"].strip(),
            data["ans_d"].strip(),
            data["correct_ans"].strip(),
            point,
            str(data.get("explanation", "")).strip()
        ))

        db.commit()
        new_id = cursor.lastrowid

        return jsonify({
            "success": True,
            "message": "Tạo câu hỏi thành công",
            "id_ques": new_id
        })

    except Exception as e:
        import traceback
        print("Lỗi add_question:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server: " + str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()
# -------------------- Gắn câu hỏi vào đề --------------------
@exam_ad.route('/add_exam_question', methods=['POST'])
def add_exam_question():
    db = cursor = None
    try:
        data = request.get_json()

        if "id_ex" not in data or "id_ques" not in data:
            return jsonify({"success": False, "message": "Thiếu id_ex hoặc id_ques"}), 400

        db = get_db_connection()
        cursor = db.cursor()

        sql = "INSERT INTO exam_question(id_ex, id_ques) VALUES (%s, %s)"
        cursor.execute(sql, (int(data["id_ex"]), int(data["id_ques"])))
        db.commit()

        return jsonify({"success": True, "message": "Gắn câu hỏi vào đề thành công"})

    except Exception:
        print("Lỗi add_exam_question:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server"}), 500
    finally:
        _close(cursor, db)
# -------------------- Quản lý đề thi --------------------
@exam_ad.route('/manage_exams', methods=['GET'])
def get_exams():
    db = cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        sql = """
            SELECT 
                e.id_ex,
                e.name_ex,
                e.id_class,
                e.id_diff,
                e.total_ques,
                e.duration,
                IFNULL(e.exam_cat,'') as exam_cat,
                e.start_time,
                e.end_time,
                IFNULL(c.class_name,'') as class_name,
                IFNULL(d.difficulty,'') as difficulty
            FROM exam e
            LEFT JOIN classroom c ON e.id_class = c.id_class
            LEFT JOIN difficulty d ON e.id_diff = d.id_diff
            ORDER BY e.id_ex DESC
        """
        cursor.execute(sql)
        exams = cursor.fetchall()

        return jsonify({"success": True, "data": exams})

    except Exception as e:
        import traceback
        print("Lỗi get_exams:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server: " + str(e)}), 500

    finally:
        _close(cursor, db)
@exam_ad.route('/exam_detail', methods=['GET'])
def exam_detail():
    db = cursor = None
    try:
        id_ex = request.args.get('id_ex', type=int)
        if not id_ex:
            return jsonify({"success": False, "message": "Thiếu id_ex"}), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Thông tin đề
        cursor.execute("""
            SELECT 
                e.id_ex, e.name_ex, e.id_class, e.id_diff, e.total_ques, e.duration,
                e.exam_cat, e.start_time, e.end_time,
                c.class_name, d.difficulty
            FROM exam e
            LEFT JOIN classroom c ON e.id_class = c.id_class
            LEFT JOIN difficulty d ON e.id_diff = d.id_diff
            WHERE e.id_ex = %s
        """, (id_ex,))
        exam = cursor.fetchone()
        if not exam:
            return jsonify({"success": False, "message": "Không tìm thấy đề"}), 404

        # Danh sách câu hỏi trong đề
        cursor.execute("""
            SELECT 
                q.id_ques, q.ques_text, q.ans_a, q.ans_b, q.ans_c, q.ans_d,
                q.correct_ans, q.point, q.explanation
            FROM exam_question eq
            JOIN questions q ON eq.id_ques = q.id_ques
            WHERE eq.id_ex = %s
            ORDER BY q.id_ques ASC
        """, (id_ex,))
        questions = cursor.fetchall()

        return jsonify({"success": True, "data": {"exam": exam, "questions": questions}})
    except Exception as e:
        import traceback
        print("Lỗi exam_detail:", traceback.format_exc())
        return jsonify({"success": False, "message": "Lỗi server: " + str(e)}), 500
    finally:
        if cursor: cursor.close()
        if db: db.close()
@exam_ad.route('/delete_exam', methods=['DELETE'])
def delete_exam():
    db = cursor = None
    try:
        data = request.get_json() or {}
        id_ex = data.get("id_ex", None)
        mode = (data.get("mode") or "keep_questions").strip()
        # mode: "keep_questions" (mặc định) hoặc "delete_questions"

        if not id_ex:
            return jsonify({"success": False, "message": "Thiếu id_ex"}), 400

        db = get_db_connection()
        cursor = db.cursor()
        db.start_transaction()

        # Lấy danh sách id_ques thuộc đề (phục vụ mode delete_questions)
        cursor.execute("SELECT id_ques FROM exam_question WHERE id_ex = %s", (int(id_ex),))
        ques_ids = [row[0] for row in cursor.fetchall()]

        # Xóa quan hệ câu hỏi-đề
        cursor.execute("DELETE FROM exam_question WHERE id_ex = %s", (int(id_ex),))
        # Xóa đề
        cursor.execute("DELETE FROM exam WHERE id_ex = %s", (int(id_ex),))

        if mode == "delete_questions" and ques_ids:
            # Chỉ xóa câu hỏi nếu không còn gắn ở đề khác
            # (tránh xóa nhầm câu hỏi đang dùng nơi khác)
            for qid in ques_ids:
                cursor.execute("SELECT COUNT(*) FROM exam_question WHERE id_ques = %s", (qid,))
                cnt = cursor.fetchone()[0]
                if cnt == 0:
                    cursor.execute("DELETE FROM questions WHERE id_ques = %s", (qid,))

        db.commit()
        return jsonify({"success": True, "message": "Xóa đề thi thành công", "mode": mode})
    except Exception as e:
        import traceback
        print("Lỗi delete_exam:", traceback.format_exc())
        if db: db.rollback()
        return jsonify({"success": False, "message": "Lỗi server: " + str(e)}), 500
    finally:
        if cursor: cursor.close()
        if db: db.close()


