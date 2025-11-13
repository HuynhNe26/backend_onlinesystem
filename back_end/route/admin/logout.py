from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import mysql.connector

logout_bp = Blueprint('logout', __name__)

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Anhkiet3307*",
        database="online_testing"
    )

@logout_bp.route('', methods=['POST'])
@jwt_required()
def logout_admin():
    try:
        # Lấy id_user từ identity, ép về int
        user_id = int(get_jwt_identity())

        db = get_db()
        cursor = db.cursor(dictionary=True)

        update_logout = """
            UPDATE users
            SET logout_time = NOW()
            WHERE id_user = %s
        """
        cursor.execute(update_logout, (user_id,))
        db.commit()

        return jsonify({"msg": "Đăng xuất thành công!", "user_id": user_id}), 200

    except Exception as e:
        print("Logout error:", e)
        return jsonify({"msg": "Lỗi server"}), 500

    finally:
        cursor.close()
        db.close()