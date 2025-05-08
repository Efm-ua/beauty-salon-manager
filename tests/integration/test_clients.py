"""
Інтеграційні тести для модуля управління клієнтами.

Тести перевіряють різні аспекти роботи системи управління клієнтами:

1. Відображення списку клієнтів:
   - test_client_list_page_accessible: Доступність сторінки списку клієнтів для авторизованого користувача
   - test_client_list_unauthorized: Заборона доступу до списку клієнтів для неавторизованих користувачів

2. Створення клієнтів:
   - test_client_create_page_accessible: Доступність сторінки створення клієнта
   - test_client_create_success: Успішне створення клієнта з коректними даними
   - test_client_create_duplicate_phone: Невдале створення клієнта з дублікатом телефону
   - test_client_create_invalid_email: Невдале створення клієнта з неправильним email

3. Перегляд клієнта:
   - test_client_view_page_accessible: Доступність сторінки перегляду клієнта
   - test_client_view_shows_correct_info: Відображення коректної інформації про клієнта

4. Редагування клієнта:
   - test_client_edit_page_accessible: Доступність сторінки редагування клієнта
   - test_client_edit_success: Успішне оновлення інформації про клієнта
   - test_client_edit_duplicate_phone: Невдале оновлення з дублікатом телефону

5. Пошук клієнтів:
   - test_client_search_by_name: Пошук клієнтів за ім'ям
   - test_client_search_by_phone: Пошук клієнтів за телефоном
   - test_client_search_by_multiple_name_words: Пошук клієнтів за кількома словами в імені
   - test_client_search_cyrillic_case_insensitive: Пошук клієнтів за кириличним ім'ям з різним регістром

6. Видалення клієнта:
   - test_client_delete_with_appointments: Заборона видалення клієнта з існуючими записами
   - test_client_delete_success: Успішне видалення клієнта без записів

7. API клієнтів:
   - test_client_api_search: Тест API пошуку клієнтів
   - test_client_api_search_multiple_words: Тест API пошуку клієнтів за кількома словами
   - test_client_api_search_cyrillic_case_insensitive: Тест API пошуку клієнтів за кириличним ім'ям з різним регістром
"""

import uuid
from datetime import date, time, timedelta

import pytest
from werkzeug.security import generate_password_hash

from app.models import Appointment, Client, User, db


# Фікстура для авторизованого користувача спеціально для тестів клієнтів
@pytest.fixture(scope="function")
def auth_client_for_clients(client, session):
    """
    Створює авторизованого клієнта для тестів клієнтів.
    """
    # Перевіряємо, чи існує вже користувач
    test_user = User.query.filter_by(username="test_user_for_clients").first()

    # Якщо користувач не існує - створюємо його
    if not test_user:
        test_user = User(
            username="test_user_for_clients",
            password=generate_password_hash("test_password"),
            full_name="Test User For Clients",
            is_admin=True,  # Змінено на True щоб створити адміністратора
        )
        session.add(test_user)
        session.commit()

    # Логінимось
    response = client.post(
        "/auth/login",
        data={
            "username": "test_user_for_clients",
            "password": "test_password",
            "remember_me": False,
        },
        follow_redirects=True,
    )

    # Перевірка успішності автентифікації
    assert (
        response.status_code == 200
    ), f"Login failed: status code {response.status_code}"

    # Перевірка наявності ознак успішного входу в систему
    # 1. Перевірка наявності елементу, який видно тільки після входу (посилання на вихід)
    assert (
        "/auth/logout" in response.text
    ), "Login failed: Logout link not found in response"

    # 2. Перевірка наявності імені користувача у відповіді
    assert (
        "Test User For Clients" in response.text
    ), "Login failed: User name not found in response"

    # 3. Перевірка наявності мітки "Адміністратор" у відповіді
    assert (
        "Адміністратор" in response.text
    ), "Login failed: Admin label not found in response"

    yield client

    # Виходимо з системи після тестів
    client.get("/auth/logout", follow_redirects=True)


