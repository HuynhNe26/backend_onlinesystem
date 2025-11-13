from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager

# users
from back_end.route.users.auth import users_bp
from back_end.route.admin.dashboard import admin_bp
from back_end.route.admin.login import login_bp
from back_end.route.admin.logout import logout_bp
from back_end.route.admin.fullAdmin import admin_users_bp
from back_end.route.payment.payment_api import payment_bp
from back_end.route.users.exam import exam_bp
from back_end.route.users.category import category_bp

app = Flask(__name__)

# ===== CORS CONFIGURATION =====
CORS(app,
     origins=["http://localhost:3000", "http://localhost:5173",
              "http://127.0.0.1:3000", "http://127.0.0.1:5173"],
     supports_credentials=True,
     allow_headers=["Content-Type", "Authorization", "Access-Control-Allow-Credentials"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     expose_headers=["Content-Type", "Authorization"])

app.config["JWT_SECRET_KEY"] = "online_testing@123"
jwt = JWTManager(app)

# Register blueprints
app.register_blueprint(admin_users_bp, url_prefix="/api/admin/users")
app.register_blueprint(users_bp, url_prefix='/api/users')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(login_bp, url_prefix='/api/login')
app.register_blueprint(logout_bp, url_prefix='/api/logout')
app.register_blueprint(payment_bp, url_prefix='/api/payment')
app.register_blueprint(exam_bp, url_prefix='/api/exam')
app.register_blueprint(exam_bp, url_prefix='/api/categories')


if __name__ == '__main__':
    # Lấy PORT từ environment variable (Render sẽ cung cấp)
    import os

    port = int(os.environ.get('PORT', 5000))

    # QUAN TRỌNG: phải bind vào 0.0.0.0
    app.run(host='0.0.0.0', port=port, debug=False)