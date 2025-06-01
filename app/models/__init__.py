from datetime import datetime, timezone
from decimal import Decimal
from types import MethodType
from typing import TYPE_CHECKING, Any

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Numeric, event, func, text
from sqlalchemy.engine import Connection

if TYPE_CHECKING:
    from typing import List

db = SQLAlchemy()


# Модель способу оплати (замість enum)
class PaymentMethod(db.Model):  # type: ignore[name-defined]
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    appointments = db.relationship("Appointment", backref="payment_method_ref", lazy=True)
    sales = db.relationship("Sale", backref="payment_method_ref", lazy=True)

    def __repr__(self) -> str:
        return f"<PaymentMethod {self.name}>"


# Клас для забезпечення сумісності з Enum API
class PaymentMethodCompat:
    """
    Клас-адаптер для забезпечення сумісності з кодом, який очікує Enum.
    Створює статичні атрибути, які імітують поведінку Enum.
    """

    @staticmethod
    def _get_method_by_name(name: str):
        """Отримує PaymentMethod за назвою або створює тимчасовий об'єкт з value"""
        # Спробуємо знайти в базі даних
        try:
            method = PaymentMethod.query.filter_by(name=name).first()
            if method:
                # Додаємо атрибут value для сумісності з Enum API
                method.value = method.name

                # Додаємо метод для порівняння
                def eq_method(self, other):
                    if hasattr(other, "value"):
                        return self.value == other.value
                    elif hasattr(other, "name"):
                        return self.name == other.name
                    elif hasattr(other, "id") and hasattr(self, "id"):
                        return self.id == other.id
                    return False

                # Використовуємо types.MethodType для правильного зв'язування методу
                method.__eq__ = MethodType(eq_method, method)
                return method
        except Exception:
            pass

        # Якщо не знайдено, створюємо тимчасовий об'єкт
        class TempPaymentMethod:
            def __init__(self, name: str):
                self.name = name
                self.value = name
                self.id = None

            def __eq__(self, other):
                if hasattr(other, "value"):
                    return self.value == other.value
                elif hasattr(other, "name"):
                    return self.name == other.name
                elif hasattr(other, "id") and hasattr(self, "id"):
                    return self.id == other.id
                return False

        return TempPaymentMethod(name)

    @property
    def CASH(self):
        return self._get_method_by_name("Готівка")

    @property
    def MALIBU(self):
        return self._get_method_by_name("Малібу")

    @property
    def FOP(self):
        return self._get_method_by_name("ФОП")

    @property
    def PRIVAT(self):
        return self._get_method_by_name("Приват")

    @property
    def MONO(self):
        return self._get_method_by_name("MONO")

    @property
    def DEBT(self):
        return self._get_method_by_name("Борг")

    def __iter__(self):
        """Дозволяє ітерацію через методи оплати для сумісності з for pm in PaymentMethod"""
        try:
            methods = PaymentMethod.query.all()
            for method in methods:
                method.value = method.name  # Додаємо атрибут value

                # Додаємо метод для порівняння
                def eq_method(self, other):
                    if hasattr(other, "value"):
                        return self.value == other.value
                    elif hasattr(other, "name"):
                        return self.name == other.name
                    elif hasattr(other, "id") and hasattr(self, "id"):
                        return self.id == other.id
                    return False

                # Використовуємо types.MethodType для правильного зв'язування методу
                method.__eq__ = MethodType(eq_method, method)
                yield method
        except Exception:
            # Якщо база недоступна, повертаємо стандартні методи
            names = ["Готівка", "Малібу", "ФОП", "Приват", "MONO", "Борг"]
            for name in names:
                yield self._get_method_by_name(name)


# Створюємо екземпляр для використання як PaymentMethod
PaymentMethodEnum = PaymentMethodCompat()