def test_client_list_page_accessible(auth_client_for_clients):
    """
    Тест доступності сторінки списку клієнтів для авторизованого користувача.
    Перевіряє статус відповіді та наявність елементів інтерфейсу.
    """
    response = auth_client_for_clients.get("/clients/")
    assert response.status_code == 200
    assert "Клієнти" in response.data.decode("utf-8")
    assert "Додати клієнта" in response.data.decode("utf-8")


def test_client_list_unauthorized(client):
    """
    Тест заборони доступу до списку клієнтів для неавторизованих користувачів.
    Перевіряє перенаправлення на сторінку входу.
    """
    response = client.get("/clients/", follow_redirects=False)
    assert response.status_code == 302  # Редирект

    # Перевірка, що перенаправлення веде на сторінку входу
    response = client.get("/clients/", follow_redirects=True)
    assert response.status_code == 200
    assert "Увійти в систему" in response.data.decode(
        "utf-8"
    ) or "Вхід - Салон краси" in response.data.decode("utf-8")


def test_client_create_page_accessible(auth_client_for_clients):
    """
    Тест доступності сторінки створення клієнта для авторизованого користувача.
    Перевіряє статус відповіді та наявність форми створення.
    """
    response = auth_client_for_clients.get("/clients/create")
    assert response.status_code == 200
    assert "Новий клієнт" in response.data.decode("utf-8")
    assert "Зберегти" in response.data.decode("utf-8")


def test_client_create_success(auth_client_for_clients, session):
    """
    Тест успішного створення клієнта з коректними даними.
    Перевіряє статус відповіді, перенаправлення та збереження даних у БД.
    """
    # Дані для нового клієнта з унікальним телефоном
    unique_id = uuid.uuid4().hex[:8]
    client_data = {
        "name": f"Test New Client {unique_id}",
        "phone": f"+38099{unique_id}",
        "email": f"test_new_{unique_id}@example.com",
        "notes": "Test notes for new client",
        "submit": "Зберегти",
    }

    response = auth_client_for_clients.post(
        "/clients/create", data=client_data, follow_redirects=True
    )
    assert response.status_code == 200
    assert "Клієнт успішно доданий!" in response.data.decode("utf-8")

    # Перевірка, що клієнт збережений у БД
    client = Client.query.filter_by(phone=client_data["phone"]).first()
    assert client is not None
    assert client.name == client_data["name"]
    assert client.email == client_data["email"]
    assert client.notes == client_data["notes"]


def test_client_create_duplicate_phone(auth_client_for_clients, session):
    """
    Тест невдалого створення клієнта з дублікатом телефону.
    Перевіряє відхилення форми та повідомлення про помилку.
    """
    # Спочатку створюємо клієнта
    unique_id = uuid.uuid4().hex[:8]

    test_client = Client(
        name=f"Test Client For Duplicate {unique_id}",
        phone=f"+38077{unique_id}",
        email=f"duplicate_{unique_id}@example.com",
        notes="Test client for duplicate test",
    )
    session.add(test_client)
    session.commit()

    # Дані для нового клієнта з існуючим телефоном
    client_data = {
        "name": "Another Test Client",
        "phone": f"+38077{unique_id}",  # Той самий телефон
        "email": "another_test@example.com",
        "notes": "Test notes for duplicate phone",
        "submit": "Зберегти",
    }

    response = auth_client_for_clients.post(
        "/clients/create", data=client_data, follow_redirects=True
    )
    assert response.status_code == 200
    assert "Клієнт з таким номером телефону вже існує" in response.data.decode("utf-8")


def test_client_create_invalid_email(auth_client_for_clients):
    """
    Тест невдалого створення клієнта з неправильним email.
    Перевіряє відхилення форми та повідомлення про помилку.
    """
    # Дані для нового клієнта з неправильним email
    unique_id = uuid.uuid4().hex[:8]
    client_data = {
        "name": f"Test Client Bad Email {unique_id}",
        "phone": f"+38088{unique_id}",
        "email": "not_an_email",  # Неправильний формат email
        "notes": "Test notes for invalid email",
        "submit": "Зберегти",
    }

    response = auth_client_for_clients.post(
        "/clients/create", data=client_data, follow_redirects=True
    )
    assert response.status_code == 200
    # Перевірка наявності повідомлення про помилку валідації email
    decoded_response = response.data.decode("utf-8")
    assert (
        "Введіть правильну адресу електронної пошти" in decoded_response
        or "Невірний email" in decoded_response
        or "Invalid email" in decoded_response
    )


