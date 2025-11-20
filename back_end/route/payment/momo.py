import base64
import json
import time
import uuid
import hmac
import hashlib
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ...config.db_config import get_db_connection
import requests

momo_bp = Blueprint("momo_bp", __name__)

MOMO_CONFIG = {
    "endpoint": "https://test-payment.momo.vn/v2/gateway/api/create",
    "partnerCode": "MOMOT5BZ20231213_TEST",
    "accessKey": "F8BBA842ECF85",
    "secretKey": "K951B6PE1waDMi640xX08PD3vg6EkVlz",
    "redirectUrl": "https://frontend-admin-onlinesystem-eugd.onrender.com/payment-success",
    "ipnUrl": "https://uninclined-overhonestly-jone.ngrok-free.dev/api/payment/momo/ipn"
}

def get_current_user_id():
    identity = get_jwt_identity()
    if isinstance(identity, dict):
        return identity.get("id") or identity.get("id_user")
    try:
        return int(identity)
    except:
        return identity

def generate_momo_signature(params, secret_key):
    # Chú ý: thứ tự fields phải đúng như MoMo yêu cầu
    raw_signature = (
        f"accessKey={params['accessKey']}"
        f"&amount={params['amount']}"
        f"&extraData={params['extraData']}"
        f"&ipnUrl={params['ipnUrl']}"
        f"&orderId={params['orderId']}"
        f"&orderInfo={params['orderInfo']}"
        f"&partnerCode={params['partnerCode']}"
        f"&redirectUrl={params['redirectUrl']}"
        f"&requestId={params['requestId']}"
        f"&requestType={params['requestType']}"
    )
    return hmac.new(secret_key.encode(), raw_signature.encode(), hashlib.sha256).hexdigest()

@momo_bp.route("/momo", methods=["POST"])
@jwt_required()
def momo_payment():
    conn = cursor = None
    try:
        user_id = get_current_user_id()
        data = request.json
        required_fields = ["price_month", "name_package", "id_package"]
        if not data:
            return jsonify({"success": False, "message": "Không có dữ liệu."}), 400
        missing = [f for f in required_fields if f not in data]
        if missing:
            return jsonify({"success": False, "message": f"Thiếu: {', '.join(missing)}"}), 400

        price = str(int(data["price_month"]))  # MoMo muốn string
        id_package = data["id_package"]
        name_package = data.get("name_package", f"Thanh toán gói {id_package}")

        # ExtraData phải base64 encode
        extra_data_dict = {"id_package": id_package, "id_user": user_id}
        extra_data = base64.b64encode(
            json.dumps(extra_data_dict, separators=(',', ':')).encode()
        ).decode()

        request_id = f"{MOMO_CONFIG['partnerCode']}_{int(time.time() * 1000)}"
        order_id = str(uuid.uuid4()).replace('-', '')[:12]

        params = {
            "partnerCode": MOMO_CONFIG["partnerCode"],
            "accessKey": MOMO_CONFIG["accessKey"],
            "requestId": request_id,
            "amount": price,
            "orderId": order_id,
            "orderInfo": name_package,
            "redirectUrl": MOMO_CONFIG["redirectUrl"],
            "ipnUrl": MOMO_CONFIG["ipnUrl"],
            "extraData": extra_data,
            "requestType": "captureWallet",
        }

        signature = generate_momo_signature(params, MOMO_CONFIG["secretKey"])
        payload = {**params, "signature": signature, "lang": "vi"}

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            INSERT INTO payment (id_user, id_package, id_order, amount, status, payment, code, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (user_id, id_package, order_id, price, "Đang giao dịch", "momo", None)
        )
        conn.commit()

        # Gửi request MoMo
        resp = requests.post(MOMO_CONFIG["endpoint"], json=payload, timeout=10)
        result = resp.json()

        if result.get("resultCode") == 0 and result.get("payUrl"):
            return jsonify({"success": True, "payUrl": result["payUrl"], "orderId": order_id}), 200
        else:
            return jsonify({"success": False, "message": result.get("message","Lỗi tạo link"), "resultCode": result.get("resultCode")}), 400

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"success": False, "message": f"Lỗi hệ thống: {str(e)}"}), 500
    finally:
        if cursor: cursor: cursor.close()
        if conn: conn: conn.close()


# ---- IPN MoMo ----
@momo_bp.route("/momo/ipn", methods=["POST"])
def momo_ipn():
    conn = cursor = None
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No IPN data"}), 400
        if not verify_momo_signature(data, MOMO_CONFIG["secretKey"]):
            return jsonify({"success": False, "message": "Invalid signature"}), 403

        order_id = data["orderId"]
        result_code = data["resultCode"]
        trans_id = data.get("transId")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM payment WHERE id_order=%s", (order_id,))
        tx = cursor.fetchone()
        if not tx:
            return jsonify({"success": False, "message": "Order not found"}), 404

        status = "success" if str(result_code) == "0" else "failed"
        cursor.execute("UPDATE payment SET status=%s, code=%s WHERE id_order=%s",
                       ("Giao dịch thành công" if status=="success" else "Giao dịch thất bại", trans_id, order_id))

        if status == "success":
            id_user = tx["id_user"]
            id_package = tx["id_package"]

            cursor.execute("SELECT * FROM package WHERE id_package=%s", (id_package,))
            pkg = cursor.fetchone()
            if not pkg: conn.rollback(); return jsonify({"success": False, "message": "Package not found"}), 404

            if id_package == 1: duration=0; quantity=1
            elif id_package == 2: duration=30; quantity=10
            elif id_package == 3: duration=30; quantity=20
            else: duration=0; quantity=1

            cursor.execute("""
                UPDATE users
                SET id_package=%s,
                    start_package=NOW(),
                    end_package=DATE_ADD(NOW(), INTERVAL %s DAY),
                    quantity_exam=%s
                WHERE id_user=%s
            """, (id_package, duration, quantity, id_user))

        conn.commit()
        return jsonify({"resultCode": 0, "message": "IPN handled successfully", "orderId": order_id}), 200

    except Exception as e:
        if conn: conn.rollback()
        logging.error(str(e))
        return jsonify({"success": False, "message": f"IPN Error: {str(e)}"}), 500
    finally:
        if cursor: cursor: cursor.close()
        if conn: conn: conn.close()

# ---- Check status MoMo ----
@momo_bp.route("/momo/check-status/<order_id>", methods=["GET"])
@jwt_required()
def check_payment_status(order_id):
    conn = cursor = None
    try:
        user_id = get_current_user_id()
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.*, pkg.name_package
            FROM payment p
            LEFT JOIN package pkg ON p.id_package=pkg.id_package
            WHERE p.id_order=%s AND p.id_user=%s
        """, (order_id, user_id))
        tx = cursor.fetchone()
        if not tx: return jsonify({"success": False, "message": "Không tìm thấy giao dịch"}), 404
        result = {
            "orderId": tx["id_order"],
            "amount": tx["amount"],
            "status": tx["status"],
            "paymentMethod": tx["payment"],
            "packageName": tx["name_package"],
            "duration": tx.get("duration"),
            "createdAt": tx["created_at"].isoformat() if tx["created_at"] else None,
            "code": tx["code"]
        }
        return jsonify({"success": True, "transaction": result}), 200
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi kiểm tra trạng thái: {str(e)}"}), 500
    finally:
        if cursor: cursor: cursor.close()
        if conn: conn: conn.close()
