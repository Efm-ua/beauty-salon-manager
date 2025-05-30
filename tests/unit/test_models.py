import uuid
from datetime import date, datetime, time
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from app.models import Appointment, AppointmentService, Client, PaymentMethod, Service, User


class TestUserModel:
    """Тести для моделі User (користувачі/майстри салону)"""

    def test_create_user(self, session):
        """Тест створення користувача та збереження в базі даних"""
        username = f"testuser_{uuid.uuid4().hex[:8]}"
        user = User(
            username=username,
            password=generate_password_hash("password123"),
            full_name="Test User",
            is_admin=False,
        )
        session.add(user)
        session.commit()

        # Перевірка, що запис збережено в базі даних
        saved_user = session.query(User).filter_by(username=username).first()
        assert saved_user is not None
        assert saved_user.id is not None

    def test_user_attributes(self, regular_user):
        """Тест перевірки атрибутів користувача"""
        assert "user_test" in regular_user.username
        assert regular_user.full_name == "User Test"
        assert regular_user.is_admin is False

    def test_user_admin_status(self, admin_user):
        """Тест перевірки адміністративного статусу"""
        # Створюємо новий об'єкт User з даними з admin_user об'єкта
        admin = User(
            username=admin_user.username,
            password=admin_user.password,
            full_name=admin_user.full_name,
            is_admin=True,
        )

        # Перевіряємо атрибути створеного об'єкта
        assert admin.is_admin is True
        assert admin.is_administrator() is True  # Перевірка методу is_administrator

    def test_username_unique_constraint(self, session, regular_user):
        """Тест перевірки унікальності імені користувача"""
        # Спроба створити користувача з таким самим ім'ям
        duplicate_user = User(
            username=regular_user.username,  # Таке саме ім'я як у regular_user
            password=generate_password_hash("another_password"),
            full_name="Another User",
            is_admin=False,
        )
        session.add(duplicate_user)

        # Має виникнути IntegrityError через порушення обмеження унікальності
        with pytest.raises(IntegrityError):
            session.commit()

        # Відкат транзакції для інших тестів
        session.rollback()

    def test_new_master_default_is_active(self, session):
        """Перевірка, що при створенні нового користувача-майстра (is_admin=False)
        поле is_active_master за замовчуванням True."""
        # Створюємо нового користувача через функцію, яка має встановити значення is_active_master
        username = f"testmaster_{uuid.uuid4().hex[:8]}"
        user = User(
            username=username,
            password=generate_password_hash("password123"),
            full_name="Test Master",
            is_admin=False,
        )
        session.add(user)
        session.commit()

        # Перевіряємо, що is_active_master за замовчуванням True для майстра
        saved_user = session.query(User).filter_by(username=username).first()
        assert hasattr(saved_user, "is_active_master"), "User model doesn't have is_active_master attribute"
        assert saved_user.is_active_master is True

    def test_new_admin_default_is_inactive(self, session):
        """Перевірка, що при створенні нового користувача-адміністратора (is_admin=True)
        поле is_active_master за замовчуванням False."""
        # Створюємо нового адміністратора через функцію, яка має встановити значення is_active_master
        username = f"testadmin_{uuid.uuid4().hex[:8]}"
        user = User(
            username=username,
            password=generate_password_hash("password123"),
            full_name="Test Admin",
            is_admin=True,
        )
        session.add(user)
        session.commit()

        # Перевіряємо, що is_active_master за замовчуванням False для адміністратора
        saved_user = session.query(User).filter_by(username=username).first()
        assert hasattr(saved_user, "is_active_master"), "User model doesn't have is_active_master attribute"
        assert saved_user.is_active_master is False

    def test_user_can_toggle_is_active_master(self, session):
        """Перевірка можливості встановлення та отримання значення is_active_master."""
        # Створюємо користувача з явним встановленням is_active_master=False
        username = f"testuser_{uuid.uuid4().hex[:8]}"
        user = User(
            username=username,
            password=generate_password_hash("password123"),
            full_name="Test User",
            is_admin=False,
            is_active_master=False,  # Явно встановлюємо False
        )
        session.add(user)
        session.commit()

        # Перевіряємо початкове значення
        saved_user = session.query(User).filter_by(username=username).first()
        assert saved_user.is_active_master is False

        # Змінюємо значення is_active_master на True
        saved_user.is_active_master = True
        session.commit()

        # Перевіряємо оновлене значення
        updated_user = session.query(User).filter_by(username=username).first()
        assert updated_user.is_active_master is True


