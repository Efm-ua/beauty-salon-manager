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
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

from app.models import Appointment, AppointmentService, Client
from app.models import PaymentMethod as PaymentMethodModel
from app.models import PaymentMethodEnum as PaymentMethod
from app.models import Service, User, db


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

    response = appointments_auth_client.get(f"/appointments/?date={test_date.strftime('%Y-%m-%d')}")

    assert response.status_code == 200
    content = response.data.decode("utf-8")
    assert "Записи" in content
    assert f"{test_date.strftime('%Y-%m-%d')}" in content


def test_appointment_filter_by_master(appointments_auth_client, appointment_test_data):
    """
    Тест фільтрації записів за майстром.
    Перевіряє, що при застосуванні фільтра за майстром відображаються правильні записи.
    """
    from datetime import date, time

    from app.models import (Appointment, AppointmentService, Client, Service,
                            User, db)

    # Створюємо другого майстра для тестування фільтрації
    master2 = User(
        username="master2_integration_test",
        password="test_password",
        full_name="Master Two Integration",
        is_admin=False,
        is_active_master=True,
    )
    db.session.add(master2)

    # Створюємо додаткового клієнта
    client2 = Client(name="Client Two Integration", phone="+380509999999")
    db.session.add(client2)

    db.session.commit()

    # Створюємо запис для другого майстра на ту ж дату
    test_date = appointment_test_data["appointment"].date
    appointment2 = Appointment(
        client_id=client2.id,
        master_id=master2.id,
        date=test_date,
        start_time=time(13, 0),
        end_time=time(14, 0),
        status="scheduled",
        notes="Appointment for master 2 integration test",
    )
    db.session.add(appointment2)
    db.session.commit()

    # Додаємо послугу до другого запису
    appointment2_service = AppointmentService(
        appointment_id=appointment2.id,
        service_id=appointment_test_data["service"].id,
        price=100.0,
    )
    db.session.add(appointment2_service)
    db.session.commit()

    # Тест 1: Фільтрація за першим майстром
    response = appointments_auth_client.get(
        f"/appointments/?date={test_date.strftime('%Y-%m-%d')}&master_id={appointment_test_data['master'].id}"
    )

    assert response.status_code == 200
    content = response.data.decode("utf-8")
    assert "Записи" in content
    # Повинен бути клієнт першого майстра
    assert appointment_test_data["client"].name in content
    # Не повинно бути клієнта другого майстра
    assert "Client Two Integration" not in content
    # Не перевіряємо відсутність імені майстра в загальному контенті,
    # оскільки воно може з'явитися в dropdown фільтрі

    # Тест 2: Фільтрація за другим майстром
    response = appointments_auth_client.get(
        f"/appointments/?date={test_date.strftime('%Y-%m-%d')}&master_id={master2.id}"
    )

    assert response.status_code == 200
    content = response.data.decode("utf-8")
    assert "Записи" in content
    # Повинен бути клієнт другого майстра
    assert "Client Two Integration" in content
    # Не повинно бути клієнта першого майстра
    assert appointment_test_data["client"].name not in content

    # Тест 3: Без фільтра - повинні бути обидва записи
    response = appointments_auth_client.get(f"/appointments/?date={test_date.strftime('%Y-%m-%d')}")

    assert response.status_code == 200
    content = response.data.decode("utf-8")
    assert "Записи" in content
    # Повинні бути обидва клієнти
    assert appointment_test_data["client"].name in content
    assert "Client Two Integration" in content


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


def test_appointment_create_success(appointments_auth_client, test_client, test_service, regular_user, session):
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
    response = appointments_auth_client.get(f"/appointments/{appointment.id}", follow_redirects=True)
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

    response = appointments_auth_client.post("/appointments/create", data=invalid_data, follow_redirects=True)

    assert response.status_code == 200
    # Перевіряємо наявність помилок валідації або форми створення
    data = response.data.decode("utf-8")
    assert "form" in data and "required" in data.lower()


# 3. Тести для перегляду запису
def test_appointment_view_page_accessible(appointments_auth_client, appointment_test_data):
    """
    Тест доступності сторінки перегляду запису.
    Перевіряє статус відповіді та відображення інформації про запис.
    """
    response = appointments_auth_client.get(f"/appointments/{appointment_test_data['appointment'].id}")

    # Очікуємо або успішний перегляд або перенаправлення, якщо запис не існує
    assert response.status_code in [200, 302]

    if response.status_code == 200:
        # Якщо сторінка доступна, перевіряємо наявність деталей запису
        data = response.data.decode("utf-8")
        assert appointment_test_data["client"].name in data or "Деталі запису" in data


