import os
from datetime import timedelta


class Config:
    # Секретний ключ для підписання сесій
    SECRET_KEY = (
        os.environ.get("SECRET_KEY") or "change-this-to-something-secure-111123456789"
    )

    # Налаштування бази даних
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL") or "sqlite:///beauty_salon.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Налаштування авторизації
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
