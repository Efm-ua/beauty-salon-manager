"""
Тести перевірки консистентності звітів
Фаза 3: Тести перевірки звітів

Цей файл покриває тестування:
- Кроки 3.1.1-3.1.4: Тести консистентності звітів
- Кроки 3.2.1-3.2.4: Тести валідації даних у звітах
"""

import pytest
from datetime import date, datetime, time
from decimal import Decimal
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


class TestReportConsistency:
    """Тести консистентності звітів"""

    def test_sum_consistency_between_salary_and_financial_reports(
        self, app, session, admin_user, regular_user, test_client, test_product, test_service
    ):
        """
        Крок 3.1.2: Тест "сума_в_звіті_зарплати_дорівнює_сумі_в_щоденному_звіті"

        Перевіряє, що суми в звіті зарплати точно відповідають сумам у фінансовому звіті.
        """
        # Створюємо методи оплати
        cash_method = PaymentMethod(name="Готівка", is_active=True)
        debt_method = PaymentMethod(name="Борг", is_active=True)
        session.add_all([cash_method, debt_method])
        session.commit()

        test_date = date.today()

        # Створюємо продажі товарів
        sale1 = Sale(
            sale_date=datetime.combine(test_date, time(10, 0)),
            client_id=test_client.id,
            user_id=admin_user.id,
            total_amount=Decimal("300.00"),
            payment_method_id=cash_method.id,
            created_by_user_id=admin_user.id,
        )
        session.add(sale1)
        session.commit()

        sale_item1 = SaleItem(
            sale_id=sale1.id,
            product_id=test_product.id,
            quantity=3,
            price_per_unit=Decimal("100.00"),
            cost_price_per_unit=Decimal("60.00"),
        )
        session.add(sale_item1)

        # Створюємо завершений запис
        appointment = Appointment(
            client_id=test_client.id,
            master_id=regular_user.id,
            date=test_date,
            start_time=time(14, 0),
            end_time=time(15, 0),
            status="completed",
            payment_status="paid",
            amount_paid=Decimal("250.00"),
            payment_method_id=cash_method.id,
        )
        session.add(appointment)
        session.commit()

        appointment_service = AppointmentService(appointment_id=appointment.id, service_id=test_service.id, price=250.0)
        session.add(appointment_service)
        session.commit()

        # Перевіряємо консистентність між звітами

        # 1. Фінансовий звіт: дохід від товарів
        product_revenue = (
            db.session.query(func.sum(SaleItem.price_per_unit * SaleItem.quantity))
            .join(Sale)
            .filter(func.date(Sale.sale_date) == test_date)
            .scalar()
        )

        # 2. Фінансовий звіт: дохід від послуг
        service_revenue = (
            db.session.query(func.sum(Appointment.amount_paid))
            .filter(
                Appointment.date == test_date, Appointment.status == "completed", Appointment.amount_paid.isnot(None)
            )
            .scalar()
        )

        # 3. Звіт зарплати: комісія з товарів (9%)
        products_commission_base = (
            db.session.query(func.sum(Sale.total_amount))
            .filter(Sale.user_id == admin_user.id, func.date(Sale.sale_date) == test_date)
            .scalar()
        )

        # 4. Звіт зарплати: комісія з послуг (15% для regular_user)
        if not regular_user.configurable_commission_rate:
            regular_user.configurable_commission_rate = Decimal("15.0")
            session.commit()

        services_commission_base = (
            db.session.query(func.sum(AppointmentService.price))
            .join(Appointment)
            .filter(
                Appointment.master_id == regular_user.id,
                Appointment.date == test_date,
                Appointment.status == "completed",
            )
            .scalar()
        )

        # Перевіряємо консистентність
        assert product_revenue == Decimal("300.00"), f"Дохід від товарів неправильний: {product_revenue}"
        assert service_revenue == Decimal("250.00"), f"Дохід від послуг неправильний: {service_revenue}"
        assert products_commission_base == Decimal(
            "300.00"
        ), f"База для комісії з товарів неправильна: {products_commission_base}"
        assert services_commission_base == Decimal(
            "250.00"
        ), f"База для комісії з послуг неправильна: {services_commission_base}"

        # Розрахунки комісій
        expected_products_commission = products_commission_base * Decimal("0.09")  # 27.00
        expected_services_commission = Decimal(str(services_commission_base)) * Decimal("0.15")  # 37.50

        assert expected_products_commission == Decimal(
            "27.00"
        ), f"Комісія з товарів неправильна: {expected_products_commission}"
        assert expected_services_commission == Decimal(
            "37.50"
        ), f"Комісія з послуг неправильна: {expected_services_commission}"

    def test_operation_count_consistency_between_reports(self, app, session, admin_user, test_client, test_product):
        """
        Крок 3.1.3: Тест "кількість_операцій_співпадає_між_звітами"

        Перевіряє, що кількість операцій в різних звітах співпадає.
        """
        # Створюємо методи оплати
        payment_methods = [
            PaymentMethod(name="Готівка", is_active=True),
            PaymentMethod(name="Борг", is_active=True),
            PaymentMethod(name="Приват", is_active=True),
        ]
        session.add_all(payment_methods)
        session.commit()

        test_date = date.today()

        # Створюємо 5 продажів різними способами оплати
        sales_count = 5
        for i in range(sales_count):
            method = payment_methods[i % len(payment_methods)]
            sale = Sale(
                sale_date=datetime.combine(test_date, time(10 + i, 0)),
                client_id=test_client.id,
                user_id=admin_user.id,
                total_amount=Decimal(f"{(i + 1) * 50}.00"),
                payment_method_id=method.id,
                created_by_user_id=admin_user.id,
            )
            session.add(sale)
            session.commit()

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=test_product.id,
                quantity=1,
                price_per_unit=Decimal(f"{(i + 1) * 50}.00"),
                cost_price_per_unit=Decimal(f"{(i + 1) * 25}.00"),
            )
            session.add(sale_item)

        session.commit()

        # Перевіряємо кількість операцій у фінансовому звіті
        financial_sales_count = Sale.query.filter(func.date(Sale.sale_date) == test_date).count()

        # Перевіряємо кількість операцій у звіті зарплати
        salary_sales_count = Sale.query.filter(
            Sale.user_id == admin_user.id, func.date(Sale.sale_date) == test_date
        ).count()

        assert (
            financial_sales_count == sales_count
        ), f"Кількість продажів у фінансовому звіті неправильна: {financial_sales_count}"
        assert (
            salary_sales_count == sales_count
        ), f"Кількість продажів у звіті зарплати неправильна: {salary_sales_count}"
        assert financial_sales_count == salary_sales_count, "Кількість операцій між звітами не співпадає!"

    def test_master_filtering_works_consistently(
        self, app, session, admin_user, regular_user, test_client, test_product, test_service
    ):
        """
        Крок 3.1.4: Тест "фільтрація_за_майстром_працює_однаково"

        Перевіряє, що фільтрація за майстром працює однаково в різних звітах.
        """
        # Створюємо метод оплати
        cash_method = PaymentMethod(name="Готівка", is_active=True)
        session.add(cash_method)
        session.commit()

        test_date = date.today()

        # Створюємо продажі для різних майстрів
        # Продаж admin_user
        admin_sale = Sale(
            sale_date=datetime.combine(test_date, time(10, 0)),
            client_id=test_client.id,
            user_id=admin_user.id,
            total_amount=Decimal("100.00"),
            payment_method_id=cash_method.id,
            created_by_user_id=admin_user.id,
        )
        session.add(admin_sale)
        session.commit()

        admin_sale_item = SaleItem(
            sale_id=admin_sale.id,
            product_id=test_product.id,
            quantity=1,
            price_per_unit=Decimal("100.00"),
            cost_price_per_unit=Decimal("50.00"),
        )
        session.add(admin_sale_item)

        # Продаж regular_user
        regular_sale = Sale(
            sale_date=datetime.combine(test_date, time(11, 0)),
            client_id=test_client.id,
            user_id=regular_user.id,
            total_amount=Decimal("200.00"),
            payment_method_id=cash_method.id,
            created_by_user_id=regular_user.id,
        )
        session.add(regular_sale)
        session.commit()

        regular_sale_item = SaleItem(
            sale_id=regular_sale.id,
            product_id=test_product.id,
            quantity=2,
            price_per_unit=Decimal("100.00"),
            cost_price_per_unit=Decimal("50.00"),
        )
        session.add(regular_sale_item)

        # Створюємо записи для різних майстрів
        admin_appointment = Appointment(
            client_id=test_client.id,
            master_id=admin_user.id,
            date=test_date,
            start_time=time(14, 0),
            end_time=time(15, 0),
            status="completed",
            payment_status="paid",
            amount_paid=Decimal("150.00"),
            payment_method_id=cash_method.id,
        )
        session.add(admin_appointment)
        session.commit()

        admin_app_service = AppointmentService(
            appointment_id=admin_appointment.id, service_id=test_service.id, price=150.0
        )
        session.add(admin_app_service)

        regular_appointment = Appointment(
            client_id=test_client.id,
            master_id=regular_user.id,
            date=test_date,
            start_time=time(16, 0),
            end_time=time(17, 0),
            status="completed",
            payment_status="paid",
            amount_paid=Decimal("300.00"),
            payment_method_id=cash_method.id,
        )
        session.add(regular_appointment)
        session.commit()

        regular_app_service = AppointmentService(
            appointment_id=regular_appointment.id, service_id=test_service.id, price=300.0
        )
        session.add(regular_app_service)
        session.commit()

        # Перевіряємо фільтрацію для admin_user
        admin_sales = Sale.query.filter(Sale.user_id == admin_user.id, func.date(Sale.sale_date) == test_date).all()

        admin_appointments = Appointment.query.filter(
            Appointment.master_id == admin_user.id, Appointment.date == test_date, Appointment.status == "completed"
        ).all()

        # Перевіряємо фільтрацію для regular_user
        regular_sales = Sale.query.filter(Sale.user_id == regular_user.id, func.date(Sale.sale_date) == test_date).all()

        regular_appointments = Appointment.query.filter(
            Appointment.master_id == regular_user.id, Appointment.date == test_date, Appointment.status == "completed"
        ).all()

        # Перевіряємо правильність фільтрації
        assert len(admin_sales) == 1, f"Неправильна кількість продажів admin_user: {len(admin_sales)}"
        assert len(regular_sales) == 1, f"Неправильна кількість продажів regular_user: {len(regular_sales)}"
        assert len(admin_appointments) == 1, f"Неправильна кількість записів admin_user: {len(admin_appointments)}"
        assert (
            len(regular_appointments) == 1
        ), f"Неправильна кількість записів regular_user: {len(regular_appointments)}"

        # Перевіряємо суми
        assert admin_sales[0].total_amount == Decimal("100.00"), "Сума продажу admin_user неправильна"
        assert regular_sales[0].total_amount == Decimal("200.00"), "Сума продажу regular_user неправильна"
        assert admin_appointments[0].amount_paid == Decimal("150.00"), "Сума запису admin_user неправильна"
        assert regular_appointments[0].amount_paid == Decimal("300.00"), "Сума запису regular_user неправильна"


