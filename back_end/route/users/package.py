from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ...config.db_config import get_db_connection

package_bp = Blueprint('package_bp', __name__)


@package_bp.route('/packages', methods=['GET'])
def get_all_packages():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM package ORDER BY id_package")
        packages = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "msg": "Lấy danh sách package thành công",
            "data": packages,
            "total": len(packages)
        }), 200

    except Exception as e:
        print("Error getting packages:", e)
        return jsonify({"msg": "Lỗi server khi lấy danh sách package"}), 500


@package_bp.route('/packages/<int:package_id>', methods=['GET'])
def get_package_by_id(package_id):
    """
    Lấy thông tin chi tiết 1 package theo ID
    Endpoint: GET /api/packages/<id>
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM package WHERE id_package = %s", (package_id,))
        package = cursor.fetchone()

        cursor.close()
        conn.close()

        if not package:
            return jsonify({"msg": "Không tìm thấy package"}), 404

        return jsonify({
            "msg": "Lấy thông tin package thành công",
            "data": package
        }), 200

    except Exception as e:
        print("Error getting package:", e)
        return jsonify({"msg": "Lỗi server khi lấy thông tin package"}), 500
