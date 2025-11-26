from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from datetime import timedelta
import os

# -------------------- Admin Blueprints --------------------
from back_end.route.admin.login import login_bp
from back_end.route.admin.admin import admin_bp
from back_end.route.admin.users import users_ad
from back_end.route.admin.exam import exam_ad

# -------------------- Users Blueprints --------------------
from back_end.route.users.auth import users_bp
from back_end.route.users.exam import exam_bp
from back_end.route.users.profile import profile_bp

app = Flask(__name__)
frontend_origins = [
    "https://frontend-admin-onlinesystem-eugd.onrender.com",
    "http://localhost:3000",
]

CORS(
    app,
    origins=frontend_origins,
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization", "Access-Control-Allow-Credentials"],
    methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    expose_headers=["Content-Type", "Authorization"]
)

app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "online_testing@123")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=1)
jwt = JWTManager(app)
# Users
app.register_blueprint(users_bp, url_prefix='/api/users')
app.register_blueprint(exam_bp, url_prefix='/api/exam')
app.register_blueprint(profile_bp, url_prefix='/api/users')
# Admin
app.register_blueprint(login_bp, url_prefix='/api/admin')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(users_ad, url_prefix='/api')
app.register_blueprint(exam_ad, url_prefix='/api/ad_exam')

# -------------------- Run App --------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # debug=True để test local, deploy thì để False
    app.run(host='0.0.0.0', port=port, debug=True)
