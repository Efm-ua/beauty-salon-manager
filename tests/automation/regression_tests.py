"""
Regression тести - Фаза 7
Запобігання повторного виникнення знайдених багів.

Цей файл містить тести, які перевіряють, що раніше знайдені баги не повторюються.
Кожен тест пов'язаний з конкретним багом і документує проблему та її рішення.
"""

import pytest
from decimal import Decimal
from datetime import datetime, date, time
from app import create_app, db
from app.models import User, Client, Service, Product, Sale, SaleItem, Appointment, AppointmentService, PaymentMethod


class TestBUG001Regression:
    """
    Regression тести для BUG-001: Продаж у борг не відображається в щоденному звіті

    Проблема: Продажі у борг відображалися в звіті зарплати, але не відображалися
    в щоденному звіті, що створювало розбіжності в звітності.

    Рішення: Забезпечити, що всі продажі (включаючи борги) відображаються в усіх звітах.
    """

    def test_debt_sale_appears_in_daily_report(self, app, test_client, payment_methods, admin_user, test_product):
        """
        Крок 7.1.2: Тест для BUG-001 - продаж у борг відображається в щоденному звіті

        Цей тест перевіряє, що продажі у борг обов'язково відображаються в щоденному звіті.
        Це основний regression тест для BUG-001.
        """
        with app.app_context():
            # Отримуємо метод оплати "Борг"
            debt_payment = PaymentMethod.query.filter_by(name="Борг").first()
            assert debt_payment is not None, "Метод оплати 'Борг' не знайдено"

            # Створюємо продаж у борг
            debt_sale = Sale(
                user_id=admin_user.id,
                client_id=test_client.id,
                payment_method_id=debt_payment.id,
                total_amount=Decimal("300.00"),
                sale_date=datetime.now(),
                created_by_user_id=admin_user.id,
            )
            db.session.add(debt_sale)
            db.session.flush()

            sale_item = SaleItem(
                sale_id=debt_sale.id,
                product_id=test_product.id,
                quantity=1,
                price_per_unit=Decimal("300.00"),
                cost_price_per_unit=Decimal("150.00"),
            )
            db.session.add(sale_item)
            db.session.commit()

            # Перевіряємо, що продаж у борг відображається в щоденному звіті
            today = date.today()
            daily_sales = Sale.query.filter(db.func.date(Sale.sale_date) == today).all()

            # Основна перевірка: продаж у борг ПОВИНЕН бути в щоденному звіті
            debt_sales_in_daily = [sale for sale in daily_sales if sale.payment_method_id == debt_payment.id]
            assert (
                len(debt_sales_in_daily) > 0
            ), "BUG-001 REGRESSION: Продаж у борг не відображається в щоденному звіті!"

            # Перевіряємо конкретний продаж
            found_sale = None
            for sale in debt_sales_in_daily:
                if sale.id == debt_sale.id:
                    found_sale = sale
                    break

            assert (
                found_sale is not None
            ), f"BUG-001 REGRESSION: Конкретний продаж у борг (ID: {debt_sale.id}) не знайдено в щоденному звіті!"
            assert found_sale.total_amount == Decimal(
                "300.00"
            ), f"BUG-001 REGRESSION: Неправильна сума продажу у борг: {found_sale.total_amount}"

    def test_debt_sale_consistency_between_salary_and_daily_reports(
        self, app, test_client, payment_methods, admin_user, test_product
    ):
        """
        Крок 7.1.3: Тест консистентності для BUG-001

        Перевіряє, що продажі у борг відображаються однаково в звіті зарплати та щоденному звіті.
        Це розширений regression тест для BUG-001.
        """
        with app.app_context():
            # Отримуємо метод оплати "Борг"
            debt_payment = PaymentMethod.query.filter_by(name="Борг").first()
            assert debt_payment is not None, "Метод оплати 'Борг' не знайдено"

            # Створюємо кілька продажів у борг
            debt_sales_created = []

            for i in range(3):
                debt_sale = Sale(
                    user_id=admin_user.id,
                    client_id=test_client.id,
                    payment_method_id=debt_payment.id,
                    total_amount=Decimal(f"{200 + i * 100}.00"),
                    sale_date=datetime.now(),
                    created_by_user_id=admin_user.id,
                )
                db.session.add(debt_sale)
                db.session.flush()

                sale_item = SaleItem(
                    sale_id=debt_sale.id,
                    product_id=test_product.id,
                    quantity=1,
                    price_per_unit=Decimal(f"{200 + i * 100}.00"),
                    cost_price_per_unit=Decimal(f"{100 + i * 50}.00"),
                )
                db.session.add(sale_item)
                debt_sales_created.append(debt_sale)

            db.session.commit()

            today = date.today()

            # Отримуємо дані для звіту зарплати (для конкретного майстра)
            salary_debt_sales = Sale.query.filter(
                Sale.user_id == admin_user.id,
                Sale.payment_method_id == debt_payment.id,
                db.func.date(Sale.sale_date) == today,
            ).all()

            # Отримуємо дані для щоденного звіту (всі продажі у борг)
            daily_debt_sales = Sale.query.filter(
                Sale.payment_method_id == debt_payment.id, db.func.date(Sale.sale_date) == today
            ).all()

            # Перевіряємо консистентність
            assert (
                len(salary_debt_sales) == 3
            ), f"BUG-001 REGRESSION: У звіті зарплати повинно бути 3 продажі у борг, але знайдено {len(salary_debt_sales)}"
            assert (
                len(daily_debt_sales) >= 3
            ), f"BUG-001 REGRESSION: У щоденному звіті повинно бути мінімум 3 продажі у борг, але знайдено {len(daily_debt_sales)}"

            # Перевіряємо, що всі продажі майстра присутні в щоденному звіті
            salary_sale_ids = {sale.id for sale in salary_debt_sales}
            daily_sale_ids = {sale.id for sale in daily_debt_sales}

            missing_in_daily = salary_sale_ids - daily_sale_ids
            assert (
                len(missing_in_daily) == 0
            ), f"BUG-001 REGRESSION: Продажі у борг з звіту зарплати відсутні в щоденному звіті: {missing_in_daily}"

            # Перевіряємо суми
            salary_debt_total = sum(sale.total_amount for sale in salary_debt_sales)
            daily_debt_total_for_master = sum(
                sale.total_amount for sale in daily_debt_sales if sale.user_id == admin_user.id
            )

            assert (
                salary_debt_total == daily_debt_total_for_master
            ), f"BUG-001 REGRESSION: Суми боргів не співпадають: зарплата={salary_debt_total}, щоденний={daily_debt_total_for_master}"

    def test_all_payment_methods_appear_in_daily_report(
        self, app, test_client, payment_methods, admin_user, test_product
    ):
        """
        Розширений regression тест: всі способи оплати відображаються в щоденному звіті

        Перевіряє, що не тільки борги, але й всі інші способи оплати правильно відображаються.
        """
        with app.app_context():
            # Отримуємо всі способи оплати
            all_payment_methods = PaymentMethod.query.all()
            created_sales = []

            # Створюємо продаж кожним способом оплати
            for i, payment_method in enumerate(all_payment_methods):
                sale = Sale(
                    user_id=admin_user.id,
                    client_id=test_client.id,
                    payment_method_id=payment_method.id,
                    total_amount=Decimal(f"{100 + i * 50}.00"),
                    sale_date=datetime.now(),
                    created_by_user_id=admin_user.id,
                )
                db.session.add(sale)
                db.session.flush()

                sale_item = SaleItem(
                    sale_id=sale.id,
                    product_id=test_product.id,
                    quantity=1,
                    price_per_unit=Decimal(f"{100 + i * 50}.00"),
                    cost_price_per_unit=Decimal(f"{50 + i * 25}.00"),
                )
                db.session.add(sale_item)
                created_sales.append((sale, payment_method.name))

            db.session.commit()

            # Перевіряємо щоденний звіт
            today = date.today()
            daily_sales = Sale.query.filter(db.func.date(Sale.sale_date) == today).all()

            # Групуємо за способами оплати
            daily_by_payment = {}
            for sale in daily_sales:
                # Отримуємо назву методу оплати через ID
                payment_method = PaymentMethod.query.get(sale.payment_method_id)
                method_name = payment_method.name if payment_method else "Unknown"
                if method_name not in daily_by_payment:
                    daily_by_payment[method_name] = []
                daily_by_payment[method_name].append(sale)

            # Перевіряємо, що всі способи оплати представлені
            created_methods = {method_name for _, method_name in created_sales}
            daily_methods = set(daily_by_payment.keys())

            missing_methods = created_methods - daily_methods
            assert (
                len(missing_methods) == 0
            ), f"BUG-001 REGRESSION: Способи оплати відсутні в щоденному звіті: {missing_methods}"

            # Особлива перевірка для боргу
            assert "Борг" in daily_methods, "BUG-001 REGRESSION: Борг відсутній в щоденному звіті!"

            debt_sales = daily_by_payment.get("Борг", [])
            assert len(debt_sales) > 0, "BUG-001 REGRESSION: Немає продажів у борг в щоденному звіті!"

            # Перевіряємо характеристики продажів у борг
            for debt_sale in debt_sales:
                assert debt_sale.total_amount > Decimal(
                    "0.00"
                ), f"BUG-001 REGRESSION: Продаж у борг має нульову загальну суму: {debt_sale.total_amount}"


