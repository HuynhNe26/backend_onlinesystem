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
    "redirectUrl": "https://frontend-admin-onlinesystem-eugd.onrender.com/payment-success",
    "ipnUrl": "https://uninclined-overhonestly-jone.ngrok-free.dev/api/payment/momo/ipn"
}

# Lấy ID user hiện tại
def get_current_user_id():
    identity = get_jwt_identity()
    if isinstance(identity, dict):
        return identity.get("id") or identity.get("id_user")
    try:
        return int(identity)
    except:
        return identity

# Tạo chữ ký MoMo
def generate_momo_signature(params, secret_key):
    raw_signature = (
        f"accessKey={params.get('accessKey','')}"
        f"&amount={params.get('amount','')}"
        f"&extraData={params.get('extraData','')}"
        f"&ipnUrl={params.get('ipnUrl','')}"
        f"&orderId={params.get('orderId','')}"
        f"&orderInfo={params.get('orderInfo','')}"
        f"&partnerCode={params.get('partnerCode','')}"
        f"&redirectUrl={params.get('redirectUrl','')}"
        f"&requestId={params.get('requestId','')}"
        f"&requestType={params.get('requestType','')}"
    )
    return hmac.new(secret_key.encode('utf-8'), raw_signature.encode('utf-8'), hashlib.sha256).hexdigest()

# Verify chữ ký IPN
def verify_momo_signature(data, secret_key):
    raw_data = (
        f"partnerCode={data.get('partnerCode','')}"
        f"&accessKey={data.get('accessKey','')}"
        f"&requestId={data.get('requestId','')}"
        f"&amount={data.get('amount','')}"
        f"&orderId={data.get('orderId','')}"
        f"&orderInfo={data.get('orderInfo','')}"
        f"&orderType={data.get('orderType','')}"
        f"&transId={data.get('transId','')}"
        f"&message={data.get('message','')}"
        f"&localMessage={data.get('localMessage','')}"
        f"&responseTime={data.get('responseTime','')}"
        f"&errorCode={data.get('errorCode','')}"
        f"&payType={data.get('payType','')}"
        f"&extraData={data.get('extraData','')}"
    )
    expected_signature = hmac.new(secret_key.encode('utf-8'), raw_data.encode('utf-8'), hashlib.sha256).hexdigest()
    received_signature = data.get('signature','')
    print("Raw data for signature:", raw_data)
    print("Expected signature:", expected_signature)
    print("Received signature:", received_signature)
    return hmac.compare_digest(received_signature, expected_signature)

# Tạo payment
@momo_bp.route("/momo", methods=["POST"])
@jwt_required()
def momo_payment():
    conn = cursor = None
    try:
        id_user = get_current_user_id()
        data = request.json
        required_fields = ["price_month", "name_package", "id_package"]
        if not data:
            return jsonify({"success": False, "message": "Không có dữ liệu."}), 400
        missing = [f for f in required_fields if f not in data]
        if missing:
            return jsonify({"success": False, "message": f"Thiếu: {', '.join(missing)}"}), 400

        try:
            price = int(data["price_month"])
            if price <= 0: raise ValueError
        except:
            return jsonify({"success": False, "message": "Số tiền không hợp lệ."}), 400

        id_package = data["id_package"]
        name_package = data.get("name_package", f"Thanh toán gói {id_package}")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        request_id = f"{MOMO_CONFIG['partnerCode']}_{int(time.time() * 1000)}"
        order_id = str(uuid.uuid4()).replace('-','')[:12]
        extra_data = json.dumps({"id_package": id_package, "id_user": id_user})

        params = {
            "accessKey": MOMO_CONFIG["accessKey"],
            "amount": str(price),
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

        # Lưu DB
        cursor.execute("""
            INSERT INTO payment (id_user, id_package, id_order, amount, duration, status, payment, code, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())
        """, (id_user, id_package, order_id, price, None, "Đang giao dịch", "momo", None))
        conn.commit()

        # Gửi request MoMo
        resp = requests.post(MOMO_CONFIG["endpoint"], json=payload, timeout=10)
        if resp.status_code != 200:
            return jsonify({"success": False, "message": f"Cổng thanh toán lỗi {resp.status_code}"}), 500

        result = resp.json()
        if result.get("resultCode")==0 and result.get("payUrl"):
            return jsonify({"data": result}), 200
        return jsonify({"success": False, "message": result.get("message","Lỗi tạo link"), "resultCode": result.get("resultCode")}), 400

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"success": False, "message": f"Lỗi hệ thống: {str(e)}"}), 500
    finally:
        if cursor: cursor.close() if cursor else None
        if conn: conn.close()

# IPN MoMo
@momo_bp.route("/momo/ipn", methods=["POST"])
def momo_ipn():
    conn = cursor = None
    try:
        data = request.get_json(silent=True) or {}
        if not data: return jsonify({"success": False, "message": "Không có dữ liệu IPN"}), 400

        order_id = data.get("orderId")
        result_code = str(data.get("resultCode"))
        trans_id = data.get("transId")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM payment WHERE id_order=%s", (order_id,))
        tx = cursor.fetchone()
        if not tx: return jsonify({"success": False, "message": "Giao dịch không tồn tại"}), 404

        status = "success" if result_code in ("0",0) else "failed"
        status_msg = "Giao dịch thành công" if status=="success" else "Giao dịch thất bại"
        cursor.execute("UPDATE payment SET status=%s, code=%s WHERE id_order=%s", (status_msg, trans_id, order_id))

        if status=="success":
            id_user = tx["id_user"]
            id_package = tx["id_package"]
            cursor.execute("SELECT * FROM package WHERE id_package=%s", (id_package,))
            pkg = cursor.fetchone()
            if not pkg:
                conn.rollback()
                return jsonify({"success": False, "message": "Không tìm thấy gói"}), 404

            # Duration & quantity
            if id_package==1: duration=0; quantity=1
            elif id_package==2: duration=30; quantity=10
            elif id_package==3: duration=30; quantity=20
            else: duration=0; quantity=1

            cursor.execute("""
                UPDATE users
                SET id_package=%s, start_package=NOW(), end_package=DATE_ADD(NOW(), INTERVAL %s DAY),
                    quantity_exam=%s
                WHERE id_user=%s
            """, (id_package, duration, quantity, id_user))

        conn.commit()
        return jsonify({"resultCode":0,"message":"Giao dịch thành công","orderId":order_id,"status":status}), 200

    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"success": False, "message": f"Lỗi xử lý IPN: {str(e)}"}), 500
    finally:
        if cursor: cursor.close() if cursor else None
        if conn: conn.close()

# Check trạng thái
@momo_bp.route("/momo/check-status/<order_id>", methods=["GET"])
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
            "duration": tx["duration"],
            "createdAt": tx["created_at"].isoformat() if tx["created_at"] else None,
            "code": tx["code"]
        }
        return jsonify({"success": True, "transaction": result}), 200
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi kiểm tra trạng thái: {str(e)}"}), 500
    finally:
        if cursor: cursor.close() if cursor else None
        if conn: conn.close()
