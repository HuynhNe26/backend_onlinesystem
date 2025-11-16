from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
import os

# admin
from back_end.route.admin.login import login_bp
from back_end.route.admin.admin import admin_bp

# users
from back_end.route.users.auth import users_bp
from back_end.route.payment.payment_api import payment_bp
from back_end.route.users.exam import exam_bp
from back_end.route.users.category import category_bp
from back_end.route.users.package import package_bp

app = Flask(__name__)

frontend_origins = "https://frontend-admin-onlinesystem-eugd.onrender.com"

CORS(app,
     origins=frontend_origins,
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization", "Access-Control-Allow-Credentials"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     expose_headers=["Content-Type", "Authorization"])

app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "online_testing@123")
jwt = JWTManager(app)

app.register_blueprint(users_bp, url_prefix='/api/users')
app.register_blueprint(payment_bp, url_prefix='/api/payment')
app.register_blueprint(exam_bp, url_prefix='/api/exam')
app.register_blueprint(category_bp, url_prefix='/api/categories')
app.register_blueprint(package_bp, url_prefix='/api')

app.register_blueprint(login_bp, url_prefix='/api/admin')
app.register_blueprint(admin_bp, url_prefix='/api/admin')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)