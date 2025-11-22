
from flask import Blueprint, request, jsonify
from ...config.db_config import get_db_connection

users_ad = Blueprint('users_ad', __name__)

@users_ad.route("/users", methods=['GET'])
def getAllUser():
    db = None
    cursor = None
    try:
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM users WHERE level = 1")
        
        users = cursor.fetchall()
        
        if not users:
            return jsonify({'msg':'Lỗi lấy thông tin người dùng!'}), 400
        
        return jsonify({"success": True, "data": users}), 200
    
    except Exception as e:
        print("Lỗi lấy dữ liệu:", e)
        return jsonify({"msg": "Lỗi server"}), 500

    finally:
        if cursor:
            cursor.close()
        if db:
            db.close()