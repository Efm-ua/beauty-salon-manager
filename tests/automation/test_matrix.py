"""
Матриця тестових сценаріїв - Фаза 2
Систематичне тестування всіх комбінацій сценаріїв

Цей файл покриває тестування:
- Кроки 2.1.1-2.1.4: Матриця способів оплати × операції/звіти
- Кроки 2.2.1-2.2.2: Матриця статусів × звіти та переходи
- Крок 2.3.1: Тести з різними датами
"""

import pytest
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from itertools import product
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
    db,
)


class TestPaymentMethodOperationsMatrix:
    """
    Крок 2.1.2: Матриця способів оплати × операції

    Перевіряє всі комбінації способів оплати з різними типами операцій
    """

    def test_all_payment_methods_with_product_sales(
        self, app, session, admin_user, test_client, test_product, payment_methods
    ):
        """
        Матриця: Всі способи оплати × Продаж товарів

        Перевіряє, що продаж товарів працює з кожним способом оплати
        """
        test_date = date.today()
        results_matrix = {}

        for payment_method in payment_methods:
            # Створюємо продаж з кожним способом оплати
            sale = Sale(
                sale_date=datetime.combine(test_date, time(10, 0)),
                client_id=test_client.id,
                user_id=admin_user.id,
                total_amount=Decimal("100.00"),
                payment_method_id=payment_method.id,
                created_by_user_id=admin_user.id,
            )
            session.add(sale)
            session.commit()

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=test_product.id,
                quantity=1,
                price_per_unit=Decimal("100.00"),
                cost_price_per_unit=Decimal("50.00"),
            )
            session.add(sale_item)
            session.commit()

            # Перевіряємо, що продаж створився успішно
            created_sale = Sale.query.get(sale.id)
            results_matrix[payment_method.name] = {
                "sale_created": created_sale is not None,
                "correct_amount": created_sale.total_amount == Decimal("100.00"),
                "correct_payment_method": created_sale.payment_method_id == payment_method.id,
                "items_linked": len(created_sale.items) == 1,
            }

        # Перевіряємо результати матриці
        for method_name, results in results_matrix.items():
            assert results["sale_created"], f"Продаж не створився для методу {method_name}"
            assert results["correct_amount"], f"Неправильна сума для методу {method_name}"
            assert results["correct_payment_method"], f"Неправильний метод оплати для {method_name}"
            assert results["items_linked"], f"Товари не прив'язались для методу {method_name}"

    def test_all_payment_methods_with_appointment_services(
        self, app, session, regular_user, test_client, test_service, payment_methods
    ):
        """
        Матриця: Всі способи оплати × Послуги (записи)

        Перевіряє, що записи на послуги працюють з кожним способом оплати
        """
        test_date = date.today()
        results_matrix = {}

        for i, payment_method in enumerate(payment_methods):
            # Створюємо запис з кожним способом оплати
            appointment = Appointment(
                client_id=test_client.id,
                master_id=regular_user.id,
                date=test_date,
                start_time=time(10 + i, 0),
                end_time=time(11 + i, 0),
                status="completed",
                payment_status="paid" if payment_method.name != "Борг" else "unpaid",
                amount_paid=Decimal("150.00") if payment_method.name != "Борг" else Decimal("0.00"),
                payment_method_id=payment_method.id if payment_method.name != "Борг" else payment_method.id,
            )
            session.add(appointment)
            session.commit()

            appointment_service = AppointmentService(
                appointment_id=appointment.id, service_id=test_service.id, price=150.0
            )
            session.add(appointment_service)
            session.commit()

            # Перевіряємо, що запис створився успішно
            created_appointment = Appointment.query.get(appointment.id)
            expected_amount = Decimal("0.00") if payment_method.name == "Борг" else Decimal("150.00")

            results_matrix[payment_method.name] = {
                "appointment_created": created_appointment is not None,
                "correct_status": created_appointment.status == "completed",
                "correct_payment_method": created_appointment.payment_method_id == payment_method.id,
                "correct_amount": created_appointment.amount_paid == expected_amount,
                "services_linked": len(created_appointment.services) == 1,
            }

        # Перевіряємо результати матриці
        for method_name, results in results_matrix.items():
            assert results["appointment_created"], f"Запис не створився для методу {method_name}"
            assert results["correct_status"], f"Неправильний статус для методу {method_name}"
            assert results["correct_payment_method"], f"Неправильний метод оплати для {method_name}"
            assert results["correct_amount"], f"Неправильна сума для методу {method_name}"
            assert results["services_linked"], f"Послуги не прив'язались для методу {method_name}"

    def test_mixed_operations_same_day(
        self, app, session, admin_user, regular_user, test_client, test_product, test_service, payment_methods
    ):
        """
        Матриця: Змішані операції (продажі + записи) в один день

        Перевіряє комбінації продажів товарів та записів на послуги в один день
        """
        test_date = date.today()
        operations_performed = []

        # Створюємо по одному продажу та запису для кожного способу оплати
        for i, payment_method in enumerate(payment_methods):
            # Продаж товару
            sale = Sale(
                sale_date=datetime.combine(test_date, time(9 + i, 0)),
                client_id=test_client.id,
                user_id=admin_user.id,
                total_amount=Decimal(f"{50 + i * 10}.00"),
                payment_method_id=payment_method.id,
                created_by_user_id=admin_user.id,
            )
            session.add(sale)
            session.commit()

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=test_product.id,
                quantity=1,
                price_per_unit=Decimal(f"{50 + i * 10}.00"),
                cost_price_per_unit=Decimal(f"{25 + i * 5}.00"),
            )
            session.add(sale_item)

            # Запис на послугу
            appointment = Appointment(
                client_id=test_client.id,
                master_id=regular_user.id,
                date=test_date,
                start_time=time(14 + i, 0),
                end_time=time(15 + i, 0),
                status="completed",
                payment_status="paid" if payment_method.name != "Борг" else "unpaid",
                amount_paid=Decimal(f"{100 + i * 20}.00") if payment_method.name != "Борг" else Decimal("0.00"),
                payment_method_id=payment_method.id,
            )
            session.add(appointment)
            session.commit()

            appointment_service = AppointmentService(
                appointment_id=appointment.id, service_id=test_service.id, price=100.0 + i * 20
            )
            session.add(appointment_service)

            operations_performed.append(
                {"payment_method": payment_method.name, "sale_id": sale.id, "appointment_id": appointment.id}
            )

        session.commit()

        # Перевіряємо, що всі операції відображаються в звітах
        daily_sales = Sale.query.filter(func.date(Sale.sale_date) == test_date).all()
        daily_appointments = Appointment.query.filter(
            Appointment.date == test_date, Appointment.status == "completed"
        ).all()

        # Кількість операцій повинна відповідати кількості способів оплати
        assert len(daily_sales) == len(payment_methods), f"Неправильна кількість продажів: {len(daily_sales)}"
        assert len(daily_appointments) == len(
            payment_methods
        ), f"Неправильна кількість записів: {len(daily_appointments)}"

        # Перевіряємо, що всі способи оплати представлені
        sales_payment_methods = {PaymentMethod.query.get(sale.payment_method_id).name for sale in daily_sales}
        appointments_payment_methods = {
            PaymentMethod.query.get(apt.payment_method_id).name for apt in daily_appointments
        }
        expected_methods = {pm.name for pm in payment_methods}

        assert sales_payment_methods == expected_methods, "Не всі способи оплати представлені в продажах"
        assert appointments_payment_methods == expected_methods, "Не всі способи оплати представлені в записах"


