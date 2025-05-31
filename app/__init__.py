import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# Завантаження змінних із .env файлу - має бути перед усіма імпортами
load_dotenv()

from flask import Flask  # noqa: E402
from flask_login import LoginManager  # noqa: E402
from flask_wtf.csrf import CSRFProtect  # noqa: E402

# Imports after load_dotenv to ensure environment variables are loaded
from .config import Config  # noqa: E402

# Import all models to ensure they are registered with SQLAlchemy
from .models import Appointment  # noqa: F401, E402
from .models import AppointmentService  # noqa: F401, E402
from .models import Brand  # noqa: F401, E402
from .models import Client  # noqa: F401, E402
from .models import Product  # noqa: F401, E402
from .models import Service  # noqa: F401, E402
from .models import StockLevel  # noqa: F401, E402
from .models import User, db  # noqa: E402
from .models import WriteOffReason, ProductWriteOff, ProductWriteOffItem  # noqa: F401, E402
from .models import GoodsReceipt, GoodsReceiptItem  # noqa: F401, E402

# Mark imports as used for SQLAlchemy model registration
__all__ = [
    "Appointment",
    "AppointmentService",
    "Brand",
    "Client",
    "Product",
    "Service",
    "StockLevel",
    "User",
    "WriteOffReason",
    "ProductWriteOff",
    "ProductWriteOffItem",
    "GoodsReceipt",
    "GoodsReceiptItem",
    "db",
    "create_app",
]

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(test_config: Optional[Dict[str, Any]] = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    # Ініціалізація розширень
    db.init_app(app)

    # Налаштування foreign key constraints для SQLite
    with app.app_context():
        from .models import setup_foreign_key_constraints

        setup_foreign_key_constraints(app)

    # Ініціалізація міграцій після ініціалізації SQLAlchemy
    from flask_migrate import Migrate

    _migrate = Migrate(app, db)  # noqa: F841

    login_manager.init_app(app)
    csrf.init_app(app)

    # Налаштування менеджера входу
    login_manager.login_view = "auth.login"  # type: ignore
    login_manager.login_message = "Please login to access this page"
    login_manager.login_message_category = "info"

    @login_manager.user_loader  # type: ignore[misc]
    def load_user(user_id: str) -> Optional[User]:  # type: ignore[reportUnusedFunction]
        return db.session.get(User, int(user_id))

    # Jinja2 filters
    @app.template_filter("format_percentage")  # type: ignore[misc]
    def format_percentage(value: Optional[float]) -> str:  # type: ignore[reportUnusedFunction]
        if value is None:
            return "0.00"
        return f"{float(value):.2f}"

    @app.template_filter("format_currency")  # type: ignore[misc]
    def format_currency(value: Optional[float]) -> str:  # type: ignore[reportUnusedFunction]
        if value is None:
            return "0,00"
        return f"{float(value):.2f}".replace(".", ",")

    # Реєстрація маршрутів (routes)
    from .routes import appointments, auth, clients, main, products, reports, sales, services

    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(appointments.bp)  # type: ignore[attr-defined]
    app.register_blueprint(clients.bp)
    app.register_blueprint(services.bp)
    app.register_blueprint(products.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(sales.bp)

    # Register CLI commands
    from . import commands

    commands.init_app(app)  # type: ignore[attr-defined]

    @app.route("/ping")  # type: ignore[misc]
    def ping() -> str:  # type: ignore[reportUnusedFunction]
        return "pong"

    # Set upload folder path
    app.config["UPLOAD_FOLDER"] = os.path.join(app.instance_path, "uploads")
    # Create upload directory if it doesn't exist
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    @app.context_processor  # type: ignore[misc]
    def inject_now() -> Dict[str, datetime]:  # type: ignore[reportUnusedFunction]
        return {"now": datetime.now(timezone.utc)}

    @app.context_processor  # type: ignore[misc]
    def inject_csrf_token() -> Dict[str, Any]:  # type: ignore[reportUnusedFunction]
        from flask_wtf.csrf import generate_csrf

        return {"csrf_token": generate_csrf}

    return app
