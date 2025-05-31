"""
Скрипт для оновлення схеми бази даних SQLite для додавання нових полів
до таблиці appointment.

Цей скрипт можна запустити напряму на PythonAnywhere або локально для
оновлення бази даних після зміни моделі Appointment.

Використання:
1. Активуйте віртуальне середовище: source venv/bin/activate
2. Запустіть скрипт: python update_db.py [шлях_до_бази_даних]
   За замовчуванням використовується шлях 'instance/app.db'
"""

import sqlite3
import sys
from datetime import datetime


def update_appointments_table(db_path):
    """
    Додає нові колонки до таблиці appointment: payment_status, amount_paid, payment_method.

    :param db_path: Шлях до файлу бази даних SQLite
    """
    try:
        # Підключення до бази даних
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Перевірка існування колонок (щоб не додавати їх знову, якщо вони вже є)
        cursor.execute("PRAGMA table_info(appointment)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]

        # Додавання колонок, якщо їх ще немає
        if "payment_status" not in column_names:
            print("Додавання колонки payment_status...")
            cursor.execute("ALTER TABLE appointment ADD COLUMN payment_status VARCHAR(10) NOT NULL DEFAULT 'unpaid'")

        if "amount_paid" not in column_names:
            print("Додавання колонки amount_paid...")
            cursor.execute("ALTER TABLE appointment ADD COLUMN amount_paid DECIMAL(10, 2)")

        if "payment_method" not in column_names:
            print("Додавання колонки payment_method...")
            cursor.execute("ALTER TABLE appointment ADD COLUMN payment_method VARCHAR(50)")

        # Збереження змін
        conn.commit()
        print(f"База даних {db_path} успішно оновлена!")

        # Закриття з'єднання
        conn.close()

    except Exception as e:
        print(f"Помилка при оновленні бази даних: {e}")
        if "conn" in locals():
            conn.close()
        sys.exit(1)


if __name__ == "__main__":
    # Використання аргументу командного рядка як шляху до бази даних або значення за замовчуванням
    db_path = sys.argv[1] if len(sys.argv) > 1 else "instance/app.db"
    print(f"Розпочато оновлення бази даних: {db_path}")
    print(f"Час: {datetime.now()}")

    update_appointments_table(db_path)