class TestPaymentMethodReportsMatrix:
    """
    Крок 2.1.3: Матриця способів оплати × звіти

    Перевіряє, що всі способи оплати правильно відображаються в різних звітах
    """

    def test_payment_methods_in_financial_report(
        self, app, session, admin_user, test_client, test_product, payment_methods
    ):
        """
        Матриця: Способи оплати × Фінансовий звіт
        """
        test_date = date.today()
        expected_totals = {}

        # Створюємо продажі з різними сумами для кожного способу оплати
        for i, payment_method in enumerate(payment_methods):
            amount = Decimal(f"{100 + i * 50}.00")
            expected_totals[payment_method.name] = amount

            sale = Sale(
                sale_date=datetime.combine(test_date, time(10 + i, 0)),
                client_id=test_client.id,
                user_id=admin_user.id,
                total_amount=amount,
                payment_method_id=payment_method.id,
                created_by_user_id=admin_user.id,
            )
            session.add(sale)
            session.commit()

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=test_product.id,
                quantity=1,
                price_per_unit=amount,
                cost_price_per_unit=amount / Decimal("2"),
            )
            session.add(sale_item)

        session.commit()

        # Перевіряємо фінансовий звіт
        financial_report_data = {}
        daily_sales = Sale.query.filter(func.date(Sale.sale_date) == test_date).all()

        for sale in daily_sales:
            payment_method_name = PaymentMethod.query.get(sale.payment_method_id).name
            if payment_method_name not in financial_report_data:
                financial_report_data[payment_method_name] = Decimal("0.00")
            financial_report_data[payment_method_name] += sale.total_amount

        # Перевіряємо, що всі способи оплати присутні з правильними сумами
        for method_name, expected_amount in expected_totals.items():
            assert method_name in financial_report_data, f"Метод {method_name} відсутній у фінансовому звіті"
            assert (
                financial_report_data[method_name] == expected_amount
            ), f"Неправильна сума для {method_name}: {financial_report_data[method_name]} != {expected_amount}"

    def test_payment_methods_in_salary_report(
        self, app, session, admin_user, regular_user, test_client, test_product, payment_methods
    ):
        """
        Матриця: Способи оплати × Звіт зарплати
        """
        test_date = date.today()

        # Створюємо продажі від різних майстрів з різними способами оплати
        masters = [admin_user, regular_user]
        sales_by_master = {admin_user.id: [], regular_user.id: []}

        for i, payment_method in enumerate(payment_methods):
            master = masters[i % len(masters)]  # Чергуємо майстрів
            amount = Decimal(f"{200 + i * 30}.00")

            sale = Sale(
                sale_date=datetime.combine(test_date, time(11 + i, 0)),
                client_id=test_client.id,
                user_id=master.id,
                total_amount=amount,
                payment_method_id=payment_method.id,
                created_by_user_id=master.id,
            )
            session.add(sale)
            session.commit()

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=test_product.id,
                quantity=1,
                price_per_unit=amount,
                cost_price_per_unit=amount / Decimal("2"),
            )
            session.add(sale_item)

            sales_by_master[master.id].append({"payment_method": payment_method.name, "amount": amount})

        session.commit()

        # Перевіряємо звіт зарплати для кожного майстра
        for master_id, expected_sales in sales_by_master.items():
            if not expected_sales:  # Пропускаємо майстрів без продажів
                continue

            master_sales = Sale.query.filter(Sale.user_id == master_id, func.date(Sale.sale_date) == test_date).all()

            # Групуємо за способами оплати
            actual_by_method = {}
            for sale in master_sales:
                method_name = PaymentMethod.query.get(sale.payment_method_id).name
                if method_name not in actual_by_method:
                    actual_by_method[method_name] = Decimal("0.00")
                actual_by_method[method_name] += sale.total_amount

            # Перевіряємо відповідність
            expected_by_method = {}
            for sale_info in expected_sales:
                method = sale_info["payment_method"]
                if method not in expected_by_method:
                    expected_by_method[method] = Decimal("0.00")
                expected_by_method[method] += sale_info["amount"]

            for method, expected_amount in expected_by_method.items():
                assert method in actual_by_method, f"Метод {method} відсутній у звіті зарплати майстра {master_id}"
                assert (
                    actual_by_method[method] == expected_amount
                ), f"Неправильна сума для майстра {master_id}, метод {method}: {actual_by_method[method]} != {expected_amount}"


