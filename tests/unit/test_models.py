import pytest
import uuid
from sqlalchemy.exc import IntegrityError
from datetime import datetime, time, date

from app.models import User, Client, Service, Appointment, AppointmentService
from werkzeug.security import generate_password_hash


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
        assert admin_user.is_admin is True
        assert (
            admin_user.is_administrator() is True
        )  # Перевірка методу is_administrator

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
        assert (
            saved_client.created_at is not None
        )  # Перевірка автоматичного створення timestamp

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
            session.query(Appointment)
            .filter_by(client_id=test_client.id, date=date(2023, 5, 15))
            .first()
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

    def test_appointment_relationships(
        self, test_appointment, test_client, regular_user
    ):
        """Тест зв'язків запису з клієнтом та майстром"""
        # Перевірка відносин з клієнтом
        assert test_appointment.client_id == test_client.id
        assert "Test Client" in test_appointment.client.name
        assert test_appointment.client.phone.startswith("+38099")

        # Перевірка відносин з майстром
        assert test_appointment.master_id == regular_user.id
        assert "user_test" in test_appointment.master.username
        assert test_appointment.master.full_name == "User Test"

    def test_get_total_price(self, session, test_appointment):
        """Тест методу розрахунку загальної суми"""
        # Метод get_total_price має повертати суму цін усіх послуг запису
        # В тестових даних у test_appointment вже є одна послуга з ціною 100.0

        # Додаємо ще одну послугу
        unique_id = uuid.uuid4().hex[:8]
        service = Service(
            name=f"Additional Service {unique_id}",
            description="Additional service for test",
            duration=30,
        )
        session.add(service)
        session.flush()  # Потрібно отримати ID

        # Додавання послуги до запису
        appointment_service = AppointmentService(
            appointment_id=test_appointment.id,
            service_id=service.id,
            price=50.0,
            notes="Additional service",
        )
        session.add(appointment_service)
        session.commit()

        # Перевірка розрахунку загальної суми
        # 100.0 (перша послуга) + 50.0 (друга послуга) = 150.0
        total_price = test_appointment.get_total_price()
        assert total_price == 150.0

    def test_appointment_payment_fields(self, session, test_client, regular_user):
        """Тест полів оплати"""
        appointment = Appointment(
            client_id=test_client.id,
            master_id=regular_user.id,
            date=date(2023, 6, 15),
            start_time=time(15, 0),
            end_time=time(16, 0),
            status="completed",
            payment_status="paid",
            amount_paid=500.50,
            payment_method="Картка",
            notes="Paid appointment",
        )
        session.add(appointment)
        session.commit()

        # Перевірка, що запис збережено в базі даних
        saved_appointment = (
            session.query(Appointment)
            .filter_by(client_id=test_client.id, date=date(2023, 6, 15))
            .first()
        )
        assert saved_appointment is not None
        assert saved_appointment.payment_status == "paid"
        assert float(saved_appointment.amount_paid) == 500.50
        assert saved_appointment.payment_method == "Картка"


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
        updated_service = session.query(AppointmentService).get(appointment_service.id)
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
        updated_appointment = session.query(Appointment).get(test_appointment.id)
        assert len(updated_appointment.services) > 1  # Має бути більше однієї послуги
