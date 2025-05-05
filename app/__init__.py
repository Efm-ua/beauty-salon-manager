import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text

# Завантаження змінних із .env файлу
load_dotenv()

# Imports after load_dotenv to ensure environment variables are loaded
from .config import Config  # noqa: E402
from .models import User, db  # noqa: E402

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    # Ініціалізація розширень
    db.init_app(app)

    # Ініціалізація міграцій після ініціалізації SQLAlchemy
    from flask_migrate import Migrate

    migrate = Migrate(app, db)

    login_manager.init_app(app)
    csrf.init_app(app)

    # Налаштування менеджера входу
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please login to access this page"
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Jinja2 filters
    @app.template_filter("format_percentage")
    def format_percentage(value):
        if value is None:
            return "0.00"
        return f"{float(value):.2f}"

    @app.template_filter("format_currency")
    def format_currency(value):
        if value is None:
            return "0.00"
        return f"{float(value):.2f}"

    # Реєстрація маршрутів (routes)
    from .routes import appointments, auth, clients, main, reports, services

    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(appointments.bp)
    app.register_blueprint(clients.bp)
    app.register_blueprint(services.bp)
    app.register_blueprint(reports.bp)

    # Створення бази даних при першому запуску
    with app.app_context():
        db.create_all()

        # Налаштування SQLite для регістронезалежного пошуку
        if db.engine.name == "sqlite":
            # Встановлюємо прагму для стандартного пошуку
            db.session.execute(text("PRAGMA case_sensitive_like=OFF"))
            db.session.commit()

    @app.route("/ping")
    def ping():
        return "pong"

    # Create upload directory if it doesn't exist
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    @app.context_processor
    def inject_now():
        return {"now": datetime.utcnow()}

    # Create first admin user if no users exist
    with app.app_context():
        from werkzeug.security import generate_password_hash

        if User.query.count() == 0:
            admin_username = app.config.get("ADMIN_USERNAME", "admin")
            admin_password = app.config.get("ADMIN_PASSWORD", "admin")
            admin_full_name = app.config.get("ADMIN_FULL_NAME", "Administrator")

            admin = User(
                username=admin_username,
                password=generate_password_hash(admin_password),
                full_name=admin_full_name,
                is_admin=True,
            )
            db.session.add(admin)
            db.session.commit()

    return app
