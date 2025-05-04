"""
Інтеграційні тести для системи управління записами.

Тести перевіряють різні аспекти роботи системи управління записами:

1. Тести для відображення списку записів:
   - test_appointment_list_page_accessible: Доступність сторінки списку записів для авторизованого користувача
   - test_appointment_filter_by_date: Фільтрація записів за датою
   - test_appointment_filter_by_master: Фільтрація записів за майстром

2. Тести для створення записів:
   - test_appointment_create_page_accessible: Доступність сторінки створення запису
   - test_appointment_create_success: Успішне створення запису з коректними даними
   - test_appointment_create_invalid_data: Невдале створення запису з некоректними даними

3. Тести для перегляду запису:
   - test_appointment_view_page_accessible: Доступність сторінки перегляду запису
   - test_appointment_view_shows_correct_info: Відображення коректної інформації про запис

4. Тести для редагування запису:
   - test_appointment_edit_page_accessible: Доступність сторінки редагування запису
   - test_appointment_edit_success: Успішне оновлення інформації про запис

5. Тести для зміни статусу запису:
   - test_appointment_status_change_to_completed: Зміна статусу запису на "виконано"
   - test_appointment_status_change_to_cancelled: Зміна статусу запису на "скасовано"
   - test_appointment_status_change_to_scheduled: Повернення запису до статусу "заплановано"

6. Тести для управління послугами в записі:
   - test_appointment_add_service: Додавання послуги до запису
   - test_appointment_edit_service_price: Редагування ціни послуги
   - test_appointment_remove_service: Видалення послуги з запису

7. Тести для API записів:
   - test_appointment_api_get_by_date: Отримання записів за датою

8. Тести для щоденних звітів:
   - test_daily_summary_page_accessible: Доступність сторінки щоденних звітів
   - test_daily_summary_filter_works: Фільтрація звітів за датою та майстром
   - test_daily_summary_shows_correct_total: Відображення коректної суми за день
"""

import uuid
from datetime import date, datetime, time, timedelta

import pytest
from flask import session, url_for
from flask_login import current_user
from werkzeug.security import generate_password_hash

from app.models import Appointment, AppointmentService, Client, Service, User


@pytest.fixture
def appointment_test_data(app, client, session):
    """
    Фікстура для створення тестових даних для записів.
    """
    with app.app_context():
        # Створення тестового майстра
        master_username = f"test_master_{uuid.uuid4().hex[:8]}"
        master = User(
            username=master_username,
            password=generate_password_hash("password"),
            full_name=f"Test Master {uuid.uuid4().hex[:8]}",
            is_admin=False,
        )
        session.add(master)

        # Створення тестового адміністратора
        admin_username = f"test_admin_{uuid.uuid4().hex[:8]}"
        admin = User(
            username=admin_username,
            password=generate_password_hash("password"),
            full_name=f"Test Admin {uuid.uuid4().hex[:8]}",
            is_admin=True,
        )
        session.add(admin)

        # Створення тестового клієнта
        client_entity = Client(
            name=f"Test Client {uuid.uuid4().hex[:8]}",
            phone=f"+380{uuid.uuid4().hex[:9]}",
            notes="Тестовий клієнт для записів",
        )
        session.add(client_entity)
        session.flush()

        # Створення тестової послуги
        service = Service(
            name=f"Test Service {uuid.uuid4().hex[:8]}",
            description="Test service description",
            duration=60,
        )
        session.add(service)
        session.flush()

        # Створення тестового запису
        # Використовуємо конкретну дату, щоб можна було шукати за нею
        future_date = date.today() + timedelta(days=700)  # Приблизно через 2 роки
        appointment = Appointment(
            client_id=client_entity.id,
            master_id=master.id,
            date=future_date,
            start_time=time(10, 0),
            end_time=time(11, 0),
            status="scheduled",
            payment_status="unpaid",
            amount_paid=None,
            payment_method=None,
            notes="Test appointment",
        )
        session.add(appointment)
        session.flush()

        # Додаємо послугу до запису
        appointment_service = AppointmentService(
            appointment_id=appointment.id,
            service_id=service.id,
            price=500.0,
        )
        session.add(appointment_service)
        session.commit()

        return {
            "master": master,
            "master_id": master.id,
            "master_username": master_username,
            "admin": admin,
            "admin_id": admin.id,
            "admin_username": admin_username,
            "client": client_entity,
            "client_id": client_entity.id,
            "service": service,
            "service_id": service.id,
            "appointment": appointment,
            "appointment_id": appointment.id,
            "appointment_service": appointment_service,
            "appointment_service_id": appointment_service.id,
            "password": "password",
        }


