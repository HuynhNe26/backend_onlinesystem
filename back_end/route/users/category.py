from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from ...config.db_config import get_db_connection

category_bp = Blueprint('category_bp', __name__)

@category_bp.route('/categories', methods=['GET'])
@jwt_required()
def get_all_categories():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM categories")
        categories = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({"success": True, "categories": categories}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