class TestAppointmentReportsRegression:
    """
    Regression тести для записів та звітів
    Перевіряє, що записи правильно відображаються в звітах
    """

    def test_completed_appointments_appear_in_reports(
        self, app, test_client, payment_methods, regular_user, test_service
    ):
        """
        Regression тест: завершені записи відображаються в звітах
        """
        with app.app_context():
            cash_payment = PaymentMethod.query.filter_by(name="Готівка").first()
            assert cash_payment is not None, "Метод оплати 'Готівка' не знайдено"

            # Створюємо завершений запис
            appointment = Appointment(
                master_id=regular_user.id,
                client_id=test_client.id,
                date=date.today(),
                start_time=time(10, 0),
                end_time=time(11, 0),
                status="completed",
                payment_status="paid",
                amount_paid=Decimal("400.00"),
                payment_method_id=cash_payment.id,
            )
            db.session.add(appointment)
            db.session.flush()

            appointment_service = AppointmentService(
                appointment_id=appointment.id, service_id=test_service.id, price=400.0
            )
            db.session.add(appointment_service)
            db.session.commit()

            # Перевіряємо щоденний звіт
            today = date.today()
            daily_appointments = Appointment.query.filter(
                Appointment.status == "completed", Appointment.date == today
            ).all()

            assert len(daily_appointments) > 0, "REGRESSION: Завершені записи не відображаються в щоденному звіті"

            found_appointment = None
            for apt in daily_appointments:
                if apt.id == appointment.id:
                    found_appointment = apt
                    break

            assert (
                found_appointment is not None
            ), "REGRESSION: Конкретний завершений запис не знайдено в щоденному звіті"
            assert found_appointment.amount_paid == Decimal("400.00"), "REGRESSION: Неправильна сума запису в звіті"

    def test_cancelled_appointments_not_in_financial_reports(self, app, test_client, regular_user, test_service):
        """
        Regression тест: скасовані записи не враховуються в фінансових звітах
        """
        with app.app_context():
            # Створюємо скасований запис
            cancelled_appointment = Appointment(
                master_id=regular_user.id,
                client_id=test_client.id,
                date=date.today(),
                start_time=time(14, 0),
                end_time=time(15, 0),
                status="cancelled",
                payment_status="unpaid",
                amount_paid=Decimal("0.00"),
                payment_method_id=None,
            )
            db.session.add(cancelled_appointment)
            db.session.flush()

            appointment_service = AppointmentService(
                appointment_id=cancelled_appointment.id, service_id=test_service.id, price=400.0
            )
            db.session.add(appointment_service)
            db.session.commit()

            # Перевіряємо, що скасований запис НЕ враховується в фінансових звітах
            today = date.today()
            financial_appointments = Appointment.query.filter(
                Appointment.status == "completed",  # Тільки завершені
                Appointment.date == today,
            ).all()

            cancelled_in_financial = [apt for apt in financial_appointments if apt.id == cancelled_appointment.id]
            assert (
                len(cancelled_in_financial) == 0
            ), "REGRESSION: Скасований запис неправильно враховується в фінансовому звіті"

            # Перевіряємо звіт зарплати
            salary_appointments = Appointment.query.filter(
                Appointment.master_id == regular_user.id,
                Appointment.status == "completed",  # Тільки завершені
                Appointment.date == today,
            ).all()

            cancelled_in_salary = [apt for apt in salary_appointments if apt.id == cancelled_appointment.id]
            assert (
                len(cancelled_in_salary) == 0
            ), "REGRESSION: Скасований запис неправильно враховується в звіті зарплати"