# Модель користувача (майстри салону)
class User(UserMixin, db.Model):  # type: ignore[name-defined]
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active_master = db.Column(db.Boolean, nullable=False, default=True)
    schedule_display_order = db.Column(db.Integer, nullable=True, index=True)
    configurable_commission_rate = db.Column(db.Numeric(5, 2), nullable=True, default=Decimal("0.00"))
    appointments = db.relationship("Appointment", backref="master", lazy=True, cascade="all, delete-orphan")
    sales_as_seller = db.relationship("Sale", foreign_keys="Sale.user_id", backref="seller", lazy=True)
    sales_as_creator = db.relationship("Sale", foreign_keys="Sale.created_by_user_id", backref="creator", lazy=True)
    goods_receipts = db.relationship("GoodsReceipt", back_populates="user", lazy=True)

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
    sales = db.relationship("Sale", backref="client", lazy=True)

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
    payment_method_id = db.Column(db.Integer, db.ForeignKey("payment_method.id"), nullable=True)
    discount_percentage = db.Column(db.Numeric(precision=5, scale=2), default=Decimal("0.0"), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    services = db.relationship(
        "AppointmentService",
        backref="appointment",
        lazy=True,
        cascade="all, delete-orphan",
    )
    sales = db.relationship("Sale", back_populates="appointment", lazy=True)

    @property
    def payment_method(self):
        """Повертає об'єкт PaymentMethod з атрибутом value для сумісності з Enum API"""
        if self.payment_method_id:
            method = PaymentMethod.query.get(self.payment_method_id)
            if method:
                method.value = method.name  # Додаємо атрибут value

                # Додаємо метод для порівняння
                def eq_method(self, other):
                    if hasattr(other, "value"):
                        return self.value == other.value
                    elif hasattr(other, "name"):
                        return self.name == other.name
                    elif hasattr(other, "id") and hasattr(self, "id"):
                        return self.id == other.id
                    return False

                # Використовуємо types.MethodType для правильного зв'язування методу
                method.__eq__ = MethodType(eq_method, method)
                return method
        return None

    @payment_method.setter
    def payment_method(self, value: Any) -> None:
        """Встановлює payment_method_id на основі переданого значення"""
        if value is None:
            self.payment_method_id = None
        elif hasattr(value, "id"):
            # Якщо передано об'єкт PaymentMethod
            self.payment_method_id = value.id
        elif hasattr(value, "value"):
            # Якщо передано об'єкт з атрибутом value (наприклад, з Enum)
            method = PaymentMethod.query.filter_by(name=value.value).first()
            if method:
                self.payment_method_id = method.id
            else:
                raise ValueError(f"PaymentMethod з назвою '{value.value}' не знайдено")
        elif hasattr(value, "name"):
            # Якщо передано об'єкт з атрибутом name
            method = PaymentMethod.query.filter_by(name=value.name).first()
            if method:
                self.payment_method_id = method.id
            else:
                raise ValueError(f"PaymentMethod з назвою '{value.name}' не знайдено")
        elif isinstance(value, str):
            # Якщо передано рядок
            method = PaymentMethod.query.filter_by(name=value).first()
            if method:
                self.payment_method_id = method.id
            else:
                raise ValueError(f"PaymentMethod з назвою '{value}' не знайдено")
        elif isinstance(value, int):
            # Якщо передано ID
            self.payment_method_id = value
        else:
            raise ValueError(f"Неприпустимий тип для payment_method: {type(value)}")

    def get_total_price(self) -> float:
        """Повертає загальну вартість всіх послуг та пов'язаних продажів"""
        from app.models import AppointmentService, Sale

        # Сума послуг
        services = AppointmentService.query.filter_by(appointment_id=self.id).all()
        services_total = sum(service.price for service in services)

        # Сума пов'язаних продажів
        sales = Sale.query.filter_by(appointment_id=self.id).all()
        sales_total = sum(float(sale.total_amount) for sale in sales)

        return services_total + sales_total

    def get_discounted_price(self) -> Decimal:
        """Повертає вартість з урахуванням знижки"""
        total = Decimal(str(self.get_total_price()))
        if self.discount_percentage:
            discount_amount = total * (self.discount_percentage / Decimal("100"))
            return total - discount_amount
        return total

    def update_payment_status(self) -> None:
        """Оновлює статус оплати на основі суми оплати"""
        # Якщо запис скасований, статус оплати не застосовується
        if self.status == "cancelled":
            self.payment_status = "not_applicable"
            return

        discounted_price = self.get_discounted_price()

        if self.amount_paid is None:
            # Якщо сума не вказана, то завжди unpaid, навіть якщо ціна 0
            self.payment_status = "unpaid"
        elif self.amount_paid == 0:
            # Якщо ціна також 0, то вважається оплаченим
            if discounted_price == 0:
                self.payment_status = "paid"
            else:
                self.payment_status = "unpaid"
        else:
            if self.amount_paid >= discounted_price:
                self.payment_status = "paid"
            else:
                self.payment_status = "partially_paid"

    def __repr__(self) -> str:
        client_name = self.client.name if self.client else "Unknown"
        master_name = self.master.full_name if self.master else "Unknown"
        return f"<Appointment {self.id} - {client_name} with {master_name}>"


# Модель послуги в записі
class AppointmentService(db.Model):  # type: ignore[name-defined]
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointment.id"), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=False)
    price = db.Column(db.Float, nullable=False)  # фактична ціна, може відрізнятися від стандартної
    notes = db.Column(db.Text, nullable=True)

    def __repr__(self) -> str:
        return f"<AppointmentService {self.service.name if self.service else 'Unknown'} - {self.price}>"


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
    min_stock_level = db.Column(db.Integer, nullable=True, default=None)
    current_sale_price = db.Column(Numeric(10, 2), nullable=True)
    last_cost_price = db.Column(Numeric(10, 2), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Foreign Keys
    brand_id = db.Column(db.Integer, db.ForeignKey("brand.id"), nullable=False)

    # Relationships
    stock_records = db.relationship("StockLevel", backref="product", lazy=True, cascade="all, delete-orphan")
    goods_receipt_items = db.relationship("GoodsReceiptItem", back_populates="product", lazy=True)
    sale_items = db.relationship("SaleItem", backref="product", lazy=True)

    def __repr__(self) -> str:
        return f"<Product {self.name} ({self.sku})>"

    @staticmethod
    def generate_sku(brand_name: str, product_name: str) -> str:
        """
        Генерує SKU на основі назви бренду та товару.
        Формат: BRANDPRODUCT001, BRANDPRODUCT002, etc.
        """
        import re

        # Очищаємо та форматуємо назви
        def clean_name(name: str) -> str:
            # Видаляємо спеціальні символи та пробіли, залишаємо тільки букви та цифри
            cleaned = re.sub(r"[^\w]", "", name)
            return cleaned.upper()

        # Обрізаємо назви та забезпечуємо мінімальну довжину
        brand_code = clean_name(brand_name)[:3].ljust(3, "X")  # Мінімум 3 символи
        product_code = clean_name(product_name)[:3].ljust(3, "Y")  # Мінімум 3 символи

        # Базовий SKU (мінімум 6 символів)
        base_sku = f"{brand_code}{product_code}"

        # Перевіряємо унікальність, починаючи з 001
        counter = 1
        sku = f"{base_sku}{counter:03d}"
        while Product.query.filter_by(sku=sku).first():
            counter += 1
            sku = f"{base_sku}{counter:03d}"

        return sku


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


# Модель надходження товарів
class GoodsReceipt(db.Model):  # type: ignore[name-defined]
    id = db.Column(db.Integer, primary_key=True)
    receipt_number = db.Column(db.String(50), nullable=True)
    receipt_date = db.Column(db.Date, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # хто створив
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    items = db.relationship("GoodsReceiptItem", back_populates="receipt", lazy=True, cascade="all, delete-orphan")
    user = db.relationship("User", back_populates="goods_receipts", lazy=True)

    def __repr__(self) -> str:
        return f"<GoodsReceipt {self.receipt_number or self.id}>"


# Модель позиції надходження товарів
class GoodsReceiptItem(db.Model):  # type: ignore[name-defined]
    id = db.Column(db.Integer, primary_key=True)
    receipt_id = db.Column(db.Integer, db.ForeignKey("goods_receipt.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity_received = db.Column(db.Integer, nullable=False)
    quantity_remaining = db.Column(db.Integer, nullable=False)  # залишок з цієї партії
    cost_price_per_unit = db.Column(Numeric(10, 2), nullable=False)
    receipt_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expiry_date = db.Column(db.Date, nullable=True)
    batch_number = db.Column(db.String(50), nullable=True)
    supplier_info = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    receipt = db.relationship("GoodsReceipt", back_populates="items", lazy=True)
    product = db.relationship("Product", back_populates="goods_receipt_items", lazy=True)

    def __repr__(self) -> str:
        return (
            f"<GoodsReceiptItem Product: {self.product_id}, "
            f"Received: {self.quantity_received}, Remaining: {self.quantity_remaining}>"
        )

    @property
    def total_cost(self) -> Decimal:
        """Повертає загальну вартість позиції"""
        return Decimal(str(self.quantity_received)) * self.cost_price_per_unit


# Модель продажу
class Sale(db.Model):  # type: ignore[name-defined]
    id = db.Column(db.Integer, primary_key=True)
    sale_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # продавець
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointment.id"), nullable=True)
    total_amount = db.Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    payment_method_id = db.Column(db.Integer, db.ForeignKey("payment_method.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # хто створив запис
    notes = db.Column(db.Text, nullable=True)

    # Relationships
    items = db.relationship("SaleItem", backref="sale", lazy=True, cascade="all, delete-orphan")
    appointment = db.relationship("Appointment", back_populates="sales", lazy=True)

    def __repr__(self) -> str:
        return f"<Sale {self.id} - {self.sale_date} - Total: {self.total_amount}>"


# Модель позиції продажу
class SaleItem(db.Model):  # type: ignore[name-defined]
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sale.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_per_unit = db.Column(Numeric(10, 2), nullable=False)  # ціна продажу
    cost_price_per_unit = db.Column(Numeric(10, 2), nullable=False)  # собівартість (FIFO)

    def __repr__(self) -> str:
        return f"<SaleItem Sale: {self.sale_id}, Product: {self.product_id}, Qty: {self.quantity}>"

    @property
    def total_price(self) -> Decimal:
        """Повертає загальну вартість позиції"""
        return Decimal(str(self.quantity)) * self.price_per_unit

    @property
    def total_cost(self) -> Decimal:
        """Повертає загальну собівартість позиції"""
        return Decimal(str(self.quantity)) * self.cost_price_per_unit

    @property
    def profit(self) -> Decimal:
        """Повертає прибуток з позиції"""
        return self.total_price - self.total_cost


# Модель причини списання
class WriteOffReason(db.Model):  # type: ignore[name-defined]
    __tablename__ = "write_off_reason"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    write_offs = db.relationship("ProductWriteOff", backref="reason", lazy=True)

    def __repr__(self) -> str:
        return f"<WriteOffReason {self.name}>"


# Модель документа списання товарів
class ProductWriteOff(db.Model):  # type: ignore[name-defined]
    __tablename__ = "product_write_off"

    id = db.Column(db.Integer, primary_key=True)
    write_off_date = db.Column(db.Date, nullable=False, default=lambda: datetime.now(timezone.utc).date())
    reason_id = db.Column(db.Integer, db.ForeignKey("write_off_reason.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)  # хто списав
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    items = db.relationship("ProductWriteOffItem", backref="product_write_off", lazy=True, cascade="all, delete-orphan")
    user = db.relationship("User", backref="write_offs", lazy=True)

    def __repr__(self) -> str:
        return f"<ProductWriteOff {self.id} - {self.write_off_date}>"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProductWriteOff):
            return False
        return self.id == other.id

    @property
    def total_cost(self) -> Decimal:
        """Повертає загальну собівартість списаних товарів"""
        from app.models import ProductWriteOffItem

        items = ProductWriteOffItem.query.filter_by(product_write_off_id=self.id).all()
        return sum((item.total_cost for item in items), Decimal("0.00"))


# Модель позиції списання товарів
class ProductWriteOffItem(db.Model):  # type: ignore[name-defined]
    __tablename__ = "product_write_off_item"

    id = db.Column(db.Integer, primary_key=True)
    product_write_off_id = db.Column(db.Integer, db.ForeignKey("product_write_off.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    cost_price_per_unit = db.Column(Numeric(10, 2), nullable=False)  # собівартість списаної одиниці (FIFO)

    # Relationships
    product = db.relationship("Product", backref="write_off_items", lazy=True)

    def __repr__(self) -> str:
        return f"<ProductWriteOffItem {self.product.name if self.product else 'Unknown'}: {self.quantity}>"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProductWriteOffItem):
            return False
        return self.id == other.id

    @property
    def total_cost(self) -> Decimal:
        """Повертає загальну собівартість позиції"""
        return Decimal(str(self.quantity)) * self.cost_price_per_unit


# Event listener для автоматичного створення StockLevel при створенні Product
@event.listens_for(Product, "after_insert")
def create_stock_level(mapper: Any, connection: Connection, target: Product) -> None:
    """
    Автоматично створити StockLevel для нового товару.
    """
    stmt = text("INSERT INTO stock_level (product_id, quantity, last_updated) VALUES (:product_id, 0, :now)")
    connection.execute(stmt, {"product_id": target.id, "now": datetime.now(timezone.utc)})


# Модель акту інвентаризації
class InventoryAct(db.Model):  # type: ignore[name-defined]
    __tablename__ = "inventory_act"

    id = db.Column(db.Integer, primary_key=True)
    act_date = db.Column(db.Date, nullable=False, default=lambda: datetime.now(timezone.utc).date())
    status = db.Column(db.String(20), nullable=False, default="new")  # new, in_progress, completed
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # Relationships
    items = db.relationship("InventoryActItem", backref="inventory_act", lazy=True, cascade="all, delete-orphan")
    user = db.relationship("User", backref="inventory_acts", lazy=True)

    def __repr__(self) -> str:
        return f"<InventoryAct {self.id} - {self.act_date} - {self.status}>"

    @property
    def total_discrepancy(self) -> int:
        """Загальна розбіжність по акту"""
        return sum((item.discrepancy or 0) for item in self.items)  # type: ignore[attr-defined]

    @property
    def items_with_discrepancy(self) -> int:
        """Кількість позицій з розбіжностями"""
        items_with_diff = [
            item for item in self.items if item.discrepancy and item.discrepancy != 0  # type: ignore[attr-defined]
        ]
        return len(items_with_diff)


# Модель позиції в акті інвентаризації
class InventoryActItem(db.Model):  # type: ignore[name-defined]
    __tablename__ = "inventory_act_item"

    id = db.Column(db.Integer, primary_key=True)
    inventory_act_id = db.Column(db.Integer, db.ForeignKey("inventory_act.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    expected_quantity = db.Column(db.Integer, nullable=False)  # планова кількість з StockLevel
    actual_quantity = db.Column(db.Integer, nullable=True)  # фактична кількість
    discrepancy = db.Column(db.Integer, nullable=True)  # розбіжність (actual - expected)

    # Relationships
    product = db.relationship("Product", backref="inventory_act_items", lazy=True)

    def __repr__(self) -> str:
        return (
            f"<InventoryActItem {self.id} - Product {self.product_id} - "
            f"Expected: {self.expected_quantity}, Actual: {self.actual_quantity}>"
        )

    def calculate_discrepancy(self) -> None:
        """Розрахувати розбіжність"""
        if self.actual_quantity is not None:
            self.discrepancy = self.actual_quantity - self.expected_quantity
        else:
            self.discrepancy = None


def setup_foreign_key_constraints(app):
    """Налаштовує foreign key constraints для SQLite"""

    @event.listens_for(db.engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Увімкнення foreign key constraints для SQLite"""
        if "sqlite" in str(dbapi_connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