class TestClientModel:
    """Тести для моделі Client (клієнти салону)"""

    def test_create_client(self, session):
        """Тест створення клієнта та збереження в базі даних"""
        unique_id = uuid.uuid4().hex[:8]
        client = Client(
            name=f"New Test Client {unique_id}",
            phone=f"+38099{unique_id}",
            email=f"new_client_{unique_id}@example.com",
            notes="Test notes for new client",
        )
        session.add(client)
        session.commit()

        # Перевірка, що запис збережено в базі даних
        saved_client = session.query(Client).filter_by(phone=client.phone).first()
        assert saved_client is not None
        assert saved_client.id is not None
        assert saved_client.created_at is not None  # Перевірка автоматичного створення timestamp

    def test_client_attributes(self, test_client):
        """Тест перевірки атрибутів клієнта"""
        assert "Test Client" in test_client.name
        assert test_client.phone.startswith("+38099")
        assert "test_" in test_client.email
        assert "@example.com" in test_client.email
        assert test_client.notes == "Test client notes"
        assert isinstance(test_client.created_at, datetime)

    def test_phone_unique_constraint(self, session, test_client):
        """Тест перевірки унікальності телефону клієнта"""
        # Спроба створити клієнта з таким самим телефоном
        duplicate_client = Client(
            name="Another Client",
            phone=test_client.phone,  # Такий самий телефон як у test_client
            email=f"another_{uuid.uuid4().hex[:8]}@example.com",
            notes="Another client notes",
        )
        session.add(duplicate_client)

        # Має виникнути IntegrityError через порушення обмеження унікальності
        with pytest.raises(IntegrityError):
            session.commit()

        # Відкат транзакції для інших тестів
        session.rollback()

    def test_email_unique_constraint(self, session, test_client):
        """Тест перевірки унікальності email клієнта"""
        # Спроба створити клієнта з таким самим email
        unique_id = uuid.uuid4().hex[:8]
        duplicate_client = Client(
            name="Another Client",
            phone=f"+38099{unique_id}",  # Інший телефон
            email=test_client.email,  # Такий самий email як у test_client
            notes="Another client notes",
        )
        session.add(duplicate_client)

        # Має виникнути IntegrityError через порушення обмеження унікальності
        with pytest.raises(IntegrityError):
            session.commit()

        # Відкат транзакції для інших тестів
        session.rollback()

    def test_email_can_be_null(self, session):
        """Тест можливості створення клієнта без email"""
        unique_id = uuid.uuid4().hex[:8]
        client = Client(
            name=f"Client Without Email {unique_id}",
            phone=f"+38099{unique_id}",
            email=None,  # Без email
            notes="Client with no email",
        )
        session.add(client)

        # Не повинно виникнути помилки
        session.commit()

        saved_client = session.query(Client).filter_by(phone=client.phone).first()
        assert saved_client is not None
        assert saved_client.email is None


class TestServiceModel:
    """Тести для моделі Service (послуги салону)"""

    def test_create_service(self, session):
        """Тест створення послуги та збереження в базі даних"""
        unique_id = uuid.uuid4().hex[:8]
        service = Service(
            name=f"New Test Service {unique_id}",
            description="Description for new test service",
            duration=45,  # 45 хвилин
        )
        session.add(service)
        session.commit()

        # Перевірка, що запис збережено в базі даних
        saved_service = session.query(Service).filter_by(name=service.name).first()
        assert saved_service is not None
        assert saved_service.id is not None

    def test_service_attributes(self, test_service):
        """Тест перевірки атрибутів послуги"""
        assert "Test Service" in test_service.name
        assert test_service.description == "Test service description"
        assert test_service.duration == 60  # 60 хвилин

    def test_service_without_description(self, session):
        """Тест можливості створення послуги без опису"""
        unique_id = uuid.uuid4().hex[:8]
        service = Service(
            name=f"Service Without Description {unique_id}",
            description=None,  # Без опису
            duration=30,
        )
        session.add(service)

        # Не повинно виникнути помилки
        session.commit()

        saved_service = session.query(Service).filter_by(name=service.name).first()
        assert saved_service is not None
        assert saved_service.description is None


