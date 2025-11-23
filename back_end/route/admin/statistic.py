from flask import Blueprint, jsonify
from ...config.db_config import get_db_connection
from flask import request

statistic = Blueprint('statistic', __name__)

statistic.route("/user", methods=['GET'])
def getUser():
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute('SELECT * FROM users WHERE level = 1')
        users = cursor.fetchall()

        if not users:
            return jsonify({"msg": "Không có dữ liệu người dùng"}), 404

        return jsonify({"success": True, "data": users}), 200

    except Exception as e:
        print("Lỗi lấy dữ liệu:", e)
        return jsonify({"msg": "Lỗi server"}), 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()