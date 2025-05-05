import os
from datetime import timedelta

# Define base directory for the project
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))


class Config:
    SECRET_KEY = (
        os.environ.get("SECRET_KEY") or "change-this-to-something-secure-111123456789"
    )

    # Шлях до бази даних - тут ми використовуємо абсолютний шлях для PythonAnywhere
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or "sqlite:///" + os.path.join(BASE_DIR, "instance", "beauty_salon.db")

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