def test_client_view_page_accessible(auth_client_for_clients, session):
    """
    Тест доступності сторінки перегляду клієнта.
    Перевіряє статус відповіді та відображення даних клієнта.
    """
    # Створюємо тестового клієнта
    unique_id = uuid.uuid4().hex[:8]

    test_client = Client(
        name=f"Test Client For View {unique_id}",
        phone=f"+38066{unique_id}",
        email=f"view_{unique_id}@example.com",
        notes="Test client for view test",
    )
    session.add(test_client)
    session.commit()
    client_id = test_client.id

    # Використовуємо адміністратора для перевірки доступу до сторінки перегляду клієнта
    response = auth_client_for_clients.get(f"/clients/{client_id}")
    assert response.status_code == 200
    assert f"Test Client For View {unique_id}" in response.data.decode("utf-8")
    assert f"+38066{unique_id}" in response.data.decode("utf-8")


def test_client_view_shows_correct_info(auth_client_for_clients, session):
    """
    Тест відображення коректної інформації про клієнта.
    Перевіряє наявність всіх атрибутів клієнта на сторінці.
    """
    # Створюємо тестового клієнта
    unique_id = uuid.uuid4().hex[:8]

    test_client = Client(
        name=f"Test Client For Info {unique_id}",
        phone=f"+38055{unique_id}",
        email=f"info_{unique_id}@example.com",
        notes="Test client notes for info test",
    )
    session.add(test_client)
    session.commit()
    client_id = test_client.id

    response = auth_client_for_clients.get(f"/clients/{client_id}")
    assert response.status_code == 200
    content = response.data.decode("utf-8")

    assert f"Test Client For Info {unique_id}" in content
    assert f"+38055{unique_id}" in content
    assert f"info_{unique_id}@example.com" in content
    assert "Test client notes for info test" in content


def test_client_edit_page_accessible(auth_client_for_clients, session):
    """
    Тест доступності сторінки редагування клієнта.
    Перевіряє статус відповіді та наявність форми редагування.
    """
    # Створюємо тестового клієнта
    unique_id = uuid.uuid4().hex[:8]

    test_client = Client(
        name=f"Test Client For Edit {unique_id}",
        phone=f"+38044{unique_id}",
        email=f"edit_{unique_id}@example.com",
        notes="Test client for edit test",
    )
    session.add(test_client)
    session.commit()
    client_id = test_client.id
    client_name = test_client.name

    response = auth_client_for_clients.get(f"/clients/{client_id}/edit")
    assert response.status_code == 200
    assert f"Редагування клієнта: {client_name}" in response.data.decode("utf-8")
    assert "Зберегти" in response.data.decode("utf-8")


def test_client_edit_success(auth_client_for_clients, session):
    """
    Тест успішного оновлення інформації про клієнта.
    Перевіряє статус відповіді, перенаправлення та оновлення даних у БД.
    """
    # Створюємо тестового клієнта
    unique_id = uuid.uuid4().hex[:8]

    test_client = Client(
        name=f"Test Client For Edit Success {unique_id}",
        phone=f"+38033{unique_id}",
        email=f"edit_success_{unique_id}@example.com",
        notes="Original notes",
    )
    session.add(test_client)
    session.commit()
    client_id = test_client.id

    # Дані для оновлення клієнта
    updated_data = {
        "name": f"Updated Test Client {unique_id}",
        "phone": f"+38033{unique_id}",  # Залишаємо той самий телефон
        "email": f"edit_success_{unique_id}@example.com",  # Залишаємо той самий email
        "notes": "Updated notes for test client",
        "submit": "Зберегти",
    }

    response = auth_client_for_clients.post(
        f"/clients/{client_id}/edit", data=updated_data, follow_redirects=True
    )
    assert response.status_code == 200
    assert "Інформацію про клієнта успішно оновлено!" in response.data.decode("utf-8")

    # Перевірка, що дані клієнта оновлені в БД
    updated_client = db.session.get(Client, client_id)
    assert updated_client.name == updated_data["name"]
    assert updated_client.notes == updated_data["notes"]


