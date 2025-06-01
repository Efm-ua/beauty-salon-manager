import os
import uuid
from datetime import date, datetime, time, timedelta

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import Config
from app.models import (Appointment, AppointmentService, Brand, Client,
                        PaymentMethod, Product, Service, StockLevel, User)
from app.models import db as _db


# Клас тестової конфігурації
class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret-key"


# Створення тестового додатку Flask
@pytest.fixture(scope="function")
def app():
    """
    Створює тестовий додаток Flask з налаштуваннями для тестування.

    Налаштування:
    - TESTING=True - включений режим тестування
    - SQLALCHEMY_DATABASE_URI='sqlite:///:memory:' - база даних SQLite у пам'яті
    - WTF_CSRF_ENABLED=False - відключений CSRF захист для тестових форм
    """
    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret-key",
        "UPLOAD_FOLDER": os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads"),
    }
    app = create_app(test_config=test_config)

    # Створення контексту додатка
    with app.app_context():
        yield app


# Фікстура для доступу до об'єкта бази даних
@pytest.fixture(scope="function")
def db(app):
    """
    Надає доступ до об'єкта бази даних.

    Створює всі таблиці в базі даних перед кожним тестом
    і підтримує ізоляцію тестів через транзакції.
    """
    with app.app_context():
        # Переконуємося, що всі попередні сесії закриті
        _db.session.remove()

        # Видаляємо всі таблиці, якщо вони існують
        _db.drop_all()

        # Створюємо таблиці в контексті додатку для кожної функції
        _db.create_all()

        yield _db

        # Завершуємо всі транзакції та очищуємо сесію
        _db.session.remove()

        # Явно видаляємо таблиці після завершення тесту
        _db.drop_all()


# Фікстура для ізольованої сесії бази даних
@pytest.fixture(scope="function")
def session(db):  # 'db' - це екземпляр Flask-SQLAlchemy
    """
    Надає сесію бази даних для кожного тесту всередини транзакції,
    яка відкочується після завершення тесту. Сесії налаштовані
    з expire_on_commit=False для запобігання DetachedInstanceError.
    """
    connection = db.engine.connect()
    transaction = connection.begin()

    configured_session_factory = db.sessionmaker(bind=connection, expire_on_commit=False)

    original_factory = db.session.session_factory
    db.session.session_factory = configured_session_factory

    # Important: Remove existing session and create a new one with the test configuration
    db.session.remove()

    # Now db.session() will use our test transaction
    # This makes test data accessible through db.session queries
    test_session_instance = db.session()

    yield test_session_instance  # Надаємо екземпляр сесії, а не proxy

    # Teardown
    test_session_instance.close()  # Закриваємо конкретний екземпляр сесії
    db.session.remove()  # Очищуємо scoped_session
    db.session.session_factory = original_factory
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function", autouse=True)
def cleanup_flask_login_state(app):  # Додано 'app' як залежність для контексту
    """Очищує стан flask-login між тестами"""
    print("DEBUG: Cleaning up Flask-Login state")

    # Ініціалізуємо контекст додатка, щоб очистити login_manager
    with app.app_context():
        try:
            # Виконуємо очищення якщо ми не в контексті тесту
            if not hasattr(app, "test_client"):
                from flask_login import login_manager

                login_manager._login_disabled = False
                if hasattr(login_manager, "_user_callback"):
                    login_manager._user_callback = None
        except Exception:  # Fixed: not assigning to unused variable 'e'
            pass  # Ігноруємо помилки, оскільки це лише очищення


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
        is_active_master=False,  # За замовчуванням адміністратор не є активним майстром
    )
    session.add(user)
    session.commit()

    # Переконуємося, що об'єкт прив'язаний до сесії перед поверненням
    session.refresh(user)
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
        is_admin=False,  # Повернуто до оригінального значення
        is_active_master=True,  # За замовчуванням майстер є активним
    )
    session.add(user)
    session.commit()

    # Переконуємося, що об'єкт прив'язаний до сесії перед поверненням
    session.refresh(user)
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
        base_price=100.0,  # Add base_price
    )
    session.add(service)
    session.commit()

    return service


# Фікстура для послуги "Haircut"
@pytest.fixture(scope="function")
def haircut_service(session):
    """
    Створює тестову послугу "Haircut" для тестів з цінами.
    """
    service = Service(
        name="Haircut",
        description="Basic haircut service",
        duration=30,  # 30 хвилин
        base_price=75.0,  # Add base_price
    )
    session.add(service)
    session.commit()
    return service