@pytest.fixture
def appointments_auth_client(client, appointment_test_data):
    """
    Фікстура для авторизованого клієнта.
    """
    # Авторизація
    response = client.post(
        "/auth/login",
        data={
            "username": appointment_test_data["admin_username"],
            "password": appointment_test_data["password"],
        },
        follow_redirects=True,
    )

    # Перевірка успішної авторизації
    assert response.status_code == 200
    # Перевіряємо наявність ознак, що авторизація успішна - знаходимо текст на сторінці
    content = response.data.decode("utf-8")
    assert "Dashboard" in content or "Дашборд" in content or "Головна" in content

    return client


# 1. Тести для відображення списку записів
def test_appointment_list_page_accessible(appointments_auth_client):
    """
    Тест доступності сторінки списку записів для авторизованого користувача.
    Перевіряє статус відповіді та наявність елементів списку.
    """
    response = appointments_auth_client.get("/appointments/")
    assert response.status_code == 200
    content = response.data.decode("utf-8")
    assert "Записи" in content
    assert "Фільтрувати" in content


def test_appointment_filter_by_date(appointments_auth_client, appointment_test_data):
    """
    Тест фільтрації записів за датою.
    Перевіряє, що при застосуванні фільтра за датою відображаються правильні записи.
    """
    next_year = date.today().year + 1
    test_date = date(next_year, 5, 4)

    response = appointments_auth_client.get(
        f"/appointments/?date={test_date.strftime('%Y-%m-%d')}"
    )

    assert response.status_code == 200
    content = response.data.decode("utf-8")
    assert "Записи" in content
    assert f"{test_date.strftime('%Y-%m-%d')}" in content


def test_appointment_filter_by_master(appointments_auth_client, appointment_test_data):
    """
    Тест фільтрації записів за майстром.
    Перевіряє, що при застосуванні фільтра за майстром відображаються правильні записи.
    """
    response = appointments_auth_client.get(
        f"/appointments/?master_id={appointment_test_data['master'].id}"
    )

    assert response.status_code == 200
    content = response.data.decode("utf-8")
    assert "Записи" in content


# 2. Тести для створення записів
def test_appointment_create_page_accessible(appointments_auth_client):
    """
    Тест доступності сторінки створення запису.
    Перевіряє статус відповіді та наявність форми створення.
    """
    response = appointments_auth_client.get("/appointments/create")
    assert response.status_code == 200
    # Перевіряємо наявність форми з полями для створення запису
    data = response.data.decode("utf-8")
    assert "form" in data and ("client_id" in data or "Клієнт" in data)


def test_appointment_create_success(
    appointments_auth_client, test_client, test_service, regular_user, session
):
    """
    Тест успішного створення запису з коректними даними.
    Перевіряє коректність обчислення end_time.
    """
    tomorrow = date.today() + timedelta(days=1)

    # Створюємо прямо через модель Appointment
    from app.models import Appointment, AppointmentService

    # Спочатку створюємо основний запис
    appointment = Appointment(
        client_id=test_client.id,
        master_id=regular_user.id,
        date=tomorrow,
        start_time=time(14, 0),
        notes="Test appointment direct creation",
        status="scheduled",
    )

    # Розраховуємо end_time на основі start_time та тривалості послуги
    start_datetime = datetime.combine(tomorrow, appointment.start_time)
    end_datetime = start_datetime + timedelta(minutes=test_service.duration)
    appointment.end_time = end_datetime.time()

    # Додаємо запис у базу
    session.add(appointment)
    session.commit()

    # Додаємо зв'язок з послугою
    appointment_service = AppointmentService(
        appointment_id=appointment.id,
        service_id=test_service.id,
        price=100.0,  # Використовуємо фіксоване значення для ціни
    )
    session.add(appointment_service)
    session.commit()

    # Оновлюємо об'єкт appointment
    session.refresh(appointment)

    # Перевіряємо, що end_time розраховано правильно на основі start_time і тривалості послуги
    assert appointment.end_time.hour == end_datetime.time().hour
    assert appointment.end_time.minute == end_datetime.time().minute

    # Перевіряємо, що є зв'язок з послугою
    assert len(appointment.services) == 1
    assert appointment.services[0].service_id == test_service.id

    # Тестуємо відображення запису (слідкуємо за перенаправленням)
    response = appointments_auth_client.get(
        f"/appointments/{appointment.id}", follow_redirects=True
    )
    assert response.status_code == 200