def test_client_edit_duplicate_phone(auth_client_for_clients, session):
    """
    Тест невдалого оновлення клієнта з дублікатом телефону.
    Перевіряє відхилення форми та повідомлення про помилку.
    """
    # Створюємо двох тестових клієнтів
    unique_id1 = uuid.uuid4().hex[:8]
    unique_id2 = uuid.uuid4().hex[:8]

    test_client1 = Client(
        name=f"Test Client For Edit Duplicate 1 {unique_id1}",
        phone=f"+38022{unique_id1}",
        email=f"edit_dup1_{unique_id1}@example.com",
        notes="Client 1 notes",
    )
    session.add(test_client1)

    test_client2 = Client(
        name=f"Test Client For Edit Duplicate 2 {unique_id2}",
        phone=f"+38022{unique_id2}",
        email=f"edit_dup2_{unique_id2}@example.com",
        notes="Client 2 notes",
    )
    session.add(test_client2)
    session.commit()

    client1_id = test_client1.id
    client2_phone = test_client2.phone

    # Спроба оновити client1, використовуючи телефон client2
    updated_data = {
        "name": f"Test Client For Edit Duplicate 1 {unique_id1}",
        "phone": client2_phone,  # Телефон іншого клієнта
        "email": f"edit_dup1_{unique_id1}@example.com",
        "notes": "Client 1 notes",
        "submit": "Зберегти",
    }

    response = auth_client_for_clients.post(
        f"/clients/{client1_id}/edit", data=updated_data, follow_redirects=True
    )
    assert response.status_code == 200
    assert "Клієнт з таким номером телефону вже існує" in response.data.decode("utf-8")


def test_client_search_by_name(auth_client_for_clients, session):
    """
    Тест пошуку клієнтів за ім'ям.
    Перевіряє відображення результатів пошуку за ім'ям клієнта.
    """
    # Створюємо тестового клієнта з унікальним ім'ям для пошуку
    unique_id = uuid.uuid4().hex[:8]
    unique_name = f"TestClientForSearch{unique_id}"

    test_client = Client(
        name=unique_name,
        phone=f"+38011{unique_id}",
        email=f"search_{unique_id}@example.com",
        notes="Test client for search test",
    )
    session.add(test_client)
    session.commit()

    # Використовуємо частину імені для пошуку
    search_term = unique_name[:15]
    response = auth_client_for_clients.get(f"/clients/?search={search_term}")
    assert response.status_code == 200

    # Перевірка, що клієнт знайдений
    content = response.data.decode("utf-8")
    assert unique_name in content
    assert f"+38011{unique_id}" in content


def test_client_search_by_phone(auth_client_for_clients, session):
    """
    Тест пошуку клієнтів за телефоном.
    Перевіряє відображення результатів пошуку за телефоном клієнта.
    """
    # Створюємо тестового клієнта з унікальним телефоном для пошуку
    unique_id = uuid.uuid4().hex[:8]
    unique_phone = f"+38000{unique_id}"

    test_client = Client(
        name=f"Test Client For Phone Search {unique_id}",
        phone=unique_phone,
        email=f"phone_search_{unique_id}@example.com",
        notes="Test client for phone search test",
    )
    session.add(test_client)
    session.commit()

    # Використовуємо частину телефону для пошуку
    search_term = unique_phone[5:10]
    response = auth_client_for_clients.get(f"/clients/?search={search_term}")
    assert response.status_code == 200

    # Перевірка, що клієнт знайдений
    content = response.data.decode("utf-8")
    assert f"Test Client For Phone Search {unique_id}" in content
    assert unique_phone in content


