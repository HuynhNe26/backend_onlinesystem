from flask import Blueprint
from .momo import momo_bp
from .vnpay import vnpay_bp
from .zalopay import zalopay_bp

payment_bp = Blueprint("payment_bp", __name__)
payment_bp.register_blueprint(momo_bp, url_prefix="/momo")
payment_bp.register_blueprint(vnpay_bp, url_prefix="/vnpay")
payment_bp.register_blueprint(zalopay_bp, url_prefix="/zalopay")
