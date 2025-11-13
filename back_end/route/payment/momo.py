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
    "redirectUrl": "https://127.0.0.1:5000/payment-success",
    "ipnUrl": "https://127.0.0.1:5000/api/payment/momo/ipn"
}


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
        secret_key.encode('utf-8'),
        raw_signature.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return signature


def verify_momo_signature(data, secret_key):
    received_signature = data.get("signature", "")
    raw_data = (
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
    expected_signature = hmac.new(
        secret_key.encode('utf-8'),
        raw_data.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(received_signature, expected_signature)


@momo_bp.route("/momo", methods=["POST"])
@jwt_required()
def momo_payment():
    conn = None
    cursor = None

    try:
        id_user = get_current_user_id()

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

        try:
            price_month = int(data.get("price_month"))
            if price_month <= 0:
                return jsonify({
                    "success": False,
                    "message": "Số tiền phải lớn hơn 0."
                }), 400
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "message": "Số tiền không hợp lệ."
            }), 400

        id_package = data.get("id_package")
        name_package = data.get("name_package", f"Thanh toán gói {id_package}")

        conn = get_db_connection()
        if not conn:
            logging.error("Failed to connect to database")
            return jsonify({
                "success": False,
                "message": "Không thể kết nối cơ sở dữ liệu."
            }), 500

        cursor = conn.cursor(dictionary=True)

        request_id = f"{MOMO_CONFIG['partnerCode']}_{int(time.time() * 1000)}"
        order_id = str(uuid.uuid4()).replace('-', '')[:12]

        extra_data = json.dumps({
            "id_package": id_package,
            "id_user": id_user
        })

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

        logging.debug(f"MoMo params: {json.dumps(params, indent=2)}")

        # Generate signature
        signature = generate_momo_signature(params, MOMO_CONFIG["secretKey"])

        logging.debug(f"Generated signature: {signature}")

        # Tạo payload gửi tới MoMo
        payload = {
            **params,
            "signature": signature,
            "lang": "vi"
        }

        logging.debug(f"MoMo payload: {json.dumps(payload, indent=2)}")

        # Save transaction to database (optional - uncomment nếu cần)
        # try:
        #     cursor.execute(
        #         """
        #         INSERT INTO transactions
        #         (user_id, package_id, order_id, request_id, amount, payment_method, status, created_at)
        #         VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        #         """,
        #         (
        #             id_user,
        #             id_package,
        #             order_id,
        #             request_id,
        #             price_month,
        #             "momo",
        #             "pending"
        #         )
        #     )
        #     conn.commit()
        #     logging.debug(f"Transaction saved: order_id={order_id}, user_id={id_user}")
        # except Exception as e:
        #     conn.rollback()
        #     logging.error(f"Error saving transaction: {str(e)}")
        #     return jsonify({
        #         "success": False,
        #         "message": "Lỗi lưu giao dịch vào cơ sở dữ liệu."
        #     }), 500

        # Call MoMo API
        try:
            response = requests.post(
                MOMO_CONFIG["endpoint"],
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )

            logging.debug(f"MoMo response status: {response.status_code}")
            logging.debug(f"MoMo response body: {response.text}")

            if response.status_code != 200:
                return jsonify({
                    "success": False,
                    "message": f"Không thể kết nối với cổng thanh toán MoMo. Status: {response.status_code}"
                }), 500

            result = response.json()
            result_code = result.get("resultCode")

            logging.debug(f"MoMo resultCode: {result_code}")

            if result_code == 0 and result.get("payUrl"):
                return jsonify({
                    "success": True,
                    "payUrl": result["payUrl"],
                    "orderId": order_id,
                    "message": "Tạo link thanh toán thành công."
                }), 200
            else:
                error_message = result.get("message", "Không thể tạo link thanh toán.")
                logging.error(f"MoMo error: {error_message}, resultCode: {result_code}")

                return jsonify({
                    "success": False,
                    "message": error_message,
                    "resultCode": result_code
                }), 400

        except requests.exceptions.Timeout:
            logging.error("MoMo API timeout")
            return jsonify({
                "success": False,
                "message": "Timeout khi kết nối với MoMo."
            }), 504
        except requests.exceptions.RequestException as e:
            logging.error(f"MoMo API request error: {str(e)}")
            return jsonify({
                "success": False,
                "message": "Lỗi kết nối với cổng thanh toán."
            }), 500
        except ValueError as e:
            logging.error(f"MoMo API returned invalid JSON: {response.text}")
            return jsonify({
                "success": False,
                "message": "Phản hồi từ MoMo không hợp lệ."
            }), 500

    except Exception as e:
        logging.error(f"Unexpected error in momo_payment: {str(e)}", exc_info=True)
        if conn:
            conn.rollback()
        return jsonify({
            "success": False,
            "message": f"Lỗi hệ thống khi xử lý thanh toán: {str(e)}"
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@momo_bp.route("/momo/ipn", methods=["POST"])
def momo_ipn():
    conn = None
    cursor = None

    try:
        data = request.json

        if not data:
            logging.error("IPN: No data received")
            return jsonify({
                "success": False,
                "message": "Không có dữ liệu IPN."
            }), 400

        logging.debug(f"MoMo IPN received: {json.dumps(data, indent=2)}")

        if not verify_momo_signature(data, MOMO_CONFIG["secretKey"]):
            logging.error("IPN: Invalid signature")
            return jsonify({
                "success": False,
                "message": "Chữ ký không hợp lệ."
            }), 403

        order_id = data.get("orderId")
        result_code = data.get("resultCode")
        trans_id = data.get("transId")
        amount = data.get("amount")

        if not order_id:
            logging.error("IPN: Missing orderId")
            return jsonify({
                "success": False,
                "message": "Thiếu orderId."
            }), 400

        # Connect to database
        conn = get_db_connection()
        if not conn:
            logging.error("IPN: Failed to connect to database")
            return jsonify({
                "success": False,
                "message": "Không thể kết nối cơ sở dữ liệu."
            }), 500

        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT t.*, p.duration_days, p.name as package_name
            FROM transactions t
            LEFT JOIN packages p ON t.package_id = p.id
            WHERE t.order_id = %s
            """,
            (order_id,)
        )
        transaction = cursor.fetchone()

        if not transaction:
            logging.error(f"IPN: Transaction not found for order_id: {order_id}")
            return jsonify({
                "success": False,
                "message": "Giao dịch không tồn tại."
            }), 404


        if transaction['status'] in ['success', 'failed']:
            logging.warning(f"IPN: Transaction already processed: {order_id}")
            return jsonify({
                "success": True,
                "message": "IPN đã được xử lý trước đó."
            }), 200

        # Determine status
        status = "success" if result_code == 0 else "failed"

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
                (status, trans_id, result_code, order_id)
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

            logging.info(f"IPN: Transaction {order_id} updated to {status}")

            return jsonify({
                "success": True,
                "message": "IPN processed successfully.",
                "orderId": order_id,
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


@momo_bp.route("/momo/check-status/<order_id>", methods=["GET"])
@jwt_required()
def check_payment_status(order_id):
    """Check payment status"""
    conn = None
    cursor = None

    try:
        user_id = get_current_user_id()

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
            (order_id, user_id)
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