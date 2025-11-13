from flask import Blueprint, jsonify
from ...config.db_config import get_db_connection

admin_bp = Blueprint('admin_bp', __name__)

@admin_bp.route('/dashboard', methods=['GET'])
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM exam")
    total_exams = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM department")
    total_departments = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payment")
    revenue = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return jsonify({
        "totalUsers": total_users,
        "totalExams": total_exams,
        "totalDepartments": total_departments,
        "revenue": revenue
    })
