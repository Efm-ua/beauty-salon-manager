import uuid
from datetime import date, datetime, time, timedelta

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import Config
from app.models import Appointment, AppointmentService, Client, Service, User
from app.models import db as _db


# Клас тестової конфігурації
class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key"


# Створення тестового додатку Flask
@pytest.fixture(scope="session")
def app():
    """
    Створює тестовий додаток Flask з налаштуваннями для тестування.

    Налаштування:
    - TESTING=True - включений режим тестування
    - SQLALCHEMY_DATABASE_URI='sqlite:///:memory:' - база даних SQLite у пам'яті
    - WTF_CSRF_ENABLED=False - відключений CSRF захист для тестових форм
    """
    app = create_app(config_class=TestConfig)

    # Створення контексту додатка
    with app.app_context():
        yield app


# Фікстура для доступу до об'єкта бази даних
@pytest.fixture(scope="session")
def db(app):
    """
    Надає доступ до об'єкта бази даних.

    Створює всі таблиці в базі даних перед тестами
    і видаляє їх після завершення всіх тестів.
    """
    with app.app_context():
        _db.create_all()
        yield _db
        # Очищаємо таблиці в правильному порядку перед видаленням схеми
        _db.session.query(AppointmentService).delete()
        _db.session.query(Appointment).delete()
        _db.session.query(User).delete()
        _db.session.query(Client).delete()
        _db.session.query(Service).delete()
        _db.session.commit()
        _db.session.remove()
        _db.drop_all()


# Фікстура для ізольованої сесії бази даних
@pytest.fixture(scope="function")
def session(db):
    """
    Створює ізольовану сесію бази даних для кожного тесту.

    Починає нову транзакцію перед кожним тестом і відкочує її після завершення,
    забезпечуючи ізоляцію тестів один від одного.
    """
    connection = db.engine.connect()
    transaction = connection.begin()

    session = db.session
    session.bind = connection

    yield session

    # Відкочення транзакції після тесту
    transaction.rollback()
    connection.close()
    session.remove()


# Фікстура для тестового клієнта Flask
@pytest.fixture(scope="function")
def client(app):
    """
    Надає тестовий клієнт Flask для відправки запитів.
    """
    return app.test_client()


# Фікстура для адміністратора
@pytest.fixture(scope="function")
def admin_user(session):
    """
    Створює тестового адміністратора.
    """
    user = User(
        username=f"admin_test_{uuid.uuid4().hex[:8]}",  # Унікальне ім'я користувача
        password=generate_password_hash("admin_password"),
        full_name="Admin Test",
        is_admin=True,
    )
    session.add(user)
    session.commit()
    return user


# Фікстура для звичайного користувача
@pytest.fixture(scope="function")
def regular_user(session):
    """
    Створює тестового звичайного користувача (майстра).
    """
    user = User(
        username=f"user_test_{uuid.uuid4().hex[:8]}",  # Унікальне ім'я користувача
        password=generate_password_hash("user_password"),
        full_name="User Test",
        is_admin=False,
    )
    session.add(user)
    session.commit()
    return user


# Фікстура для клієнта салону
@pytest.fixture(scope="function")
def test_client(session):
    """
    Створює тестового клієнта салону.
    """
    # Генеруємо унікальні значення для кожного запуску тесту
    unique_id = uuid.uuid4().hex[:8]

    client = Client(
        name=f"Test Client {unique_id}",
        phone=f"+38099{unique_id}",
        email=f"test_{unique_id}@example.com",
        notes="Test client notes",
    )
    session.add(client)
    session.commit()
    return client


# Фікстура для послуги салону
@pytest.fixture(scope="function")
def test_service(session):
    """
    Створює тестову послугу салону.
    """
    unique_id = uuid.uuid4().hex[:8]

    service = Service(
        name=f"Test Service {unique_id}",
        description="Test service description",
        duration=60,  # 60 хвилин
    )
    session.add(service)
    session.commit()
    return service


# Фікстура для запису клієнта
@pytest.fixture(scope="function")
def test_appointment(session, test_client, regular_user, test_service):
    """
    Створює тестовий запис клієнта з призначеною послугою.
    """
    # Створення запису
    start_time = time(10, 0)  # 10:00

    # Обчислення end_time на основі start_time та тривалості послуги
    start_datetime = datetime.combine(date.today(), start_time)
    end_datetime = start_datetime + timedelta(minutes=test_service.duration)
    end_time = end_datetime.time()

    appointment = Appointment(
        client_id=test_client.id,
        master_id=regular_user.id,
        date=date.today(),
        start_time=start_time,
        end_time=end_time,
        status="scheduled",
        payment_status="unpaid",
        amount_paid=None,
        payment_method=None,
        notes="Test appointment",
    )
    session.add(appointment)
    session.flush()

    # Додавання послуги до запису
    appointment_service = AppointmentService(
        appointment_id=appointment.id,
        service_id=test_service.id,
        price=100.0,
        notes="Test appointment service",
    )
    session.add(appointment_service)
    session.commit()

    return appointment


# Фікстура для авторизованого тестового клієнта
@pytest.fixture(scope="function")
def auth_client(client, regular_user):
    """
    Надає авторизований тестовий клієнт Flask із сесією.

    Виконує імітацію входу користувача та повертає клієнт
    із встановленою сесією для тестування захищених маршрутів.
    """
    client.post(
        "/login",
        data={"username": regular_user.username, "password": "user_password"},
        follow_redirects=True,
    )

    return client


# Фікстура для авторизованого адміністративного клієнта
@pytest.fixture(scope="function")
def admin_auth_client(client, admin_user):
    """
    Надає авторизований тестовий клієнт Flask із сесією адміністратора.

    Виконує імітацію входу адміністратора та повертає клієнт
    із встановленою сесією для тестування адміністративних маршрутів.
    """
    client.post(
        "/login",
        data={"username": admin_user.username, "password": "admin_password"},
        follow_redirects=True,
    )

    return client