# Фікстура для додаткової послуги
@pytest.fixture(scope="function")
def additional_service(session):
    """
    Створює тестову послугу "Additional Service" для тестів з записами.
    """
    service = Service(
        name="Additional Service",
        description="Additional service for appointment tests",
        duration=30,  # 30 хвилин
        base_price=75.5,  # Add base_price
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

    # Переконуємося, що всі пов'язані об'єкти дійсні
    session.refresh(test_client)
    session.refresh(regular_user)
    session.refresh(test_service)

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
    session.flush()  # Отримуємо ID

    # Додавання послуги до запису
    appointment_service = AppointmentService(
        appointment_id=appointment.id,
        service_id=test_service.id,
        price=100.0,
        notes="Test appointment service",
    )
    session.add(appointment_service)
    session.commit()

    # Переконуємося, що всі об'єкти приєднані до сесії
    session.refresh(appointment)

    # Явно встановлюємо залежності для запобігання detached instance
    appointment.client = test_client
    appointment.master = regular_user
    return appointment


# Фікстура для авторизованого тестового клієнта
@pytest.fixture(scope="function")
def auth_client(client, regular_user):
    """
    Надає авторизований тестовий клієнт Flask із сесією.

    Виконує імітацію входу користувача та повертає клієнт
    із встановленою сесією для тестування захищених маршрутів.
    """
    print(f"DEBUG auth_client: Trying to login as {regular_user.username}")
    response = client.post(
        "/auth/login",
        data={"username": regular_user.username, "password": "user_password"},
        follow_redirects=True,
    )
    print(f"DEBUG auth_client: Login response status code: {response.status_code}")
    print(f"DEBUG auth_client: Login response data: {response.data[:100]}")

    return client


# Фікстура для авторизованого адміністративного клієнта
@pytest.fixture(scope="function")
def admin_auth_client(client, admin_user):
    """
    Надає авторизований тестовий клієнт Flask із сесією адміністратора.

    Виконує імітацію входу адміністратора та повертає клієнт
    із встановленою сесією для тестування адміністративних маршрутів.
    """
    print(f"DEBUG admin_auth_client: Trying to login as {admin_user.username}")
    print(f"DEBUG admin_auth_client: Admin user data: {admin_user}")
    response = client.post(
        "/auth/login",
        data={"username": admin_user.username, "password": "admin_password"},
        follow_redirects=True,
    )
    print(f"DEBUG admin_auth_client: Login response status code: {response.status_code}")
    print(f"DEBUG admin_auth_client: Login response data: {response.data[:100]}")

    # Додаємо перевірку GET-запиту до кореневого URL для визначення поточного користувача
    test_response = client.get("/")
    print(f"DEBUG admin_auth_client: Test GET response status: {test_response.status_code}")
    print(f"DEBUG admin_auth_client: Is 'Вийти' in response: {'Вийти' in test_response.text}")

    # Перевірка успішності автентифікації
    assert response.status_code == 200, f"Login failed: status code {response.status_code}"

    # Перевірка наявності ознак успішного входу в систему
    # 1. Перевірка наявності елементу, який видно тільки після входу (посилання на вихід)
    logout_path = "/auth/logout"
    assert logout_path in response.text, f"Login failed: Logout link not found in response for {admin_user.username}"

    # 2. Перевірка наявності імені адміністратора у відповіді
    assert (
        admin_user.full_name in response.text
    ), f"Login failed: Admin name not found in response for {admin_user.username}"

    # 3. Перевірка наявності мітки "Адміністратор" у відповіді
    assert (
        "Адміністратор" in response.text
    ), f"Login failed: Admin label not found in response for {admin_user.username}"

    return client


# Фікстура для створення і використання тестового користувача
@pytest.fixture(scope="function")
def test_user(session):
    """
    Створює тестового користувача для використання в тестах.
    """
    user = User(
        username=f"test_user_{uuid.uuid4().hex[:8]}",
        password=generate_password_hash("test_password"),
        full_name="Test User",
        is_admin=False,
        is_active_master=True,  # За замовчуванням майстер є активним
    )
    session.add(user)
    session.commit()

    # Переконуємося, що об'єкт прив'язаний до сесії перед поверненням
    session.refresh(user)
    return user


# Фікстура для процесу авторизації
@pytest.fixture(scope="function")
def auth(client, admin_user):
    """
    Допоміжна фікстура, яка надає методи для авторизації користувача.
    """

    class AuthActions:
        def __init__(self, client, admin_user):
            self._client = client
            self._admin_user = admin_user

        def login(self, username="test_user", password="test_password"):
            return self._client.post(
                "/auth/login",
                data={"username": username, "password": password},
                follow_redirects=True,
            )

        def login_as_admin(self):
            """Login as admin user for functional tests."""
            return self._client.post(
                "/auth/login",
                data={"username": self._admin_user.username, "password": "admin_password"},
                follow_redirects=True,
            )

        def logout(self):
            return self._client.get("/auth/logout", follow_redirects=True)

    return AuthActions(client, admin_user)


# Фікстура для роботи з тестовою базою даних
@pytest.fixture(scope="function")
def test_db(session):
    """
    Повертає сесію бази даних для використання в тестах.
    """
    return session


@pytest.fixture(scope="function")
def test_service_with_price(session):
    """
    Створює тестову послугу з додатковою властивістю price.
    """
    unique_id = uuid.uuid4().hex[:8]
    service = Service(
        name=f"Test Service For Pricing {unique_id}",
        description="Test service specifically for testing pricing logic",
        duration=60,  # 60 хвилин
        base_price=100.00,  # Setting the base_price directly
    )
    session.add(service)
    session.commit()

    # We no longer need to set the price manually, as we now use base_price
    # service.price = Decimal("100.00")

    return service


# Фікстура для активного майстра
@pytest.fixture(scope="function")
def active_master(session):
    """
    Створює тестового майстра з is_active_master=True.
    """
    master = User(
        username=f"active_master_{uuid.uuid4().hex[:8]}",
        password=generate_password_hash("master_password"),
        full_name="Active Master",
        is_admin=False,
        is_active_master=True,
    )
    session.add(master)
    session.commit()
    session.refresh(master)
    return master


# Фікстура для неактивного майстра
@pytest.fixture(scope="function")
def inactive_master(session):
    """
    Створює тестового майстра з is_active_master=False.
    """
    master = User(
        username=f"inactive_master_{uuid.uuid4().hex[:8]}",
        password=generate_password_hash("master_password"),
        full_name="Inactive Master",
        is_admin=False,
        is_active_master=False,
    )
    session.add(master)
    session.commit()
    session.refresh(master)
    return master


# Фікстура для створення методів оплати
@pytest.fixture(scope="function")
def payment_methods(session):
    """
    Створює стандартні методи оплати для тестів.
    """
    payment_method_names = ["Готівка", "Малібу", "ФОП", "Приват", "MONO", "Борг"]

    for name in payment_method_names:
        payment_method = PaymentMethod()
        payment_method.name = name
        payment_method.is_active = True
        session.add(payment_method)

    session.commit()
    return PaymentMethod.query.all()


@pytest.fixture(scope="function")
def test_product(session):
    """
    Creates a test product with a brand.
    """
    # Create a test brand first
    brand = Brand(name=f"Test Brand {uuid.uuid4().hex[:8]}")
    session.add(brand)
    session.commit()

    # Create a test product
    product = Product(
        name=f"Test Product {uuid.uuid4().hex[:8]}",
        sku=f"TEST-{uuid.uuid4().hex[:8]}",
        brand_id=brand.id,
        volume_value=100,
        volume_unit="мл",
        description="Test product description",
        min_stock_level=5,
        current_sale_price=150.00,
        last_cost_price=100.00,
    )
    session.add(product)
    session.commit()

    # Get and update the auto-created stock level
    stock = StockLevel.query.filter_by(product_id=product.id).first()
    if stock:
        stock.quantity = 0
        session.commit()

    return product


# Additional fixtures for inventory tests
@pytest.fixture(scope="function")
def master_user(session):
    """
    Створює тестового майстра (не адміністратора) для тестів інвентаризації.
    """
    user = User(
        username=f"master_test_{uuid.uuid4().hex[:8]}",
        password=generate_password_hash("master_password"),
        full_name="Master Test",
        is_admin=False,
        is_active_master=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture(scope="function")
def sample_products_with_stock(session):
    """
    Створює кілька тестових товарів з відомими залишками на складі.
    """
    products = []

    # Створюємо кілька брендів
    brands = []
    for i in range(3):
        brand = Brand(name=f"Test Brand {i+1}_{uuid.uuid4().hex[:8]}")
        session.add(brand)
        brands.append(brand)
    session.commit()

    # Створюємо товари з різними залишками
    initial_quantities = [15, 25, 8, 12, 30]

    for i, qty in enumerate(initial_quantities):
        product = Product(
            name=f"Test Product {i+1}_{uuid.uuid4().hex[:8]}",
            sku=f"TEST-{i+1}-{uuid.uuid4().hex[:8]}",
            brand_id=brands[i % len(brands)].id,
            volume_value=100 + i * 10,
            volume_unit="мл",
            description=f"Test product {i+1} description",
            min_stock_level=5,
            current_sale_price=150.00 + i * 25,
            last_cost_price=100.00 + i * 15,
        )
        session.add(product)
        session.flush()  # Щоб отримати ID продукту

        # Оновлюємо автоматично створений StockLevel
        stock_level = StockLevel.query.filter_by(product_id=product.id).first()
        if stock_level:
            stock_level.quantity = qty
        else:
            # Якщо з якоїсь причини не створився автоматично
            stock_level = StockLevel(product_id=product.id, quantity=qty)
            session.add(stock_level)

        products.append(product)

    session.commit()

    # Перевіряємо, що всі товари мають залишки
    for product in products:
        session.refresh(product)
        stock = StockLevel.query.filter_by(product_id=product.id).first()
        assert stock is not None, f"StockLevel not found for product {product.id}"
        assert stock.quantity > 0, f"Stock quantity is not positive for product {product.id}"

    return products