class TestReportDataValidation:
    """Тести валідації даних у звітах"""

    def test_all_completed_appointments_present_in_report(self, app, session, regular_user, test_client, test_service):
        """
        Крок 3.2.1: Тест "всі_завершені_записи_присутні_в_звіті"

        Перевіряє, що всі завершені записи присутні в звітах.
        """
        # Створюємо методи оплати
        cash_method = PaymentMethod(name="Готівка", is_active=True)
        debt_method = PaymentMethod(name="Борг", is_active=True)
        session.add_all([cash_method, debt_method])
        session.commit()

        test_date = date.today()

        # Створюємо записи з різними статусами
        appointments_data = [
            {"status": "scheduled", "payment_status": "unpaid", "amount": Decimal("0.00"), "method": None},
            {"status": "completed", "payment_status": "paid", "amount": Decimal("100.00"), "method": cash_method},
            {"status": "completed", "payment_status": "unpaid", "amount": Decimal("0.00"), "method": debt_method},
            {"status": "cancelled", "payment_status": "unpaid", "amount": Decimal("0.00"), "method": None},
            {"status": "completed", "payment_status": "paid", "amount": Decimal("200.00"), "method": cash_method},
        ]

        created_appointments = []
        for i, data in enumerate(appointments_data):
            appointment = Appointment(
                client_id=test_client.id,
                master_id=regular_user.id,
                date=test_date,
                start_time=time(10 + i, 0),
                end_time=time(11 + i, 0),
                status=data["status"],
                payment_status=data["payment_status"],
                amount_paid=data["amount"],
                payment_method_id=data["method"].id if data["method"] else None,
            )
            session.add(appointment)
            session.commit()

            # Додаємо послугу до кожного запису
            appointment_service = AppointmentService(
                appointment_id=appointment.id,
                service_id=test_service.id,
                price=100.0 + i * 50,  # 100, 150, 200, 250, 300
            )
            session.add(appointment_service)
            created_appointments.append(appointment)

        session.commit()

        # Перевіряємо, що тільки завершені записи враховуються в звітах
        completed_appointments = Appointment.query.filter(
            Appointment.date == test_date, Appointment.status == "completed"
        ).all()

        # Має бути 3 завершених записи (індекси 1, 2, 4)
        assert (
            len(completed_appointments) == 3
        ), f"Неправильна кількість завершених записів: {len(completed_appointments)}"

        # Перевіряємо, що всі завершені записи мають правильні дані
        completed_amounts = [apt.amount_paid for apt in completed_appointments]
        expected_amounts = [Decimal("100.00"), Decimal("0.00"), Decimal("200.00")]

        for expected in expected_amounts:
            assert expected in completed_amounts, f"Завершений запис з сумою {expected} не знайдено"

    def test_all_sales_present_in_report(self, app, session, admin_user, test_client, test_product):
        """
        Крок 3.2.2: Тест "всі_продажі_присутні_в_звіті"

        Перевіряє, що всі продажі присутні в звітах.
        """
        # Створюємо методи оплати
        payment_methods = [
            PaymentMethod(name="Готівка", is_active=True),
            PaymentMethod(name="Борг", is_active=True),
            PaymentMethod(name="Приват", is_active=True),
            PaymentMethod(name="MONO", is_active=True),
        ]
        session.add_all(payment_methods)
        session.commit()

        test_date = date.today()

        # Створюємо продажі різними способами оплати
        sales_data = [
            {"amount": Decimal("50.00"), "method": payment_methods[0]},
            {"amount": Decimal("75.00"), "method": payment_methods[1]},
            {"amount": Decimal("100.00"), "method": payment_methods[2]},
            {"amount": Decimal("125.00"), "method": payment_methods[3]},
            {"amount": Decimal("150.00"), "method": payment_methods[0]},
        ]

        created_sales = []
        for i, data in enumerate(sales_data):
            sale = Sale(
                sale_date=datetime.combine(test_date, time(10 + i, 0)),
                client_id=test_client.id,
                user_id=admin_user.id,
                total_amount=data["amount"],
                payment_method_id=data["method"].id,
                created_by_user_id=admin_user.id,
            )
            session.add(sale)
            session.commit()

            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=test_product.id,
                quantity=1,
                price_per_unit=data["amount"],
                cost_price_per_unit=Decimal(str(data["amount"])) / Decimal("2"),
            )
            session.add(sale_item)
            created_sales.append(sale)

        session.commit()

        # Перевіряємо, що всі продажі присутні в фінансовому звіті
        financial_sales = Sale.query.filter(func.date(Sale.sale_date) == test_date).all()

        assert len(financial_sales) == len(
            sales_data
        ), f"Неправильна кількість продажів у фінансовому звіті: {len(financial_sales)}"

        # Перевіряємо, що всі продажі присутні в звіті зарплати
        salary_sales = Sale.query.filter(Sale.user_id == admin_user.id, func.date(Sale.sale_date) == test_date).all()

        assert len(salary_sales) == len(
            sales_data
        ), f"Неправильна кількість продажів у звіті зарплати: {len(salary_sales)}"

        # Перевіряємо суми
        financial_total = sum(sale.total_amount for sale in financial_sales)
        salary_total = sum(sale.total_amount for sale in salary_sales)
        expected_total = sum(Decimal(str(data["amount"])) for data in sales_data)

        assert financial_total == expected_total, f"Загальна сума у фінансовому звіті неправильна: {financial_total}"
        assert salary_total == expected_total, f"Загальна сума у звіті зарплати неправильна: {salary_total}"

    def test_calculations_are_correct(
        self, app, session, admin_user, regular_user, test_client, test_product, test_service
    ):
        """
        Крок 3.2.3: Тест "розрахунки_сум_правильні"

        Перевіряє правильність всіх розрахунків у звітах.
        """
        # Створюємо метод оплати
        cash_method = PaymentMethod(name="Готівка", is_active=True)
        session.add(cash_method)
        session.commit()

        # Встановлюємо комісії
        if not regular_user.configurable_commission_rate:
            regular_user.configurable_commission_rate = Decimal("20.0")
            session.commit()

        test_date = date.today()

        # Створюємо продаж товару
        sale = Sale(
            sale_date=datetime.combine(test_date, time(10, 0)),
            client_id=test_client.id,
            user_id=regular_user.id,
            total_amount=Decimal("500.00"),
            payment_method_id=cash_method.id,
            created_by_user_id=regular_user.id,
        )
        session.add(sale)
        session.commit()

        sale_item = SaleItem(
            sale_id=sale.id,
            product_id=test_product.id,
            quantity=5,
            price_per_unit=Decimal("100.00"),
            cost_price_per_unit=Decimal("60.00"),
        )
        session.add(sale_item)

        # Створюємо завершений запис
        appointment = Appointment(
            client_id=test_client.id,
            master_id=regular_user.id,
            date=test_date,
            start_time=time(14, 0),
            end_time=time(15, 0),
            status="completed",
            payment_status="paid",
            amount_paid=Decimal("400.00"),
            payment_method_id=cash_method.id,
        )
        session.add(appointment)
        session.commit()

        appointment_service = AppointmentService(appointment_id=appointment.id, service_id=test_service.id, price=400.0)
        session.add(appointment_service)
        session.commit()

        # Розрахунки для фінансового звіту
        # 1. Дохід від товарів
        product_revenue = Decimal("500.00")  # 5 * 100.00
        product_cogs = Decimal("300.00")  # 5 * 60.00
        product_gross_profit = product_revenue - product_cogs  # 200.00

        # 2. Дохід від послуг
        service_revenue = Decimal("400.00")

        # 3. Загальний дохід та прибуток
        total_revenue = product_revenue + service_revenue  # 900.00
        total_gross_profit = service_revenue + product_gross_profit  # 600.00

        # Розрахунки для звіту зарплати
        # 1. Комісія з товарів (9%)
        products_commission = product_revenue * Decimal("0.09")  # 45.00

        # 2. Комісія з послуг (20%)
        services_commission = service_revenue * Decimal("0.20")  # 80.00

        # 3. Загальна зарплата
        total_salary = products_commission + services_commission  # 125.00

        # Перевіряємо розрахунки через запити до БД

        # Фінансовий звіт
        db_product_revenue = (
            db.session.query(func.sum(SaleItem.price_per_unit * SaleItem.quantity))
            .join(Sale)
            .filter(func.date(Sale.sale_date) == test_date)
            .scalar()
        )

        db_product_cogs = (
            db.session.query(func.sum(SaleItem.cost_price_per_unit * SaleItem.quantity))
            .join(Sale)
            .filter(func.date(Sale.sale_date) == test_date)
            .scalar()
        )

        db_service_revenue = (
            db.session.query(func.sum(Appointment.amount_paid))
            .filter(
                Appointment.date == test_date, Appointment.status == "completed", Appointment.amount_paid.isnot(None)
            )
            .scalar()
        )

        # Звіт зарплати
        db_products_commission_base = (
            db.session.query(func.sum(Sale.total_amount))
            .filter(Sale.user_id == regular_user.id, func.date(Sale.sale_date) == test_date)
            .scalar()
        )

        db_services_commission_base = (
            db.session.query(func.sum(AppointmentService.price))
            .join(Appointment)
            .filter(
                Appointment.master_id == regular_user.id,
                Appointment.date == test_date,
                Appointment.status == "completed",
            )
            .scalar()
        )

        # Перевіряємо всі розрахунки
        assert db_product_revenue == product_revenue, f"Дохід від товарів неправильний: {db_product_revenue}"
        assert db_product_cogs == product_cogs, f"Собівартість товарів неправильна: {db_product_cogs}"
        assert db_service_revenue == service_revenue, f"Дохід від послуг неправильний: {db_service_revenue}"
        assert (
            db_products_commission_base == product_revenue
        ), f"База комісії з товарів неправильна: {db_products_commission_base}"
        assert (
            db_services_commission_base == service_revenue
        ), f"База комісії з послуг неправильна: {db_services_commission_base}"

        # Перевіряємо розраховані значення
        calculated_product_gross_profit = db_product_revenue - db_product_cogs
        calculated_total_revenue = db_product_revenue + db_service_revenue
        calculated_total_gross_profit = db_service_revenue + calculated_product_gross_profit
        calculated_products_commission = db_products_commission_base * Decimal("0.09")
        calculated_services_commission = Decimal(str(db_services_commission_base)) * Decimal("0.20")
        calculated_total_salary = calculated_products_commission + calculated_services_commission

        assert (
            calculated_product_gross_profit == product_gross_profit
        ), f"Валовий прибуток від товарів неправильний: {calculated_product_gross_profit}"
        assert calculated_total_revenue == total_revenue, f"Загальний дохід неправильний: {calculated_total_revenue}"
        assert (
            calculated_total_gross_profit == total_gross_profit
        ), f"Загальний валовий прибуток неправильний: {calculated_total_gross_profit}"
        assert (
            calculated_products_commission == products_commission
        ), f"Комісія з товарів неправильна: {calculated_products_commission}"
        assert (
            calculated_services_commission == services_commission
        ), f"Комісія з послуг неправильна: {calculated_services_commission}"
        assert calculated_total_salary == total_salary, f"Загальна зарплата неправильна: {calculated_total_salary}"

    def test_discounts_are_handled_correctly(self, app, session, regular_user, test_client, test_service):
        """
        Крок 3.2.4: Тест "знижки_враховуються_правильно"

        Перевіряє правильність обробки знижок у звітах.
        """
        # Створюємо метод оплати
        cash_method = PaymentMethod(name="Готівка", is_active=True)
        session.add(cash_method)
        session.commit()

        # Встановлюємо комісію майстра
        if not regular_user.configurable_commission_rate:
            regular_user.configurable_commission_rate = Decimal("15.0")
            session.commit()

        test_date = date.today()

        # Створюємо запис зі знижкою
        appointment = Appointment(
            client_id=test_client.id,
            master_id=regular_user.id,
            date=test_date,
            start_time=time(14, 0),
            end_time=time(15, 0),
            status="completed",
            payment_status="paid",
            amount_paid=Decimal("170.00"),  # Після знижки 15%
            payment_method_id=cash_method.id,
            discount_percentage=Decimal("15.0"),  # 15% знижка
        )
        session.add(appointment)
        session.commit()

        appointment_service = AppointmentService(
            appointment_id=appointment.id, service_id=test_service.id, price=200.0  # Початкова ціна до знижки
        )
        session.add(appointment_service)
        session.commit()

        # Перевіряємо обробку знижки

        # 1. Фінансовий звіт повинен враховувати фактично сплачену суму
        service_revenue = (
            db.session.query(func.sum(Appointment.amount_paid))
            .filter(
                Appointment.date == test_date, Appointment.status == "completed", Appointment.amount_paid.isnot(None)
            )
            .scalar()
        )

        assert service_revenue == Decimal("170.00"), f"Дохід від послуг зі знижкою неправильний: {service_revenue}"

        # 2. Звіт зарплати: комісія повинна розраховуватися з повної суми послуг (без знижки)
        services_commission_base = (
            db.session.query(func.sum(AppointmentService.price))
            .join(Appointment)
            .filter(
                Appointment.master_id == regular_user.id,
                Appointment.date == test_date,
                Appointment.status == "completed",
            )
            .scalar()
        )

        assert services_commission_base == Decimal(
            "200.00"
        ), f"База комісії з послуг неправильна: {services_commission_base}"

        # 3. Розрахунок комісії (15% від повної суми)
        expected_commission = Decimal(str(services_commission_base)) * Decimal("0.15")  # 30.00
        assert expected_commission == Decimal(
            "30.00"
        ), f"Комісія з послуг зі знижкою неправильна: {expected_commission}"

        # 4. Перевіряємо, що знижка правильно розрахована
        original_price = Decimal("200.00")
        discount_amount = original_price * (appointment.discount_percentage / Decimal("100"))
        discounted_price = original_price - discount_amount

        assert discount_amount == Decimal("30.00"), f"Сума знижки неправильна: {discount_amount}"
        assert discounted_price == Decimal("170.00"), f"Ціна після знижки неправильна: {discounted_price}"
        assert appointment.amount_paid == discounted_price, "Сплачена сума не відповідає ціні після знижки"
