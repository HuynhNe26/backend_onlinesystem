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
    """Tạo chữ ký theo chuẩn MoMo - KHÔNG có dấu & ở đầu"""
    raw_signature = (
        f"accessKey={params['accessKey']}&"
        f"amount={params['amount']}&"
        f"extraData={params['extraData']}&"
        f"ipnUrl={params['ipnUrl']}&"
        f"orderId={params['orderId']}&"
        f"orderInfo={params['orderInfo']}&"
        f"partnerCode={params['partnerCode']}&"
        f"redirectUrl={params['redirectUrl']}&"
        f"requestId={params['requestId']}&"
        f"requestType={params['requestType']}"
    )
    logging.debug(f"Raw signature string: {raw_signature}")
    signature = hmac.new(secret_key.encode('utf-8'), raw_signature.encode('utf-8'), hashlib.sha256).hexdigest()
    logging.debug(f"Generated signature: {signature}")
    return signature


def verify_momo_ipn_signature(data, secret_key):
    """Xác thực chữ ký IPN theo đúng chuẩn MoMo"""
    raw_signature = (
        f"accessKey={data.get('accessKey', '')}&"
        f"amount={data.get('amount', '')}&"
        f"extraData={data.get('extraData', '')}&"
        f"message={data.get('message', '')}&"
        f"orderId={data.get('orderId', '')}&"
        f"orderInfo={data.get('orderInfo', '')}&"
        f"orderType={data.get('orderType', '')}&"
        f"partnerCode={data.get('partnerCode', '')}&"
        f"payType={data.get('payType', '')}&"
        f"requestId={data.get('requestId', '')}&"
        f"responseTime={data.get('responseTime', '')}&"
        f"resultCode={data.get('resultCode', '')}&"
        f"transId={data.get('transId', '')}"
    )
    logging.debug(f"IPN Raw signature string: {raw_signature}")
    expected_signature = hmac.new(secret_key.encode('utf-8'), raw_signature.encode('utf-8'), hashlib.sha256).hexdigest()
    received_signature = data.get("signature", "")
    logging.debug(f"Expected: {expected_signature}, Received: {received_signature}")
    return expected_signature == received_signature


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

        # Tạo requestId và orderId theo chuẩn
        request_id = str(uuid.uuid4())
        order_id = f"{int(time.time())}"

        # extraData phải là chuỗi rỗng hoặc base64
        extra_data = ""  # MoMo yêu cầu để trống nếu không dùng

        # Lưu thông tin vào extraData dưới dạng JSON string
        extra_info = json.dumps({"id_package": id_package, "id_user": id_user})

        params = {
            "partnerCode": MOMO_CONFIG["partnerCode"],
            "accessKey": MOMO_CONFIG["accessKey"],
            "requestId": request_id,
            "amount": str(price),
            "orderId": order_id,
            "orderInfo": name_package,
            "redirectUrl": MOMO_CONFIG["redirectUrl"],
            "ipnUrl": MOMO_CONFIG["ipnUrl"],
            "requestType": "captureWallet",
            "extraData": extra_data,
            "lang": "vi"
        }

        # Tạo chữ ký
        signature = generate_momo_signature(params, MOMO_CONFIG["secretKey"])
        params["signature"] = signature

        # Lưu vào database với extra_info
        cursor.execute("""
            INSERT INTO payment (id_user, id_package, id_order, amount, status, payment, code, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """, (id_user, id_package, order_id, price, "Đang giao dịch", "momo", extra_info))
        conn.commit()

        logging.info(f"Sending to MoMo: {json.dumps(params, indent=2)}")

        # Gửi request đến MoMo
        resp = requests.post(MOMO_CONFIG["endpoint"], json=params, timeout=10)
        result = resp.json()

        logging.info(f"MoMo Response: {json.dumps(result, indent=2)}")

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
            "resultCode": result.get("resultCode")
        }), 400

    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"Error in momo_payment: {str(e)}")
        return jsonify({"success": False, "message": f"Lỗi hệ thống: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ---- IPN MoMo ----
@momo_bp.route("/momo/ipn", methods=["POST"])
def momo_ipn():
    conn = cursor = None
    try:
        data = request.get_json()
        logging.info(f"=== IPN RECEIVED ===")
        logging.info(f"IPN Data: {json.dumps(data, indent=2)}")

        if not data:
            return jsonify({"resultCode": 1, "message": "No IPN data"}), 400

        # Verify signature
        if not verify_momo_ipn_signature(data, MOMO_CONFIG["secretKey"]):
            logging.error("Invalid signature in IPN")
            return jsonify({"resultCode": 97, "message": "Invalid signature"}), 200

        order_id = data.get("orderId")
        result_code = int(data.get("resultCode", -1))
        trans_id = data.get("transId")
        amount = data.get("amount")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM payment WHERE id_order=%s", (order_id,))
        tx = cursor.fetchone()

        if not tx:
            logging.error(f"Order not found: {order_id}")
            return jsonify({"resultCode": 2, "message": "Order not found"}), 200

        # Kiểm tra đã xử lý chưa
        if tx["status"] not in ["Đang giao dịch"]:
            logging.info(f"Order already processed: {order_id}")
            return jsonify({"resultCode": 0, "message": "Already processed"}), 200

        # Cập nhật trạng thái thanh toán
        if result_code == 0:
            status_text = "Giao dịch thành công"
        else:
            status_text = "Giao dịch thất bại"

        cursor.execute("""
            UPDATE payment 
            SET status=%s, code=%s 
            WHERE id_order=%s
        """, (status_text, trans_id, order_id))

        # Nếu thanh toán thành công → cập nhật user package
        if result_code == 0:
            id_user = tx["id_user"]
            id_package = tx["id_package"]

            cursor.execute("SELECT * FROM package WHERE id_package=%s", (id_package,))
            pkg = cursor.fetchone()

            if not pkg:
                logging.error(f"Package not found: {id_package}")
                conn.rollback()
                return jsonify({"resultCode": 3, "message": "Package not found"}), 200

            # Logic gói cước
            if id_package == 1:
                duration = 0
                quantity = 1
            elif id_package == 2:
                duration = 30
                quantity = 10
            elif id_package == 3:
                duration = 30
                quantity = 20
            else:
                duration = 0
                quantity = 1

            cursor.execute("""
                UPDATE users
                SET id_package=%s,
                    start_package=NOW(),
                    end_package=DATE_ADD(NOW(), INTERVAL %s DAY),
                    quantity_exam=%s
                WHERE id_user=%s
            """, (id_package, duration, quantity, id_user))

            logging.info(f"Updated user {id_user} with package {id_package}")

        conn.commit()

        # Trả về response theo chuẩn MoMo
        return jsonify({"resultCode": 0, "message": "Success"}), 200

    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"IPN Error: {str(e)}")
        return jsonify({"resultCode": 1000, "message": f"System error"}), 200

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


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