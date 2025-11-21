import datetime

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import hmac
import hashlib
import json
import requests
import uuid
import time
import logging
from ...config.db_config import get_db_connection

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

momo_bp = Blueprint("momo_bp", __name__)

MOMO_CONFIG = {
    "endpoint": "https://test-payment.momo.vn/v2/gateway/api/create",
    "partnerCode": "MOMO",
    "partnerName": "Test",
    "storeId": "MomoTestStore",
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
    """Tạo chữ ký theo đúng format MoMo (UTF-8)"""
    rawSignature = (
            "accessKey=" + params['accessKey'] +
            "&amount=" + params['amount'] +
            "&extraData=" + params['extraData'] +
            "&ipnUrl=" + params['ipnUrl'] +
            "&orderId=" + params['orderId'] +
            "&orderInfo=" + params['orderInfo'] +
            "&partnerCode=" + params['partnerCode'] +
            "&redirectUrl=" + params['redirectUrl'] +
            "&requestId=" + params['requestId'] +
            "&requestType=" + params['requestType']
    )

    logging.debug(f"--------------------RAW SIGNATURE----------------")
    logging.debug(rawSignature)

    # Chỉ thay ascii → utf-8
    h = hmac.new(secret_key.encode('utf-8'), rawSignature.encode('utf-8'), hashlib.sha256)
    signature = h.hexdigest()


    logging.debug(f"--------------------SIGNATURE----------------")
    logging.debug(signature)

    return signature


def verify_momo_ipn_signature(data, secret_key):
    rawSignature = (
        f"accessKey={data.get('accessKey', '')}"
        f"&amount={data.get('amount', '')}"
        f"&extraData={data.get('extraData', '')}"
        f"&message={data.get('message', '')}"
        f"&orderId={data.get('orderId', '')}"
        f"&orderInfo={data.get('orderInfo', '')}"
        f"&orderType={data.get('orderType', '')}"
        f"&partnerCode={data.get('partnerCode', '')}"
        f"&payType={data.get('payType', '')}"
        f"&requestId={data.get('requestId', '')}"
        f"&responseTime={data.get('responseTime', '')}"
        f"&resultCode={data.get('resultCode', '')}"
        f"&transId={data.get('transId', '')}"
    )

    logging.warning("RAW IPN SIG: " + rawSignature)

    h = hmac.new(secret_key.encode(), rawSignature.encode(), hashlib.sha256)
    expected = h.hexdigest()
    received = data.get("signature")

    logging.warning(f"EXPECTED: {expected}")
    logging.warning(f"RECEIVED: {received}")

    return expected == received

# ---- Tạo Payment MoMo ----
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
            if price <= 0:
                raise ValueError
        except:
            return jsonify({"success": False, "message": "Số tiền không hợp lệ."}), 400

        id_package = data["id_package"]
        name_package = data.get("name_package", f"Thanh toán gói {id_package}")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Tạo orderId và requestId bằng UUID như example
        order_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())

        # extraData để trống
        extra_data = ""

        # Tạo params theo đúng thứ tự để tạo signature
        params = {
            'accessKey': MOMO_CONFIG["accessKey"],
            'amount': str(price),
            'extraData': extra_data,
            'ipnUrl': MOMO_CONFIG["ipnUrl"],
            'orderId': order_id,
            'orderInfo': name_package,
            'partnerCode': MOMO_CONFIG["partnerCode"],
            'redirectUrl': MOMO_CONFIG["redirectUrl"],
            'requestId': request_id,
            'requestType': "captureWallet"
        }

        # Tạo chữ ký
        signature = generate_momo_signature(params, MOMO_CONFIG["secretKey"])

        # Tạo JSON data gửi đến MoMo (thêm các field bổ sung)
        payload = {
            'partnerCode': MOMO_CONFIG["partnerCode"],
            'partnerName': MOMO_CONFIG["partnerName"],
            'storeId': MOMO_CONFIG["storeId"],
            'requestId': request_id,
            'amount': str(price),
            'orderId': order_id,
            'orderInfo': name_package,
            'redirectUrl': MOMO_CONFIG["redirectUrl"],
            'ipnUrl': MOMO_CONFIG["ipnUrl"],
            'lang': "vi",
            'extraData': extra_data,
            'requestType': "captureWallet",
            'signature': signature
        }

        logging.info(f"--------------------JSON REQUEST----------------")
        logging.info(json.dumps(payload, indent=2))

        # Lưu vào database
        extra_info = json.dumps({"id_package": id_package, "id_user": id_user})
        cursor.execute("""
            INSERT INTO payment (id_user, id_package, id_order, amount, status, payment, code, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """, (id_user, id_package, order_id, price, "Đang giao dịch", "momo", extra_info))
        conn.commit()

        # Gửi request đến MoMo
        payload_json = json.dumps(payload)
        headers = {
            'Content-Type': 'application/json',
            'Content-Length': str(len(payload_json))
        }

        resp = requests.post(
            MOMO_CONFIG["endpoint"],
            data=payload_json,
            headers=headers,
            timeout=10
        )

        logging.info(f"--------------------JSON RESPONSE----------------")
        logging.info(f"Status Code: {resp.status_code}")
        logging.info(f"Response: {resp.text}")

        result = resp.json()

        if result.get("resultCode") == 0 and result.get("payUrl"):
            return jsonify({
                "success": True,
                "payUrl": result["payUrl"],
                "orderId": order_id,
                "deeplink": result.get("deeplink"),
                "qrCodeUrl": result.get("qrCodeUrl")
            }), 200

        return jsonify({
            "success": False,
            "message": result.get("message", "Lỗi tạo link thanh toán"),
            "resultCode": result.get("resultCode"),
            "details": result
        }), 400

    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Error in momo_payment: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"Lỗi hệ thống: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ---- IPN MoMo ----