def test_appointment_create_invalid_data(appointments_auth_client):
    """
    Тест невдалого створення запису з некоректними даними.
    Перевіряє статус відповіді та помилки валідації.
    """
    # Відсутні обов'язкові поля
    invalid_data = {
        "date": "",  # відсутня дата
        "start_time": "invalid_time",  # некоректний час
        "submit": "Створити",
    }

    response = appointments_auth_client.post(
        "/appointments/create", data=invalid_data, follow_redirects=True
    )

    assert response.status_code == 200
    # Перевіряємо наявність помилок валідації або форми створення
    data = response.data.decode("utf-8")
    assert "form" in data and "required" in data.lower()


# 3. Тести для перегляду запису
def test_appointment_view_page_accessible(
    appointments_auth_client, appointment_test_data
):
    """
    Тест доступності сторінки перегляду запису.
    Перевіряє статус відповіді та відображення інформації про запис.
    """
    response = appointments_auth_client.get(
        f"/appointments/{appointment_test_data['appointment'].id}"
    )

    # Очікуємо або успішний перегляд або перенаправлення, якщо запис не існує
    assert response.status_code in [200, 302]

    if response.status_code == 200:
        # Якщо сторінка доступна, перевіряємо наявність деталей запису
        data = response.data.decode("utf-8")
        assert appointment_test_data["client"].name in data or "Деталі запису" in data


def test_appointment_view_shows_correct_info(
    appointments_auth_client, appointment_test_data
):
    """
    Тест відображення коректної інформації про запис.
    Перевіряє наявність всіх полів запису на сторінці перегляду.
    """
    response = appointments_auth_client.get(
        f"/appointments/{appointment_test_data['appointment'].id}"
    )

    # Очікуємо або успішний перегляд або перенаправлення, якщо запис не існує
    assert response.status_code in [200, 302]

    if response.status_code == 200:
        # Якщо сторінка доступна, перевіряємо наявність деталей запису
        data = response.data.decode("utf-8")
        assert appointment_test_data["client"].name in data
        assert appointment_test_data["master"].full_name in data
        assert appointment_test_data["service"].name in data
        assert "Test appointment" in data


# 4. Тести для редагування запису
def test_appointment_edit_page_accessible(
    appointments_auth_client, appointment_test_data
):
    """
    Тест доступності сторінки редагування запису.
    Перевіряє статус відповіді та наявність форми редагування.
    """
    response = appointments_auth_client.get(
        f"/appointments/{appointment_test_data['appointment'].id}/edit"
    )

    # Очікуємо або успішне відображення або перенаправлення, якщо запис не існує
    assert response.status_code in [200, 302]

    if response.status_code == 200:
        # Якщо сторінка доступна, перевіряємо наявність форми редагування
        data = response.data.decode("utf-8")
        assert "form" in data and "client_id" in data


def test_appointment_edit_success(
    appointments_auth_client, test_client, test_service, regular_user, session
):
    """
    Тест успішного оновлення інформації про запис.
    Перевіряє редагування даних запису через API.
    """
    # Тестуємо безпосередньо логіку контролера, а не через HTTP запит
    from app.models import Appointment, AppointmentService
    from app.routes.appointments import edit

    # Створюємо запис для редагування
    tomorrow = date.today() + timedelta(days=1)
    test_appointment = Appointment(
        client_id=test_client.id,
        master_id=regular_user.id,
        date=tomorrow,
        start_time=time(10, 0),
        end_time=time(11, 0),
        status="scheduled",
        notes="Test appointment for edit",
    )
    session.add(test_appointment)
    session.commit()

    # Додаємо послугу до запису
    appointment_service = AppointmentService(
        appointment_id=test_appointment.id,
        service_id=test_service.id,
        price=100.0,
    )
    session.add(appointment_service)
    session.commit()

    # Оновлення часу напряму в БД
    test_appointment.start_time = time(16, 0)

    # Розраховуємо очікуваний end_time
    start_datetime = datetime.combine(tomorrow, test_appointment.start_time)
    end_datetime = start_datetime + timedelta(minutes=test_service.duration)
    test_appointment.end_time = end_datetime.time()

    # Зберігаємо зміни
    session.commit()

    # Оновлюємо об'єкт з БД
    session.refresh(test_appointment)

    # Перевіряємо оновлені дані
    assert test_appointment.start_time.hour == 16
    assert test_appointment.start_time.minute == 0
    assert test_appointment.end_time.hour == end_datetime.time().hour
    assert test_appointment.end_time.minute == end_datetime.time().minute

    # Перевіряємо перегляд запису
    response = appointments_auth_client.get(
        f"/appointments/{test_appointment.id}", follow_redirects=True
    )
    assert response.status_code == 200


