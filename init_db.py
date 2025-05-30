#!/usr/bin/env python3
"""
Скрипт для ініціалізації бази даних
"""

import sys
from flask_migrate import upgrade
from app import create_app


def init_database():
    """Ініціалізує базу даних з усіма міграціями"""

    # Створюємо додаток
    app = create_app()

    with app.app_context():
        try:
            print("Початок ініціалізації бази даних...")

            # Застосовуємо всі міграції
            upgrade()

            print("База даних успішно ініціалізована!")
            return True

        except Exception as e:
            print(f"Помилка при ініціалізації бази даних: {e}")
            return False


if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