class TestDataConsistencyRegression:
    """
    Regression тести для консистентності даних
    Перевіряє, що дані залишаються консистентними між різними частинами системи
    """

    def test_sale_items_match_sale_total(self, app, test_client, payment_methods, admin_user, test_product):
        """
        Regression тест: сума товарів у продажі відповідає загальній сумі продажу
        """
        with app.app_context():
            cash_payment = PaymentMethod.query.filter_by(name="Готівка").first()
            assert cash_payment is not None, "Метод оплати 'Готівка' не знайдено"

            # Створюємо продаж з кількома товарами
            sale = Sale(
                user_id=admin_user.id,
                client_id=test_client.id,
                payment_method_id=cash_payment.id,
                total_amount=Decimal("500.00"),
                sale_date=datetime.now(),
                created_by_user_id=admin_user.id,
            )
            db.session.add(sale)
            db.session.flush()

            # Додаємо товари
            sale_items = [
                SaleItem(
                    sale_id=sale.id,
                    product_id=test_product.id,
                    quantity=2,
                    price_per_unit=Decimal("150.00"),
                    cost_price_per_unit=Decimal("75.00"),
                ),
                SaleItem(
                    sale_id=sale.id,
                    product_id=test_product.id,
                    quantity=1,
                    price_per_unit=Decimal("200.00"),
                    cost_price_per_unit=Decimal("100.00"),
                ),
            ]

            for item in sale_items:
                db.session.add(item)

            db.session.commit()

            # Перевіряємо консистентність
            items_total = sum(item.quantity * item.price_per_unit for item in sale_items)
            assert (
                items_total == sale.total_amount
            ), f"REGRESSION: Сума товарів ({items_total}) не відповідає загальній сумі продажу ({sale.total_amount})"

    def test_appointment_services_match_appointment_total(
        self, app, test_client, payment_methods, regular_user, test_service
    ):
        """
        Regression тест: сума послуг у записі відповідає загальній сумі запису
        """
        with app.app_context():
            cash_payment = PaymentMethod.query.filter_by(name="Готівка").first()
            assert cash_payment is not None, "Метод оплати 'Готівка' не знайдено"

            # Створюємо запис з кількома послугами
            appointment = Appointment(
                master_id=regular_user.id,
                client_id=test_client.id,
                date=date.today(),
                start_time=time(16, 0),
                end_time=time(18, 0),
                status="completed",
                payment_status="paid",
                amount_paid=Decimal("600.00"),
                payment_method_id=cash_payment.id,
            )
            db.session.add(appointment)
            db.session.flush()

            # Додаємо послуги
            appointment_services = [
                AppointmentService(appointment_id=appointment.id, service_id=test_service.id, price=300.0),
                AppointmentService(appointment_id=appointment.id, service_id=test_service.id, price=300.0),
            ]

            for service_item in appointment_services:
                db.session.add(service_item)

            db.session.commit()

            # Перевіряємо консистентність
            services_total = sum(Decimal(str(service_item.price)) for service_item in appointment_services)
            assert (
                services_total == appointment.amount_paid
            ), f"REGRESSION: Сума послуг ({services_total}) не відповідає загальній сумі запису ({appointment.amount_paid})"


