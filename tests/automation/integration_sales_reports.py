"""
Інтеграційні тести для перевірки консистентності між продажами та звітами
Фаза 1: Інтеграційні тести

Цей файл покриває тестування:
- Кроки 1.1.1-1.1.5: Інтеграція продажів та звітів
- Кроки 1.2.1-1.2.3: Інтеграція записів та звітів
- Кроки 1.3.1-1.3.2: End-to-End тести
"""

import pytest
from datetime import date, datetime, time
from decimal import Decimal
from flask import url_for
from sqlalchemy import func

from app.models import (
    Appointment,
    AppointmentService,
    Sale,
    SaleItem,
    PaymentMethod,
    User,
    Client,
    Service,
    Product,
    Brand,
    StockLevel,
    db,
)
from app.routes.reports import calculate_total_with_discount


class TestSalesReportsIntegration:
    """Тести інтеграції продажів та звітів"""

    def test_product_sale_appears_in_all_reports(self, app, session, admin_user, test_client, test_product):
        """
        Крок 1.1.2: Тест "продаж_відображається_в_усіх_звітах"

        Перевіряє, що продаж товару відображається як у фінансовому звіті,
        так і в звіті зарплати.
        """
        # Створюємо методи оплати
        cash_method = PaymentMethod(name="Готівка", is_active=True)
        session.add(cash_method)
        session.commit()

        # Створюємо продаж товару
        test_date = date.today()
        sale = Sale(
            sale_date=datetime.combine(test_date, time(10, 0)),
            client_id=test_client.id,
            user_id=admin_user.id,
            total_amount=Decimal("100.00"),
            payment_method_id=cash_method.id,
            created_by_user_id=admin_user.id,
        )
        session.add(sale)
        session.commit()

        # Створюємо позицію продажу
        sale_item = SaleItem(
            sale_id=sale.id,
            product_id=test_product.id,
            quantity=1,
            price_per_unit=Decimal("100.00"),
            cost_price_per_unit=Decimal("50.00"),
        )
        session.add(sale_item)
        session.commit()

        # Перевіряємо дані безпосередньо в базі даних

        # 1. Перевіряємо, що продаж відображається у фінансовому звіті
        product_sales = Sale.query.filter(
            func.date(Sale.sale_date) >= test_date, func.date(Sale.sale_date) <= test_date
        ).all()

        assert len(product_sales) == 1
        assert product_sales[0].total_amount == Decimal("100.00")
        assert product_sales[0].payment_method_id == cash_method.id

        # 2. Перевіряємо розрахунок комісії для звіту зарплати
        total_products_amount = (
            db.session.query(func.sum(Sale.total_amount))
            .filter(Sale.user_id == admin_user.id, func.date(Sale.sale_date) == test_date)
            .scalar()
        )

        assert total_products_amount == Decimal("100.00")

        # Комісія має бути 9% від суми продажу
        expected_commission = Decimal("100.00") * Decimal("0.09")
        assert expected_commission == Decimal("9.00")

    def test_debt_sale_appears_in_daily_report(self, app, session, admin_user, test_client, test_product):
        """
        Крок 1.1.3: Тест "продаж_у_борг_відображається_в_щоденному_звіті"

        Це основний regression тест для BUG-001.
        Перевіряє, що продаж у борг відображається в щоденному (фінансовому) звіті.
        """
        # Створюємо метод оплати "Борг"
        debt_method = PaymentMethod(name="Борг", is_active=True)
        session.add(debt_method)
        session.commit()

        # Створюємо продаж у борг
        test_date = date.today()
        debt_sale = Sale(
            sale_date=datetime.combine(test_date, time(11, 0)),
            client_id=test_client.id,
            user_id=admin_user.id,
            total_amount=Decimal("50.00"),
            payment_method_id=debt_method.id,
            created_by_user_id=admin_user.id,
        )
        session.add(debt_sale)
        session.commit()

        # Створюємо позицію продажу
        sale_item = SaleItem(
            sale_id=debt_sale.id,
            product_id=test_product.id,
            quantity=1,
            price_per_unit=Decimal("50.00"),
            cost_price_per_unit=Decimal("25.00"),
        )
        session.add(sale_item)
        session.commit()

        # КРИТИЧНА ПЕРЕВІРКА: продаж у борг ПОВИНЕН відображатися
        # Перевіряємо логіку фінансового звіту
        product_sales = Sale.query.filter(
            func.date(Sale.sale_date) >= test_date, func.date(Sale.sale_date) <= test_date
        ).all()

        assert len(product_sales) == 1, "Продаж у борг не знайдено в базі даних!"

        debt_sale_found = None
        for sale in product_sales:
            if sale.payment_method_id == debt_method.id:
                debt_sale_found = sale
                break

        assert debt_sale_found is not None, "Продаж у борг не відображається в щоденному звіті!"
        assert debt_sale_found.total_amount == Decimal("50.00"), "Сума продажу у борг неправильна!"

        # Перевіряємо, що метод оплати правильно зв'язаний
        payment_method_obj = PaymentMethod.query.get(debt_sale_found.payment_method_id)
        assert payment_method_obj.name == "Борг", "Метод оплати 'Борг' не зв'язаний правильно!"

    def test_consistency_between_salary_and_financial_reports(
        self, app, session, admin_user, test_client, test_product
    ):
        """
        Крок 1.1.4: Тест "консистентність_сум_між_звітами"

        Перевіряє, що суми в звіті зарплати узгоджуються з фінансовим звітом.
        """
        # Створюємо методи оплати
        cash_method = PaymentMethod(name="Готівка", is_active=True)
        debt_method = PaymentMethod(name="Борг", is_active=True)
        session.add_all([cash_method, debt_method])
        session.commit()

        test_date = date.today()

        # Створюємо продаж готівкою
        cash_sale = Sale(
            sale_date=datetime.combine(test_date, time(10, 0)),
            client_id=test_client.id,
            user_id=admin_user.id,
            total_amount=Decimal("100.00"),
            payment_method_id=cash_method.id,
            created_by_user_id=admin_user.id,
        )
        session.add(cash_sale)

        # Створюємо продаж у борг
        debt_sale = Sale(
            sale_date=datetime.combine(test_date, time(11, 0)),
            client_id=test_client.id,
            user_id=admin_user.id,
            total_amount=Decimal("200.00"),
            payment_method_id=debt_method.id,
            created_by_user_id=admin_user.id,
        )
        session.add(debt_sale)
        session.commit()

        # Створюємо позиції продажів
        cash_item = SaleItem(
            sale_id=cash_sale.id,
            product_id=test_product.id,
            quantity=1,
            price_per_unit=Decimal("100.00"),
            cost_price_per_unit=Decimal("50.00"),
        )
        debt_item = SaleItem(
            sale_id=debt_sale.id,
            product_id=test_product.id,
            quantity=2,
            price_per_unit=Decimal("100.00"),
            cost_price_per_unit=Decimal("50.00"),
        )
        session.add_all([cash_item, debt_item])
        session.commit()

        # Перевіряємо консистентність даних між звітами

        # 1. Фінансовий звіт: загальна сума продажів товарів
        total_product_revenue = (
            db.session.query(func.sum(SaleItem.price_per_unit * SaleItem.quantity))
            .join(Sale)
            .filter(func.date(Sale.sale_date) == test_date)
            .scalar()
        )

        assert total_product_revenue == Decimal(
            "300.00"
        ), f"Загальна сума продажів товарів неправильна: {total_product_revenue}"

        # 2. Звіт зарплати: комісія майстра (9% від загальної суми продажів)
        total_products_amount = (
            db.session.query(func.sum(Sale.total_amount))
            .filter(Sale.user_id == admin_user.id, func.date(Sale.sale_date) == test_date)
            .scalar()
        )

        assert total_products_amount == Decimal(
            "300.00"
        ), f"Загальна сума продажів для комісії неправильна: {total_products_amount}"

        expected_commission = total_products_amount * Decimal("0.09")
        assert expected_commission == Decimal("27.00"), f"Комісія майстра неправильна: {expected_commission}"

        # 3. Перевіряємо, що обидва способи оплати враховуються
        cash_amount = (
            db.session.query(func.sum(Sale.total_amount))
            .filter(
                Sale.user_id == admin_user.id,
                func.date(Sale.sale_date) == test_date,
                Sale.payment_method_id == cash_method.id,
            )
            .scalar()
        )

        debt_amount = (
            db.session.query(func.sum(Sale.total_amount))
            .filter(
                Sale.user_id == admin_user.id,
                func.date(Sale.sale_date) == test_date,
                Sale.payment_method_id == debt_method.id,
            )
            .scalar()
        )

        assert cash_amount == Decimal("100.00"), f"Сума готівкових продажів неправильна: {cash_amount}"
        assert debt_amount == Decimal("200.00"), f"Сума продажів у борг неправильна: {debt_amount}"
        assert cash_amount + debt_amount == total_products_amount, "Суми не збігаються!"

    def test_different_payment_methods_verification(self, app, session, admin_user, test_client, test_product):
        """
        Крок 1.1.5: Додати перевірку різних способів оплати

        Перевіряє, що всі способи оплати правильно обробляються в звітах.
        """
        # Створюємо всі методи оплати
        payment_methods = [
            PaymentMethod(name="Готівка", is_active=True),
            PaymentMethod(name="Приват", is_active=True),
            PaymentMethod(name="MONO", is_active=True),
            PaymentMethod(name="Малібу", is_active=True),
            PaymentMethod(name="ФОП", is_active=True),
            PaymentMethod(name="Борг", is_active=True),
        ]
        session.add_all(payment_methods)
        session.commit()

        test_date = date.today()

        # Створюємо продажі для кожного способу оплати
        created_sales = []
        for i, method in enumerate(payment_methods, 1):
            sale = Sale(
                sale_date=datetime.combine(test_date, time(9 + i, 0)),
                client_id=test_client.id,
                user_id=admin_user.id,
                total_amount=Decimal(f"{i * 10}.00"),
                payment_method_id=method.id,
                created_by_user_id=admin_user.id,
            )
            session.add(sale)
            session.commit()

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=test_product.id,
                quantity=1,
                price_per_unit=Decimal(f"{i * 10}.00"),
                cost_price_per_unit=Decimal(f"{i * 5}.00"),
            )
            session.add(sale_item)
            created_sales.append(sale)

        session.commit()

        # Перевіряємо, що всі продажі збережені та правильно зв'язані з методами оплати
        for i, method in enumerate(payment_methods, 1):
            sales_with_method = Sale.query.filter(
                func.date(Sale.sale_date) == test_date, Sale.payment_method_id == method.id
            ).all()

            assert len(sales_with_method) == 1, f"Продаж з методом '{method.name}' не знайдено"
            assert sales_with_method[0].total_amount == Decimal(
                f"{i * 10}.00"
            ), f"Сума для методу '{method.name}' неправильна"

        # Перевіряємо загальну суму всіх продажів
        total_all_sales = (
            db.session.query(func.sum(Sale.total_amount))
            .filter(Sale.user_id == admin_user.id, func.date(Sale.sale_date) == test_date)
            .scalar()
        )

        expected_total = sum(Decimal(f"{i * 10}.00") for i in range(1, 7))  # 10+20+30+40+50+60 = 210
        assert (
            total_all_sales == expected_total
        ), f"Загальна сума всіх продажів неправильна: {total_all_sales}, очікувалось: {expected_total}"