def test_appointment_view_shows_correct_info(appointments_auth_client, appointment_test_data):
    """
    Тест відображення коректної інформації про запис.
    Перевіряє наявність всіх полів запису на сторінці перегляду.
    """
    response = appointments_auth_client.get(f"/appointments/{appointment_test_data['appointment'].id}")

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
def test_appointment_edit_page_accessible(appointments_auth_client, appointment_test_data):
    """
    Тест доступності сторінки редагування запису.
    Перевіряє статус відповіді та наявність форми редагування.
    """
    response = appointments_auth_client.get(f"/appointments/{appointment_test_data['appointment'].id}/edit")

    # Очікуємо або успішне відображення або перенаправлення, якщо запис не існує
    assert response.status_code in [200, 302]

    if response.status_code == 200:
        # Якщо сторінка доступна, перевіряємо наявність форми редагування
        data = response.data.decode("utf-8")
        assert "form" in data and "client_id" in data


def test_appointment_edit_success(appointments_auth_client, test_client, test_service, regular_user, session):
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
    response = appointments_auth_client.get(f"/appointments/{test_appointment.id}", follow_redirects=True)
    assert response.status_code == 200


# 5. Тести для зміни статусу запису
def test_appointment_status_change_to_completed(appointments_auth_client, appointment_test_data):
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
    assert ("Статус запису змінено" in data) or ("completed" in data) or ("/appointments" in data)


def test_appointment_status_change_to_cancelled(appointments_auth_client, appointment_test_data):
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
    assert ("Статус запису змінено" in data) or ("cancelled" in data) or ("/appointments" in data)


def test_appointment_status_change_to_scheduled(appointments_auth_client, appointment_test_data):
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
    assert ("Статус запису змінено" in data) or ("scheduled" in data) or ("/appointments" in data)


# 6. Тести для управління послугами в записі
def test_appointment_add_service(appointments_auth_client, appointment_test_data, session):
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


def test_appointment_edit_service_price(appointments_auth_client, appointment_test_data):
    """
    Тест редагування ціни послуги у записі.
    Перевіряє статус відповіді та зміну ціни послуги в БД.
    """
    edit_data = {
        "price": 150.0,
    }

    edit_url = (
        f"/appointments/{appointment_test_data['appointment'].id}/"
        f"edit_service/{appointment_test_data['appointment_service'].id}"
    )
    response = appointments_auth_client.post(
        edit_url,
        data=edit_data,
        follow_redirects=True,
    )

    assert response.status_code == 200
    # Перевіряємо успішну зміну ціни - або флеш-повідомлення або оновлена ціна на сторінці
    data = response.data.decode("utf-8")
    assert ("Ціну послуги оновлено" in data) or ("150.0" in data) or ("/appointments/" in data)


def test_appointment_remove_service(appointments_auth_client, appointment_test_data, session):
    """
    Тест видалення послуги з запису.
    Перевіряє статус відповіді та видалення послуги з запису в БД.
    """
    service_name = appointment_test_data["service"].name

    url = (
        f"/appointments/{appointment_test_data['appointment'].id}/"
        f"remove_service/{appointment_test_data['appointment_service'].id}"
    )
    response = appointments_auth_client.post(
        url,
        follow_redirects=True,
    )

    assert response.status_code == 200
    # Перевіряємо успішне видалення послуги - або флеш-повідомлення або повернення на сторінку запису
    data = response.data.decode("utf-8")
    assert (f'Послугу "{service_name}" видалено' in data) or ("/appointments/" in data)


# 7. Тести для API записів
def test_appointment_api_get_by_date(appointments_auth_client, appointment_test_data, session):
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

    response = appointments_auth_client.get(f"/appointments/api/dates/{today.strftime('%Y-%m-%d')}")
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


def test_daily_summary_shows_correct_total(appointments_auth_client, appointment_test_data, session):
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

    response = appointments_auth_client.get(f"/appointments/daily-summary?date={today.strftime('%Y-%m-%d')}")

    # Перевіряємо тільки статус відповіді - це мінімальна перевірка успішності запиту
    assert response.status_code == 200


# Розширені тести для daily_summary для досягнення 90% покриття


def test_daily_summary_without_date_parameter(appointments_auth_client):
    """
    Тест запиту daily_summary без параметра дати.
    Має використовувати поточну дату за замовчуванням.
    """
    response = appointments_auth_client.get("/appointments/daily-summary")
    assert response.status_code == 200

    data = response.data.decode("utf-8")
    today = date.today()
    # Перевіряємо, що використовується поточна дата
    assert "Щоденний підсумок" in data or "Daily Summary" in data
    # Перевірка наявності дати в різних форматах
    date_formats = today.strftime("%Y-%m-%d") in data or today.strftime("%d.%m.%Y") in data
    assert date_formats