@momo_bp.route("/momo/ipn", methods=["POST"])
def momo_ipn():
    logging.warning("=== IPN RECEIVED ===")
    data = request.get_json()
    logging.warning(data)

    # ======= 1. TẠO RAW SIGNATURE THEO ĐÚNG THỨ TỰ MOMO ======== #
    raw = (
        f"accessKey={data.get('accessKey','')}"
        f"&amount={data.get('amount','')}"
        f"&extraData={data.get('extraData','')}"
        f"&message={data.get('message','')}"
        f"&orderId={data.get('orderId','')}"
        f"&orderInfo={data.get('orderInfo','')}"
        f"&orderType={data.get('orderType','')}"
        f"&partnerCode={data.get('partnerCode','')}"
        f"&payType={data.get('payType','')}"
        f"&requestId={data.get('requestId','')}"
        f"&responseTime={data.get('responseTime','')}"
        f"&resultCode={data.get('resultCode','')}"
        f"&transId={data.get('transId','')}"
    )

    logging.warning("RAW SIGNATURE >>> " + raw)

    # ======= 2. TÍNH CHỮ KÝ SERVER ======== #
    h = hmac.new(
        MOMO_CONFIG["secretKey"].encode(),
        raw.encode(),
        hashlib.sha256
    )
    expected_signature = h.hexdigest()

    logging.warning("EXPECTED SIGNATURE >>> " + expected_signature)
    logging.warning("RECEIVED SIGNATURE >>> " + data.get("signature"))

    if expected_signature != data.get("signature"):
        logging.error("❌ INVALID SIGNATURE → IGNORE IPN")
        return jsonify({'message': 'INVALID_SIGNATURE'}), 200

    logging.warning("✔ SIGNATURE OK")

    # ======= 3. KIỂM TRA ORDER ======== #
    order_id = data.get("orderId")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM payment WHERE id_order=%s", (order_id,))
    tx = cursor.fetchone()

    if not tx:
        logging.error("❌ ORDER NOT FOUND IN DATABASE")
        return jsonify({'message': 'ORDER_NOT_FOUND'}), 200

    logging.warning("✔ ORDER FOUND")

    # Nếu giao dịch đã xử lý → trả OK để MoMo không gửi lại
    if tx["status"] == 1:
        logging.warning("⚠ ORDER ALREADY PROCESSED → SKIP")
        return jsonify({'message': 'ORDER_ALREADY_SUCCESS'}), 200

    # ======= 4. NẾU THANH TOÁN THÀNH CÔNG ======== #
    result_code = data.get("resultCode")

    if result_code == 0:
        logging.warning("✔ PAYMENT SUCCESS → UPDATE DB")

        # Update trạng thái thanh toán
        cursor.execute(
            "UPDATE payment SET status=1 WHERE id_order=%s",
            (order_id,)
        )

        # Update gói dịch vụ cho user
        id_user = tx["id_user"]
        package = tx["package"]
        now = datetime.datetime.now()

        if package == 1:
            end = now + datetime.timedelta(days=31)
        elif package == 2:
            end = now + datetime.timedelta(days=93)
        elif package == 3:
            end = now + datetime.timedelta(days=186)
        else:
            end = now

        cursor.execute(
            "UPDATE users SET package=%s, start_package=%s, end_package=%s WHERE id=%s",
            (package, now, end, id_user)
        )

        conn.commit()
        cursor.close()
        conn.close()

        logging.warning("✔ DB UPDATE COMPLETE")

        return jsonify({'message': 'SUCCESS'}), 200

    # ======= 5. NẾU THANH TOÁN THẤT BẠI ======== #
    logging.warning("❌ PAYMENT FAILED → SET status = -1")

    cursor.execute(
        "UPDATE payment SET status=-1 WHERE id_order=%s",
        (order_id,)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({'message': 'FAILED'}), 200

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

        if not tx:
            return jsonify({"success": False, "message": "Không tìm thấy giao dịch"}), 404

        result = {
            "orderId": tx["id_order"],
            "amount": tx["amount"],
            "status": tx["status"],
            "paymentMethod": tx["payment"],
            "packageName": tx["name_package"],
            "createdAt": tx["created_at"].isoformat() if tx["created_at"] else None,
            "transactionCode": tx["code"]
        }

        return jsonify({"success": True, "transaction": result}), 200

    except Exception as e:
        logging.error(f"Check status error: {str(e)}")
        return jsonify({"success": False, "message": f"Lỗi kiểm tra trạng thái: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()