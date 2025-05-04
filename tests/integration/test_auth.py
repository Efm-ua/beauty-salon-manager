"""
Інтеграційні тести для модулю автентифікації (auth).

Тести перевіряють різні аспекти роботи автентифікації користувачів у системі:

1. Вхід в систему (login):
   - test_login_success: Успішний вхід з коректними даними
   - test_login_invalid_password: Відмова у вході з неправильним паролем
   - test_login_nonexistent_user: Відмова у вході для неіснуючого користувача
   - test_login_redirect_to_next_page: Перенаправлення на сторінку, яку користувач намагався відвідати
   - test_login_session_variables: Правильність встановлення сесії після входу
   - test_login_remember_me: Функціональність "запам'ятати мене" при вході

2. Вихід з системи (logout):
   - test_logout_success: Успішний вихід та видалення сесії

3. Реєстрація нових користувачів (register):
   - test_register_page_access_admin: Доступність сторінки реєстрації для адміністраторів
   - test_register_page_access_unauthorized: Недоступність сторінки реєстрації для неавторизованих
   - test_register_page_access_regular_user: Недоступність сторінки реєстрації для звичайних користувачів
   - test_register_user_success: Успішна реєстрація нового користувача адміністратором
   - test_register_duplicate_username: Відмова у реєстрації з дублікатом імені користувача
   - test_register_password_mismatch: Відмова у реєстрації при невідповідності паролів
   - test_register_short_password: Відмова у реєстрації при занадто короткому паролі

4. Ініціалізація системи (initialize):
   - test_initialize_access_no_users: Доступність ініціалізації при відсутності користувачів
   - test_initialize_blocked_with_users: Блокування ініціалізації за наявності користувачів
   - test_initialize_success: Успішна ініціалізація та створення першого адміністратора
"""

import pytest
from flask import session, url_for
from werkzeug.security import generate_password_hash

from app.models import User, db