class TestEdgeCasesMatrix:
    """
    Крок 2.1.4: Граничні випадки

    Тестує граничні випадки та нестандартні сценарії
    """

    def test_zero_amount_transactions(self, app, session, admin_user, test_client, test_product, payment_methods):
        """
        Граничний випадок: Транзакції з нульовою сумою
        """
        test_date = date.today()

        # Знаходимо метод "Борг" для тестування нульових сум
        debt_method = next((pm for pm in payment_methods if pm.name == "Борг"), None)
        assert debt_method is not None, "Метод 'Борг' не знайдено"

        # Створюємо продаж з нульовою сумою (технічно можливо в борг)
        zero_sale = Sale(
            sale_date=datetime.combine(test_date, time(10, 0)),
            client_id=test_client.id,
            user_id=admin_user.id,
            total_amount=Decimal("0.00"),
            payment_method_id=debt_method.id,
            created_by_user_id=admin_user.id,
        )
        session.add(zero_sale)
        session.commit()

        # Перевіряємо, що нульовий продаж обробляється правильно
        saved_sale = Sale.query.get(zero_sale.id)
        assert saved_sale is not None, "Продаж з нульовою сумою не збережено"
        assert saved_sale.total_amount == Decimal("0.00"), "Нульова сума змінилась"

        # Перевіряємо, що він відображається в звітах
        daily_sales = Sale.query.filter(func.date(Sale.sale_date) == test_date).all()
        zero_sales = [sale for sale in daily_sales if sale.total_amount == Decimal("0.00")]
        assert len(zero_sales) == 1, "Продаж з нульовою сумою не відображається в звітах"

    def test_very_large_amounts(self, app, session, admin_user, test_client, test_product, payment_methods):
        """
        Граничний випадок: Дуже великі суми
        """
        test_date = date.today()

        # Тестуємо з дуже великою сумою
        large_amount = Decimal("999999.99")
        cash_method = next((pm for pm in payment_methods if pm.name == "Готівка"), payment_methods[0])

        large_sale = Sale(
            sale_date=datetime.combine(test_date, time(11, 0)),
            client_id=test_client.id,
            user_id=admin_user.id,
            total_amount=large_amount,
            payment_method_id=cash_method.id,
            created_by_user_id=admin_user.id,
        )
        session.add(large_sale)
        session.commit()

        sale_item = SaleItem(
            sale_id=large_sale.id,
            product_id=test_product.id,
            quantity=1,
            price_per_unit=large_amount,
            cost_price_per_unit=large_amount / Decimal("2"),
        )
        session.add(sale_item)
        session.commit()

        # Перевіряємо, що велика сума обробляється правильно
        saved_sale = Sale.query.get(large_sale.id)
        assert (
            saved_sale.total_amount == large_amount
        ), f"Велика сума змінилась: {saved_sale.total_amount} != {large_amount}"

        # Перевіряємо розрахунки комісії (не повинні ламатися)
        commission_base = saved_sale.total_amount * Decimal("0.09")
        assert commission_base == large_amount * Decimal("0.09"), "Розрахунок комісії з великої суми неправильний"

    def test_multiple_transactions_same_minute(
        self, app, session, admin_user, test_client, test_product, payment_methods
    ):
        """
        Граничний випадок: Кілька транзакцій в одну хвилину
        """
        test_date = date.today()
        same_time = datetime.combine(test_date, time(12, 30))

        # Створюємо 5 продажів в одну хвилину
        created_sales = []
        for i in range(5):
            payment_method = payment_methods[i % len(payment_methods)]

            sale = Sale(
                sale_date=same_time,
                client_id=test_client.id,
                user_id=admin_user.id,
                total_amount=Decimal(f"{10 + i}.00"),
                payment_method_id=payment_method.id,
                created_by_user_id=admin_user.id,
            )
            session.add(sale)
            session.commit()

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=test_product.id,
                quantity=1,
                price_per_unit=Decimal(f"{10 + i}.00"),
                cost_price_per_unit=Decimal(f"{5 + i}.00"),
            )
            session.add(sale_item)
            created_sales.append(sale)

        session.commit()

        # Перевіряємо, що всі продажі збережено та обробляються правильно
        saved_sales = Sale.query.filter(Sale.sale_date == same_time).all()
        assert len(saved_sales) == 5, f"Не всі продажі збережено: {len(saved_sales)} з 5"

        # Перевіряємо, що всі відображаються в щоденному звіті
        daily_sales = Sale.query.filter(func.date(Sale.sale_date) == test_date).all()
        same_minute_sales = [sale for sale in daily_sales if sale.sale_date == same_time]
        assert len(same_minute_sales) == 5, "Не всі продажі з однієї хвилини відображаються в звіті"


