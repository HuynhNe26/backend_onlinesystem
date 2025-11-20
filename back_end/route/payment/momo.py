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

def get_current_user_id():
    identity = get_jwt_identity()
    if isinstance(identity, dict):
        return identity.get("id") or identity.get("id_user")
    try:
        return int(identity)
    except:
        return identity

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

def verify_momo_signature(data, secret_key):
    raw_data = (
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

    expected_signature = hmac.new(
        secret_key.encode("utf-8"),
        raw_data.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return expected_signature == data.get("signature","")


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
            INSERT INTO payment (id_user, id_package, id_order, amount, status, payment, code, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())
        """, (id_user, id_package, order_id, price, "Đang giao dịch", "momo", None))

        # Gửi request MoMo
        resp = requests.post(MOMO_CONFIG["endpoint"], json=payload, timeout=10)
        if resp.status_code != 200:
            return jsonify({"success": False, "message": f"Cổng thanh toán lỗi {resp.status_code}"}), 500

        result = resp.json()
        if result.get("resultCode") == 0 and result.get("payUrl"):
            return jsonify({
                "success": True,
                "payUrl": result["payUrl"],
                "orderId": order_id
            }), 200

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
        status_msg = "Giao dịch thành công" if status == "success" else "Giao dịch thất bại"

        cursor.execute("""
            UPDATE payment
            SET status=%s, code=%s
            WHERE id_order=%s
        """, (status_msg, trans_id, order_id))

        if status == "success":
            id_user = tx["id_user"]
            id_package = tx["id_package"]

            cursor.execute("SELECT * FROM package WHERE id_package=%s", (id_package,))
            pkg = cursor.fetchone()

            if not pkg:
                conn.rollback()
                return jsonify({"success": False, "message": "Package not found"}), 404

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

        conn.commit()

        return jsonify({
            "resultCode": 0,
            "message": "IPN handled successfully",
            "orderId": order_id
        }), 200

    except Exception as e:
        import traceback
        print("🔥 IPN ERROR:", str(e))
        print(traceback.format_exc())

        if conn: conn.rollback()
        return jsonify({"success": False, "message": f"IPN Error: {str(e)}"}), 500

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

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import hmac
import hashlib
import urllib.parse
import datetime
import logging
from ...config.db_config import get_db_connection

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

vnpay_bp = Blueprint("vnpay_bp", __name__)

VNPAY_CONFIG = {
    "vnp_TmnCode": "4FZ1N3EZ",
    "vnp_HashSecret": "G0S15BZBGXV9CO47K7FSJEIO2NAS544V",
    "vnp_Url": "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html",
    "vnp_Returnurl": "https://frontend-admin-onlinesystem-eugd.onrender.com/payment-success",
    "vnp_IpnUrl": "https://uninclined-overhonestly-jone.ngrok-free.dev/api/payment/vnpay/ipn"
}


@vnpay_bp.route("/vnpay", methods=["POST"])
@jwt_required()
def vnpay_payment():
    conn = None
    cursor = None

    try:
        current_user = get_jwt_identity()
        print(current_user)

        data = request.json
        required_fields = ["price_month", "name_package", "id_package"]

        if not data:
            return jsonify({
                "success": False,
                "message": "Không có dữ liệu được gửi lên."
            }), 400

        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            return jsonify({
                "success": False,
                "message": f"Thiếu thông tin: {', '.join(missing_fields)}"
            }), 400

        # Validate amount
        try:
            amount = int(data.get("amount"))
            if amount <= 0:
                return jsonify({
                    "success": False,
                    "message": "Số tiền phải lớn hơn 0."
                }), 400
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "message": "Số tiền không hợp lệ."
            }), 400

        package_id = data.get("id_package")
        order_info = data.get("name_package", f"Thanh toán gói {package_id}")

        conn = get_db_connection()
        if not conn:
            logging.error("Failed to connect to database")
            return jsonify({
                "success": False,
                "message": "Không thể kết nối cơ sở dữ liệu."
            }), 500

        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT id, name, price FROM packages WHERE id = %s",
            (package_id,)
        )
        package = cursor.fetchone()

        if not package:
            return jsonify({
                "success": False,
                "message": "Gói dịch vụ không tồn tại."
            }), 404

        if amount != package['price']:
            return jsonify({
                "success": False,
                "message": "Số tiền không khớp với giá gói."
            }), 400

        vnp_TxnRef = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        vnp_CreateDate = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        vnp_Amount = amount * 100

        vnp_params = {
            "vnp_Version": "2.1.0",
            "vnp_Command": "pay",
            "vnp_TmnCode": VNPAY_CONFIG["vnp_TmnCode"],
            "vnp_Amount": str(vnp_Amount),
            "vnp_CurrCode": "VND",
            "vnp_TxnRef": vnp_TxnRef,
            "vnp_OrderInfo": order_info,
            "vnp_OrderType": "billpayment",
            "vnp_ReturnUrl": VNPAY_CONFIG["vnp_Returnurl"],
            "vnp_IpAddr": request.remote_addr or "127.0.0.1",
            "vnp_CreateDate": vnp_CreateDate,
            "vnp_Locale": "vn"
        }

        try:
            cursor.execute(
                """
                INSERT INTO transactions 
                (user_id, package_id, order_id, request_id, amount, payment_method, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    current_user.get("id"),
                    package_id,
                    vnp_TxnRef,
                    vnp_TxnRef,
                    amount,
                    "vnpay",
                    "pending"
                )
            )
            conn.commit()
            logging.debug(f"Transaction saved: order_id={vnp_TxnRef}, user_id={current_user.get('id')}")
        except Exception as e:
            conn.rollback()
            logging.error(f"Error saving transaction: {str(e)}")
            return jsonify({
                "success": False,
                "message": "Lỗi lưu giao dịch vào cơ sở dữ liệu."
            }), 500

        sorted_keys = sorted(vnp_params.keys())
        query_string = "&".join([
            f"{key}={urllib.parse.quote(str(vnp_params[key]))}"
            for key in sorted_keys
        ])

        hash_value = hmac.new(
            VNPAY_CONFIG["vnp_HashSecret"].encode(),
            query_string.encode(),
            hashlib.sha512
        ).hexdigest()

        pay_url = f"{VNPAY_CONFIG['vnp_Url']}?{query_string}&vnp_SecureHash={hash_value}"

        logging.debug(f"VNPay payment URL generated for order: {vnp_TxnRef}")

        return jsonify({
            "success": True,
            "payUrl": pay_url,
            "orderId": vnp_TxnRef,
            "message": "Tạo link thanh toán thành công."
        }), 200

    except Exception as e:
        logging.error(f"Unexpected error in vnpay_payment: {str(e)}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Lỗi hệ thống khi xử lý thanh toán."
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@vnpay_bp.route("/vnpay/ipn", methods=["GET"])
def vnpay_ipn():
    conn = None
    cursor = None

    try:
        vnp_params = request.args.to_dict()

        logging.debug(f"VNPay IPN received: {vnp_params}")

        vnp_SecureHash = vnp_params.pop('vnp_SecureHash', None)

        if not vnp_SecureHash:
            logging.error("IPN: Missing vnp_SecureHash")
            return jsonify({
                "success": False,
                "message": "Thiếu chữ ký bảo mật."
            }), 400

        sorted_keys = sorted(vnp_params.keys())
        query_string = "&".join([
            f"{key}={urllib.parse.quote(str(vnp_params[key]))}"
            for key in sorted_keys
        ])

        expected_hash = hmac.new(
            VNPAY_CONFIG["vnp_HashSecret"].encode(),
            query_string.encode(),
            hashlib.sha512
        ).hexdigest()

        if not hmac.compare_digest(vnp_SecureHash, expected_hash):
            logging.error("IPN: Invalid signature")
            return jsonify({
                "success": False,
                "message": "Chữ ký không hợp lệ."
            }), 403

        vnp_TxnRef = vnp_params.get('vnp_TxnRef')
        vnp_ResponseCode = vnp_params.get('vnp_ResponseCode')
        vnp_TransactionNo = vnp_params.get('vnp_TransactionNo')
        vnp_Amount = int(vnp_params.get('vnp_Amount', 0)) // 100  # Convert back to VND

        if not vnp_TxnRef:
            logging.error("IPN: Missing vnp_TxnRef")
            return jsonify({
                "success": False,
                "message": "Thiếu mã giao dịch."
            }), 400

        conn = get_db_connection()
        if not conn:
            logging.error("IPN: Failed to connect to database")
            return jsonify({
                "success": False,
                "message": "Không thể kết nối cơ sở dữ liệu."
            }), 500

        cursor = conn.cursor(dictionary=True)

        # Get transaction details
        cursor.execute(
            """
            SELECT t.*, p.duration_days, p.name as package_name
            FROM transactions t
            LEFT JOIN packages p ON t.package_id = p.id
            WHERE t.order_id = %s
            """,
            (vnp_TxnRef,)
        )
        transaction = cursor.fetchone()

        if not transaction:
            logging.error(f"IPN: Transaction not found for order_id: {vnp_TxnRef}")
            return jsonify({
                "success": False,
                "message": "Giao dịch không tồn tại."
            }), 404

        # Check if already processed
        if transaction['status'] in ['success', 'failed']:
            logging.warning(f"IPN: Transaction already processed: {vnp_TxnRef}")
            return jsonify({
                "success": True,
                "message": "IPN đã được xử lý trước đó."
            }), 200

        # Determine status (00 = success in VNPay)
        status = "success" if vnp_ResponseCode == "00" else "failed"

        try:
            # Update transaction
            cursor.execute(
                """
                UPDATE transactions
                SET status = %s, 
                    trans_id = %s,
                    result_code = %s,
                    updated_at = NOW()
                WHERE order_id = %s
                """,
                (status, vnp_TransactionNo, vnp_ResponseCode, vnp_TxnRef)
            )

            # If payment successful, update user package
            if status == "success":
                user_id = transaction['user_id']
                package_id = transaction['package_id']
                duration_days = transaction['duration_days']

                # Update user's package and expiry date
                cursor.execute(
                    """
                    UPDATE users
                    SET package_id = %s,
                        package_expiry_date = DATE_ADD(
                            COALESCE(
                                CASE 
                                    WHEN package_expiry_date > NOW() THEN package_expiry_date
                                    ELSE NOW()
                                END,
                                NOW()
                            ),
                            INTERVAL %s DAY
                        ),
                        updated_at = NOW()
                    WHERE id_user = %s
                    """,
                    (package_id, duration_days, user_id)
                )

                logging.info(f"IPN: User {user_id} updated with package {package_id}")

            conn.commit()

            logging.info(f"IPN: Transaction {vnp_TxnRef} updated to {status}")

            return jsonify({
                "success": True,
                "message": "IPN processed successfully.",
                "orderId": vnp_TxnRef,
                "status": status
            }), 200

        except Exception as e:
            conn.rollback()
            logging.error(f"IPN: Error updating database: {str(e)}")
            return jsonify({
                "success": False,
                "message": "Lỗi cập nhật dữ liệu."
            }), 500

    except Exception as e:
        logging.error(f"IPN: Unexpected error: {str(e)}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": "Lỗi xử lý IPN."
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@vnpay_bp.route("/vnpay/check-status/<order_id>", methods=["GET"])
@jwt_required()
def check_payment_status(order_id):
    """Check payment status"""
    conn = None
    cursor = None

    try:
        current_user = get_jwt_identity()

        conn = get_db_connection()
        if not conn:
            return jsonify({
                "success": False,
                "message": "Không thể kết nối cơ sở dữ liệu."
            }), 500

        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT t.*, p.name as package_name
            FROM transactions t
            LEFT JOIN packages p ON t.package_id = p.id
            WHERE t.order_id = %s AND t.user_id = %s
            """,
            (order_id, current_user.get("id"))
        )

        transaction = cursor.fetchone()

        if not transaction:
            return jsonify({
                "success": False,
                "message": "Không tìm thấy giao dịch."
            }), 404

        return jsonify({
            "success": True,
            "transaction": {
                "orderId": transaction['order_id'],
                "amount": transaction['amount'],
                "status": transaction['status'],
                "packageName": transaction['package_name'],
                "createdAt": transaction['created_at'].isoformat() if transaction['created_at'] else None,
                "updatedAt": transaction['updated_at'].isoformat() if transaction['updated_at'] else None
            }
        }), 200

    except Exception as e:
        logging.error(f"Error checking payment status: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Lỗi kiểm tra trạng thái thanh toán."
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()