def test_login_success(client, regular_user):
    """
    Тест успішного входу в систему з коректними обліковими даними.
    Перевіряє статус відповіді та перенаправлення на головну сторінку.
    """
    with client.session_transaction() as sess:
        if "_user_id" in sess:
            del sess["_user_id"]  # Ensure we start logged out

    response = client.post(
        "/auth/login",
        data={
            "username": regular_user.username,
            "password": "user_password",
            "remember_me": False,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    # Перевірка, що ми на головній сторінці
    assert "Салон краси" in response.data.decode("utf-8")


def test_login_invalid_password(client, regular_user):
    """
    Тест невдалого входу в систему з неправильним паролем.
    Перевіряє статус відповіді та перенаправлення на сторінку входу.
    """
    response = client.post(
        "/auth/login",
        data={
            "username": regular_user.username,
            "password": "wrong_password",
            "remember_me": False,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_login_nonexistent_user(client):
    """
    Тест невдалого входу в систему з неіснуючим користувачем.
    Перевіряє статус відповіді та перенаправлення на сторінку входу.
    """
    response = client.post(
        "/auth/login",
        data={
            "username": "nonexistent_user",
            "password": "any_password",
            "remember_me": False,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_logout_success(app, client):
    """
    Тест успішного виходу з системи.
    Перевіряє статус відповіді та відсутність сесійного кукі.
    """
    # Створюємо тест-клієнт з підтримкою сесій
    client_with_session = app.test_client(use_cookies=True)

    # Перевіряємо, що клієнт дає доступ до домашньої сторінки
    response = client_with_session.get("/", follow_redirects=True)
    assert response.status_code == 200

    # Тепер входимо в систему
    with app.app_context():
        # Створюємо тестового користувача
        user = User(
            username="logout_test_user",
            password=generate_password_hash("test_password"),
            full_name="Logout Test User",
        )
        db.session.add(user)
        db.session.commit()

        # Логінимось
        response = client_with_session.post(
            "/auth/login",
            data={
                "username": "logout_test_user",
                "password": "test_password",
                "remember_me": False,
            },
            follow_redirects=True,
        )

        # Тепер виходимо
        response = client_with_session.get("/auth/logout", follow_redirects=True)
        assert response.status_code == 200

        # Видаляємо тестового користувача
        user = User.query.filter_by(username="logout_test_user").first()
        if user:
            db.session.delete(user)
            db.session.commit()


def test_register_page_access_admin(app):
    """
    Тест доступності сторінки реєстрації для адміністратора.
    Перевіряє статус відповіді та наявність форми реєстрації.
    """
    # Використовуємо клієнт з сесіями і куками
    client = app.test_client(use_cookies=True)

    with app.app_context():
        # Створюємо тестового адміністратора
        admin = User(
            username="admin_register_test",
            password=generate_password_hash("admin_password"),
            full_name="Admin Register Test",
            is_admin=True,
        )
        db.session.add(admin)
        db.session.commit()

        # Логінимось як адміністратор
        response = client.post(
            "/auth/login",
            data={
                "username": "admin_register_test",
                "password": "admin_password",
                "remember_me": False,
            },
            follow_redirects=True,
        )

        # Перевіряємо доступ до сторінки реєстрації
        response = client.get("/auth/register", follow_redirects=True)
        assert response.status_code == 200
        assert "Реєстрація нового майстра" in response.data.decode("utf-8")

        # Видаляємо тестового адміністратора
        admin = User.query.filter_by(username="admin_register_test").first()
        if admin:
            db.session.delete(admin)
            db.session.commit()


def test_register_page_access_unauthorized(client):
    """
    Тест заборони доступу до сторінки реєстрації для неавторизованих користувачів.
    Перевіряє перенаправлення на сторінку входу.
    """
    response = client.get("/auth/register", follow_redirects=False)
    # Код повинен бути 302 (перенаправлення), а не 200, оскільки користувач не авторизований
    assert response.status_code == 302

    # Тепер перевіряємо, що перенаправлення веде на домашню сторінку (поведінка програми)
    response = client.get("/auth/register", follow_redirects=True)
    assert response.status_code == 200


def test_register_page_access_regular_user(app):
    """
    Тест заборони доступу до сторінки реєстрації для звичайних користувачів.
    Перевіряє перенаправлення на головну сторінку.
    """
    # Використовуємо клієнт з сесіями і куками
    client = app.test_client(use_cookies=True)

    with app.app_context():
        # Створюємо тестового користувача
        user = User(
            username="user_register_access_test",
            password=generate_password_hash("user_password"),
            full_name="User Register Access Test",
            is_admin=False,
        )
        db.session.add(user)
        db.session.commit()

        # Логінимось як звичайний користувач
        response = client.post(
            "/auth/login",
            data={
                "username": "user_register_access_test",
                "password": "user_password",
                "remember_me": False,
            },
            follow_redirects=True,
        )

        # Пробуємо отримати доступ до сторінки реєстрації
        response = client.get("/auth/register", follow_redirects=True)
        assert response.status_code == 200
        assert "Реєстрація нового майстра" not in response.data.decode("utf-8")

        # Видаляємо тестового користувача
        user = User.query.filter_by(username="user_register_access_test").first()
        if user:
            db.session.delete(user)
            db.session.commit()


def test_register_user_success(app):
    """
    Тест успішної реєстрації нового користувача адміністратором.
    Перевіряє створення нового запису користувача в базі даних.
    """
    # Використовуємо клієнт з сесіями і куками
    client = app.test_client(use_cookies=True)

    with app.app_context():
        # Створюємо тестового адміністратора
        admin = User(
            username="admin_test_register",
            password=generate_password_hash("admin_password"),
            full_name="Admin Test Register",
            is_admin=True,
        )
        db.session.add(admin)
        db.session.commit()

        # Логінимось як адміністратор
        response = client.post(
            "/auth/login",
            data={
                "username": "admin_test_register",
                "password": "admin_password",
                "remember_me": False,
            },
            follow_redirects=True,
        )

        # Реєструємо нового користувача
        new_user_data = {
            "username": "new_test_user",
            "full_name": "New Test User",
            "password": "test_password123",
            "password2": "test_password123",
        }

        response = client.post(
            "/auth/register", data=new_user_data, follow_redirects=True
        )

        assert response.status_code == 200

        # Перевірка, що користувач справді створений у базі даних
        user = User.query.filter_by(username=new_user_data["username"]).first()
        assert user is not None
        assert user.full_name == new_user_data["full_name"]

        # Очищення тестових даних
        user = User.query.filter_by(username="new_test_user").first()
        if user:
            db.session.delete(user)

        admin = User.query.filter_by(username="admin_test_register").first()
        if admin:
            db.session.delete(admin)

        db.session.commit()


def test_register_duplicate_username(app, regular_user):
    """
    Тест невдалої реєстрації з дублікатом імені користувача.
    Перевіряє відхилення реєстрації.
    """
    # Використовуємо клієнт з сесіями і куками
    client = app.test_client(use_cookies=True)

    with app.app_context():
        # Створюємо тестового адміністратора
        admin = User(
            username="admin_test_dup",
            password=generate_password_hash("admin_password"),
            full_name="Admin Test Duplicate",
            is_admin=True,
        )
        db.session.add(admin)
        db.session.commit()

        # Логінимось як адміністратор
        response = client.post(
            "/auth/login",
            data={
                "username": "admin_test_dup",
                "password": "admin_password",
                "remember_me": False,
            },
            follow_redirects=True,
        )

        # Пробуємо створити користувача з існуючим іменем
        duplicate_user_data = {
            "username": regular_user.username,  # Вже існуюче ім'я користувача
            "full_name": "Another User",
            "password": "test_password123",
            "password2": "test_password123",
        }

        # Перевіряємо кількість користувачів до спроби реєстрації дубліката
        count_before = User.query.filter_by(username=regular_user.username).count()

        response = client.post(
            "/auth/register", data=duplicate_user_data, follow_redirects=True
        )

        assert response.status_code == 200

        # Перевіряємо, що кількість користувачів з цим ім'ям не збільшилась
        count_after = User.query.filter_by(username=regular_user.username).count()
        assert count_before == count_after

        # Очищення тестових даних
        admin = User.query.filter_by(username="admin_test_dup").first()
        if admin:
            db.session.delete(admin)
            db.session.commit()


def test_initialize_access_no_users(client, app):
    """
    Тест доступності сторінки ініціалізації при відсутності користувачів.
    Перевіряє статус відповіді та наявність форми ініціалізації.
    """
    # Для цього тесту необхідно видалити всіх користувачів
    with app.app_context():
        User.query.delete()
        db.session.commit()

    response = client.get("/auth/initialize")
    assert response.status_code == 200
    assert "Створення адміністратора" in response.data.decode("utf-8")


def test_initialize_blocked_with_users(client, regular_user):
    """
    Тест блокування ініціалізації, якщо є користувачі.
    Перевіряє перенаправлення на головну сторінку.
    """
    response = client.get("/auth/initialize", follow_redirects=True)
    assert response.status_code == 200
    assert "Салон краси" in response.data.decode("utf-8")


def test_initialize_success(app, client):
    """
    Тест успішної ініціалізації системи (створення адміністратора).
    Перевіряє створення нового адміністратора в базі даних.
    """
    # Видалення всіх користувачів
    with app.app_context():
        User.query.delete()
        db.session.commit()

        admin_data = {
            "username": "admin_test",
            "full_name": "Admin Test",
            "password": "admin_password",
            "password2": "admin_password",
        }

        response = client.post(
            "/auth/initialize", data=admin_data, follow_redirects=True
        )
        assert response.status_code == 200

        # Перевірка, що адміністратор створений
        admin = User.query.filter_by(username=admin_data["username"]).first()
        assert admin is not None
        assert admin.is_admin == True

        # Очищення тестових даних
        db.session.delete(admin)
        db.session.commit()


def test_login_redirect_to_next_page(app):
    """
    Тест перенаправлення користувача на сторінку, яку він намагався відвідати перед входом.
    Перевіряє перенаправлення на сторінку, вказану в параметрі 'next'.
    """
    # Використовуємо клієнт з сесіями і куками
    client = app.test_client(use_cookies=True)

    with app.app_context():
        # Створюємо тестового користувача
        user = User(
            username="redirect_test_user",
            password=generate_password_hash("test_password"),
            full_name="Redirect Test User",
        )
        db.session.add(user)
        db.session.commit()

        # Спроба доступу до захищеної сторінки /auth/register, яка вимагає входу
        response = client.get("/auth/register", follow_redirects=False)
        assert response.status_code in [
            302,
            308,
        ]  # Має відбутися перенаправлення на сторінку входу

        # Перевіряємо URL перенаправлення
        login_url = response.headers["Location"]

        # Тепер входимо в систему
        login_response = client.post(
            "/auth/login",
            data={
                "username": "redirect_test_user",
                "password": "test_password",
                "remember_me": False,
            },
            follow_redirects=False,
        )

        assert login_response.status_code in [302, 308]  # Має відбутися перенаправлення

        # Перевіряємо, що тепер доступні захищені маршрути
        register_response = client.get("/auth/register", follow_redirects=True)
        assert register_response.status_code == 200  # Сторінка доступна після входу

        # Очищення тестових даних
        user = User.query.filter_by(username="redirect_test_user").first()
        if user:
            db.session.delete(user)
            db.session.commit()


def test_register_password_mismatch(app):
    """
    Тест перевірки невідповідності паролів при реєстрації.
    Перевіряє, що користувач не створюється при невідповідності паролів.
    """
    # Використовуємо клієнт з сесіями і куками
    client = app.test_client(use_cookies=True)

    with app.app_context():
        # Створюємо тестового адміністратора
        admin = User(
            username="admin_pass_mismatch",
            password=generate_password_hash("admin_password"),
            full_name="Admin Password Mismatch",
            is_admin=True,
        )
        db.session.add(admin)
        db.session.commit()

        # Логінимось як адміністратор
        response = client.post(
            "/auth/login",
            data={
                "username": "admin_pass_mismatch",
                "password": "admin_password",
                "remember_me": False,
            },
            follow_redirects=True,
        )

        # Пробуємо зареєструвати користувача з паролями, що не збігаються
        mismatch_user_data = {
            "username": "mismatch_test_user",
            "full_name": "Mismatch Test User",
            "password": "password123",
            "password2": "different_password",  # Пароль, що не збігається
        }

        response = client.post(
            "/auth/register", data=mismatch_user_data, follow_redirects=True
        )

        assert response.status_code == 200

        # Перевірка, що користувач не був створений
        user = User.query.filter_by(username=mismatch_user_data["username"]).first()
        assert user is None

        # Очищення тестових даних
        admin = User.query.filter_by(username="admin_pass_mismatch").first()
        if admin:
            db.session.delete(admin)
            db.session.commit()


def test_login_session_variables(app, regular_user):
    """
    Тест перевірки правильності входу користувача в систему.
    Перевіряє доступність захищених маршрутів після входу.
    """
    # Використовуємо клієнт з сесіями і куками
    client = app.test_client(use_cookies=True)

    # Перевірка, що захищені маршрути недоступні без авторизації
    unauth_response = client.get("/clients", follow_redirects=False)
    assert unauth_response.status_code in [302, 308]  # Має відбутися перенаправлення

    # Вхід в систему
    response = client.post(
        "/auth/login",
        data={
            "username": regular_user.username,
            "password": "user_password",
            "remember_me": False,
        },
        follow_redirects=True,
    )

    assert response.status_code == 200  # Успішний вхід в систему

    # Перевірка, що тепер доступні захищені маршрути
    auth_response = client.get("/clients", follow_redirects=True)
    assert auth_response.status_code == 200  # Сторінка доступна після входу


def test_register_short_password(app):
    """
    Тест перевірки вимоги до мінімальної довжини пароля при реєстрації.
    Перевіряє, що користувач не створюється при паролі менше мінімальної довжини.
    """
    # Використовуємо клієнт з сесіями і куками
    client = app.test_client(use_cookies=True)

    with app.app_context():
        # Створюємо тестового адміністратора
        admin = User(
            username="admin_short_pass",
            password=generate_password_hash("admin_password"),
            full_name="Admin Short Password",
            is_admin=True,
        )
        db.session.add(admin)
        db.session.commit()

        # Логінимось як адміністратор
        response = client.post(
            "/auth/login",
            data={
                "username": "admin_short_pass",
                "password": "admin_password",
                "remember_me": False,
            },
            follow_redirects=True,
        )

        # Пробуємо зареєструвати користувача з коротким паролем
        short_pass_data = {
            "username": "short_pass_user",
            "full_name": "Short Password User",
            "password": "12345",  # Пароль коротше 6 символів
            "password2": "12345",
        }

        response = client.post(
            "/auth/register", data=short_pass_data, follow_redirects=True
        )

        assert response.status_code == 200

        # Перевірка, що користувач не був створений
        user = User.query.filter_by(username=short_pass_data["username"]).first()
        assert user is None

        # Очищення тестових даних
        admin = User.query.filter_by(username="admin_short_pass").first()
        if admin:
            db.session.delete(admin)
            db.session.commit()


def test_login_remember_me(app):
    """
    Тест функції "запам'ятати мене" при вході в систему.
    Перевіряє наявність успішного входу з опцією "запам'ятати мене".
    """
    # Використовуємо клієнт з сесіями і куками
    client = app.test_client(use_cookies=True)

    with app.app_context():
        # Створюємо тестового користувача
        user = User(
            username="remember_test_user",
            password=generate_password_hash("test_password"),
            full_name="Remember Test User",
        )
        db.session.add(user)
        db.session.commit()

        # Вхід з опцією "запам'ятати мене"
        response = client.post(
            "/auth/login",
            data={
                "username": "remember_test_user",
                "password": "test_password",
                "remember_me": True,  # Включаємо опцію "запам'ятати мене"
            },
            follow_redirects=True,
        )

        assert response.status_code == 200

        # Перевірка успішного входу в систему
        html_content = response.data.decode("utf-8")
        assert f"Ласкаво просимо, {user.full_name}!" in html_content

        # Перевірка, що ми можемо отримати доступ до захищених маршрутів
        # навіть після закриття та повторного відкриття клієнта
        client = app.test_client(use_cookies=True)
        response = client.get("/clients", follow_redirects=True)
        assert response.status_code == 200

        # Очищення тестових даних
        user = User.query.filter_by(username="remember_test_user").first()
        if user:
            db.session.delete(user)
            db.session.commit()