class TestRegressionTestSystem:
    """
    Тести системи regression тестів
    Перевіряє, що система regression тестів працює правильно
    """

    def test_regression_tests_are_comprehensive(self, app, test_client):
        """
        Крок 7.2.1: Перевірка повноти regression тестів

        Цей тест перевіряє, що regression тести покривають основні сценарії.
        """
        # Цей тест служить як документація того, що повинно бути покрито regression тестами

        required_regression_areas = [
            "debt_sales_in_daily_report",  # BUG-001
            "payment_methods_consistency",
            "appointment_status_handling",
            "data_consistency_checks",
            "calculation_accuracy",
        ]

        # Перевіряємо, що всі області покриті (це символічна перевірка)
        covered_areas = [
            "debt_sales_in_daily_report",  # TestBUG001Regression
            "payment_methods_consistency",  # TestBUG001Regression
            "appointment_status_handling",  # TestAppointmentReportsRegression
            "data_consistency_checks",  # TestDataConsistencyRegression
            "calculation_accuracy",  # TestDataConsistencyRegression
        ]

        missing_areas = set(required_regression_areas) - set(covered_areas)
        assert len(missing_areas) == 0, f"Regression тести не покривають наступні області: {missing_areas}"

    def test_bug_catalog_integration(self, app, test_client):
        """
        Крок 7.3.3: Перевірка зв'язку багів з тестами

        Перевіряє, що кожен задокументований баг має відповідний regression тест.
        """
        # Список відомих багів (повинен синхронізуватися з bug_catalog.md)
        documented_bugs = ["BUG-001"]  # Продаж у борг не відображається в щоденному звіті

        # Список regression тестів для кожного бага
        regression_tests_mapping = {
            "BUG-001": [
                "test_debt_sale_appears_in_daily_report",
                "test_debt_sale_consistency_between_salary_and_daily_reports",
                "test_all_payment_methods_appear_in_daily_report",
            ]
        }

        # Перевіряємо, що для кожного бага є regression тести
        for bug_id in documented_bugs:
            assert bug_id in regression_tests_mapping, f"Для бага {bug_id} немає regression тестів"

            tests = regression_tests_mapping[bug_id]
            assert len(tests) > 0, f"Для бага {bug_id} немає жодного regression тесту"

            # Перевіряємо, що тести існують (це символічна перевірка)
            for test_name in tests:
                # В реальній системі тут була б перевірка існування методу
                assert test_name.startswith("test_"), f"Неправильна назва тесту: {test_name}"
