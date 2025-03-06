import os
from datetime import timedelta


class Config:
    SECRET_KEY = (
        os.environ.get("SECRET_KEY") or "change-this-to-something-secure-111123456789"
    )

    # Шлях до бази даних - тут ми використовуємо абсолютний шлях для PythonAnywhere
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or "sqlite:////" + os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "../beauty_salon.db"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