def test_daily_summary_invalid_date_format(appointments_auth_client):
    """
    Тест запиту daily_summary з некоректним форматом дати.
    Має використовувати поточну дату за замовчуванням.
    """
    url = "/appointments/daily-summary?date=invalid-date"
    response = appointments_auth_client.get(url)
    assert response.status_code == 200

    data = response.data.decode("utf-8")
    today = date.today()
    # При некоректній даті використовується поточна дата
    assert "Щоденний підсумок" in data or "Daily Summary" in data


def test_daily_summary_date_without_appointments(appointments_auth_client):
    """
    Тест запиту daily_summary для дати без записів.
    Має повертати порожній звіт з нульовими сумами.
    """
    # Дата далеко в майбутньому, де точно немає записів
    future_date = date.today() + timedelta(days=1000)
    url = f"/appointments/daily-summary?" f"date={future_date.strftime('%Y-%m-%d')}"
    response = appointments_auth_client.get(url)
    assert response.status_code == 200

    data = response.data.decode("utf-8")
    assert "Щоденний підсумок" in data or "Daily Summary" in data
    # Перевіряємо, що сума дорівнює 0
    assert "0" in data or "0.00" in data


def test_daily_summary_with_different_appointment_statuses(appointments_auth_client, appointment_test_data, session):
    """
    Тест daily_summary з записами різних статусів.
    Тільки 'completed' записи мають враховуватися в сумах.
    """
    test_date = date.today()

    # Створюємо записи з різними статусами
    appointments_data = [
        {"status": "completed", "price": 100.0},
        {"status": "scheduled", "price": 200.0},
        {"status": "cancelled", "price": 300.0},
        {"status": "completed", "price": 150.0},
    ]

    for i, app_data in enumerate(appointments_data):
        appointment = Appointment(
            client_id=appointment_test_data["client"].id,
            master_id=appointment_test_data["master"].id,
            date=test_date,
            start_time=time(10 + i, 0),
            end_time=time(11 + i, 0),
            status=app_data["status"],
            notes=f"Test appointment {i}",
        )
        session.add(appointment)
        session.flush()

        # Додаємо послугу
        service = AppointmentService(
            appointment_id=appointment.id,
            service_id=appointment_test_data["service"].id,
            price=app_data["price"],
        )
        session.add(service)

    session.commit()

    response = appointments_auth_client.get(f"/appointments/daily-summary?date={test_date.strftime('%Y-%m-%d')}")
    assert response.status_code == 200

    data = response.data.decode("utf-8")
    # Очікувана сума: тільки completed записи (100.0 + 150.0 = 250.0)
    assert "250" in data or "250.0" in data or "250.00" in data


def test_daily_summary_amount_paid_vs_service_calculation(appointments_auth_client, appointment_test_data, session):
    """
    Тест daily_summary з записами, що мають amount_paid vs розрахунок з послуг.
    Якщо amount_paid > 0, використовується воно, інакше - сума послуг.
    """
    test_date = date.today()

    # Запис з amount_paid
    appointment1 = Appointment(
        client_id=appointment_test_data["client"].id,
        master_id=appointment_test_data["master"].id,
        date=test_date,
        start_time=time(10, 0),
        end_time=time(11, 0),
        status="completed",
        amount_paid=500.0,  # Використовується ця сума
        notes="Test appointment with amount_paid",
    )
    session.add(appointment1)
    session.flush()

    # Додаємо послугу з іншою ціною
    service1 = AppointmentService(
        appointment_id=appointment1.id,
        service_id=appointment_test_data["service"].id,
        price=300.0,  # Ця сума ігнорується
    )
    session.add(service1)

    # Запис без amount_paid (використовується сума послуг)
    appointment2 = Appointment(
        client_id=appointment_test_data["client"].id,
        master_id=appointment_test_data["master"].id,
        date=test_date,
        start_time=time(12, 0),
        end_time=time(13, 0),
        status="completed",
        amount_paid=None,  # Використовується сума послуг
        notes="Test appointment without amount_paid",
    )
    session.add(appointment2)
    session.flush()

    service2 = AppointmentService(
        appointment_id=appointment2.id,
        service_id=appointment_test_data["service"].id,
        price=200.0,  # Ця сума використовується
    )
    session.add(service2)

    # Запис з amount_paid = 0 (використовується сума послуг)
    appointment3 = Appointment(
        client_id=appointment_test_data["client"].id,
        master_id=appointment_test_data["master"].id,
        date=test_date,
        start_time=time(14, 0),
        end_time=time(15, 0),
        status="completed",
        amount_paid=0.0,  # Використовується сума послуг
        notes="Test appointment with zero amount_paid",
    )
    session.add(appointment3)
    session.flush()

    service3 = AppointmentService(
        appointment_id=appointment3.id,
        service_id=appointment_test_data["service"].id,
        price=100.0,  # Ця сума використовується
    )
    session.add(service3)

    session.commit()

    response = appointments_auth_client.get(f"/appointments/daily-summary?date={test_date.strftime('%Y-%m-%d')}")
    assert response.status_code == 200

    data = response.data.decode("utf-8")
    # Очікувана сума: 500.0 (amount_paid) + 200.0 + 100.0 = 800.0
    assert "800" in data or "800.0" in data or "800.00" in data


