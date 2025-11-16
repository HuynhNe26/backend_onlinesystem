from flask import Blueprint, jsonify
from ...config.db_config import get_db_connection

admin_bp = Blueprint('admin_bp', __name__)

@admin_bp.route('/admin', methods=['GET'])
def getAdllAdmin():
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute('SELECT * FROM users WHERE level >= 2')
        admins = cursor.fetchall()

        if not admins:
            return jsonify({"msg": "Không có dữ liệu quản trị viên"}), 404

        return jsonify({"data": admins}), 200

    except Exception as e:
        print("Lỗi lấy dữ liệu:", e)
        return jsonify({"msg": "Lỗi server"}), 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()