class TestAppointmentModel:
    """Тести для моделі Appointment (записи клієнтів)"""

    def test_create_appointment(self, session, test_client, regular_user):
        """Тест створення запису та збереження в базі даних"""
        appointment = Appointment(
            client_id=test_client.id,
            master_id=regular_user.id,
            date=date(2023, 5, 15),
            start_time=time(13, 0),  # 13:00
            end_time=time(14, 0),  # 14:00
            status="scheduled",
            notes="New test appointment",
        )
        session.add(appointment)
        session.commit()

        # Перевірка, що запис збережено в базі даних
        saved_appointment = (
            session.query(Appointment).filter_by(client_id=test_client.id, date=date(2023, 5, 15)).first()
        )
        assert saved_appointment is not None
        assert saved_appointment.id is not None
        assert saved_appointment.created_at is not None

        # Перевірка значень за замовчуванням для нових полів
        assert saved_appointment.payment_status == "unpaid"
        assert saved_appointment.amount_paid is None
        assert saved_appointment.payment_method is None

    def test_appointment_attributes(self, test_appointment):
        """Тест перевірки атрибутів запису"""
        assert test_appointment.date == date.today()
        assert test_appointment.start_time == time(10, 0)
        assert test_appointment.end_time == time(11, 0)
        assert test_appointment.status == "scheduled"
        assert test_appointment.notes == "Test appointment"
        assert isinstance(test_appointment.created_at, datetime)

        # Перевірка значень за замовчуванням для нових полів
        assert test_appointment.payment_status == "unpaid"
        assert test_appointment.amount_paid is None
        assert test_appointment.payment_method is None

    def test_appointment_relationships(self, test_appointment, test_client, regular_user):
        """Тест перевірки зв'язків запису з клієнтом та майстром"""
        assert test_appointment.client_id == test_client.id
        assert test_appointment.master_id == regular_user.id
        assert test_appointment.client.name == test_client.name
        assert test_appointment.master.username == regular_user.username

    def test_get_total_price(self, session, test_appointment):
        """Тест методу get_total_price для запису"""
        # Clear existing services from the test_appointment fixture
        for app_service_to_remove in list(test_appointment.services):
            session.delete(app_service_to_remove)
        session.commit()
        test_appointment.services.clear()  # Ensure the collection in the object is also clear
        session.refresh(test_appointment)  # Re-fetch to confirm cleared state if needed

        # Тепер додаємо нові послуги для тесту
        service1_price = 100.00
        service2_price = 50.00

        service1 = Service(name="Service 1 For TotalPriceTest", duration=30)
        service2 = Service(name="Service 2 For TotalPriceTest", duration=60)
        session.add_all([service1, service2])
        session.commit()

        app_service1 = AppointmentService(
            appointment_id=test_appointment.id,
            service_id=service1.id,
            price=service1_price,
        )
        app_service2 = AppointmentService(
            appointment_id=test_appointment.id,
            service_id=service2.id,
            price=service2_price,
        )
        session.add_all([app_service1, app_service2])
        test_appointment.services.append(app_service1)
        test_appointment.services.append(app_service2)
        session.commit()

        assert test_appointment.get_total_price() == service1_price + service2_price

        # Перевірка з пустим списком послуг (новий запис)
        # Create a new client and user for this empty appointment if necessary, or use existing test_client/regular_user
        client_for_empty = Client.query.first() or Client(name="Empty Client", phone="0000000000")
        master_for_empty = User.query.first() or User(username="empty_master", password="pwd", full_name="Empty Master")
        if not client_for_empty.id:
            session.add(client_for_empty)
        if not master_for_empty.id:
            session.add(master_for_empty)
        session.commit()

        empty_appointment = Appointment(
            client_id=client_for_empty.id,
            master_id=master_for_empty.id,
            date=date.today(),
            start_time=time(0, 0),
            end_time=time(0, 0),
        )
        session.add(empty_appointment)
        session.commit()
        assert empty_appointment.get_total_price() == 0.00

    def test_appointment_payment_fields(self, session, test_client, regular_user):
        """Тест значень за замовчуванням для полів оплати"""
        appointment = Appointment(
            client_id=test_client.id,
            master_id=regular_user.id,
            date=date(2023, 10, 10),
            start_time=time(14, 0),
            end_time=time(15, 0),
            status="scheduled",
        )
        session.add(appointment)
        session.commit()

        assert appointment.payment_status == "unpaid"  # Enum значення
        assert appointment.amount_paid is None
        assert appointment.payment_method is None

    def test_update_payment_status(self, session, test_client, regular_user):
        """Тест методу update_payment_status для різних сценаріїв оплати."""
        appointment = Appointment(
            client_id=test_client.id,
            master_id=regular_user.id,
            date=date(2024, 1, 1),
            start_time=time(10, 0),
            end_time=time(11, 0),
            status="scheduled",
        )
        session.add(appointment)
        session.commit()

        # Мокуємо get_discounted_price, щоб повернути фіксовану ціну для тестування
        appointment.get_discounted_price = MagicMock(return_value=100.0)

        # Сценарій 1: amount_paid = 0
        appointment.amount_paid = 0.0
        appointment.update_payment_status()
        assert appointment.payment_status == "unpaid"

        # Сценарій 2: amount_paid < discounted_price (часткова оплата)
        appointment.amount_paid = 50.0
        appointment.update_payment_status()
        assert appointment.payment_status == "partially_paid"

        # Сценарій 3: amount_paid == discounted_price (повна оплата)
        appointment.amount_paid = 100.0
        appointment.update_payment_status()
        assert appointment.payment_status == "paid"

        # Сценарій 4: amount_paid > discounted_price (переплата, вважається повною оплатою)
        appointment.amount_paid = 150.0
        appointment.update_payment_status()
        assert appointment.payment_status == "paid"

        # Сценарій 5: amount_paid = None (не оплачено)
        appointment.amount_paid = None
        appointment.update_payment_status()
        assert appointment.payment_status == "unpaid"

        # Сценарій 6: discounted_price = 0, amount_paid = 0 (безкоштовно і не оплачено/оплачено)
        appointment.get_discounted_price = MagicMock(return_value=0.0)
        appointment.amount_paid = 0.0
        appointment.update_payment_status()
        # Якщо ціна 0, і сплачено 0, то вважається оплаченим
        assert appointment.payment_status == "paid"  # Based on Appointment.update_payment_status logic

        # Сценарій 7: discounted_price = 0, amount_paid = None (безкоштовно, але сума не вказана)
        appointment.amount_paid = None
        appointment.update_payment_status()
        # Якщо ціна 0 і сума не вказана, то unpaid.
        assert appointment.payment_status == "unpaid"  # Based on Appointment.update_payment_status logic

    def test_get_total_price_with_custom_service_prices(self, session):
        """Тест методу get_total_price для запису з індивідуальними цінами послуг"""
        # Створюємо послуги з певними базовими цінами
        service1 = Service(name="Service Custom 1", duration=30, base_price=100.0)
        service2 = Service(name="Service Custom 2", duration=60, base_price=200.0)
        session.add_all([service1, service2])

        # Створюємо клієнта та майстра для запису
        client = Client(name="Client Custom Price", phone="+380991234567")
        master = User(
            username="master_custom",
            password="password",
            full_name="Master Custom",
            is_admin=False,
            is_active_master=True,
        )
        session.add_all([client, master])
        session.commit()

        # Створюємо запис
        appointment = Appointment(
            client_id=client.id,
            master_id=master.id,
            date=date.today(),
            start_time=time(13, 0),
            end_time=time(14, 30),
            status="scheduled",
        )
        session.add(appointment)
        session.commit()

        # Додаємо послуги з ІНДИВІДУАЛЬНИМИ цінами, відмінними від базових
        custom_price1 = 125.0  # Відрізняється від базової ціни service1
        custom_price2 = 185.0  # Відрізняється від базової ціни service2

        appointment_service1 = AppointmentService(
            appointment_id=appointment.id, service_id=service1.id, price=custom_price1
        )
        appointment_service2 = AppointmentService(
            appointment_id=appointment.id, service_id=service2.id, price=custom_price2
        )
        session.add_all([appointment_service1, appointment_service2])
        session.commit()

        # Оновлюємо об'єкт запису з БД
        session.refresh(appointment)

        # Перевіряємо, що total_price використовує індивідуальні ціни, а не базові ціни послуг
        expected_total = custom_price1 + custom_price2
        actual_total = appointment.get_total_price()
        assert actual_total == expected_total
        assert actual_total != (service1.base_price + service2.base_price)

        # Перевіряємо, що знижка коректно застосовується з урахуванням індивідуальних цін
        discount_percentage = Decimal("10.0")
        appointment.discount_percentage = discount_percentage
        session.commit()
        session.refresh(appointment)

        expected_discounted = Decimal(str(expected_total)) * (Decimal("100") - discount_percentage) / Decimal("100")
        actual_discounted = appointment.get_discounted_price()

        # Порівнюємо з невеликою похибкою через перетворення float в Decimal
        assert abs(actual_discounted - expected_discounted) < Decimal("0.01")