def test_client_delete_with_appointments(auth_client_for_clients, session):
    """
    Тест заборони видалення клієнта з існуючими записами.
    Перевіряє відхилення запиту на видалення та повідомлення про помилку.
    """
    # Створюємо тестового клієнта та запис
    unique_id = uuid.uuid4().hex[:8]

    # Створюємо користувача (майстра)
    master = User(
        username=f"master_for_delete_test_{unique_id}",
        password=generate_password_hash("test_password"),
        full_name="Master For Delete Test",
        is_admin=False,
    )
    session.add(master)
    session.flush()

    # Створюємо клієнта
    test_client = Client(
        name=f"Test Client For Delete Restriction {unique_id}",
        phone=f"+38777{unique_id}",
        email=f"delete_restriction_{unique_id}@example.com",
        notes="Client for delete restriction test",
    )
    session.add(test_client)
    session.flush()

    # Створюємо майбутній запис для клієнта
    future_date = date.today() + timedelta(days=1)
    appointment = Appointment(
        client_id=test_client.id,
        master_id=master.id,
        date=future_date,
        start_time=time(10, 0),
        end_time=time(11, 0),
        status="scheduled",
        notes="Future appointment",
    )
    session.add(appointment)
    session.commit()

    client_id = test_client.id

    response = auth_client_for_clients.post(
        f"/clients/{client_id}/delete", follow_redirects=True
    )
    assert response.status_code == 200
    assert "Не можна видалити клієнта" in response.data.decode("utf-8")
    assert "запланованих записів" in response.data.decode("utf-8")

    # Перевірка, що клієнт не видалений
    client = db.session.get(Client, client_id)
    assert client is not None


def test_client_delete_success(auth_client_for_clients, session):
    """
    Тест успішного видалення клієнта без записів.
    Перевіряє видалення клієнта з БД та повідомлення про успіх.
    """
    # Створюємо клієнта без записів
    unique_id = uuid.uuid4().hex[:8]

    client_to_delete = Client(
        name=f"Client To Delete {unique_id}",
        phone=f"+38999{unique_id}",
        email=f"delete_test_{unique_id}@example.com",
        notes="Client for delete test",
    )
    session.add(client_to_delete)
    session.commit()

    client_id = client_to_delete.id

    response = auth_client_for_clients.post(
        f"/clients/{client_id}/delete", follow_redirects=True
    )
    assert response.status_code == 200
    assert "Клієнт успішно видалений!" in response.data.decode("utf-8")

    # Перевірка, що клієнт видалений
    client = db.session.get(Client, client_id)
    assert client is None


def test_client_api_search(auth_client_for_clients, session):
    """
    Тест API пошуку клієнтів.
    Перевіряє коректність роботи API для пошуку клієнтів.
    """
    # Створюємо тестового клієнта з унікальним ім'ям для API пошуку
    unique_id = uuid.uuid4().hex[:8]
    unique_name = f"ApiSearchClient{unique_id}"

    test_client = Client(
        name=unique_name,
        phone=f"+38555{unique_id}",
        email=f"api_search_{unique_id}@example.com",
        notes="Test client for API search test",
    )
    session.add(test_client)
    session.commit()
    client_id = test_client.id

    # Використовуємо частину імені для пошуку через API
    search_term = unique_name[:8]
    response = auth_client_for_clients.get(f"/clients/api/search?q={search_term}")
    assert response.status_code == 200

    # Перевірка, що відповідь є JSON з правильними даними
    data = response.get_json()
    assert isinstance(data, list)

    # Знаходимо тестового клієнта в результатах
    found = False
    for client in data:
        if client["id"] == client_id:
            found = True
            assert client["name"] == unique_name
            assert client["phone"] == f"+38555{unique_id}"
            assert client["email"] == f"api_search_{unique_id}@example.com"
            break

    assert found, "Тестовий клієнт не знайдений в результатах API пошуку"


