import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

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

    _migrate = Migrate(app, db)  # noqa: F841

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

    # Register CLI commands
    from . import commands

    commands.init_app(app)

    @app.route("/ping")
    def ping():
        return "pong"

    # Set upload folder path
    app.config["UPLOAD_FOLDER"] = os.path.join(app.instance_path, "uploads")
    # Create upload directory if it doesn't exist
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    @app.context_processor
    def inject_now():
        return {"now": datetime.now(timezone.utc)}

    return app