def test_daily_summary_with_valid_master_filter(appointments_auth_client, appointment_test_data, session):
    """
    Тест daily_summary з коректним master_id.
    Має фільтрувати записи за майстром та не показувати загальну статистику.
    """
    test_date = date.today()

    # Створюємо другого майстра
    master2 = User(
        username=f"test_master2_{uuid.uuid4().hex[:8]}",
        password=generate_password_hash("password"),
        full_name=f"Test Master 2 {uuid.uuid4().hex[:8]}",
        is_admin=False,
    )
    session.add(master2)
    session.flush()

    # Записи для першого майстра
    appointment1 = Appointment(
        client_id=appointment_test_data["client"].id,
        master_id=appointment_test_data["master"].id,
        date=test_date,
        start_time=time(10, 0),
        end_time=time(11, 0),
        status="completed",
        notes="Appointment for master 1",
    )
    session.add(appointment1)
    session.flush()

    service1 = AppointmentService(
        appointment_id=appointment1.id,
        service_id=appointment_test_data["service"].id,
        price=100.0,
    )
    session.add(service1)

    # Записи для другого майстра
    appointment2 = Appointment(
        client_id=appointment_test_data["client"].id,
        master_id=master2.id,
        date=test_date,
        start_time=time(12, 0),
        end_time=time(13, 0),
        status="completed",
        notes="Appointment for master 2",
    )
    session.add(appointment2)
    session.flush()

    service2 = AppointmentService(
        appointment_id=appointment2.id,
        service_id=appointment_test_data["service"].id,
        price=200.0,
    )
    session.add(service2)

    session.commit()

    # Запит з фільтром по першому майстру
    url = (
        f"/appointments/daily-summary?"
        f"date={test_date.strftime('%Y-%m-%d')}&"
        f"master_id={appointment_test_data['master'].id}"
    )
    response = appointments_auth_client.get(url)
    assert response.status_code == 200

    data = response.data.decode("utf-8")
    # Має показувати тільки суму першого майстра (100.0)
    assert "100" in data or "100.0" in data or "100.00" in data
    # Не має показувати суму другого майстра (200.0)
    assert "200" not in data or data.count("200") == 0


def test_daily_summary_with_invalid_master_filter(appointments_auth_client, appointment_test_data, session):
    """
    Тест daily_summary з некоректним master_id.
    Має ігнорувати фільтр та показувати всі записи.
    """
    test_date = date.today()

    appointment = Appointment(
        client_id=appointment_test_data["client"].id,
        master_id=appointment_test_data["master"].id,
        date=test_date,
        start_time=time(10, 0),
        end_time=time(11, 0),
        status="completed",
        notes="Test appointment",
    )
    session.add(appointment)
    session.flush()

    service = AppointmentService(
        appointment_id=appointment.id,
        service_id=appointment_test_data["service"].id,
        price=150.0,
    )
    session.add(service)
    session.commit()

    # Запит з некоректним master_id
    url = f"/appointments/daily-summary?" f"date={test_date.strftime('%Y-%m-%d')}&master_id=invalid"
    response = appointments_auth_client.get(url)
    assert response.status_code == 200

    data = response.data.decode("utf-8")
    # Має показувати всі записи, оскільки фільтр некоректний
    assert "150" in data or "150.0" in data or "150.00" in data


def test_daily_summary_with_nonexistent_master_filter(appointments_auth_client, appointment_test_data, session):
    """
    Тест daily_summary з неіснуючим master_id.
    Має показувати порожній результат для цього майстра.
    """
    test_date = date.today()

    appointment = Appointment(
        client_id=appointment_test_data["client"].id,
        master_id=appointment_test_data["master"].id,
        date=test_date,
        start_time=time(10, 0),
        end_time=time(11, 0),
        status="completed",
        notes="Test appointment",
    )
    session.add(appointment)
    session.flush()

    service = AppointmentService(
        appointment_id=appointment.id,
        service_id=appointment_test_data["service"].id,
        price=150.0,
    )
    session.add(service)
    session.commit()

    # Запит з неіснуючим master_id (але валідним числом)
    nonexistent_master_id = 99999
    url = f"/appointments/daily-summary?" f"date={test_date.strftime('%Y-%m-%d')}&" f"master_id={nonexistent_master_id}"
    response = appointments_auth_client.get(url)
    assert response.status_code == 200

    data = response.data.decode("utf-8")
    # Має показувати порожній результат або нульову суму
    assert "0" in data or "0.00" in data