def test_client_search_by_multiple_name_words(auth_client_for_clients, session):
    """
    Тест пошуку клієнтів за кількома словами в імені.
    Перевіряє відображення результатів пошуку, коли використовується кілька слів з імені клієнта.
    """
    # Створюємо тестового клієнта з іменем, що містить кілька слів
    unique_id = uuid.uuid4().hex[:8]
    first_name = f"TestFirstName{unique_id}"
    last_name = f"TestLastName{unique_id}"
    unique_name = f"{first_name} {last_name}"

    test_client = Client(
        name=unique_name,
        phone=f"+38022{unique_id}",
        email=f"multiword_search_{unique_id}@example.com",
        notes="Test client for multi-word search test",
    )
    session.add(test_client)
    session.commit()

    # 1. Використовуємо пошук з двома словами в правильному порядку
    search_term = f"{first_name} {last_name}"
    response = auth_client_for_clients.get(f"/clients/?search={search_term}")
    assert response.status_code == 200
    content = response.data.decode("utf-8")
    assert unique_name in content
    assert f"+38022{unique_id}" in content

    # 2. Використовуємо пошук з двома словами в зворотному порядку
    search_term = f"{last_name} {first_name}"
    response = auth_client_for_clients.get(f"/clients/?search={search_term}")
    assert response.status_code == 200
    content = response.data.decode("utf-8")
    assert unique_name in content
    assert f"+38022{unique_id}" in content

    # 3. Використовуємо пошук з частинами обох слів
    search_term = f"{first_name[:5]} {last_name[:5]}"
    response = auth_client_for_clients.get(f"/clients/?search={search_term}")
    assert response.status_code == 200
    content = response.data.decode("utf-8")
    assert unique_name in content
    assert f"+38022{unique_id}" in content


def test_client_api_search_multiple_words(auth_client_for_clients, session):
    """
    Тест API пошуку клієнтів з кількома словами.
    Перевіряє коректність роботи API для пошуку клієнтів за кількома словами імені.
    """
    # Створюємо тестового клієнта з іменем, що містить кілька слів
    unique_id = uuid.uuid4().hex[:8]
    first_name = f"ApiMultiFirstName{unique_id}"
    last_name = f"ApiMultiLastName{unique_id}"
    unique_name = f"{first_name} {last_name}"

    test_client = Client(
        name=unique_name,
        phone=f"+38666{unique_id}",
        email=f"api_multi_search_{unique_id}@example.com",
        notes="Test client for API multi-word search test",
    )
    session.add(test_client)
    session.commit()
    client_id = test_client.id

    # 1. Використовуємо пошук з двома словами в правильному порядку
    search_term = f"{first_name} {last_name}"
    response = auth_client_for_clients.get(f"/clients/api/search?q={search_term}")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert any(c["id"] == client_id for c in data)

    # 2. Використовуємо пошук з двома словами в зворотному порядку
    search_term = f"{last_name} {first_name}"
    response = auth_client_for_clients.get(f"/clients/api/search?q={search_term}")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert any(c["id"] == client_id for c in data)

    # 3. Використовуємо пошук з частинами обох слів
    search_term = f"{first_name[:5]} {last_name[:5]}"
    response = auth_client_for_clients.get(f"/clients/api/search?q={search_term}")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert any(c["id"] == client_id for c in data)