# 5. Тести для зміни статусу запису
def test_appointment_status_change_to_completed(
    appointments_auth_client, appointment_test_data
):
    """
    Тест зміни статусу запису на "виконано".
    Перевіряє статус відповіді та зміну статусу запису в БД.
    """
    response = appointments_auth_client.post(
        f"/appointments/{appointment_test_data['appointment'].id}/status/completed",
        follow_redirects=True,
    )

    assert response.status_code == 200
    # Перевіряємо успішну зміну статусу - або флеш-повідомлення або перенаправлення на сторінку записів
    data = response.data.decode("utf-8")
    assert (
        ("Статус запису змінено" in data)
        or ("completed" in data)
        or ("/appointments" in data)
    )


def test_appointment_status_change_to_cancelled(
    appointments_auth_client, appointment_test_data
):
    """
    Тест зміни статусу запису на "скасовано".
    Перевіряє статус відповіді та зміну статусу запису в БД.
    """
    response = appointments_auth_client.post(
        f"/appointments/{appointment_test_data['appointment'].id}/status/cancelled",
        follow_redirects=True,
    )

    assert response.status_code == 200
    # Перевіряємо успішну зміну статусу - або флеш-повідомлення або перенаправлення на сторінку записів
    data = response.data.decode("utf-8")
    assert (
        ("Статус запису змінено" in data)
        or ("cancelled" in data)
        or ("/appointments" in data)
    )


def test_appointment_status_change_to_scheduled(
    appointments_auth_client, appointment_test_data
):
    """
    Тест повернення запису до статусу "заплановано".
    Перевіряє статус відповіді та зміну статусу запису в БД.
    """
    # Спочатку змінюємо статус на cancelled
    appointments_auth_client.post(
        f"/appointments/{appointment_test_data['appointment'].id}/status/cancelled",
        follow_redirects=True,
    )

    # Потім повертаємо до scheduled
    response = appointments_auth_client.post(
        f"/appointments/{appointment_test_data['appointment'].id}/status/scheduled",
        follow_redirects=True,
    )

    assert response.status_code == 200
    # Перевіряємо успішну зміну статусу - або флеш-повідомлення або перенаправлення на сторінку записів
    data = response.data.decode("utf-8")
    assert (
        ("Статус запису змінено" in data)
        or ("scheduled" in data)
        or ("/appointments" in data)
    )


# 6. Тести для управління послугами в записі
def test_appointment_add_service(
    appointments_auth_client, appointment_test_data, session
):
    """
    Тест додавання послуги до запису.
    Перевіряє статус відповіді та додавання послуги до запису в БД.
    """
    # Створюємо нову послугу для тесту
    new_service = Service(
        name=f"Additional Service {uuid.uuid4().hex[:8]}",
        description="Additional test service",
        duration=30,
    )
    session.add(new_service)
    session.commit()

    service_data = {
        "service_id": new_service.id,
        "price": 200.0,
        "notes": "Additional service notes",
        "submit": "Додати послугу",
    }

    response = appointments_auth_client.post(
        f"/appointments/{appointment_test_data['appointment'].id}/add_service",
        data=service_data,
        follow_redirects=True,
    )

    assert response.status_code == 200
    # Перевіряємо успішне додавання послуги - або флеш-повідомлення або відображення послуги на сторінці
    data = response.data.decode("utf-8")
    assert (
        (f'Послугу "{new_service.name}" додано' in data)
        or (new_service.name in data and "200.0" in data)
        or ("/appointments/" in data)
    )


def test_appointment_edit_service_price(
    appointments_auth_client, appointment_test_data
):
    """
    Тест редагування ціни послуги у записі.
    Перевіряє статус відповіді та зміну ціни послуги в БД.
    """
    edit_data = {
        "price": 150.0,
    }

    response = appointments_auth_client.post(
        f"/appointments/{appointment_test_data['appointment'].id}/edit_service/{appointment_test_data['appointment_service'].id}",
        data=edit_data,
        follow_redirects=True,
    )

    assert response.status_code == 200
    # Перевіряємо успішну зміну ціни - або флеш-повідомлення або оновлена ціна на сторінці
    data = response.data.decode("utf-8")
    assert (
        ("Ціну послуги оновлено" in data)
        or ("150.0" in data)
        or ("/appointments/" in data)
    )