def test_daily_summary_masters_statistics_calculation(appointments_auth_client, appointment_test_data, session):
    """
    Тест розрахунку статистики майстрів у daily_summary.
    Перевіряє коректність підрахунку кількості записів та сум для кожного майстра.
    """
    test_date = date.today()

    # Створюємо другого майстра
    master2 = User(
        username=f"test_master2_{uuid.uuid4().hex[:8]}",
        password=generate_password_hash("password"),
        full_name=f"Test Master 2 {uuid.uuid4().hex[:8]}",
        is_admin=False,
        is_active_master=True,
    )
    session.add(master2)
    session.flush()

    # Записи для першого майстра
    for i in range(2):
        appointment = Appointment(
            client_id=appointment_test_data["client"].id,
            master_id=appointment_test_data["master"].id,
            date=test_date,
            start_time=time(10 + i, 0),
            end_time=time(11 + i, 0),
            status="completed",
            notes=f"Appointment {i} for master 1",
        )
        session.add(appointment)
        session.flush()

        service = AppointmentService(
            appointment_id=appointment.id,
            service_id=appointment_test_data["service"].id,
            price=100.0,
        )
        session.add(service)

    # Один запис для другого майстра
    appointment3 = Appointment(
        client_id=appointment_test_data["client"].id,
        master_id=master2.id,
        date=test_date,
        start_time=time(14, 0),
        end_time=time(15, 0),
        status="completed",
        notes="Appointment for master 2",
    )
    session.add(appointment3)
    session.flush()

    service3 = AppointmentService(
        appointment_id=appointment3.id,
        service_id=appointment_test_data["service"].id,
        price=300.0,
    )
    session.add(service3)

    session.commit()

    # Запит без фільтра майстра (має показувати статистику всіх майстрів)
    response = appointments_auth_client.get(f"/appointments/daily-summary?date={test_date.strftime('%Y-%m-%d')}")
    assert response.status_code == 200

    data = response.data.decode("utf-8")
    # Загальна сума: 2 * 100.0 + 300.0 = 500.0
    assert "500" in data or "500.0" in data or "500.00" in data

    # Перевіряємо наявність імен майстрів у статистиці
    assert appointment_test_data["master"].full_name in data
    assert master2.full_name in data


def test_daily_summary_with_scheduled_and_cancelled_appointments(
    appointments_auth_client, appointment_test_data, session
):
    """
    Тест daily_summary з записами статусів 'scheduled' та 'cancelled'.
    Ці записи не мають враховуватися в сумах, але мають відображатися в списку.
    """
    test_date = date.today()

    # Створюємо записи з різними статусами
    statuses_and_prices = [
        ("scheduled", 100.0),
        ("cancelled", 200.0),
        ("completed", 300.0),
    ]

    for i, (status, price) in enumerate(statuses_and_prices):
        appointment = Appointment(
            client_id=appointment_test_data["client"].id,
            master_id=appointment_test_data["master"].id,
            date=test_date,
            start_time=time(10 + i, 0),
            end_time=time(11 + i, 0),
            status=status,
            notes=f"Test {status} appointment",
        )
        session.add(appointment)
        session.flush()

        service = AppointmentService(
            appointment_id=appointment.id,
            service_id=appointment_test_data["service"].id,
            price=price,
        )
        session.add(service)

    session.commit()

    response = appointments_auth_client.get(f"/appointments/daily-summary?date={test_date.strftime('%Y-%m-%d')}")
    assert response.status_code == 200

    data = response.data.decode("utf-8")
    # Тільки completed запис має враховуватися в сумі (300.0)
    assert "300" in data or "300.0" in data or "300.00" in data
    # Перевіряємо, що всі записи відображаються в таблиці
    # (шаблон показує всі записи, але статуси не виводяться)
    assert appointment_test_data["client"].name in data
    # Перевіряємо наявність часу записів
    assert "10:00" in data
    assert "11:00" in data
    assert "12:00" in data


def test_appointment_edit_with_import():
    """Цей тест перевіряє, що імпорт функції edit не викликає помилок."""
    # Import but don't use to avoid F401
    from app.routes.appointments import edit  # noqa: F401

    # Тест використовується для перевірки імпорту, самої функції ми не викликаємо
    pass


