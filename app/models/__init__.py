from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Numeric, event
from sqlalchemy.engine import Connection

db = SQLAlchemy()


# Enum для типів оплати
class PaymentMethod(Enum):
    CASH = "Готівка"
    MALIBU = "Малібу"
    FOP = "ФОП"
    PRIVAT = "Приват"
    MONO = "MONO"
    DEBT = "Борг"


# Модель користувача (майстри салону)
class User(UserMixin, db.Model):  # type: ignore[name-defined]
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active_master = db.Column(db.Boolean, nullable=False, default=True)
    schedule_display_order = db.Column(db.Integer, nullable=True, index=True)
    appointments = db.relationship("Appointment", backref="master", lazy=True, cascade="all, delete-orphan")

    def __init__(self, **kwargs: Any) -> None:
        super(User, self).__init__(**kwargs)
        # Якщо is_active_master не встановлено явно, встановлюємо значення залежно від is_admin
        if "is_active_master" not in kwargs:
            self.is_active_master = not kwargs.get("is_admin", False)

        # Для неактивних майстрів та адмінів встановлюємо schedule_display_order в None
        if "schedule_display_order" not in kwargs and not self.is_active_master:
            self.schedule_display_order = None

    def is_administrator(self) -> bool:
        return bool(self.is_admin)

    def is_master(self) -> bool:
        return not bool(self.is_admin)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