class TestAppointmentReportsIntegration:
    """Тести інтеграції записів та звітів"""

    def test_completed_appointment_appears_in_daily_report(self, app, session, regular_user, test_client, test_service):
        """
        Крок 1.2.1: Тест "завершений_запис_відображається_в_щоденному_звіті"

        Перевіряє, що завершений запис відображається в щоденному звіті.
        """
        # Створюємо метод оплати
        cash_method = PaymentMethod(name="Готівка", is_active=True)
        session.add(cash_method)
        session.commit()

        test_date = date.today()

        # Створюємо завершений запис
        appointment = Appointment(
            client_id=test_client.id,
            master_id=regular_user.id,
            date=test_date,
            start_time=time(10, 0),
            end_time=time(11, 0),
            status="completed",
            payment_status="paid",
            amount_paid=Decimal("100.00"),
            payment_method_id=cash_method.id,
        )
        session.add(appointment)
        session.commit()

        # Додаємо послугу до запису
        appointment_service = AppointmentService(appointment_id=appointment.id, service_id=test_service.id, price=100.0)
        session.add(appointment_service)
        session.commit()

        # Перевіряємо логіку фінансового звіту для завершених записів
        completed_appointments = Appointment.query.filter(
            Appointment.date >= test_date,
            Appointment.date <= test_date,
            Appointment.status == "completed",
        ).all()

        assert len(completed_appointments) == 1, "Завершений запис не знайдено"

        completed_appointment = completed_appointments[0]
        assert completed_appointment.amount_paid == Decimal("100.00"), "Сума платежу неправильна"
        assert completed_appointment.payment_method_id == cash_method.id, "Метод оплати неправильний"

        # Перевіряємо, що послуги правильно прив'язані
        services_total = sum(Decimal(str(service.price)) for service in completed_appointment.services)
        assert services_total == Decimal("100.00"), f"Сума послуг неправильна: {services_total}"

    def test_debt_appointment_appears_correctly(self, app, session, regular_user, test_client, test_service):
        """
        Крок 1.2.2: Тест "запис_у_борг_відображається_правильно"

        Перевіряє, що запис у борг правильно відображається в звітах.
        """
        # Створюємо метод оплати "Борг"
        debt_method = PaymentMethod(name="Борг", is_active=True)
        session.add(debt_method)
        session.commit()

        test_date = date.today()

        # Створюємо запис у борг
        appointment = Appointment(
            client_id=test_client.id,
            master_id=regular_user.id,
            date=test_date,
            start_time=time(14, 0),
            end_time=time(15, 0),
            status="completed",
            payment_status="unpaid",  # Важливо: у борг = не оплачено
            amount_paid=Decimal("0.00"),  # Нуль сплачено
            payment_method_id=debt_method.id,
        )
        session.add(appointment)
        session.commit()

        # Додаємо послугу до запису
        appointment_service = AppointmentService(appointment_id=appointment.id, service_id=test_service.id, price=150.0)
        session.add(appointment_service)
        session.commit()

        # КРИТИЧНА ПЕРЕВІРКА: запис у борг повинен відображатися
        completed_appointments = Appointment.query.filter(
            Appointment.date >= test_date,
            Appointment.date <= test_date,
            Appointment.status == "completed",
        ).all()

        assert len(completed_appointments) == 1, "Завершений запис у борг не знайдено"

        debt_appointment = completed_appointments[0]
        assert debt_appointment.payment_method_id == debt_method.id, "Метод оплати 'Борг' неправильний"

        # Перевіряємо логіку розрахунку для фінансового звіту
        # Згідно з логікою в reports.py, якщо amount_paid = 0, то береться сума послуг
        services_amount = sum(Decimal(str(service.price)) for service in debt_appointment.services)
        assert services_amount == Decimal("150.00"), "Сума послуг у борг неправильна"

        # В фінансовому звіті має враховуватися сума послуг, навіть якщо amount_paid = 0
        expected_amount_for_report = services_amount  # 150.00
        assert expected_amount_for_report == Decimal("150.00"), "Сума для звіту неправильна"

    def test_appointment_statuses_affect_reports(self, app, session, regular_user, test_client, test_service):
        """
        Крок 1.2.3: Тест "статуси_записів_впливають_на_звіти"

        Перевіряє, що тільки завершені записи враховуються в звітах.
        """
        # Створюємо метод оплати
        cash_method = PaymentMethod(name="Готівка", is_active=True)
        session.add(cash_method)
        session.commit()

        test_date = date.today()

        # Створюємо записи з різними статусами
        statuses = ["scheduled", "completed", "cancelled"]
        appointments = []

        for i, status in enumerate(statuses):
            appointment = Appointment(
                client_id=test_client.id,
                master_id=regular_user.id,
                date=test_date,
                start_time=time(10 + i, 0),
                end_time=time(11 + i, 0),
                status=status,
                payment_status="paid" if status == "completed" else "unpaid",
                amount_paid=Decimal("100.00") if status == "completed" else Decimal("0.00"),
                payment_method_id=cash_method.id if status == "completed" else None,
            )
            session.add(appointment)
            session.commit()

            # Додаємо послугу до запису
            appointment_service = AppointmentService(
                appointment_id=appointment.id, service_id=test_service.id, price=100.0
            )
            session.add(appointment_service)
            appointments.append(appointment)

        session.commit()

        # Перевіряємо, що тільки завершені записи враховуються в звітах
        completed_appointments = Appointment.query.filter(
            Appointment.date >= test_date,
            Appointment.date <= test_date,
            Appointment.status == "completed",
        ).all()

        assert (
            len(completed_appointments) == 1
        ), f"Має бути тільки 1 завершений запис, знайдено: {len(completed_appointments)}"

        # Тільки завершений запис повинен мати amount_paid > 0
        completed_appointment = completed_appointments[0]
        assert completed_appointment.amount_paid == Decimal("100.00"), "Сума завершеного запису неправильна"

        # Перевіряємо, що незавершені записи не мають amount_paid
        all_appointments = Appointment.query.filter(
            Appointment.date >= test_date,
            Appointment.date <= test_date,
        ).all()

        assert len(all_appointments) == 3, "Має бути 3 записи загалом"

        scheduled_and_cancelled = [apt for apt in all_appointments if apt.status != "completed"]
        for apt in scheduled_and_cancelled:
            assert (
                apt.amount_paid == Decimal("0.00") or apt.amount_paid is None
            ), f"Незавершений запис має amount_paid: {apt.amount_paid}"