class TestAppointmentStatusMatrix:
    """
    Крок 2.2.1: Матриця статусів × звіти

    Перевіряє як різні статуси записів впливають на звіти
    """

    def test_all_appointment_statuses_in_reports(
        self, app, session, regular_user, test_client, test_service, payment_methods
    ):
        """
        Матриця: Всі статуси записів × Звіти
        """
        test_date = date.today()
        appointment_statuses = ["scheduled", "completed", "cancelled", "no_show"]
        cash_method = next((pm for pm in payment_methods if pm.name == "Готівка"), payment_methods[0])

        created_appointments = {}

        # Створюємо записи з різними статусами
        for i, status in enumerate(appointment_statuses):
            appointment = Appointment(
                client_id=test_client.id,
                master_id=regular_user.id,
                date=test_date,
                start_time=time(10 + i, 0),
                end_time=time(11 + i, 0),
                status=status,
                payment_status="paid" if status == "completed" else "unpaid",
                amount_paid=Decimal("200.00") if status == "completed" else Decimal("0.00"),
                payment_method_id=cash_method.id if status == "completed" else None,
            )
            session.add(appointment)
            session.commit()

            appointment_service = AppointmentService(
                appointment_id=appointment.id, service_id=test_service.id, price=200.0
            )
            session.add(appointment_service)

            created_appointments[status] = appointment.id

        session.commit()

        # Перевіряємо які статуси відображаються в фінансовому звіті
        financial_appointments = Appointment.query.filter(
            Appointment.date == test_date, Appointment.status == "completed"  # Тільки завершені
        ).all()

        completed_in_financial = [apt.id for apt in financial_appointments]

        # Тільки completed повинен бути в фінансовому звіті
        assert (
            created_appointments["completed"] in completed_in_financial
        ), "Завершений запис відсутній у фінансовому звіті"
        assert (
            created_appointments["scheduled"] not in completed_in_financial
        ), "Заплановані записи не повинні бути в фінансовому звіті"
        assert (
            created_appointments["cancelled"] not in completed_in_financial
        ), "Скасовані записи не повинні бути в фінансовому звіті"
        assert (
            created_appointments["no_show"] not in completed_in_financial
        ), "No-show записи не повинні бути в фінансовому звіті"

        # Перевіряємо звіт зарплати (також тільки completed)
        salary_appointments = Appointment.query.filter(
            Appointment.master_id == regular_user.id, Appointment.date == test_date, Appointment.status == "completed"
        ).all()

        completed_in_salary = [apt.id for apt in salary_appointments]
        assert created_appointments["completed"] in completed_in_salary, "Завершений запис відсутній у звіті зарплати"
        assert (
            len(completed_in_salary) == 1
        ), f"У звіті зарплати повинен бути 1 запис, знайдено: {len(completed_in_salary)}"

    def test_appointment_status_transitions_impact(
        self, app, session, regular_user, test_client, test_service, payment_methods
    ):
        """
        Крок 2.2.2: Переходи між статусами

        Перевіряє як зміна статусу запису впливає на звіти
        """
        test_date = date.today()
        cash_method = next((pm for pm in payment_methods if pm.name == "Готівка"), payment_methods[0])

        # Створюємо запис у статусі "scheduled"
        appointment = Appointment(
            client_id=test_client.id,
            master_id=regular_user.id,
            date=test_date,
            start_time=time(15, 0),
            end_time=time(16, 0),
            status="scheduled",
            payment_status="unpaid",
            amount_paid=Decimal("0.00"),
            payment_method_id=None,
        )
        session.add(appointment)
        session.commit()

        appointment_service = AppointmentService(appointment_id=appointment.id, service_id=test_service.id, price=300.0)
        session.add(appointment_service)
        session.commit()

        # Перевіряємо, що scheduled запис НЕ в звітах
        financial_before = Appointment.query.filter(
            Appointment.date == test_date, Appointment.status == "completed"
        ).count()

        assert financial_before == 0, "Scheduled запис не повинен бути в фінансовому звіті"

        # Переводимо запис у статус "completed"
        appointment.status = "completed"
        appointment.payment_status = "paid"
        appointment.amount_paid = Decimal("300.00")
        appointment.payment_method_id = cash_method.id
        session.commit()

        # Перевіряємо, що тепер запис З'ЯВИВСЯ в звітах
        financial_after = Appointment.query.filter(
            Appointment.date == test_date, Appointment.status == "completed"
        ).all()

        assert len(financial_after) == 1, "Завершений запис повинен з'явитися в фінансовому звіті"
        assert financial_after[0].id == appointment.id, "Неправильний запис у фінансовому звіті"
        assert financial_after[0].amount_paid == Decimal("300.00"), "Неправильна сума після переходу статусу"

        # Тепер скасовуємо запис
        appointment.status = "cancelled"
        appointment.payment_status = "unpaid"
        appointment.amount_paid = Decimal("0.00")
        appointment.payment_method_id = None
        session.commit()

        # Перевіряємо, що запис ЗНИК з звітів
        financial_cancelled = Appointment.query.filter(
            Appointment.date == test_date, Appointment.status == "completed"
        ).count()

        assert financial_cancelled == 0, "Скасований запис не повинен бути в фінансовому звіті"


