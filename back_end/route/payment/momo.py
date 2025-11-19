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



def verify_momo_signature(data, secret_key):
    """
    MoMo có nhiều format RAW khác nhau cho IPN.
    Hàm này thử nhiều format chuẩn của MoMo và chọn format nào khớp chữ ký.
    Nếu khớp → True, không khớp → False.
    """

    def hmac_sha256(msg):
        return hmac.new(secret_key.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()

    received_sig = data.get("signature", "")
    if not received_sig:
        print(" IPN không có signature.")
        return False

    candidates = []

    # Format IPN CHUẨN NHẤT của MoMo (tài liệu chính thức)
    candidates.append(
        f"partnerCode={data.get('partnerCode','')}"
        f"&accessKey={data.get('accessKey','')}"
        f"&requestId={data.get('requestId','')}"
        f"&amount={data.get('amount','')}"
        f"&orderId={data.get('orderId','')}"
        f"&orderInfo={data.get('orderInfo','')}"
        f"&orderType={data.get('orderType','')}"
        f"&transId={data.get('transId','')}"
        f"&message={data.get('message','')}"
        f"&responseTime={data.get('responseTime','')}"
        f"&resultCode={data.get('resultCode','')}"
    )

    # Format IPN phổ biến thứ 2 (có extraData + payType)
    candidates.append(
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

    # Format của yêu cầu create payment (để dự phòng)
    candidates.append(
        f"accessKey={data.get('accessKey','')}"
        f"&amount={data.get('amount','')}"
        f"&extraData={data.get('extraData','')}"
        f"&ipnUrl={data.get('ipnUrl','')}"
        f"&orderId={data.get('orderId','')}"
        f"&orderInfo={data.get('orderInfo','')}"
        f"&partnerCode={data.get('partnerCode','')}"
        f"&redirectUrl={data.get('redirectUrl','')}"
        f"&requestId={data.get('requestId','')}"
        f"&requestType={data.get('requestType','')}"
    )

    # Fallback: build raw theo các key IPN thường gặp
    fallback_keys = [
        "partnerCode", "accessKey", "requestId", "amount",
        "orderId", "orderInfo", "orderType", "transId",
        "message", "responseTime", "resultCode"
    ]
    fallback_raw = "&".join([f"{k}={data.get(k,'')}" for k in fallback_keys if k in data])
    candidates.append(fallback_raw)

    # Check từng kiểu raw xem có match không
    for raw in candidates:
        if not raw:
            continue
        computed = hmac_sha256(raw)
        if computed == received_sig:
            print(" MoMo signature verified.")
            return True

    # Log giúp debug khi sai
    print(" Sai chữ ký MoMo IPN — không format nào khớp.")
    print("Signature nhận được:", received_sig)
    for i, raw in enumerate(candidates):
        print(f"\n---- RAW CANDIDATE {i+1} ----")
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

        cursor.execute("""
            INSERT INTO payment (id_user, id_package, id_order, amount, duration, status, payment, code, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())
        """, (id_user, id_package, order_id, price, None, "Đang giao dịch", "momo", None))
        conn.commit()

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
        if cursor: cursor.close()
        if conn: conn.close()

# IPN MoMo
@momo_bp.route("/momo/ipn", methods=["POST"])
def momo_ipn():
    conn = cursor = None
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "message": "No IPN data"}), 400

        # VERIFY SIGNATURE
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

            # Gán gói
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
        print(" IPN ERROR:", str(e))
        print(traceback.format_exc())

        if conn: conn.rollback()
        return jsonify({"success": False, "message": f"IPN Error: {str(e)}"}), 500

    finally:
        if cursor: cursor.close()
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
        if cursor: cursor.close()
        if conn: conn.close()
