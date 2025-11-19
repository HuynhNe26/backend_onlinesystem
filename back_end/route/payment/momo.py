from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import hmac
import hashlib
import json
import requests
import uuid
import time
import os
from ...config.db_config import get_db_connection

momo_bp = Blueprint("momo_bp", __name__)

# NÊN LẤY TỪ ENV THAY VÌ HARD-CODE
MOMO_CONFIG = {
    "endpoint": os.getenv("MOMO_ENDPOINT", "https://test-payment.momo.vn/v2/gateway/api/create"),
    "partnerCode": os.getenv("MOMO_PARTNER_CODE", "MOMO"),
    "accessKey": os.getenv("MOMO_ACCESS_KEY", "F8BBA842ECF85"),
    "secretKey": os.getenv("MOMO_SECRET_KEY", "K951B6PE1waDMi640xX08PD3vg6EkVlz"),
    "redirectUrl": os.getenv("MOMO_REDIRECT_URL",
                             "https://frontend-admin-onlinesystem-eugd.onrender.com/payment-success"),
    "ipnUrl": os.getenv("MOMO_IPN_URL", "https://uninclined-overhonestly-jone.ngrok-free.dev/api/payment/momo/ipn")
}


# Lấy ID user hiện tại
def get_current_user_id():
    identity = get_jwt_identity()
    if isinstance(identity, dict):
        return identity.get("id") or identity.get("id_user")
    try:
        return int(identity)
    except Exception:
        return identity


