# blueprints/momo.py
import os
import json
import time
import uuid
import base64
import hmac
import hashlib
import traceback
import requests

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ...config.db_config import get_db_connection

momo_bp = Blueprint("momo_bp", __name__)

# === CONFIG từ ENV (không hard-code) ===
MOMO_CONFIG = {
    "endpoint": os.getenv("MOMO_ENDPOINT", "https://test-payment.momo.vn/v2/gateway/api/create"),
    "partnerCode": os.getenv("MOMO_PARTNER_CODE", "MOMO"),        # thay bằng mã partner thực tế nếu có
    "accessKey": os.getenv("MOMO_ACCESS_KEY", "F8BBA842ECF85"),
    "secretKey": os.getenv("MOMO_SECRET_KEY", "K951B6PE1waDMi640xX08PD3vg6EkVlz"),
    "redirectUrl": os.getenv("MOMO_REDIRECT_URL", "https://frontend-admin-onlinesystem-eugd.onrender.com/payment-success"),
    "ipnUrl": os.getenv("MOMO_IPN_URL", "https://uninclined-overhonestly-jone.ngrok-free.dev/api/payment/momo/ipn"),
    "timeout": int(os.getenv("MOMO_HTTP_TIMEOUT", "10"))
}


# ----------------------
# Helpers
# ----------------------
def get_current_user_id():
    identity = get_jwt_identity()
    if isinstance(identity, dict):
        return identity.get("id") or identity.get("id_user")
    try:
        return int(identity)
    except Exception:
        return identity


