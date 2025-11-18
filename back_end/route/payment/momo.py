from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import hmac
import hashlib
import json
import requests
import uuid
import time
from ...config.db_config import get_db_connection

momo_bp = Blueprint("momo_bp", __name__)

MOMO_CONFIG = {
    "endpoint": "https://test-payment.momo.vn/v2/gateway/api/create",
    "partnerCode": "MOMO",
    "accessKey": "F8BBA842ECF85",
    "secretKey": "K951B6PE1waDMi640xX08PD3vg6EkVlz",
    "redirectUrl": "https://frontend-admin-onlinesystem-eugd.onrender.com/payment-success/",
    "ipnUrl": "https://backend-onlinesystem.onrender.com/api/payment/momo/ipn"
}

def log(msg, data=None):
    print(f"=== LOG === {msg}")
    if data is not None:
        print(json.dumps(data, indent=2, ensure_ascii=False))

def get_current_user_id():
    identity = get_jwt_identity()
    if isinstance(identity, dict):
        return identity.get("id") or identity.get("id_user")
    try:
        return int(identity)
    except (ValueError, TypeError):
        return identity

def generate_momo_signature(params, secret_key):
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
    signature = hmac.new(
        secret_key.encode("utf-8"),
        raw_signature.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    log("Generated signature", {"raw": raw_signature, "signature": signature})
    return signature

def verify_momo_signature(data, secret_key):
    received_signature = data.get("signature", "")
    raw_data = (
        f"accessKey={data.get('accessKey')}"
        f"&amount={data.get('amount')}"
        f"&extraData={data.get('extraData')}"
        f"&message={data.get('message')}"
        f"&orderId={data.get('orderId')}"
        f"&orderInfo={data.get('orderInfo')}"
        f"&orderType={data.get('orderType')}"
        f"&partnerCode={data.get('partnerCode')}"
        f"&payType={data.get('payType')}"
        f"&requestId={data.get('requestId')}"
        f"&responseTime={data.get('responseTime')}"
        f"&resultCode={data.get('resultCode')}"
        f"&transId={data.get('transId')}"
    )
    expected_signature = hmac.new(
        secret_key.encode('utf-8'),
        raw_data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    log("Verifying signature", {"received": received_signature, "expected": expected_signature})
    return hmac.compare_digest(received_signature, expected_signature)

@momo_bp.route("/momo", methods=["POST"])
@jwt_required()
def momo_payment():
    conn = None
    cursor = None
    try:
        id_user = get_current_user_id()
        data = request.json
        log("Received /momo request", data)

        required_fields = ["price_month", "name_package", "id_package"]
        if not data:
            return jsonify({"success": False, "message": "Không có dữ liệu được gửi lên."}), 400
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({"success": False, "message": f"Thiếu thông tin: {', '.join(missing_fields)}"}), 400

        price_month = int(data.get("price_month"))
        id_package = data.get("id_package")
        name_package = data.get("name_package", f"Thanh toán gói {id_package}")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        request_id = f"{MOMO_CONFIG['partnerCode']}_{int(time.time() * 1000)}"
        order_id = str(uuid.uuid4()).replace('-', '')[:12]
        extra_data = json.dumps({"id_package": id_package, "id_user": id_user})

        params = {
            "accessKey": MOMO_CONFIG["accessKey"],
            "amount": str(price_month),
            "extraData": extra_data,
            "ipnUrl": MOMO_CONFIG["ipnUrl"],
            "orderId": order_id,
            "orderInfo": name_package,
            "partnerCode": MOMO_CONFIG["partnerCode"],
            "redirectUrl": MOMO_CONFIG["redirectUrl"],
            "requestId": request_id,
            "requestType": "captureWallet"
        }

        signature = generate_momo_signature(params, MOMO_CONFIG["secretKey"])
        payload = {**params, "signature": signature, "lang": "vi"}
        log("Sending payload to MoMo", payload)

        cursor.execute("""
            INSERT INTO payment
            (id_user, id_package, id_order, amount, duration, status, payment, code, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (id_user, id_package, order_id, price_month, None, "Đang giao dịch", "momo", None))
        conn.commit()

        response = requests.post(MOMO_CONFIG["endpoint"], json=payload, timeout=10, headers={"Content-Type": "application/json"})
        log("MoMo response", response.json())
        result = response.json()
        result_code = result.get("resultCode")
        if result_code == 0 and result.get("payUrl"):
            return jsonify({"success": True, "payUrl": result["payUrl"], "orderId": order_id, "message": "Tạo link thanh toán thành công."}), 200
        else:
            return jsonify({"success": False, "message": result.get("message", "Không thể tạo link thanh toán."), "resultCode": result_code}), 400
    except Exception as e:
        log("Error in /momo", str(e))
        if conn: conn.rollback()
        return jsonify({"success": False, "message": f"Lỗi hệ thống: {str(e)}"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@momo_bp.route("/momo/ipn", methods=["POST"])
def momo_ipn():
    conn = None
    cursor = None
    try:
        data = request.get_json() or request.form.to_dict()
        log("Received IPN", data)

        if not data:
            return jsonify({"success": False, "message": "Không có dữ liệu IPN."}), 400
        if not verify_momo_signature(data, MOMO_CONFIG["secretKey"]):
            return jsonify({"success": False, "message": "Chữ ký không hợp lệ."}), 403

        order_id = data.get("orderId")
        result_code = data.get("resultCode")
        trans_id = data.get("transId")
        log(f"Processing IPN for order {order_id}", data)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM payment WHERE id_order = %s", (order_id,))
        tx = cursor.fetchone()
        if not tx:
            return jsonify({"success": False, "message": "Giao dịch không tồn tại."}), 404

        status = "success" if result_code == 0 else "failed"
        cursor.execute("UPDATE payment SET status=%s, code=%s, updated_at=NOW() WHERE id_order=%s",
                       ("Giao dịch thành công!" if status=="success" else "Giao dịch thất bại", trans_id, order_id))

        if status == "success":
            id_user = tx["id_user"]
            id_package = tx["id_package"]
            cursor.execute("SELECT * FROM package WHERE id_package=%s", (id_package,))
            pkg = cursor.fetchone()
            duration, quantity = (0,1) if id_package==1 else (30,10) if id_package==2 else (30,20)
            cursor.execute("""
                UPDATE users
                SET id_package=%s, start_package=NOW(), end_package=DATE_ADD(NOW(), INTERVAL %s DAY), quantity_exam=%s
                WHERE id_user=%s
            """, (id_package, duration, quantity, id_user))

        conn.commit()
        return jsonify({"success": True, "message": "IPN xử lý thành công", "orderId": order_id, "status": status}), 200
    except Exception as e:
        log("Error in /momo/ipn", str(e))
        if conn: conn.rollback()
        return jsonify({"success": False, "message": f"Lỗi xử lý IPN: {str(e)}"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

@momo_bp.route("/momo/check-status/<order_id>", methods=["GET"])
@jwt_required()
def check_payment_status(order_id):
    conn = None
    cursor = None
    try:
        user_id = get_current_user_id()
        log(f"Checking status for user {user_id}, order {order_id}")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT p.*, pkg.name_package
            FROM payment p
            LEFT JOIN package pkg ON p.id_package = pkg.id_package
            WHERE p.id_order=%s AND p.id_user=%s
        """, (order_id, user_id))
        transaction = cursor.fetchone()
        log("Check-status result", transaction)

        if not transaction:
            return jsonify({"success": False, "message": "Không tìm thấy giao dịch."}), 404

        result = {
            "orderId": transaction['id_order'],
            "amount": transaction['amount'],
            "status": transaction['status'],
            "paymentMethod": transaction['payment'],
            "packageName": transaction['name_package'],
            "duration": transaction['duration'],
            "createdAt": transaction['created_at'].isoformat() if transaction['created_at'] else None,
            "code": transaction['code']
        }
        return jsonify({"success": True, "transaction": result}), 200
    except Exception as e:
        log("Error in /check-status", str(e))
        return jsonify({"success": False, "message": f"Lỗi kiểm tra trạng thái: {str(e)}"}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