# Tạo chữ ký MoMo cho request tạo payment
def generate_momo_signature(params, secret_key):
    raw_signature = (
        f"accessKey={params.get('accessKey', '')}"
        f"&amount={params.get('amount', '')}"
        f"&extraData={params.get('extraData', '')}"
        f"&ipnUrl={params.get('ipnUrl', '')}"
        f"&orderId={params.get('orderId', '')}"
        f"&orderInfo={params.get('orderInfo', '')}"
        f"&partnerCode={params.get('partnerCode', '')}"
        f"&redirectUrl={params.get('redirectUrl', '')}"
        f"&requestId={params.get('requestId', '')}"
        f"&requestType={params.get('requestType', '')}"
    )
    return hmac.new(
        secret_key.encode("utf-8"),
        raw_signature.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def verify_momo_signature_ipn(data, secret_key):
    """
    Verify chữ ký IPN MoMo.
    MoMo có vài format khác nhau, mình thử lần lượt.
    """

    def hmac_sha256(msg: str) -> str:
        return hmac.new(secret_key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()

    received_sig = data.get("signature", "")
    if not received_sig:
        print("IPN không có signature.")
        return False

    candidates = []

    # Format IPN phổ biến nhất theo tài liệu (v2)
    candidates.append(
        "accessKey={accessKey}&amount={amount}&extraData={extraData}"
        "&message={message}&orderId={orderId}&orderInfo={orderInfo}"
        "&orderType={orderType}&partnerCode={partnerCode}&payType={payType}"
        "&requestId={requestId}&responseTime={responseTime}&resultCode={resultCode}"
        "&transId={transId}".format(
            accessKey=data.get("accessKey", ""),
            amount=data.get("amount", ""),
            extraData=data.get("extraData", ""),
            message=data.get("message", ""),
            orderId=data.get("orderId", ""),
            orderInfo=data.get("orderInfo", ""),
            orderType=data.get("orderType", ""),
            partnerCode=data.get("partnerCode", ""),
            payType=data.get("payType", ""),
            requestId=data.get("requestId", ""),
            responseTime=data.get("responseTime", ""),
            resultCode=data.get("resultCode", ""),
            transId=data.get("transId", ""),
        )
    )

    # Format khác (một số tài liệu cũ)
    candidates.append(
        "partnerCode={partnerCode}&accessKey={accessKey}&requestId={requestId}"
        "&amount={amount}&orderId={orderId}&orderInfo={orderInfo}"
        "&orderType={orderType}&transId={transId}&message={message}"
        "&responseTime={responseTime}&resultCode={resultCode}".format(
            partnerCode=data.get("partnerCode", ""),
            accessKey=data.get("accessKey", ""),
            requestId=data.get("requestId", ""),
            amount=data.get("amount", ""),
            orderId=data.get("orderId", ""),
            orderInfo=data.get("orderInfo", ""),
            orderType=data.get("orderType", ""),
            transId=data.get("transId", ""),
            message=data.get("message", ""),
            responseTime=data.get("responseTime", ""),
            resultCode=data.get("resultCode", ""),
        )
    )

    # Fallback: build theo thứ tự key cơ bản
    fallback_keys = [
        "partnerCode", "accessKey", "requestId", "amount",
        "orderId", "orderInfo", "orderType", "transId",
        "message", "responseTime", "resultCode", "extraData", "payType"
    ]
    fallback_raw = "&".join([f"{k}={data.get(k, '')}" for k in fallback_keys if k in data])
    if fallback_raw:
        candidates.append(fallback_raw)

    for raw in candidates:
        if not raw:
            continue
        computed = hmac_sha256(raw)
        if computed == received_sig:
            print("MoMo IPN signature verified with raw:", raw)
            return True

    print("Sai chữ ký MoMo IPN — không format nào khớp.")
    print("Signature nhận được:", received_sig)
    for i, raw in enumerate(candidates):
        if not raw:
            continue
        print(f"\n---- RAW CANDIDATE {i + 1} ----")
        print(raw)
        print("Computed:", hmac_sha256(raw))

    return False


# Tạo payment
@momo_bp.route("/momo", methods=["POST"])
@jwt_required()
def momo_payment():
    conn = cursor = None
    try:
        id_user = get_current_user_id()
        data = request.json

        required_fields = ["id_package"]
        if not data:
            return jsonify({"success": False, "message": "Không có dữ liệu."}), 400

        missing = [f for f in required_fields if f not in data]
        if missing:
            return jsonify({"success": False, "message": f"Thiếu: {', '.join(missing)}"}), 400

        id_package = data["id_package"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # LẤY THÔNG TIN PACKAGE TỪ DB (CHỐT GIÁ Ở SERVER)
        cursor.execute(
            """
            SELECT 
                name_package,
                price_month,
                duration,        -- ĐIỀU CHỈNH TÊN CỘT NÀY THEO SCHEMA CỦA BẠN
                quantity_exam    -- ĐIỀU CHỈNH TÊN CỘT NÀY THEO SCHEMA CỦA BẠN
            FROM package 
            WHERE id_package = %s
            """,
            (id_package,)
        )
        pkg = cursor.fetchone()
        if not pkg:
            return jsonify({"success": False, "message": "Gói không tồn tại."}), 404

        # GIÁ CHÍNH THỨC LẤY TỪ DB, KHÔNG DÙNG GIÁ TỪ CLIENT
        try:
            price = int(pkg["price_month"])
            if price <= 0:
                raise ValueError
        except Exception:
            return jsonify({"success": False, "message": "Giá gói không hợp lệ trong hệ thống."}), 500

        # Name package ưu tiên từ DB, nếu không thì fallback client gửi (hiếm)
        name_package = pkg.get("name_package") or data.get("name_package") or f"Thanh toán gói {id_package}"

        request_id = f"{MOMO_CONFIG['partnerCode']}_{int(time.time() * 1000)}"
        order_id = str(uuid.uuid4()).replace("-", "")[:12]

        extra_data = json.dumps({
            "id_package": id_package,
            "id_user": id_user
        })

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

        # Lưu giao dịch ở trạng thái "Đang giao dịch"
        cursor.execute(
            """
            INSERT INTO payment (
                id_user, id_package, id_order, amount, status, payment, code, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                id_user,
                id_package,
                order_id,
                price,
                "Đang giao dịch",
                "momo",
                None
            )
        )
        conn.commit()

        resp = requests.post(MOMO_CONFIG["endpoint"], json=payload, timeout=10)
        if resp.status_code != 200:
            # NÊN CẬP NHẬT TRẠNG THÁI ĐƠN NÀY LÀ FAIL LUÔN
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "UPDATE payment SET status=%s WHERE id_order=%s",
                ("Không tạo được link thanh toán", order_id)
            )
            conn.commit()
            return jsonify({
                "success": False,
                "message": f"Cổng thanh toán lỗi {resp.status_code}"
            }), 500

        result = resp.json()
        if result.get("resultCode") == 0 and result.get("payUrl"):
            return jsonify({"data": result}), 200

        # Nếu MoMo trả về lỗi nghiệp vụ
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "UPDATE payment SET status=%s WHERE id_order=%s",
            (result.get("message", "Lỗi tạo link thanh toán"), order_id)
        )
        conn.commit()

        return jsonify({
            "success": False,
            "message": result.get("message", "Lỗi tạo link"),
            "resultCode": result.get("resultCode")
        }), 400

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": f"Lỗi hệ thống: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# IPN MoMo
@momo_bp.route("/momo/ipn", methods=["POST"])
def momo_ipn():
    conn = cursor = None
    try:
        if request.content_type != "application/json":
            return jsonify({"success": False, "message": "Invalid content type"}), 400

        data = request.get_json()
        print("IPN RECEIVED:", data)

        if not data:
            return jsonify({"success": False, "message": "No IPN data"}), 400

        # Verify chữ ký
        if not verify_momo_signature_ipn(data, MOMO_CONFIG["secretKey"]):
            return jsonify({"success": False, "message": "Invalid signature"}), 403

        order_id = data.get("orderId")
        result_code = str(data.get("resultCode"))
        trans_id = data.get("transId")
        ipn_amount = data.get("amount")
        partner_code = data.get("partnerCode")

        # Check partnerCode xem có khớp không
        if partner_code != MOMO_CONFIG["partnerCode"]:
            return jsonify({"success": False, "message": "Invalid partnerCode"}), 403

        if not order_id:
            return jsonify({"success": False, "message": "Missing orderId"}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM payment WHERE id_order = %s FOR UPDATE", (order_id,))
        tx = cursor.fetchone()

        if not tx:
            return jsonify({"success": False, "message": "Order not found"}), 404

        # IDPOTENT: Nếu đã xử lý thành công thì không làm lại
        if tx["status"] == "Giao dịch thành công":
            return jsonify({
                "resultCode": 0,
                "message": "Order already processed",
                "orderId": order_id
            }), 200

        # Nếu trạng thái không phải "Đang giao dịch" (ví dụ đã failed trước đó)
        if tx["status"] not in ("Đang giao dịch",):
            return jsonify({
                "resultCode": 0,
                "message": f"Order in terminal state: {tx['status']}",
                "orderId": order_id
            }), 200

        # So khớp số tiền IPN với DB
        try:
            db_amount = int(tx["amount"])
            if int(ipn_amount) != db_amount:
                conn.rollback()
                return jsonify({
                    "success": False,
                    "message": "Amount mismatch",
                    "orderId": order_id
                }), 400
        except Exception:
            conn.rollback()
            return jsonify({
                "success": False,
                "message": "Amount parse error",
                "orderId": order_id
            }), 400

        # Xác định trạng thái thanh toán
        is_success = (result_code == "0")
        status_msg = "Giao dịch thành công" if is_success else "Giao dịch thất bại"

        cursor.execute(
            """
            UPDATE payment
            SET status = %s,
                code = %s
            WHERE id_order = %s
            """,
            (status_msg, trans_id, order_id)
        )

        if is_success:
            id_user = tx["id_user"]
            id_package = tx["id_package"]

            # Lấy lại thông tin gói
            cursor.execute(
                """
                SELECT 
                    duration,
                    quantity_exam
                FROM package
                WHERE id_package = %s
                """,
                (id_package,)
            )
            pkg = cursor.fetchone()

            if not pkg:
                conn.rollback()
                return jsonify({"success": False, "message": "Package not found"}), 404

            # Nếu bảng package không có duration/quantity_exam, bạn có thể hardcode lại giống code cũ ở đây
            duration_days = pkg.get("duration") if pkg.get("duration") is not None else 0
            quantity_exam = pkg.get("quantity_exam") if pkg.get("quantity_exam") is not None else 1

            # Cập nhật gói user
            cursor.execute(
                """
                UPDATE users
                SET 
                    id_package = %s,
                    start_package = NOW(),
                    end_package = DATE_ADD(NOW(), INTERVAL %s DAY),
                    quantity_exam = %s
                WHERE id_user = %s
                """,
                (id_package, duration_days, quantity_exam, id_user)
            )

        conn.commit()

        return jsonify({
            "resultCode": 0,
            "message": "IPN handled successfully",
            "orderId": order_id
        }), 200

    except Exception as e:
        import traceback
        print("IPN ERROR:", str(e))
        print(traceback.format_exc())

        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": f"IPN Error: {str(e)}"}), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# Check trạng thái
@momo_bp.route("/momo/check-status/<order_id>", methods=["GET"])
@jwt_required()
def check_payment_status(order_id):
    conn = cursor = None
    try:
        user_id = get_current_user_id()
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT 
                p.*, 
                pkg.name_package
            FROM payment p
            LEFT JOIN package pkg ON p.id_package = pkg.id_package
            WHERE p.id_order = %s AND p.id_user = %s
            """,
            (order_id, user_id)
        )
        tx = cursor.fetchone()
        if not tx:
            return jsonify({"success": False, "message": "Không tìm thấy giao dịch"}), 404

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
        if cursor:
            cursor.close()
        if conn:
            conn.close()
