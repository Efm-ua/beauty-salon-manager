"""
Скрипт для перевірки бази даних та таблиці appointment.
"""

import sqlite3
import sys
from datetime import datetime


def check_database(db_path):
    """
    Перевіряє структуру бази даних SQLite.

    :param db_path: Шлях до файлу бази даних SQLite
    """
    try:
        # Підключення до бази даних
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Отримання списку таблиць
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print("Таблиці в базі даних:", [table[0] for table in tables])

        # Перевірка наявності таблиці appointment
        if ("appointment",) in tables:
            # Отримання інформації про колонки таблиці appointment
            cursor.execute("PRAGMA table_info(appointment)")
            columns = cursor.fetchall()
            print("\nКолонки таблиці appointment:")
            for column in columns:
                print(
                    f"- {column[1]} ({column[2]}), NotNull: {column[3]}, DefaultValue: {column[4]}"
                )

            # Перевірка наявності конкретних колонок
            column_names = [column[1] for column in columns]
            print("\nПеревірка наявності нових колонок:")
            print("payment_status:", "payment_status" in column_names)
            print("amount_paid:", "amount_paid" in column_names)
            print("payment_method:", "payment_method" in column_names)
        else:
            print("\nТаблиця appointment не знайдена!")

        # Закриття з'єднання
        conn.close()

    except Exception as e:
        print(f"Помилка при перевірці бази даних: {e}")
        if "conn" in locals():
            conn.close()
        sys.exit(1)


if __name__ == "__main__":
    # Використання аргументу командного рядка як шляху до бази даних або значення за замовчуванням
    db_path = sys.argv[1] if len(sys.argv) > 1 else "instance/beauty_salon.db"
    print(f"Перевірка бази даних: {db_path}")
    print(f"Час: {datetime.now()}")

    check_database(db_path)
