from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

classroom_bp = Blueprint('classroom_bp', __name__)

def get_current_user_id():
    identity = get_jwt_identity()

    if isinstance(identity, dict):
        return identity.get("id") or identity.get("id_user")

    try:
        return int(identity)
    except (ValueError, TypeError):
        return identity

@classroom_bp.route('/exam', methods=['POST'])
def register():
    data = request.get_json()
    required_fields = ["fullName", "username", "email", "password", "gender"]
    if not all(field in data for field in required_fields):
        return jsonify({"success": False, "message": "Thiếu dữ liệu."}), 400

    success, message = create_user(
        data["fullName"],
        data["username"],
        data["email"],
        data["password"],
        data["gender"],
        data.get("avatar"),
        data.get("birth_date")
    )
    return jsonify({"success": success, "message": message}), 200 if success else 400