import os

from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event, text

# Завантаження змінних із .env файлу
load_dotenv()

from .config import Config
from .models import User, db

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ініціалізація розширень
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Налаштування менеджера входу
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Будь ласка, увійдіть для доступу до цієї сторінки"
    login_manager.login_message_category = "info"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Реєстрація маршрутів (routes)
    from .routes import appointments, auth, clients, main, services

    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(appointments.bp)
    app.register_blueprint(clients.bp)
    app.register_blueprint(services.bp)

    # Створення бази даних при першому запуску
    with app.app_context():
        db.create_all()

        # Налаштування SQLite для регістронезалежного пошуку для кириличних символів
        if db.engine.name == "sqlite":
            # Встановлюємо прагму для стандартного пошуку
            db.session.execute(text("PRAGMA case_sensitive_like=OFF"))

            # Створюємо власне порівняння Unicode з підтримкою кирилиці
            def unicode_nocase_collation(string1, string2):
                if string1 is None or string2 is None:
                    return (
                        0
                        if string1 is None and string2 is None
                        else -1 if string1 is None else 1
                    )
                string1_folded = string1.casefold()
                string2_folded = string2.casefold()
                if string1_folded == string2_folded:
                    return 0
                elif string1_folded < string2_folded:
                    return -1
                else:
                    return 1

            # Реєструємо функцію CASEFOLD для використання в SQL запитах
            def casefold_function(string):
                if string is None:
                    return None
                return string.casefold()

            # Отримуємо з'єднання з базою даних
            connection = db.engine.raw_connection()

            # Реєструємо функцію порівняння для використання в запитах
            connection.create_collation("UNICODE_NOCASE", unicode_nocase_collation)

            # Реєструємо функцію CASEFOLD як детерміністичну SQL функцію
            connection.create_function(
                "CASEFOLD", 1, casefold_function, deterministic=True
            )

            # Закриваємо з'єднання
            connection.close()

            db.session.commit()

    return app