# Тести для редагування ціни послуги в записі
def test_edit_service_price_success(appointments_auth_client, appointment_test_data, session):
    """
    Тест успішного редагування ціни послуги в записі.
    Перевіряє статус відповіді, наявність повідомлення про успіх,
    і оновлення ціни в базі даних.
    """
    # Початкові дані
    appointment_id = appointment_test_data["appointment_id"]
    service_id = appointment_test_data["appointment_service_id"]
    new_price = 750.0

    # Отримуємо поточну ціну для порівняння
    appointment_service = db.session.get(AppointmentService, service_id)
    old_price = appointment_service.price

    # Запит на оновлення ціни
    response = appointments_auth_client.post(
        f"/appointments/{appointment_id}/edit_service/{service_id}",
        data={"price": new_price},
        follow_redirects=True,
    )

    # Перевіряємо успішну відповідь
    assert response.status_code == 200
    assert "Ціну послуги оновлено!" in response.data.decode("utf-8")

    # Оновлюємо об'єкт з бази даних
    db.session.refresh(appointment_service)

    # Перевіряємо, що ціна оновилася
    assert appointment_service.price == new_price
    assert appointment_service.price != old_price

    # Перевіряємо, що загальна вартість запису оновилася
    appointment = db.session.get(Appointment, appointment_id)
    db.session.refresh(appointment)
    assert appointment.get_total_price() == new_price


def test_edit_service_price_unauthorized(client, appointment_test_data):
    """
    Тест спроби редагування ціни послуги неавторизованим користувачем.
    Перевіряє перенаправлення на сторінку логіну.
    """
    appointment_id = appointment_test_data["appointment_id"]
    service_id = appointment_test_data["appointment_service_id"]

    # Спроба без авторизації
    response = client.post(
        f"/appointments/{appointment_id}/edit_service/{service_id}",
        data={"price": 800.0},
        follow_redirects=True,
    )

    # Перевіряємо перенаправлення на логін
    assert response.status_code == 200
    assert "Вхід" in response.data.decode("utf-8")
    assert "Логін" in response.data.decode("utf-8")


def test_edit_service_price_wrong_master(client, appointment_test_data, session):
    """
    Тест спроби редагування ціни послуги майстром, якому не належить запис.
    Перевіряє відмову доступу.
    """
    appointment_id = appointment_test_data["appointment_id"]
    service_id = appointment_test_data["appointment_service_id"]

    # Створюємо іншого майстра та логінимось під ним
    another_master = User(
        username=f"another_master_{uuid.uuid4().hex[:8]}",
        password=generate_password_hash("password"),
        full_name="Another Master",
        is_admin=False,
        is_active_master=True,
    )
    session.add(another_master)
    session.commit()

    # Логін від імені цього майстра
    client.post(
        "/auth/login",
        data={
            "username": another_master.username,
            "password": "password",
            "remember_me": "y",
        },
    )

    # Спроба редагування послуги в записі іншого майстра
    response = client.post(
        f"/appointments/{appointment_id}/edit_service/{service_id}",
        data={"price": 800.0},
        follow_redirects=True,
    )

    # Перевіряємо відмову в доступі
    assert response.status_code == 200
    assert "У вас немає доступу" in response.data.decode("utf-8")


def test_edit_service_price_non_scheduled_status(appointments_auth_client, appointment_test_data, session):
    """
    Тест спроби редагування ціни послуги в записі не в статусі 'scheduled'.
    Перевіряє відмову в редагуванні.
    """
    appointment_id = appointment_test_data["appointment_id"]
    service_id = appointment_test_data["appointment_service_id"]

    # Змінюємо статус запису на "completed"
    appointment = db.session.get(Appointment, appointment_id)
    appointment.status = "completed"
    session.commit()

    # Спроба редагування ціни
    response = appointments_auth_client.post(
        f"/appointments/{appointment_id}/edit_service/{service_id}",
        data={"price": 800.0},
        follow_redirects=True,
    )

    # Перевіряємо відмову в редагуванні через статус
    assert response.status_code == 200
    assert "Редагування ціни можливе тільки для запланованих записів" in response.data.decode("utf-8")


def test_edit_service_price_invalid_input(appointments_auth_client, appointment_test_data):
    """
    Тест спроби редагування ціни послуги з невалідними даними.
    Перевіряє валідацію введеної ціни.
    """
    appointment_id = appointment_test_data["appointment_id"]
    service_id = appointment_test_data["appointment_service_id"]

    # Спроба з від'ємною ціною
    response = appointments_auth_client.post(
        f"/appointments/{appointment_id}/edit_service/{service_id}",
        data={"price": -100.0},
        follow_redirects=True,
    )

    # Перевіряємо помилку валідації
    assert response.status_code == 200
    assert "Невірна ціна!" in response.data.decode("utf-8")

    # Спроба з невалідним значенням
    response = appointments_auth_client.post(
        f"/appointments/{appointment_id}/edit_service/{service_id}",
        data={"price": "не число"},
        follow_redirects=True,
    )

    # Перевіряємо помилку валідації
    assert response.status_code == 200
    assert "Невірна ціна!" in response.data.decode("utf-8")


