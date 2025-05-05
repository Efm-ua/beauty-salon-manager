import enum
from datetime import datetime, timezone
from decimal import Decimal

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Numeric

db = SQLAlchemy()


# Enum для типів оплати
class PaymentMethod(enum.Enum):
    CASH = "Готівка"
    MALIBU = "Малібу"
    FOP = "ФОП"
    PRIVAT = "Приват"
    MONO = "MONO"
    DEBT = "Борг"


# Модель користувача (майстри салону)
class User(UserMixin, db.Model):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    appointments = db.relationship(
        "Appointment", backref="master", lazy=True, cascade="all, delete-orphan"
    )

    def is_administrator(self):
        return self.is_admin

    def __repr__(self):
        return f"<User {self.username}>"


# Модель клієнта
class Client(db.Model):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(
        db.String(120), unique=True, nullable=True
    )  # nullable=True дозволяє NULL
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    appointments = db.relationship(
        "Appointment", backref="client", lazy=True, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Client {self.name}>"


# Модель послуги
class Service(db.Model):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    duration = db.Column(db.Integer, nullable=False)  # тривалість у хвилинах
    appointment_services = db.relationship(
        "AppointmentService", backref="service", lazy=True
    )

    def __repr__(self):
        return f"<Service {self.name}>"


# Модель запису клієнта
class Appointment(db.Model):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    master_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    status = db.Column(
        db.String(20), nullable=False, default="scheduled"
    )  # scheduled, completed, cancelled
    payment_status = db.Column(
        db.String(10), nullable=False, default="unpaid"
    )  # paid, unpaid
    amount_paid = db.Column(Numeric(10, 2), nullable=True)
    payment_method = db.Column(db.Enum(PaymentMethod), nullable=True)
    discount_percentage = db.Column(
        db.Numeric(precision=5, scale=2), default=Decimal("0.0"), nullable=False
    )
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    services = db.relationship(
        "AppointmentService",
        backref="appointment",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def get_total_price(self):
        return sum(service.price for service in self.services)

    def get_discounted_price(self):
        total_price = self.get_total_price()
        discount_factor = 1 - (self.discount_percentage / 100)
        return total_price * discount_factor

    def __repr__(self):
        return f"<Appointment {self.id} - {self.date} {self.start_time}>"


# Модель послуг, наданих під час запису
class AppointmentService(db.Model):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(
        db.Integer, db.ForeignKey("appointment.id"), nullable=False
    )
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=False)
    price = db.Column(
        db.Float, nullable=False
    )  # фактична ціна, може відрізнятися від стандартної
    notes = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<AppointmentService {self.id} - Price: {self.price}>"
