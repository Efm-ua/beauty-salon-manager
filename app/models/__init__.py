from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


# Модель користувача (майстри салону)
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    appointments = db.relationship("Appointment", backref="master", lazy=True)

    def __repr__(self):
        return f"<User {self.username}>"


# Модель клієнта
class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    appointments = db.relationship("Appointment", backref="client", lazy=True)

    def __repr__(self):
        return f"<Client {self.name}>"


# Модель послуги
class Service(db.Model):
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
class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("client.id"), nullable=False)
    master_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    status = db.Column(
        db.String(20), nullable=False, default="scheduled"
    )  # scheduled, completed, cancelled
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    services = db.relationship(
        "AppointmentService",
        backref="appointment",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def get_total_price(self):
        return sum(service.price for service in self.services)

    def __repr__(self):
        return f"<Appointment {self.id} - {self.date} {self.start_time}>"


# Модель послуг, наданих під час запису
class AppointmentService(db.Model):
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