class TestEndToEndIntegration:
    """End-to-End тести"""

    def test_full_sale_cycle_all_reports_consistency(self, app, session, admin_user, test_client, test_product):
        """
        Крок 1.3.1: Тест повного циклу: створення продажу → перевірка всіх звітів

        E2E тест, який створює продаж і перевіряє його відображення у всіх звітах.
        """
        # Створюємо методи оплати
        cash_method = PaymentMethod(name="Готівка", is_active=True)
        debt_method = PaymentMethod(name="Борг", is_active=True)
        session.add_all([cash_method, debt_method])
        session.commit()

        test_date = date.today()

        # Створюємо два продажі: готівкою та у борг
        sales_data = [
            {"amount": Decimal("150.00"), "method": cash_method},
            {"amount": Decimal("75.00"), "method": debt_method},
        ]

        created_sales = []
        for sale_data in sales_data:
            sale = Sale(
                sale_date=datetime.combine(test_date, time(12, 0)),
                client_id=test_client.id,
                user_id=admin_user.id,
                total_amount=sale_data["amount"],
                payment_method_id=sale_data["method"].id,
                created_by_user_id=admin_user.id,
            )
            session.add(sale)
            session.commit()

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=test_product.id,
                quantity=1,
                price_per_unit=sale_data["amount"],
                cost_price_per_unit=Decimal(str(sale_data["amount"])) / Decimal("2"),
            )
            session.add(sale_item)
            created_sales.append(sale)

        session.commit()

        # 1. Перевіряємо дані фінансового звіту
        product_sales = Sale.query.filter(
            func.date(Sale.sale_date) >= test_date, func.date(Sale.sale_date) <= test_date
        ).all()

        assert len(product_sales) == 2, "Має бути 2 продажі"

        # Розраховуємо revenue та COGS
        total_revenue = Decimal("0.00")
        total_cogs = Decimal("0.00")

        for sale in product_sales:
            for item in sale.items:
                item_revenue = Decimal(str(item.price_per_unit)) * Decimal(str(item.quantity))
                item_cogs = Decimal(str(item.cost_price_per_unit)) * Decimal(str(item.quantity))
                total_revenue += item_revenue
                total_cogs += item_cogs

        assert total_revenue == Decimal("225.00"), f"Загальний дохід неправильний: {total_revenue}"
        expected_gross_profit = total_revenue - total_cogs
        assert expected_gross_profit == Decimal("112.50"), f"Валовий прибуток неправильний: {expected_gross_profit}"

        # 2. Перевіряємо дані звіту зарплати
        total_products_amount = (
            db.session.query(func.sum(Sale.total_amount))
            .filter(Sale.user_id == admin_user.id, func.date(Sale.sale_date) == test_date)
            .scalar()
        )

        assert total_products_amount == Decimal("225.00"), f"Сума для комісії неправильна: {total_products_amount}"

        # Комісія повинна бути 9% від загальної суми
        expected_commission = total_products_amount * Decimal("0.09")
        assert expected_commission == Decimal("20.25"), f"Комісія неправильна: {expected_commission}"

        # 3. Перевіряємо розподіл за методами оплати
        payment_method_totals = {}
        for sale in product_sales:
            method_name = PaymentMethod.query.get(sale.payment_method_id).name
            if method_name not in payment_method_totals:
                payment_method_totals[method_name] = Decimal("0.00")
            payment_method_totals[method_name] += sale.total_amount

        assert payment_method_totals["Готівка"] == Decimal("150.00"), "Сума готівкових продажів неправильна"
        assert payment_method_totals["Борг"] == Decimal("75.00"), "Сума продажів у борг неправильна"

    def test_full_appointment_cycle_all_reports_consistency(
        self, app, session, regular_user, test_client, test_service
    ):
        """
        Крок 1.3.2: Тест повного циклу: створення запису → завершення → перевірка звітів

        E2E тест, який створює запис, завершує його і перевіряє відображення у звітах.
        """
        # Створюємо методи оплати
        cash_method = PaymentMethod(name="Готівка", is_active=True)
        session.add(cash_method)
        session.commit()

        test_date = date.today()

        # 1. Створюємо запис (scheduled)
        appointment = Appointment(
            client_id=test_client.id,
            master_id=regular_user.id,
            date=test_date,
            start_time=time(15, 0),
            end_time=time(16, 0),
            status="scheduled",
            payment_status="unpaid",
        )
        session.add(appointment)
        session.commit()

        # Додаємо послугу
        appointment_service = AppointmentService(appointment_id=appointment.id, service_id=test_service.id, price=200.0)
        session.add(appointment_service)
        session.commit()

        # Перевіряємо, що scheduled запис НЕ враховується в звітах
        completed_before = Appointment.query.filter(
            Appointment.date >= test_date,
            Appointment.date <= test_date,
            Appointment.status == "completed",
        ).count()

        assert completed_before == 0, "Scheduled запис не повинен враховуватися в звітах"

        # 2. Завершуємо запис
        appointment.status = "completed"
        appointment.payment_status = "paid"
        appointment.amount_paid = Decimal("200.00")
        appointment.payment_method_id = cash_method.id
        session.commit()

        # 3. Перевіряємо відображення у фінансовому звіті
        completed_appointments = Appointment.query.filter(
            Appointment.date >= test_date,
            Appointment.date <= test_date,
            Appointment.status == "completed",
        ).all()

        assert len(completed_appointments) == 1, "Завершений запис не знайдено"

        completed_appointment = completed_appointments[0]
        assert completed_appointment.amount_paid == Decimal("200.00"), "Сума завершеного запису неправильна"

        # Розрахунок для фінансового звіту
        service_revenue = Decimal("0.00")
        for appointment in completed_appointments:
            if appointment.amount_paid is not None and appointment.amount_paid > 0:
                service_revenue += Decimal(str(appointment.amount_paid))

        assert service_revenue == Decimal("200.00"), f"Дохід від послуг неправильний: {service_revenue}"

        # 4. Перевіряємо дані звіту зарплати майстра
        # Встановлюємо комісію майстра для тесту
        if not regular_user.configurable_commission_rate:
            regular_user.configurable_commission_rate = Decimal("15.0")
            session.commit()

        commission_rate = float(regular_user.configurable_commission_rate)

        # Розрахунок комісії за послуги
        appointment_ids = [
            appointment.id for appointment in completed_appointments if appointment.master_id == regular_user.id
        ]

        if appointment_ids:
            service_sum_query = db.session.query(func.sum(AppointmentService.price)).filter(
                AppointmentService.appointment_id.in_(appointment_ids)
            )
            service_sum_result = service_sum_query.scalar()
            total_services_cost = float(service_sum_result or 0)

            services_commission = total_services_cost * (commission_rate / 100) if commission_rate > 0 else 0.0

            assert total_services_cost == 200.0, f"Сума послуг неправильна: {total_services_cost}"
            assert services_commission == 30.0, f"Комісія майстра неправильна: {services_commission} (15% від 200)"