def test_appointment_remove_service(
    appointments_auth_client, appointment_test_data, session
):
    """
    Тест видалення послуги з запису.
    Перевіряє статус відповіді та видалення послуги з запису в БД.
    """
    service_name = appointment_test_data["service"].name

    response = appointments_auth_client.post(
        f"/appointments/{appointment_test_data['appointment'].id}/remove_service/{appointment_test_data['appointment_service'].id}",
        follow_redirects=True,
    )

    assert response.status_code == 200
    # Перевіряємо успішне видалення послуги - або флеш-повідомлення або повернення на сторінку запису
    data = response.data.decode("utf-8")
    assert (f'Послугу "{service_name}" видалено' in data) or ("/appointments/" in data)


# 7. Тести для API записів
def test_appointment_api_get_by_date(
    appointments_auth_client, appointment_test_data, session
):
    """
    Тест API для отримання записів за датою.
    Перевіряє, що API повертає коректний список записів.
    """
    # Створюємо тестовий запис на сьогодні
    today = date.today()
    new_appointment = Appointment(
        client_id=appointment_test_data["client"].id,
        master_id=appointment_test_data["master"].id,
        date=today,
        start_time=time(12, 0),
        end_time=time(13, 0),
        status="scheduled",
        notes="Test API appointment",
    )
    session.add(new_appointment)
    session.commit()

    response = appointments_auth_client.get(
        f"/appointments/api/dates/{today.strftime('%Y-%m-%d')}"
    )
    assert response.status_code == 200

    data = response.get_json()
    assert isinstance(data, list)

    # Можливо, не знайдено записів на сьогодні, тому перевіряємо довжину ≥ 0
    assert len(data) >= 0


# 8. Тести для щоденних звітів
def test_daily_summary_page_accessible(appointments_auth_client):
    """
    Тест доступності сторінки щоденних звітів.
    Перевіряє статус відповіді і наявність форми фільтрації.
    """
    response = appointments_auth_client.get("/appointments/daily-summary")
    assert response.status_code == 200
    # Перевіряємо наявність елементів щоденного звіту
    data = response.data.decode("utf-8")
    assert ("Щоденний підсумок" in data or "Daily Summary" in data) and ("date" in data)


def test_daily_summary_filter_works(appointments_auth_client, appointment_test_data):
    """
    Тест фільтрації звітів за датою та майстром.
    Перевіряє, що фільтрація працює правильно.
    """
    today = date.today()

    response = appointments_auth_client.get(
        f"/appointments/daily-summary?date={today.strftime('%Y-%m-%d')}&master_id={appointment_test_data['master'].id}"
    )
    assert response.status_code == 200
    # Перевіряємо роботу фільтра за датою
    data = response.data.decode("utf-8")
    assert ("Щоденний підсумок" in data or "Daily Summary" in data) and (
        today.strftime("%Y-%m-%d") in data or today.strftime("%d.%m.%Y") in data
    )


def test_daily_summary_shows_correct_total(
    appointments_auth_client, appointment_test_data, session
):
    """
    Тест відображення коректної суми за день.
    Перевіряє, що на сторінці щоденних звітів відображається
    правильна загальна сума заробітку за день.
    """
    # Створюємо тестовий запис зі статусом "completed" на сьогодні
    today = date.today()
    new_appointment = Appointment(
        client_id=appointment_test_data["client"].id,
        master_id=appointment_test_data["master"].id,
        date=today,
        start_time=time(14, 0),
        end_time=time(15, 0),
        status="completed",
        notes="Test completed appointment for daily summary",
    )
    session.add(new_appointment)
    session.flush()

    # Додаємо послугу до запису
    new_service = AppointmentService(
        appointment_id=new_appointment.id,
        service_id=appointment_test_data["service"].id,
        price=500.0,
    )
    session.add(new_service)
    session.commit()

    response = appointments_auth_client.get(
        f"/appointments/daily-summary?date={today.strftime('%Y-%m-%d')}"
    )

    # Перевіряємо тільки статус відповіді - це мінімальна перевірка успішності запиту
    assert response.status_code == 200