def test_client_search_cyrillic_case_insensitive(auth_client_for_clients, session):
    """
    Тест пошуку клієнтів за кириличним ім'ям з різним регістром.
    Перевіряє нечутливість до регістру для кириличних символів.
    """
    # Створюємо тестового клієнта з кириличним ім'ям
    unique_id = uuid.uuid4().hex[:8]
    cyrillic_name = f"Анна Іванова {unique_id}"

    # Виведення інформації про клієнта, якого ми збираємося створити
    print(f"\nCreating client with name: {cyrillic_name}")
    print(f"Unique ID: {unique_id}")

    test_client = Client(
        name=cyrillic_name,
        phone=f"+38044{unique_id}",
        email=f"anna_{unique_id}@example.com",
        notes="Test client for Cyrillic case-insensitive search",
    )
    session.add(test_client)
    session.commit()

    # Перевіряємо, що клієнт був створений
    created_client = Client.query.filter_by(phone=f"+38044{unique_id}").first()
    print(f"Created client: {created_client.name}, ID: {created_client.id}")

    # Перевіримо, чи працює базовий пошук без врахування регістру
    print("\nTesting direct SQL query with UPPER():")
    from sqlalchemy import func

    sql_result = Client.query.filter(
        func.UPPER(Client.name).like(f"%{('анна').upper()}%")
    ).all()
    print(f"SQL Query direct result (length: {len(sql_result)}):")
    for c in sql_result:
        print(f"  - {c.id}: {c.name}")

    # 1. Пошук малими літерами кирилиці
    search_term = "анна"
    print(f"\nSearching for: {search_term}")
    response = auth_client_for_clients.get(f"/clients/?search={search_term}")
    assert response.status_code == 200
    content = response.data.decode("utf-8")

    # Виводимо всіх клієнтів з бази даних для порівняння
    all_clients = Client.query.all()
    print("\nAll clients in database:")
    for client in all_clients:
        print(f"ID: {client.id}, Name: {client.name}, Phone: {client.phone}")

    # Перевіряємо, чи містить сторінка необхідні дані
    if cyrillic_name not in content:
        print("\nClient not found in response content!")
        print(f"Looking for: {cyrillic_name}")

        # Виведення частини контенту для аналізу
        print("\nPart of the response content:")
        print(content[:1000])

        # Додаємо спрощену перевірку, щоб побачити, чи є клієнт на сторінці
        assert (
            "Клієнтів не знайдено" not in content
        ), "No clients found message displayed"
        # Перевіряємо, чи є унікальний ідентифікатор в контенті
        assert unique_id in content, f"Unique ID {unique_id} not found in response"

    assert cyrillic_name in content
    assert f"+38044{unique_id}" in content

    # 2. Пошук змішаним регістром
    search_term = "аНнА"
    print(f"\nSearching with mixed case: {search_term}")
    response = auth_client_for_clients.get(f"/clients/?search={search_term}")
    assert response.status_code == 200
    content = response.data.decode("utf-8")
    if cyrillic_name not in content:
        print("\nClient not found in response content for mixed case search!")
        print(f"Looking for: {cyrillic_name}")
        print("\nPart of the response content:")
        print(content[:1000])
    assert cyrillic_name in content
    assert f"+38044{unique_id}" in content

    # 3. Пошук за прізвищем малими літерами
    search_term = "іванова"
    print(f"\nSearching by last name: {search_term}")
    response = auth_client_for_clients.get(f"/clients/?search={search_term}")
    assert response.status_code == 200
    content = response.data.decode("utf-8")
    if cyrillic_name not in content:
        print("\nClient not found in response content for last name search!")
        print(f"Looking for: {cyrillic_name}")
        print("\nPart of the response content:")
        print(content[:1000])
    assert cyrillic_name in content
    assert f"+38044{unique_id}" in content


def test_client_api_search_cyrillic_case_insensitive(auth_client_for_clients, session):
    """
    Тест API пошуку клієнтів за кириличним ім'ям з різним регістром.
    Перевіряє нечутливість API пошуку до регістру для кириличних символів.
    """
    # Створюємо тестового клієнта з кириличним ім'ям
    unique_id = uuid.uuid4().hex[:8]
    cyrillic_name = f"Олена Петрова {unique_id}"

    test_client = Client(
        name=cyrillic_name,
        phone=f"+38055{unique_id}",
        email=f"olena_{unique_id}@example.com",
        notes="Test client for API Cyrillic case-insensitive search",
    )
    session.add(test_client)
    session.commit()
    client_id = test_client.id

    # 1. Пошук малими літерами кирилиці
    search_term = "олена"
    response = auth_client_for_clients.get(f"/clients/api/search?q={search_term}")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert any(c["id"] == client_id for c in data)

    # 2. Пошук змішаним регістром
    search_term = "оЛеНа"
    response = auth_client_for_clients.get(f"/clients/api/search?q={search_term}")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert any(c["id"] == client_id for c in data)

    # 3. Пошук за прізвищем малими літерами
    search_term = "петрова"
    response = auth_client_for_clients.get(f"/clients/api/search?q={search_term}")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert any(c["id"] == client_id for c in data)
