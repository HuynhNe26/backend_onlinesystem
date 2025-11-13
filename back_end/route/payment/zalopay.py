from flask import Blueprint, request, jsonify
import hmac, hashlib, json, requests, time, random

zalopay_bp = Blueprint("zalopay_bp", __name__)

@zalopay_bp.route("/zalopay", methods=["POST"])
def zalopay_payment():
    app_id = 2553
    key1 = "8PGK0A2C4UZM5NR4PGA4QKL3K9F4E8VN"
    endpoint = "https://sb-openapi.zalopay.vn/v2/create"

    data = request.json
    amount = int(data.get("amount", 10000))
    order_info = data.get("orderInfo", "Thanh toán ZaloPay")

    app_trans_id = f"{time.strftime('%y%m%d')}_{random.randint(100000, 999999)}"

    order = {
        "app_id": app_id,
        "app_trans_id": app_trans_id,
        "app_user": "user_test",
        "app_time": int(round(time.time() * 1000)),
        "item": json.dumps([]),
        "embed_data": json.dumps({}),
        "amount": amount,
        "description": order_info,
        "bank_code": "",
        "callback_url": "https://webhook.site/test"
    }

    raw_data = f"{app_id}|{order['app_trans_id']}|{order['app_user']}|{order['amount']}|{order['app_time']}|{order['embed_data']}|{order['item']}"
    order["mac"] = hmac.new(key1.encode(), raw_data.encode(), hashlib.sha256).hexdigest()

    res = requests.post(endpoint, json=order)
    return jsonify(res.json())