class TestAppointmentServiceModel:
    """Тести для моделі AppointmentService (послуги у записі)"""

    def test_appointment_service_relationship(self, test_appointment, test_service):
        """Тест зв'язку між записом та послугою"""
        # Отримуємо першу послугу з запису
        appointment_service = test_appointment.services[0]

        # Перевірка зв'язку з записом
        assert appointment_service.appointment_id == test_appointment.id
        assert appointment_service.appointment == test_appointment

        # Перевірка зв'язку з послугою
        assert appointment_service.service_id == test_service.id
        assert "Test Service" in appointment_service.service.name
        assert appointment_service.service.duration == test_service.duration

    def test_appointment_service_price(self, session, test_appointment, test_service):
        """Тест ціни послуги в записі"""
        # Отримуємо першу послугу з запису
        appointment_service = test_appointment.services[0]

        # Перевірка ціни
        assert appointment_service.price == 100.0

        # Тестуємо зміну ціни
        appointment_service.price = 120.0
        session.commit()

        # Перевіряємо, що ціна змінилася
        updated_service = session.get(AppointmentService, appointment_service.id)
        assert updated_service.price == 120.0

        # Перевіряємо, що загальна сума запису оновилася
        assert test_appointment.get_total_price() == 120.0

    def test_create_appointment_service(self, session, test_appointment, test_service):
        """Тест створення зв'язку між записом та послугою"""
        # Створюємо нову послугу
        unique_id = uuid.uuid4().hex[:8]
        new_service = Service(
            name=f"Another Service {unique_id}",
            description="Another service description",
            duration=30,
        )
        session.add(new_service)
        session.flush()

        # Створюємо зв'язок між існуючим записом і новою послугою
        appointment_service = AppointmentService(
            appointment_id=test_appointment.id,
            service_id=new_service.id,
            price=75.0,
            notes="Another service in appointment",
        )
        session.add(appointment_service)
        session.commit()

        # Перевіряємо, що зв'язок створено
        saved_service = (
            session.query(AppointmentService)
            .filter_by(appointment_id=test_appointment.id, service_id=new_service.id)
            .first()
        )
        assert saved_service is not None
        assert saved_service.price == 75.0
        assert saved_service.notes == "Another service in appointment"

        # Перевіряємо, що послуга додана до запису
        updated_appointment = session.get(Appointment, test_appointment.id)
        assert len(updated_appointment.services) > 1  # Має бути більше однієї послуги


def test_payment_method_enum():
    """Перевірка Enum PaymentMethod"""
    # Перевірка всіх значень у перерахуванні
    assert PaymentMethod.CASH.value == "Готівка"
    assert PaymentMethod.MALIBU.value == "Малібу"
    assert PaymentMethod.FOP.value == "ФОП"
    assert PaymentMethod.PRIVAT.value == "Приват"
    assert PaymentMethod.MONO.value == "MONO"
    assert PaymentMethod.DEBT.value == "Борг"

    # Перевірка кількості елементів
    assert len(list(PaymentMethod)) == 6