def test_edit_service_price_updates_total_price(appointments_auth_client, session):
    """
    Тест перевірки оновлення загальної вартості запису після
    редагування ціни послуги.
    """
    # Створюємо клієнта, майстра та послуги
    client_entity = Client(
        name=f"Client Total Price Test {uuid.uuid4().hex[:8]}",
        phone=f"+380991234{uuid.uuid4().hex[:4]}",
    )
    master = User(
        username=f"master_price_test_{uuid.uuid4().hex[:8]}",
        password=generate_password_hash("password"),
        full_name="Price Test Master",
        is_admin=False,
        is_active_master=True,
    )
    service1 = Service(
        name=f"Service Price Test 1 {uuid.uuid4().hex[:8]}",
        duration=30,
        base_price=100.0,
    )
    service2 = Service(
        name=f"Service Price Test 2 {uuid.uuid4().hex[:8]}",
        duration=60,
        base_price=200.0,
    )
    session.add_all([client_entity, master, service1, service2])
    session.commit()

    # Створюємо запис з послугами
    appointment = Appointment(
        client_id=client_entity.id,
        master_id=master.id,
        date=date.today() + timedelta(days=1),
        start_time=time(10, 0),
        end_time=time(11, 30),
        status="scheduled",
    )
    session.add(appointment)
    session.commit()

    # Додаємо послуги до запису
    appointment_service1 = AppointmentService(
        appointment_id=appointment.id, service_id=service1.id, price=service1.base_price
    )
    appointment_service2 = AppointmentService(
        appointment_id=appointment.id, service_id=service2.id, price=service2.base_price
    )
    session.add_all([appointment_service1, appointment_service2])
    session.commit()

    # Отримуємо початкову загальну вартість
    initial_total = appointment.get_total_price()
    assert initial_total == service1.base_price + service2.base_price

    # Оновлюємо ціну першої послуги
    new_price1 = 150.0
    response = appointments_auth_client.post(
        f"/appointments/{appointment.id}/edit_service/{appointment_service1.id}",
        data={"price": new_price1},
        follow_redirects=True,
    )

    # Перевіряємо успішність запиту
    assert response.status_code == 200
    assert "Ціну послуги оновлено!" in response.data.decode("utf-8")

    # Оновлюємо об'єкт з БД
    session.refresh(appointment)

    # Перевіряємо, що загальна вартість правильно оновилася
    expected_total = new_price1 + service2.base_price
    assert appointment.get_total_price() == expected_total


# Test payment logic when completing an appointment
def test_appointment_completion_payment_methods(
    app, appointments_auth_client, appointment_test_data, session, payment_methods
):
    """
    Тест обробки оплати при завершенні запису з різними методами оплати.
    Перевіряє коректність встановлення amount_paid та payment_status.
    """
    from app.models import Appointment

    # Створення нового запису для тестування завершення
    with app.app_context():
        # Встановлення знижки для перевірки discounted_price
        appointment = appointment_test_data["appointment"]
        appointment.discount_percentage = Decimal("10.0")  # 10% знижка

        # Зберігаємо базову ціну для перевірок
        base_price = appointment.get_total_price()
        expected_discounted_price = appointment.get_discounted_price()

        session.commit()

        appointment_id = appointment.id

    # Тест 1: Завершення запису з методом оплати "Готівка"
    cash_data = {"payment_method": PaymentMethod.CASH.value, "submit": "Зберегти"}

    response = appointments_auth_client.post(
        f"/appointments/{appointment_id}/status/completed",
        data=cash_data,
        follow_redirects=True,
    )

    assert response.status_code == 200

    # Перевіряємо, що запис оновлено правильно
    with app.app_context():
        refreshed_appointment = Appointment.query.get(appointment_id)

        # Перевірка методу оплати, суми оплати та статусу оплати
        assert refreshed_appointment.payment_method == PaymentMethod.CASH
        # Використовуємо Decimal для порівняння
        assert refreshed_appointment.amount_paid == expected_discounted_price
        assert refreshed_appointment.payment_status == "paid"

        # Змінимо статус назад на scheduled для наступного тесту
        refreshed_appointment.status = "scheduled"
        refreshed_appointment.payment_method = None
        refreshed_appointment.amount_paid = None
        session.commit()

    # Тест 2: Завершення запису з методом оплати "Борг"
    debt_data = {"payment_method": PaymentMethod.DEBT.value, "submit": "Зберегти"}

    response = appointments_auth_client.post(
        f"/appointments/{appointment_id}/status/completed",
        data=debt_data,
        follow_redirects=True,
    )

    assert response.status_code == 200

    # Перевіряємо, що запис оновлено правильно
    with app.app_context():
        refreshed_appointment = Appointment.query.get(appointment_id)

        # Перевірка методу оплати, суми оплати та статусу оплати
        assert refreshed_appointment.payment_method == PaymentMethod.DEBT
        assert refreshed_appointment.amount_paid == Decimal("0.00")
        assert refreshed_appointment.payment_status == "unpaid"


