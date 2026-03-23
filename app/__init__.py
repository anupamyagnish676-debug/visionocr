from flask import Flask
from flask_login import LoginManager
from app.models.database import db, User
import os

# ── PASTE YOUR GEMINI API KEY HERE (starts with AIza...) ──
import os
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyB0KEnmR5ZU1CcAl1kdXyrBey0qanqr6pw')

# ────────────────────────────────────────────────────

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"]                     = "ocr-secret-2024"
    app.config["SQLALCHEMY_DATABASE_URI"]        = "sqlite:///ocr_vlm.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"]             = 20 * 1024 * 1024
    app.config["UPLOAD_FOLDER"]                  = "app/static/uploads"
    app.config["GEMINI_API_KEY"]                 = GEMINI_API_KEY

    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'

    @login_manager.user_loader
    def load_user(uid):
        return User.query.get(int(uid))

    with app.app_context():
        db.create_all()

    from app.routes.auth    import auth_bp
    from app.routes.main    import main_bp, history_bp
    from app.routes.extract import extract_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(extract_bp)
    app.register_blueprint(history_bp)

    return app
