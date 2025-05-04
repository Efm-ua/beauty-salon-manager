#!/usr/bin/env python
import sys
from getpass import getpass
from werkzeug.security import generate_password_hash
from app import create_app
from app.models import db, User


def create_admin_user():
    print("===== Створення адміністратора =====")

    # Запитуємо дані користувача
    username = input("Введіть логін адміністратора: ")

    # Перевіряємо, чи існує користувач з таким логіном
    app = create_app()
    with app.app_context():
        if User.query.filter_by(username=username).first():
            print(f"Користувач з логіном '{username}' вже існує!")
            return

        # Запитуємо та підтверджуємо пароль
        password = getpass("Введіть пароль: ")
        password_confirm = getpass("Підтвердіть пароль: ")

        if password != password_confirm:
            print("Паролі не співпадають!")
            return

        if len(password) < 6:
            print("Пароль має містити принаймні 6 символів!")
            return

        # Створюємо користувача
        try:
            user = User(
                username=username,
                password=generate_password_hash(password),
                full_name=input("Введіть повне ім'я адміністратора: "),
                is_admin=True,
            )

            db.session.add(user)
            db.session.commit()
            print(f"\nАдміністратор '{username}' успішно створений!")
            print("Тепер ви можете увійти до системи через веб-інтерфейс.")

        except Exception as e:
            print(f"Помилка при створенні користувача: {e}")
            db.session.rollback()


if __name__ == "__main__":
    create_admin_user()