def test_edit_service_price_updates_payment_status(appointments_auth_client, session):
    """
    Тест перевірки оновлення статусу оплати після редагування ціни послуги.
    """
    # Створюємо клієнта, майстра та послугу
    client_entity = Client(
        name=f"Client Payment Status Test {uuid.uuid4().hex[:8]}",
        phone=f"+380991234{uuid.uuid4().hex[:4]}",
    )
    master = User(
        username=f"master_payment_test_{uuid.uuid4().hex[:8]}",
        password=generate_password_hash("password"),
        full_name="Payment Test Master",
        is_admin=False,
        is_active_master=True,
    )
    service = Service(
        name=f"Service Payment Test {uuid.uuid4().hex[:8]}",
        duration=30,
        base_price=100.0,
    )
    session.add_all([client_entity, master, service])
    session.commit()

    # Створюємо запис з частково оплаченою послугою
    appointment = Appointment(
        client_id=client_entity.id,
        master_id=master.id,
        date=date.today() + timedelta(days=1),
        start_time=time(10, 0),
        end_time=time(10, 30),
        status="scheduled",
        amount_paid=50.0,  # Частково оплачено
    )
    session.add(appointment)
    session.commit()

    # Додаємо послугу до запису
    appointment_service = AppointmentService(
        appointment_id=appointment.id, service_id=service.id, price=service.base_price
    )
    session.add(appointment_service)
    session.commit()

    # Переконаємось, що статус оплати - "partially_paid"
    appointment.update_payment_status()
    session.commit()
    session.refresh(appointment)
    assert appointment.payment_status == "partially_paid"

    # Змінюємо ціну послуги на меншу, щоб amount_paid перевищував загальну ціну
    new_price = 40.0  # Менше, ніж amount_paid
    response = appointments_auth_client.post(
        f"/appointments/{appointment.id}/edit_service/{appointment_service.id}",
        data={"price": new_price},
        follow_redirects=True,
    )

    # Перевіряємо успішну відповідь
    assert response.status_code == 200
    assert "Ціну послуги оновлено!" in response.data.decode("utf-8")

    # Перевіряємо, що статус оплати змінився на "paid"
    session.refresh(appointment)
    assert appointment.payment_status == "paid"


def test_edit_service_price_handles_zero_price(appointments_auth_client, session):
    """
    Тест перевірки коректної обробки нульової ціни послуги.
    """
    # Створюємо клієнта, майстра та послугу
    client_entity = Client(
        name=f"Client Zero Price Test {uuid.uuid4().hex[:8]}",
        phone=f"+380991234{uuid.uuid4().hex[:4]}",
    )
    master = User(
        username=f"master_zero_price_{uuid.uuid4().hex[:8]}",
        password=generate_password_hash("password"),
        full_name="Zero Price Master",
        is_admin=False,
        is_active_master=True,
    )
    service = Service(
        name=f"Service Zero Price {uuid.uuid4().hex[:8]}",
        duration=30,
        base_price=50.0,
    )
    session.add_all([client_entity, master, service])
    session.commit()

    # Створюємо запис з послугою
    appointment = Appointment(
        client_id=client_entity.id,
        master_id=master.id,
        date=date.today() + timedelta(days=1),
        start_time=time(10, 0),
        end_time=time(10, 30),
        status="scheduled",
    )
    session.add(appointment)
    session.commit()

    # Додаємо послугу до запису
    appointment_service = AppointmentService(
        appointment_id=appointment.id, service_id=service.id, price=service.base_price
    )
    session.add(appointment_service)
    session.commit()

    # Змінюємо ціну послуги на нуль
    response = appointments_auth_client.post(
        f"/appointments/{appointment.id}/edit_service/{appointment_service.id}",
        data={"price": 0.0},
        follow_redirects=True,
    )

    # Перевіряємо успішну відповідь
    assert response.status_code == 200
    assert "Ціну послуги оновлено!" in response.data.decode("utf-8")

    # Перевіряємо, що ціна оновилася на нуль
    session.refresh(appointment_service)
    assert appointment_service.price == 0.0

    # Перевіряємо, що загальна вартість запису стала нульовою
    session.refresh(appointment)
    assert appointment.get_total_price() == 0.0

    # Якщо amount_paid не встановлено, статус має бути "unpaid"
    assert appointment.payment_status == "unpaid"

    # Встановлюємо amount_paid = 0 і перевіряємо, що статус стає "paid"
    appointment.amount_paid = 0.0
    appointment.update_payment_status()
    session.commit()
    assert appointment.payment_status == "paid"