def hmac_sha256_hex(msg: str, secret_key: str) -> str:
    return hmac.new(secret_key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()


# Tạo chữ ký dùng khi gọi API create payment (theo thứ tự fields MoMo document)
def generate_momo_signature(params: dict, secret_key: str) -> str:
    # Thứ tự rất quan trọng
    raw = (
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
    return hmac_sha256_hex(raw, secret_key)


# Verify chữ ký IPN — dùng đúng format IPN V2 (theo docs MoMo)
def verify_momo_signature_ipn(data: dict, secret_key: str) -> bool:
    """
    Kiểm tra signature từ IPN. Dùng đúng thứ tự:
    accessKey, amount, extraData, message, orderId, orderInfo, orderType,
    partnerCode, payType, requestId, responseTime, resultCode, transId
    """
    try:
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
        computed = hmac_sha256_hex(raw, secret_key)
        received = data.get("signature", "")
        return computed == received
    except Exception:
        return False


# ----------------------
# Route: create payment
# ----------------------
@momo_bp.route("/momo", methods=["POST"])
@jwt_required()
def momo_payment():
    conn = cursor = None
    try:
        id_user = get_current_user_id()
        data = request.get_json() or {}

        required_fields = ["id_package"]
        missing = [f for f in required_fields if f not in data]
        if missing:
            return jsonify({"success": False, "message": f"Thiếu: {', '.join(missing)}"}), 400

        id_package = data["id_package"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Lấy thông tin package từ DB (server authoritative)
        cursor.execute(
            """
            SELECT 
                id_package, name_package, price_month, duration, quantity_exam
            FROM package 
            WHERE id_package = %s
            """,
            (id_package,)
        )
        pkg = cursor.fetchone()
        if not pkg:
            return jsonify({"success": False, "message": "Gói không tồn tại."}), 404

        # Giá lấy từ DB
        try:
            price = int(pkg["price_month"])
            if price <= 0:
                raise ValueError("Price <= 0")
        except Exception:
            return jsonify({"success": False, "message": "Giá gói không hợp lệ trong hệ thống."}), 500

        name_package = pkg.get("name_package") or data.get("name_package") or f"Thanh toán gói {id_package}"

        request_id = f"{MOMO_CONFIG['partnerCode']}_{int(time.time() * 1000)}"
        order_id = str(uuid.uuid4()).replace("-", "")[:12]

        # === IMPORTANT: extraData must be base64 encoded string ===
        raw_extra = json.dumps({"id_package": id_package, "id_user": id_user})
        extra_data = base64.b64encode(raw_extra.encode("utf-8")).decode("utf-8")

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

        # Lưu giao dịch (Pending)
        cursor.execute(
            """
            INSERT INTO payment (
                id_user, id_package, id_order, amount, status, payment, code, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
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

        # Gọi tới MoMo
        resp = requests.post(MOMO_CONFIG["endpoint"], json=payload, timeout=MOMO_CONFIG["timeout"])
        if resp.status_code != 200:
            # update trạng thái lỗi tạo link
            cursor.execute(
                "UPDATE payment SET status=%s WHERE id_order=%s",
                ("Không tạo được link thanh toán", order_id)
            )
            conn.commit()
            return jsonify({
                "success": False,
                "message": f"Cổng thanh toán lỗi HTTP {resp.status_code}"
            }), 500

        result = resp.json()
        # Nếu ok -> trả về payUrl cho client
        if result.get("resultCode") == 0 and result.get("payUrl"):
            return jsonify({"success": True, "data": result}), 200

        # MoMo trả lỗi nghiệp vụ
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
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Lỗi hệ thống: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ----------------------
# Route: IPN (callback)
# ----------------------
@momo_bp.route("/momo/ipn", methods=["POST"])
def momo_ipn():
    conn = cursor = None
    try:
        # MoMo gửi JSON content-type application/json
        if request.content_type and "application/json" not in request.content_type:
            return jsonify({"success": False, "message": "Invalid content type"}), 400

        data = request.get_json()
        print("IPN RECEIVED:", data)

        if not data:
            return jsonify({"success": False, "message": "No IPN data"}), 400

        # Verify chữ ký
        if not verify_momo_signature_ipn(data, MOMO_CONFIG["secretKey"]):
            print("Invalid signature. Rejecting IPN.")
            return jsonify({"success": False, "message": "Invalid signature"}), 403

        # Kiểm tra partnerCode
        partner_code = data.get("partnerCode")
        if partner_code != MOMO_CONFIG["partnerCode"]:
            print("partnerCode mismatch", partner_code)
            return jsonify({"success": False, "message": "Invalid partnerCode"}), 403

        order_id = data.get("orderId")
        result_code = str(data.get("resultCode", ""))
        trans_id = data.get("transId")
        ipn_amount = data.get("amount")

        if not order_id:
            return jsonify({"success": False, "message": "Missing orderId"}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Lock row for update to ensure atomic
        cursor.execute("SELECT * FROM payment WHERE id_order = %s FOR UPDATE", (order_id,))
        tx = cursor.fetchone()

        if not tx:
            return jsonify({"success": False, "message": "Order not found"}), 404

        # Idempotent: nếu đã thành công thì trả về 0 (MoMo expects 0)
        if tx["status"] == "Giao dịch thành công":
            return jsonify({"resultCode": 0, "message": "Order already processed", "orderId": order_id}), 200

        # Nếu trạng thái terminal khác "Đang giao dịch", trả về success để MoMo không retry
        if tx["status"] not in ("Đang giao dịch",):
            return jsonify({"resultCode": 0, "message": f"Order in terminal state: {tx['status']}", "orderId": order_id}), 200

        # So khớp số tiền
        try:
            db_amount = int(tx["amount"])
            if int(ipn_amount) != db_amount:
                conn.rollback()
                return jsonify({"success": False, "message": "Amount mismatch", "orderId": order_id}), 400
        except Exception:
            conn.rollback()
            return jsonify({"success": False, "message": "Amount parse error", "orderId": order_id}), 400

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

            # Lấy gói để update cho user (duration, quantity_exam)
            cursor.execute(
                """
                SELECT duration, quantity_exam
                FROM package
                WHERE id_package = %s
                """,
                (id_package,)
            )
            pkg = cursor.fetchone()
            if not pkg:
                conn.rollback()
                return jsonify({"success": False, "message": "Package not found"}), 404

            duration_days = pkg.get("duration") if pkg.get("duration") is not None else 0
            quantity_exam = pkg.get("quantity_exam") if pkg.get("quantity_exam") is not None else 1

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

        # Trả về 0 cho MoMo (theo spec)
        return jsonify({"resultCode": 0, "message": "IPN handled successfully", "orderId": order_id}), 200

    except Exception as e:
        traceback.print_exc()
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": f"IPN Error: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ----------------------
# Route: check status (user)
# ----------------------
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
                pkg.name_package,
                pkg.duration
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
            "packageName": tx.get("name_package"),
            "duration": tx.get("duration"),
            "createdAt": tx["created_at"].isoformat() if tx.get("created_at") else None,
            "code": tx.get("code")
        }
        return jsonify({"success": True, "transaction": result}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Lỗi kiểm tra trạng thái: {str(e)}"}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