# Модель клієнта
class Client(db.Model):  # type: ignore[name-defined]
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)  # nullable=True дозволяє NULL
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    appointments = db.relationship("Appointment", backref="client", lazy=True, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Client {self.name}>"


# Модель послуги
class Service(db.Model):  # type: ignore[name-defined]
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    duration = db.Column(db.Integer, nullable=False)  # тривалість у хвилинах
    base_price = db.Column(db.Float, nullable=True)  # базова ціна послуги
    appointment_services = db.relationship("AppointmentService", backref="service", lazy=True)

    def __repr__(self) -> str:
        return f"<Service {self.name}>"


# Модель запису клієнта
class Appointment(db.Model):  # type: ignore[name-defined]
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    master_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="scheduled")  # scheduled, completed, cancelled
    payment_status = db.Column(db.String(20), nullable=False, default="unpaid")  # paid, unpaid, partially_paid
    amount_paid = db.Column(Numeric(10, 2), nullable=True)
    payment_method = db.Column(db.Enum(PaymentMethod), nullable=True)
    discount_percentage = db.Column(db.Numeric(precision=5, scale=2), default=Decimal("0.0"), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    services = db.relationship(
        "AppointmentService",
        backref="appointment",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def get_total_price(self) -> float:
        return sum(service.price for service in self.services)  # type: ignore[attr-defined]

    def get_discounted_price(self) -> Decimal:
        total_price = self.get_total_price()
        discount_percentage = (
            self.discount_percentage
            if isinstance(self.discount_percentage, Decimal)
            else Decimal(str(self.discount_percentage))
        )
        discount_factor = Decimal("1.0") - (discount_percentage / Decimal("100.0"))
        decimal_total_price = total_price if isinstance(total_price, Decimal) else Decimal(str(total_price))
        return decimal_total_price * discount_factor

    def update_payment_status(self) -> None:
        """
        Updates the payment_status based on amount_paid and expected_price.
        """
        if self.status == "cancelled":
            self.payment_status = "not_applicable"
            return

        expected_price = self.get_discounted_price()
        expected_price = max(Decimal("0.00"), expected_price)

        amount_paid_val = self.amount_paid if self.amount_paid is not None else Decimal("0.00")

        if self.amount_paid is None:
            self.payment_status = "unpaid"
        elif expected_price == Decimal("0.00") and amount_paid_val == Decimal("0.00"):
            self.payment_status = "paid"
        elif amount_paid_val <= Decimal("0.00"):
            self.payment_status = "unpaid"
        elif amount_paid_val < expected_price:
            self.payment_status = "partially_paid"
        else:  # amount_paid_val >= expected_price
            self.payment_status = "paid"

    def __repr__(self) -> str:
        return f"<Appointment {self.id} - {self.date} {self.start_time}>"


# Модель послуг, наданих під час запису
class AppointmentService(db.Model):  # type: ignore[name-defined]
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointment.id"), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=False)
    price = db.Column(db.Float, nullable=False)  # фактична ціна, може відрізнятися від стандартної
    notes = db.Column(db.Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AppointmentService {self.id} - Price: {self.price}>"


# Модель бренду
class Brand(db.Model):  # type: ignore[name-defined]
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    # Relationships
    products = db.relationship("Product", backref="brand", lazy=True, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Brand {self.name}>"


# Модель товару
class Product(db.Model):  # type: ignore[name-defined]
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    volume_value = db.Column(db.Float, nullable=True)
    volume_unit = db.Column(db.String(20), nullable=True)  # мл, г, шт тощо
    description = db.Column(db.Text, nullable=True)
    min_stock_level = db.Column(db.Integer, nullable=False, default=1)
    current_sale_price = db.Column(Numeric(10, 2), nullable=True)
    last_cost_price = db.Column(Numeric(10, 2), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Foreign Keys
    brand_id = db.Column(db.Integer, db.ForeignKey("brand.id"), nullable=False)

    # Relationships
    stock_records = db.relationship("StockLevel", backref="product", lazy=True, cascade="all, delete-orphan")
    # Додаємо placeholder relationships для майбутніх моделей
    # goods_receipt_items = db.relationship("GoodsReceiptItem", backref="product", lazy=True)
    # sale_items = db.relationship("SaleItem", backref="product", lazy=True)
    # write_off_items = db.relationship("WriteOffItem", backref="product", lazy=True)
    # inventory_act_items = db.relationship("InventoryActItem", backref="product", lazy=True)

    def __repr__(self) -> str:
        return f"<Product {self.name} ({self.sku})>"

    @staticmethod
    def generate_sku(brand_name: str, product_name: str) -> str:
        """Генерує унікальний SKU для товару"""
        import re
        import random
        import string

        # Очищаємо назви від спеціальних символів та залишаємо тільки букви
        brand_clean = re.sub(r"[^a-zA-Zа-яА-Я]", "", brand_name.upper())
        product_clean = re.sub(r"[^a-zA-Zа-яА-Я]", "", product_name.upper())

        # Беремо перші 3 літери бренду (якщо менше, то всі)
        brand_part = brand_clean[:3] if len(brand_clean) >= 3 else brand_clean
        # Беремо перші 3-5 літер товару (якщо менше, то всі)
        product_part = product_clean[:5] if len(product_clean) >= 5 else product_clean

        # Якщо назви дуже короткі, додаємо випадкові літери
        if len(brand_part) < 2:
            brand_part += "".join(random.choices(string.ascii_uppercase, k=2 - len(brand_part)))
        if len(product_part) < 3:
            product_part += "".join(random.choices(string.ascii_uppercase, k=3 - len(product_part)))

        # Генеруємо базовий SKU
        base_sku = f"{brand_part}{product_part}"

        # Додаємо унікальний номер
        counter = 1
        while True:
            sku = f"{base_sku}{counter:03d}"
            # Перевіряємо унікальність в базі даних
            existing = Product.query.filter_by(sku=sku).first()
            if not existing:
                return sku
            counter += 1
            # Захист від нескінченного циклу
            if counter > 999:
                # Додаємо випадкові символи для унікальності
                random_suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=3))
                sku = f"{base_sku}{random_suffix}"
                existing = Product.query.filter_by(sku=sku).first()
                if not existing:
                    return sku
                # Якщо і це не спрацювало, використовуємо timestamp
                import time

                timestamp_suffix = str(int(time.time()))[-6:]
                return f"{brand_part}{product_part}{timestamp_suffix}"


# Модель рівня запасів
class StockLevel(db.Model):  # type: ignore[name-defined]
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    last_updated = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    # Foreign Keys
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), unique=True, nullable=False)

    def __repr__(self) -> str:
        return f"<StockLevel Product: {self.product_id}, Quantity: {self.quantity}>"


# Event listener для автоматичного створення StockLevel при створенні Product
@event.listens_for(Product, "after_insert")
def create_stock_level(mapper: Any, connection: Connection, target: Product) -> None:
    """Автоматично створює запис StockLevel при створенні нового Product"""
    # Використовуємо connection для вставки запису безпосередньо в базу даних
    # в рамках тієї ж транзакції
    from sqlalchemy import text

    connection.execute(
        text("INSERT INTO stock_level (product_id, quantity) VALUES (:product_id, :quantity)"),
        {"product_id": target.id, "quantity": 0},
    )
