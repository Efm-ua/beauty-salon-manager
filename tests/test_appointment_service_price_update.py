"""
Тест для перевірки актуалізації цін послуг в view маршруті
з використанням session.expire підходу
"""

import pytest
from datetime import date, time, datetime, timedelta
from decimal import Decimal

from app.models import Appointment, AppointmentService, Client, Service, User, db


def test_appointment_view_alternative_expire_approach(app, session):
    """
    Тест альтернативного підходу з db.session.expire(appointment, ['services'])
    """
    with app.app_context():
        # Створюємо тестові дані
        master = User(
            username="test_master_expire",
            password="password_hash",
            full_name="Test Master Expire",
            is_admin=False,
            is_active_master=True,
        )
        session.add(master)

        client = Client(name="Test Client Expire", phone="+380123456788", email="test_expire@example.com")
        session.add(client)

        service = Service(
            name="Test Service Expire", description="Test service description", duration=60, base_price=120.0
        )
        session.add(service)
        session.flush()

        # Створюємо запис
        tomorrow = date.today() + timedelta(days=1)
        appointment = Appointment(
            client_id=client.id,
            master_id=master.id,
            date=tomorrow,
            start_time=time(14, 0),
            end_time=time(15, 0),
            status="scheduled",
            notes="Test appointment for expire",
        )
        session.add(appointment)
        session.flush()

        # Додаємо послугу до запису з початковою ціною
        appointment_service = AppointmentService(
            appointment_id=appointment.id, service_id=service.id, price=120.0, notes="Initial price for expire test"
        )
        session.add(appointment_service)
        session.commit()

        # Імітуємо доступ до appointment.services для кешування
        initial_services = list(appointment.services)
        assert len(initial_services) == 1
        assert initial_services[0].price == 120.0

        # Змінюємо ціну послуги в записі
        appointment_service.price = 180.0
        session.commit()

        # Тепер застосовуємо альтернативний підхід - expire
        session.expire(appointment, ["services"])

        # Після цього доступ до appointment.services повинен завантажити свіжі дані
        fresh_services = list(appointment.services)
        assert len(fresh_services) == 1
        assert fresh_services[0].price == 180.0

        # Перевіряємо, що get_total_price тепер показує правильну суму
        assert appointment.get_total_price() == 180.0

        print("✅ Тест пройдено: session.expire альтернативний підхід працює")


def test_get_total_price_always_fresh_data(app, session):
    """
    Тест перевіряє, що get_total_price завжди повертає актуальні дані з БД
    """
    with app.app_context():
        # Створюємо тестові дані
        master = User(
            username="fresh_data_master",
            password="password_hash",
            full_name="Fresh Data Master",
            is_admin=False,
            is_active_master=True,
        )
        session.add(master)

        client = Client(name="Fresh Data Client", phone="+380123456786", email="fresh_data@example.com")
        session.add(client)

        service = Service(
            name="Fresh Data Service", description="Test service for fresh data", duration=60, base_price=100.0
        )
        session.add(service)
        session.flush()

        # Створюємо запис
        tomorrow = date.today() + timedelta(days=1)
        appointment = Appointment(
            client_id=client.id,
            master_id=master.id,
            date=tomorrow,
            start_time=time(10, 0),
            end_time=time(11, 0),
            status="scheduled",
            notes="Fresh data test",
        )
        session.add(appointment)
        session.flush()

        # Додаємо послугу до запису
        appointment_service = AppointmentService(
            appointment_id=appointment.id, service_id=service.id, price=100.0, notes="Initial price"
        )
        session.add(appointment_service)
        session.commit()

        # Перевіряємо початкову ціну
        assert appointment.get_total_price() == 100.0

        # Змінюємо ціну безпосередньо в БД (імітуючи зміну в іншій сесії)
        appointment_service.price = 150.0
        session.commit()

        # get_total_price повинен повертати актуальну ціну з БД
        # незалежно від кешованих даних в appointment.services
        assert appointment.get_total_price() == 150.0

        print("✅ Тест пройдено: get_total_price завжди повертає свіжі дані")
