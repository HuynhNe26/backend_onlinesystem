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