class TestDateRangeMatrix:
    """
    Крок 2.3.1: Тести з різними датами

    Перевіряє роботу системи з різними датними діапазонами
    """

    def test_cross_date_operations_isolation(
        self, app, session, admin_user, test_client, test_product, payment_methods
    ):
        """
        Ізоляція операцій між датами

        Перевіряє, що операції різних дат не змішуються в звітах
        """
        cash_method = next((pm for pm in payment_methods if pm.name == "Готівка"), payment_methods[0])

        # Створюємо операції на різні дати
        dates_to_test = [
            date.today() - timedelta(days=1),  # Вчора
            date.today(),  # Сьогодні
            date.today() + timedelta(days=1),  # Завтра
        ]

        created_sales_by_date = {}

        for test_date in dates_to_test:
            sale = Sale(
                sale_date=datetime.combine(test_date, time(12, 0)),
                client_id=test_client.id,
                user_id=admin_user.id,
                total_amount=Decimal("500.00"),
                payment_method_id=cash_method.id,
                created_by_user_id=admin_user.id,
            )
            session.add(sale)
            session.commit()

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=test_product.id,
                quantity=1,
                price_per_unit=Decimal("500.00"),
                cost_price_per_unit=Decimal("250.00"),
            )
            session.add(sale_item)

            created_sales_by_date[test_date] = sale.id

        session.commit()

        # Перевіряємо ізоляцію для кожної дати
        for test_date, expected_sale_id in created_sales_by_date.items():
            daily_sales = Sale.query.filter(func.date(Sale.sale_date) == test_date).all()

            # На кожну дату повинен бути рівно один продаж
            assert len(daily_sales) == 1, f"Неправильна кількість продажів для дати {test_date}: {len(daily_sales)}"
            assert daily_sales[0].id == expected_sale_id, f"Неправильний продаж для дати {test_date}"
            assert daily_sales[0].total_amount == Decimal("500.00"), f"Неправильна сума для дати {test_date}"

        # Перевіряємо, що сьогоднішній звіт не включає вчорашні/завтрашні операції
        today_sales = Sale.query.filter(func.date(Sale.sale_date) == date.today()).all()
        assert len(today_sales) == 1, f"У сьогоднішньому звіті повинен бути 1 продаж, знайдено: {len(today_sales)}"

    def test_month_boundary_operations(self, app, session, admin_user, test_client, test_product, payment_methods):
        """
        Операції на межі місяців

        Перевіряє коректну обробку операцій на межі місяців
        """
        cash_method = next((pm for pm in payment_methods if pm.name == "Готівка"), payment_methods[0])

        # Знаходимо останній день поточного місяця
        today = date.today()
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)

        last_day_current_month = next_month - timedelta(days=1)
        first_day_next_month = next_month

        # Створюємо операції на межі місяця
        boundary_dates = [last_day_current_month, first_day_next_month]
        created_sales = {}

        for i, boundary_date in enumerate(boundary_dates):
            sale = Sale(
                sale_date=datetime.combine(boundary_date, time(23, 59) if i == 0 else time(0, 1)),
                client_id=test_client.id,
                user_id=admin_user.id,
                total_amount=Decimal(f"{100 + i * 50}.00"),
                payment_method_id=cash_method.id,
                created_by_user_id=admin_user.id,
            )
            session.add(sale)
            session.commit()

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=test_product.id,
                quantity=1,
                price_per_unit=Decimal(f"{100 + i * 50}.00"),
                cost_price_per_unit=Decimal(f"{50 + i * 25}.00"),
            )
            session.add(sale_item)

            created_sales[boundary_date] = sale.id

        session.commit()

        # Перевіряємо, що операції правильно розподілені по місяцях
        for boundary_date, sale_id in created_sales.items():
            date_sales = Sale.query.filter(func.date(Sale.sale_date) == boundary_date).all()

            assert len(date_sales) == 1, f"Неправильна кількість продажів для граничної дати {boundary_date}"
            assert date_sales[0].id == sale_id, f"Неправильний продаж для граничної дати {boundary_date}"

        # Перевіряємо місячну звітність (концептуально)
        current_month_sales = Sale.query.filter(
            func.extract("year", Sale.sale_date) == last_day_current_month.year,
            func.extract("month", Sale.sale_date) == last_day_current_month.month,
        ).all()

        next_month_sales = Sale.query.filter(
            func.extract("year", Sale.sale_date) == first_day_next_month.year,
            func.extract("month", Sale.sale_date) == first_day_next_month.month,
        ).all()

        # Кожен місяць повинен містити відповідну операцію
        current_month_ids = [sale.id for sale in current_month_sales]
        next_month_ids = [sale.id for sale in next_month_sales]

        assert (
            created_sales[last_day_current_month] in current_month_ids
        ), "Операція останнього дня не в поточному місяці"
        assert created_sales[first_day_next_month] in next_month_ids, "Операція першого дня не в наступному місяці"
