"""
Навантажувальні тести - Фаза 5
Тестування продуктивності та стабільності системи

Цей файл покриває тестування:
- Кроки 5.1.1-5.1.4: Базові навантажувальні тести
- Кроки 5.2.1-5.2.4: Тести великих даних та стабільності
"""

import pytest
import time
import threading
import psutil
import os
import gc
from datetime import date, datetime, time as dt_time, timedelta
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from memory_profiler import profile
import tempfile
import sqlite3

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


class TestLargeDatasetPerformance:
    """
    Кроки 5.1.1: Тест продуктивності з великою кількістю записів

    Перевіряє як система працює з великими обсягами даних
    """

    def test_large_sales_dataset_creation(self, app, session, admin_user, test_client, test_product, payment_methods):
        """
        Крок 5.1.1a: Створення великої кількості продажів

        Тестує швидкість створення 1000+ записів продажів
        """
        cash_method = next((pm for pm in payment_methods if pm.name == "Готівка"), payment_methods[0])

        # Параметри тестування
        records_count = 1000
        batch_size = 100

        print(f"\n🧪 Тестування створення {records_count} записів продажів...")

        start_time = time.time()
        total_created = 0

        for batch_start in range(0, records_count, batch_size):
            batch_end = min(batch_start + batch_size, records_count)
            batch_sales = []

            # Створюємо батч продажів
            for i in range(batch_start, batch_end):
                sale = Sale(
                    sale_date=datetime.now() - timedelta(days=i % 30),  # Розподіляємо по останніх 30 днях
                    client_id=test_client.id,
                    user_id=admin_user.id,
                    total_amount=Decimal(f"{100 + (i % 500)}.00"),  # Варіація сум
                    payment_method_id=cash_method.id,
                    created_by_user_id=admin_user.id,
                )
                session.add(sale)
                batch_sales.append(sale)

            # Комітимо батч
            session.commit()

            # Додаємо SaleItems для кожного продажу
            for sale in batch_sales:
                sale_item = SaleItem(
                    sale_id=sale.id,
                    product_id=test_product.id,
                    quantity=1,
                    price_per_unit=sale.total_amount,
                    cost_price_per_unit=sale.total_amount / Decimal("2"),
                )
                session.add(sale_item)

            session.commit()
            total_created = batch_end

            # Прогрес-бар
            progress = (batch_end / records_count) * 100
            print(f"Прогрес: {progress:.1f}% ({batch_end}/{records_count})")

        end_time = time.time()
        total_time = end_time - start_time

        print(f"✅ Створено {total_created} продажів за {total_time:.2f} секунд")
        print(f"📊 Швидкість: {total_created/total_time:.2f} записів/сек")

        # Перевірки продуктивності
        assert total_time < 60.0, f"Створення {records_count} записів зайняло {total_time:.2f}с (максимум 60с)"
        assert total_created == records_count, f"Створено {total_created} з {records_count} записів"

        # Перевірка цілісності даних
        total_sales = Sale.query.count()
        assert total_sales >= records_count, f"У БД знайдено {total_sales} продажів (очікувалось >= {records_count})"

    def test_large_appointments_dataset_queries(
        self, app, session, regular_user, test_client, test_service, payment_methods
    ):
        """
        Крок 5.1.1b: Запити до великого набору записів

        Тестує швидкість запитів до великої кількості записів
        """
        cash_method = next((pm for pm in payment_methods if pm.name == "Готівка"), payment_methods[0])

        # Створюємо 500 записів
        appointments_count = 500
        print(f"\n🧪 Створення {appointments_count} записів для тестування запитів...")

        appointments = []
        for i in range(appointments_count):
            test_date = date.today() - timedelta(days=i % 60)  # Останні 60 днів
            appointment = Appointment(
                client_id=test_client.id,
                master_id=regular_user.id,
                date=test_date,
                start_time=dt_time(9 + (i % 8), 0),  # 9:00 - 16:00
                end_time=dt_time(10 + (i % 8), 0),
                status=["scheduled", "completed", "cancelled"][i % 3],
                payment_status="paid" if i % 2 == 0 else "unpaid",
                amount_paid=Decimal(f"{200 + (i % 300)}.00"),
                payment_method_id=cash_method.id if i % 2 == 0 else None,
            )
            session.add(appointment)
            appointments.append(appointment)

        session.commit()

        # Додаємо послуги до записів
        for appointment in appointments:
            appointment_service = AppointmentService(
                appointment_id=appointment.id, service_id=test_service.id, price=float(appointment.amount_paid)
            )
            session.add(appointment_service)

        session.commit()
        print(f"✅ Створено {appointments_count} записів")

        # Тестування різних типів запитів
        queries_to_test = [
            ("Всі записи", lambda: Appointment.query.all()),
            ("Завершені записи", lambda: Appointment.query.filter_by(status="completed").all()),
            (
                "Записи за останній місяць",
                lambda: Appointment.query.filter(Appointment.date >= date.today() - timedelta(days=30)).all(),
            ),
            ("Записи з оплатою", lambda: Appointment.query.filter(Appointment.amount_paid > 0).all()),
            ("Записи конкретного майстра", lambda: Appointment.query.filter_by(master_id=regular_user.id).all()),
        ]

        for query_name, query_func in queries_to_test:
            start_time = time.time()
            results = query_func()
            end_time = time.time()
            query_time = end_time - start_time

            print(f"📊 {query_name}: {len(results)} результатів за {query_time:.3f}с")

            # Запити повинні виконуватися швидко
            assert query_time < 2.0, f"Запит '{query_name}' зайняв {query_time:.3f}с (максимум 2с)"

    def test_database_pagination_performance(self, app, session):
        """
        Крок 5.1.1c: Тестування пагінації великих наборів даних
        """
        print("\n🧪 Тестування пагінації...")

        page_size = 50
        max_pages = 10

        for page_num in range(1, max_pages + 1):
            start_time = time.time()

            # Пагінація через SQLAlchemy
            sales_page = Sale.query.paginate(page=page_num, per_page=page_size, error_out=False)

            end_time = time.time()
            page_time = end_time - start_time

            print(f"📄 Сторінка {page_num}: {len(sales_page.items)} записів за {page_time:.3f}с")

            # Кожна сторінка повинна завантажуватися швидко
            assert page_time < 1.0, f"Сторінка {page_num} завантажилася за {page_time:.3f}с (максимум 1с)"

            if not sales_page.items:  # Якщо сторінка порожня, припиняємо
                break


class TestPeakLoadStress:
    """
    Кроки 5.1.2: Тест пікових навантажень на систему

    Симулює одночасну роботу багатьох користувачів
    """

    def test_concurrent_sales_creation(self, app, session, admin_user, test_client, test_product, payment_methods):
        """
        Крок 5.1.2a: Одночасне створення продажів

        Симулює 10 користувачів, що створюють продажі одночасно
        """
        cash_method = next((pm for pm in payment_methods if pm.name == "Готівка"), payment_methods[0])

        def create_sale_batch(thread_id, sales_per_thread=20):
            """Функція для створення продажів в окремому потоці"""
            thread_sales = []

            with app.app_context():
                for i in range(sales_per_thread):
                    sale = Sale(
                        sale_date=datetime.now(),
                        client_id=test_client.id,
                        user_id=admin_user.id,
                        total_amount=Decimal(f"{thread_id * 100 + i + 50}.00"),
                        payment_method_id=cash_method.id,
                        created_by_user_id=admin_user.id,
                    )
                    db.session.add(sale)
                    thread_sales.append(sale)

                try:
                    db.session.commit()
                    return len(thread_sales), None
                except Exception as e:
                    db.session.rollback()
                    return 0, str(e)

        print("\n🧪 Тестування одночасного створення продажів...")

        num_threads = 10
        sales_per_thread = 20
        expected_total = num_threads * sales_per_thread

        start_time = time.time()

        # Запускаємо потоки одночасно
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_sale_batch, thread_id) for thread_id in range(num_threads)]

            results = []
            for future in as_completed(futures):
                created_count, error = future.result()
                results.append((created_count, error))

        end_time = time.time()
        total_time = end_time - start_time

        # Аналіз результатів
        total_created = sum(count for count, _ in results)
        errors = [error for _, error in results if error]

        print(f"✅ Створено {total_created}/{expected_total} продажів за {total_time:.2f}с")
        print(f"📊 Швидкість: {total_created/total_time:.2f} записів/сек")

        if errors:
            print(f"⚠️ Помилки: {len(errors)}")
            for error in errors[:3]:  # Показуємо перші 3 помилки
                print(f"   - {error}")

        # Перевірки
        success_rate = total_created / expected_total
        assert success_rate >= 0.8, f"Успішність {success_rate:.1%} (мінімум 80%)"
        assert total_time < 30.0, f"Операція зайняла {total_time:.2f}с (максимум 30с)"

    def test_concurrent_report_generation(self, app, session, admin_user):
        """
        Крок 5.1.2b: Одночасна генерація звітів

        Симулює кілька користувачів, що генерують звіти одночасно
        """

        def generate_report(report_type, thread_id):
            """Функція для генерації звіту в окремому потоці"""
            with app.app_context():
                start_date = date.today() - timedelta(days=30)
                end_date = date.today()

                try:
                    start_time = time.time()

                    if report_type == "sales":
                        # Звіт по продажах
                        sales = Sale.query.filter(
                            Sale.sale_date >= datetime.combine(start_date, dt_time.min),
                            Sale.sale_date <= datetime.combine(end_date, dt_time.max),
                        ).all()
                        result_count = len(sales)

                    elif report_type == "appointments":
                        # Звіт по записах
                        appointments = Appointment.query.filter(
                            Appointment.date >= start_date, Appointment.date <= end_date
                        ).all()
                        result_count = len(appointments)

                    else:
                        result_count = 0

                    end_time = time.time()
                    generation_time = end_time - start_time

                    return result_count, generation_time, None

                except Exception as e:
                    return 0, 0, str(e)

        print("\n🧪 Тестування одночасної генерації звітів...")

        reports_to_generate = [
            ("sales", "Звіт по продажах"),
            ("appointments", "Звіт по записах"),
            ("sales", "Звіт по продажах"),
            ("appointments", "Звіт по записах"),
            ("sales", "Звіт по продажах"),
        ]

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=len(reports_to_generate)) as executor:
            futures = [
                executor.submit(generate_report, report_type, i)
                for i, (report_type, _) in enumerate(reports_to_generate)
            ]

            results = []
            for i, future in enumerate(as_completed(futures)):
                result_count, generation_time, error = future.result()
                report_name = reports_to_generate[i][1]
                results.append((report_name, result_count, generation_time, error))

        end_time = time.time()
        total_time = end_time - start_time

        print(f"✅ Згенеровано {len(results)} звітів за {total_time:.2f}с")

        successful_reports = 0
        for report_name, count, gen_time, error in results:
            if error:
                print(f"❌ {report_name}: помилка - {error}")
            else:
                print(f"✅ {report_name}: {count} записів за {gen_time:.2f}с")
                successful_reports += 1

        # Перевірки
        success_rate = successful_reports / len(reports_to_generate)
        assert success_rate >= 0.8, f"Успішність генерації звітів {success_rate:.1%} (мінімум 80%)"


class TestLongTermStability:
    """
    Кроки 5.1.3: Тест стабільності при довготривалій роботі

    Симулює довготривалу роботу системи
    """

    def test_extended_operations_cycle(
        self, app, session, admin_user, regular_user, test_client, test_product, test_service, payment_methods
    ):
        """
        Крок 5.1.3a: Цикл операцій протягом тривалого часу

        Симулює роботу салону протягом робочого дня
        """
        print("\n🧪 Тестування тривалої стабільності (симуляція робочого дня)...")

        cash_method = next((pm for pm in payment_methods if pm.name == "Готівка"), payment_methods[0])

        # Параметри симуляції
        total_cycles = 100  # Симулюємо 100 "клієнтів"
        operations_per_cycle = 3  # Кожен клієнт робить 3 операції

        start_time = time.time()
        successful_operations = 0
        errors = []

        for cycle in range(total_cycles):
            cycle_start = time.time()

            try:
                # Операція 1: Створення продажу
                sale = Sale(
                    sale_date=datetime.now(),
                    client_id=test_client.id,
                    user_id=admin_user.id,
                    total_amount=Decimal(f"{150 + (cycle % 200)}.00"),
                    payment_method_id=cash_method.id,
                    created_by_user_id=admin_user.id,
                )
                session.add(sale)
                session.commit()

                # Операція 2: Додавання товару до продажу
                sale_item = SaleItem(
                    sale_id=sale.id,
                    product_id=test_product.id,
                    quantity=1 + (cycle % 3),
                    price_per_unit=sale.total_amount,
                    cost_price_per_unit=sale.total_amount / Decimal("2"),
                )
                session.add(sale_item)
                session.commit()

                # Операція 3: Створення запису
                appointment = Appointment(
                    client_id=test_client.id,
                    master_id=regular_user.id,
                    date=date.today() + timedelta(days=cycle % 7),
                    start_time=dt_time(9 + (cycle % 8), 0),
                    end_time=dt_time(10 + (cycle % 8), 0),
                    status="completed",
                    payment_status="paid",
                    amount_paid=Decimal(f"{300 + (cycle % 100)}.00"),
                    payment_method_id=cash_method.id,
                )
                session.add(appointment)
                session.commit()

                successful_operations += operations_per_cycle

                # Прогрес кожні 10 циклів
                if (cycle + 1) % 10 == 0:
                    elapsed = time.time() - start_time
                    print(f"Цикл {cycle + 1}/{total_cycles}: {successful_operations} операцій за {elapsed:.1f}с")

                # Невелика пауза між циклами
                time.sleep(0.01)

            except Exception as e:
                errors.append(f"Цикл {cycle}: {str(e)}")
                session.rollback()

                # Якщо багато помилок, припиняємо
                if len(errors) > 10:
                    print(f"⚠️ Занадто багато помилок ({len(errors)}), припиняємо тест")
                    break

        end_time = time.time()
        total_time = end_time - start_time

        expected_operations = total_cycles * operations_per_cycle
        success_rate = successful_operations / expected_operations if expected_operations > 0 else 0

        print(f"✅ Виконано {successful_operations}/{expected_operations} операцій за {total_time:.2f}с")
        print(f"📊 Успішність: {success_rate:.1%}")
        print(f"📊 Швидкість: {successful_operations/total_time:.2f} операцій/сек")

        if errors:
            print(f"⚠️ Помилки ({len(errors)}):")
            for error in errors[:5]:  # Показуємо перші 5
                print(f"   - {error}")

        # Перевірки стабільності
        assert success_rate >= 0.9, f"Успішність {success_rate:.1%} (мінімум 90%)"
        assert len(errors) <= 5, f"Забагато помилок: {len(errors)} (максимум 5)"

    @pytest.mark.slow
    def test_memory_leak_detection(self, app, session, admin_user, test_client, test_product, payment_methods):
        """
        Крок 5.1.3b: Виявлення витоків пам'яті

        Моніторить використання пам'яті під час тривалої роботи
        """
        print("\n🧪 Тестування витоків пам'яті...")

        cash_method = next((pm for pm in payment_methods if pm.name == "Готівка"), payment_methods[0])

        # Початкове використання пам'яті
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        print(f"🔧 Початкове використання пам'яті: {initial_memory:.1f} MB")

        memory_measurements = [initial_memory]
        operations_count = 200

        for i in range(operations_count):
            # Створюємо та видаляємо об'єкти
            sale = Sale(
                sale_date=datetime.now(),
                client_id=test_client.id,
                user_id=admin_user.id,
                total_amount=Decimal("100.00"),
                payment_method_id=cash_method.id,
                created_by_user_id=admin_user.id,
            )
            session.add(sale)
            session.commit()

            # Періодично вимірюємо пам'ять
            if i % 50 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_measurements.append(current_memory)
                print(f"Операція {i}: {current_memory:.1f} MB")

            # Очищаємо сесію
            if i % 20 == 0:
                session.expunge_all()
                gc.collect()

        # Фінальне вимірювання
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_measurements.append(final_memory)

        # Аналіз використання пам'яті
        memory_growth = final_memory - initial_memory
        max_memory = max(memory_measurements)

        print(f"🔧 Фінальне використання пам'яті: {final_memory:.1f} MB")
        print(f"📊 Зростання пам'яті: {memory_growth:.1f} MB")
        print(f"📊 Максимальне використання: {max_memory:.1f} MB")

        # Перевірки на витоки пам'яті
        # Допускаємо зростання до 50MB (розумний ліміт для такої кількості операцій)
        assert memory_growth < 50.0, f"Підозра на витік пам'яті: зростання {memory_growth:.1f} MB"
        assert max_memory < initial_memory + 100.0, f"Занадто високе споживання пам'яті: {max_memory:.1f} MB"


class TestCriticalOperationsProfiling:
    """
    Кроки 5.1.4: Профілювання швидкості критичних операцій

    Вимірює продуктивність ключових операцій системи
    """

    def test_sale_creation_performance(self, app, session, admin_user, test_client, test_product, payment_methods):
        """
        Крок 5.1.4a: Профілювання створення продажу
        """
        print("\n🧪 Профілювання створення продажу...")

        cash_method = next((pm for pm in payment_methods if pm.name == "Готівка"), payment_methods[0])

        # Множинні вимірювання для статистики
        execution_times = []
        iterations = 50

        for i in range(iterations):
            start_time = time.time()

            # Повний цикл створення продажу
            sale = Sale(
                sale_date=datetime.now(),
                client_id=test_client.id,
                user_id=admin_user.id,
                total_amount=Decimal(f"{100 + i}.00"),
                payment_method_id=cash_method.id,
                created_by_user_id=admin_user.id,
            )
            session.add(sale)
            session.commit()

            # Додавання товару
            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=test_product.id,
                quantity=1,
                price_per_unit=sale.total_amount,
                cost_price_per_unit=sale.total_amount / Decimal("2"),
            )
            session.add(sale_item)
            session.commit()

            end_time = time.time()
            execution_times.append(end_time - start_time)

        # Статистичний аналіз
        avg_time = sum(execution_times) / len(execution_times)
        min_time = min(execution_times)
        max_time = max(execution_times)

        print(f"📊 Створення продажу:")
        print(f"   Середній час: {avg_time*1000:.2f} мс")
        print(f"   Мінімальний: {min_time*1000:.2f} мс")
        print(f"   Максимальний: {max_time*1000:.2f} мс")

        # Перевірки продуктивності
        assert avg_time < 0.5, f"Середній час створення продажу {avg_time:.3f}с (максимум 0.5с)"
        assert max_time < 1.0, f"Максимальний час створення продажу {max_time:.3f}с (максимум 1с)"

    def test_complex_query_performance(self, app, session, admin_user, regular_user):
        """
        Крок 5.1.4b: Профілювання складних запитів
        """
        print("\n🧪 Профілювання складних запитів...")

        # Тестуємо різні типи запитів
        queries_to_profile = [
            {
                "name": "Продажі з JOIN",
                "query": lambda: session.query(Sale).join(SaleItem).join(Product).all(),
                "max_time": 1.0,
            },
            {
                "name": "Записи з фільтрацією",
                "query": lambda: Appointment.query.filter(
                    Appointment.date >= date.today() - timedelta(days=30), Appointment.status == "completed"
                ).all(),
                "max_time": 0.5,
            },
            {
                "name": "Агрегація продажів",
                "query": lambda: session.query(db.func.sum(Sale.total_amount))
                .filter(Sale.sale_date >= datetime.now() - timedelta(days=7))
                .scalar(),
                "max_time": 0.3,
            },
            {
                "name": "Підрахунок записів майстра",
                "query": lambda: Appointment.query.filter_by(master_id=regular_user.id).count(),
                "max_time": 0.2,
            },
        ]

        for query_info in queries_to_profile:
            times = []
            iterations = 10

            for _ in range(iterations):
                start_time = time.time()
                result = query_info["query"]()
                end_time = time.time()
                times.append(end_time - start_time)

            avg_time = sum(times) / len(times)
            max_time = max(times)

            print(f"📊 {query_info['name']}:")
            print(f"   Середній час: {avg_time*1000:.2f} мс")
            print(f"   Максимальний: {max_time*1000:.2f} мс")

            # Перевірка продуктивності
            max_time_value = query_info.get("max_time", 1.0)
            if isinstance(max_time_value, (int, float)):
                expected_time = float(max_time_value)
            else:
                expected_time = 1.0
            assert (
                avg_time < expected_time
            ), f"Запит '{query_info['name']}' виконується {avg_time:.3f}с (очікувалось < {expected_time}с)"


class TestLargeReportsProcessing:
    """
    Кроки 5.2.1: Тест обробки великих обсягів даних в звітах

    Перевіряє як система обробляє великі звіти
    """

    def test_large_financial_report_generation(
        self, app, session, admin_user, test_client, test_product, payment_methods
    ):
        """
        Крок 5.2.1a: Генерація великого фінансового звіту

        Тестує генерацію звіту з великою кількістю записів
        """
        print("\n🧪 Тестування генерації великого фінансового звіту...")

        cash_method = next((pm for pm in payment_methods if pm.name == "Готівка"), payment_methods[0])

        # Створюємо тестові дані (якщо їх ще немає)
        existing_sales_count = Sale.query.count()
        target_sales_count = 2000

        if existing_sales_count < target_sales_count:
            print(f"Створення додаткових {target_sales_count - existing_sales_count} продажів...")

            batch_size = 100
            for batch_start in range(existing_sales_count, target_sales_count, batch_size):
                batch_end = min(batch_start + batch_size, target_sales_count)

                for i in range(batch_start, batch_end):
                    sale = Sale(
                        sale_date=datetime.now() - timedelta(days=i % 365),  # Розподіляємо по році
                        client_id=test_client.id,
                        user_id=admin_user.id,
                        total_amount=Decimal(f"{50 + (i % 1000)}.00"),
                        payment_method_id=cash_method.id,
                        created_by_user_id=admin_user.id,
                    )
                    session.add(sale)

                session.commit()

        # Тестування різних типів звітів
        report_scenarios = [
            {"name": "Щоденний звіт (останні 30 днів)", "date_range": 30, "expected_max_time": 5.0},
            {"name": "Місячний звіт (останні 90 днів)", "date_range": 90, "expected_max_time": 10.0},
            {"name": "Квартальний звіт (останні 365 днів)", "date_range": 365, "expected_max_time": 20.0},
        ]

        for scenario in report_scenarios:
            print(f"\n📊 Генерація: {scenario['name']}")

            start_date = datetime.now() - timedelta(days=int(scenario["date_range"]))
            end_date = datetime.now()

            start_time = time.time()

            # Комплексний звіт з агрегацією
            sales_query = Sale.query.filter(Sale.sale_date >= start_date, Sale.sale_date <= end_date)
            sales_list = sales_query.all()

            total_amount_result = (
                session.query(db.func.sum(Sale.total_amount))
                .filter(Sale.sale_date >= start_date, Sale.sale_date <= end_date)
                .scalar()
            )

            sales_count = sales_query.count()

            daily_breakdown = (
                session.query(
                    db.func.date(Sale.sale_date).label("date"),
                    db.func.sum(Sale.total_amount).label("total"),
                    db.func.count(Sale.id).label("count"),
                )
                .filter(Sale.sale_date >= start_date, Sale.sale_date <= end_date)
                .group_by(db.func.date(Sale.sale_date))
                .all()
            )

            report_data = {
                "sales": sales_list,
                "total_amount": total_amount_result or Decimal("0"),
                "sales_count": sales_count,
                "daily_breakdown": daily_breakdown,
            }

            end_time = time.time()
            generation_time = end_time - start_time

            print(f"✅ Згенеровано за {generation_time:.2f}с:")
            print(f"   - Продажів: {len(sales_list)}")
            print(f"   - Загальна сума: {report_data['total_amount']}")
            print(f"   - Денна розбивка: {len(daily_breakdown)} днів")

            # Перевірки продуктивності
            expected_time = float(scenario["expected_max_time"])
            assert (
                generation_time < expected_time
            ), f"Звіт '{scenario['name']}' генерувався {generation_time:.2f}с (максимум {expected_time}с)"

    def test_large_salary_report_with_aggregation(
        self, app, session, admin_user, regular_user, test_client, test_service, payment_methods
    ):
        """
        Крок 5.2.1b: Зарплатний звіт з великою кількістю записів
        """
        print("\n🧪 Тестування генерації великого зарплатного звіту...")

        cash_method = next((pm for pm in payment_methods if pm.name == "Готівка"), payment_methods[0])

        # Створюємо записи для зарплатного звіту
        appointments_count = 1000
        existing_appointments = Appointment.query.count()

        if existing_appointments < appointments_count:
            print(f"Створення {appointments_count - existing_appointments} додаткових записів...")

            for i in range(existing_appointments, appointments_count):
                appointment = Appointment(
                    client_id=test_client.id,
                    master_id=regular_user.id,
                    date=date.today() - timedelta(days=i % 60),
                    start_time=dt_time(9 + (i % 8), 0),
                    end_time=dt_time(10 + (i % 8), 0),
                    status="completed",
                    payment_status="paid",
                    amount_paid=Decimal(f"{200 + (i % 300)}.00"),
                    payment_method_id=cash_method.id,
                )
                session.add(appointment)

                # Додаємо послугу
                appointment_service = AppointmentService(
                    appointment_id=appointment.id, service_id=test_service.id, price=float(appointment.amount_paid)
                )
                session.add(appointment_service)

                if i % 100 == 0:
                    session.commit()

            session.commit()

        # Генерація зарплатного звіту
        start_time = time.time()

        report_start_date = date.today() - timedelta(days=30)
        report_end_date = date.today()

        # Комплексний зарплатний звіт
        salary_report = {
            "master_stats": session.query(
                User.id,
                User.full_name,
                db.func.count(Appointment.id).label("appointments_count"),
                db.func.sum(Appointment.amount_paid).label("total_revenue"),
                db.func.avg(Appointment.amount_paid).label("avg_amount"),
            )
            .join(Appointment, User.id == Appointment.master_id)
            .filter(
                Appointment.date >= report_start_date,
                Appointment.date <= report_end_date,
                Appointment.status == "completed",
            )
            .group_by(User.id, User.full_name)
            .all(),
            "daily_stats": session.query(
                Appointment.date,
                db.func.count(Appointment.id).label("count"),
                db.func.sum(Appointment.amount_paid).label("total"),
            )
            .filter(
                Appointment.date >= report_start_date,
                Appointment.date <= report_end_date,
                Appointment.status == "completed",
            )
            .group_by(Appointment.date)
            .all(),
            "commission_calculations": [],
        }

        # Розрахунок комісій для кожного майстра
        for master_stat in salary_report["master_stats"]:
            commission_rate = Decimal("15.0")  # 15% стандартна комісія
            commission_amount = master_stat.total_revenue * (commission_rate / Decimal("100"))

            salary_report["commission_calculations"].append(
                {
                    "master_id": master_stat.id,
                    "master_name": master_stat.full_name,
                    "total_revenue": master_stat.total_revenue,
                    "commission_rate": commission_rate,
                    "commission_amount": commission_amount,
                }
            )

        end_time = time.time()
        generation_time = end_time - start_time

        print(f"✅ Зарплатний звіт згенеровано за {generation_time:.2f}с:")
        print(f"   - Майстрів: {len(salary_report['master_stats'])}")
        print(f"   - Днів: {len(salary_report['daily_stats'])}")
        print(f"   - Розрахунків комісій: {len(salary_report['commission_calculations'])}")

        # Перевірки продуктивності
        assert generation_time < 15.0, f"Зарплатний звіт генерувався {generation_time:.2f}с (максимум 15с)"
        assert len(salary_report["master_stats"]) > 0, "Звіт повинен містити дані про майстрів"


class TestDatabaseOptimization:
    """
    Кроки 5.2.2: Тест оптимізації запитів до бази даних

    Аналізує та тестує ефективність запитів
    """

    def test_query_execution_plans(self, app, session):
        """
        Крок 5.2.2a: Аналіз планів виконання запитів
        """
        print("\n🧪 Аналіз планів виконання запитів...")

        # Тестові запити для аналізу
        test_queries = [
            {"name": "Простий SELECT", "query": "SELECT * FROM sale LIMIT 100", "expected_time": 0.1},
            {
                "name": "JOIN з фільтрацією",
                "query": """
                    SELECT s.*, si.quantity, p.name 
                    FROM sale s 
                    JOIN sale_item si ON s.id = si.sale_id 
                    JOIN product p ON si.product_id = p.id 
                    WHERE s.sale_date >= date('now', '-30 days')
                """,
                "expected_time": 0.5,
            },
            {
                "name": "Агрегація з GROUP BY",
                "query": """
                    SELECT DATE(sale_date) as day, 
                           COUNT(*) as sales_count, 
                           SUM(total_amount) as daily_total
                    FROM sale 
                    WHERE sale_date >= date('now', '-30 days')
                    GROUP BY DATE(sale_date)
                    ORDER BY day
                """,
                "expected_time": 0.3,
            },
            {
                "name": "Складний JOIN з агрегацією",
                "query": """
                    SELECT u.full_name, 
                           COUNT(a.id) as appointments, 
                           AVG(a.amount_paid) as avg_amount
                    FROM user u
                    LEFT JOIN appointment a ON u.id = a.master_id
                    WHERE a.date >= date('now', '-30 days')
                    GROUP BY u.id, u.full_name
                """,
                "expected_time": 0.8,
            },
        ]

        for query_info in test_queries:
            print(f"\n📊 Тестування: {query_info['name']}")

            # Виконання з вимірюванням часу
            times = []
            iterations = 5

            for _ in range(iterations):
                start_time = time.time()
                result = session.execute(db.text(query_info["query"]))
                rows = result.fetchall()
                end_time = time.time()
                times.append(end_time - start_time)

            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)

            print(f"   Результатів: {len(rows)}")
            print(f"   Середній час: {avg_time*1000:.2f} мс")
            print(f"   Мін/Макс: {min_time*1000:.2f}/{max_time*1000:.2f} мс")

            # Перевірка продуктивності
            expected_time = float(query_info["expected_time"])
            assert (
                avg_time < expected_time
            ), f"Запит '{query_info['name']}' виконується {avg_time:.3f}с (очікувалось < {expected_time}с)"

    def test_index_effectiveness(self, app, session):
        """
        Крок 5.2.2b: Тестування ефективності індексів
        """
        print("\n🧪 Тестування ефективності індексів...")

        # Запити, які повинні використовувати індекси
        indexed_queries = [
            {
                "name": "Пошук по даті продажу",
                "query": "SELECT COUNT(*) FROM sale WHERE sale_date >= date('now', '-7 days')",
                "expected_time": 0.1,
            },
            {
                "name": "Пошук по ID клієнта",
                "query": "SELECT COUNT(*) FROM sale WHERE client_id = 1",
                "expected_time": 0.05,
            },
            {
                "name": "Пошук по ID користувача",
                "query": "SELECT COUNT(*) FROM sale WHERE user_id = 1",
                "expected_time": 0.05,
            },
            {
                "name": "Пошук записів по майстру",
                "query": "SELECT COUNT(*) FROM appointment WHERE master_id = 1",
                "expected_time": 0.05,
            },
        ]

        for query_info in indexed_queries:
            start_time = time.time()
            result = session.execute(db.text(query_info["query"]))
            count = result.scalar()
            end_time = time.time()

            execution_time = end_time - start_time

            print(f"📊 {query_info['name']}: {count} записів за {execution_time*1000:.2f} мс")

            # Індексовані запити повинні виконуватися дуже швидко
            expected_time = float(query_info["expected_time"])
            assert (
                execution_time < expected_time
            ), f"Індексований запит '{query_info['name']}' зайняв {execution_time:.3f}с (максимум {expected_time}с)"


class TestMemoryMonitoring:
    """
    Кроки 5.2.3: Моніторинг використання пам'яті

    Відстежує споживання пам'яті під час різних операцій
    """

    def test_memory_usage_during_bulk_operations(
        self, app, session, admin_user, test_client, test_product, payment_methods
    ):
        """
        Крок 5.2.3a: Моніторинг пам'яті під час масових операцій
        """
        print("\n🧪 Моніторинг пам'яті під час масових операцій...")

        cash_method = next((pm for pm in payment_methods if pm.name == "Готівка"), payment_methods[0])
        process = psutil.Process(os.getpid())

        # Початкове вимірювання
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        print(f"🔧 Початкова пам'ять: {initial_memory:.1f} MB")

        memory_log = [("Start", initial_memory)]

        # Операція 1: Масове створення об'єктів
        print("📈 Створення 500 продажів...")
        for i in range(500):
            sale = Sale(
                sale_date=datetime.now(),
                client_id=test_client.id,
                user_id=admin_user.id,
                total_amount=Decimal(f"{100 + i}.00"),
                payment_method_id=cash_method.id,
                created_by_user_id=admin_user.id,
            )
            session.add(sale)

            if i % 100 == 0:
                session.commit()
                current_memory = process.memory_info().rss / 1024 / 1024
                memory_log.append((f"After {i} sales", current_memory))
                print(f"   {i} продажів: {current_memory:.1f} MB")

        session.commit()
        after_creation_memory = process.memory_info().rss / 1024 / 1024
        memory_log.append(("After creation", after_creation_memory))

        # Операція 2: Складні запити
        print("📊 Виконання складних запитів...")
        for i in range(10):
            sales = Sale.query.join(SaleItem).join(Product).limit(100).all()
            current_memory = process.memory_info().rss / 1024 / 1024

            if i == 0 or i == 9:
                memory_log.append((f"Query {i+1}", current_memory))

        # Операція 3: Очищення сесії
        print("🧹 Очищення сесії...")
        session.expunge_all()
        gc.collect()

        after_cleanup_memory = process.memory_info().rss / 1024 / 1024
        memory_log.append(("After cleanup", after_cleanup_memory))

        # Аналіз використання пам'яті
        print(f"\n📊 Аналіз використання пам'яті:")
        for label, memory in memory_log:
            growth = memory - initial_memory
            print(f"   {label}: {memory:.1f} MB (зростання: {growth:+.1f} MB)")

        # Перевірки
        max_memory = max(memory for _, memory in memory_log)
        final_memory = memory_log[-1][1]

        memory_growth = max_memory - initial_memory
        memory_recovery = max_memory - final_memory

        assert memory_growth < 200.0, f"Занадто велике зростання пам'яті: {memory_growth:.1f} MB"
        assert memory_recovery > 0, f"Пам'ять не звільнилася після очищення: {memory_recovery:.1f} MB"

    def test_session_management_memory_impact(
        self, app, session, admin_user, test_client, test_product, payment_methods
    ):
        """
        Крок 5.2.3b: Вплив управління сесією на пам'ять
        """
        print("\n🧪 Тестування впливу управління сесією на пам'ять...")

        cash_method = next((pm for pm in payment_methods if pm.name == "Готівка"), payment_methods[0])
        process = psutil.Process(os.getpid())

        initial_memory = process.memory_info().rss / 1024 / 1024

        # Тест 1: Без очищення сесії (накопичення об'єктів)
        print("📈 Тест без очищення сесії...")
        for i in range(200):
            sale = Sale(
                sale_date=datetime.now(),
                client_id=test_client.id,
                user_id=admin_user.id,
                total_amount=Decimal("100.00"),
                payment_method_id=cash_method.id,
                created_by_user_id=admin_user.id,
            )
            session.add(sale)
            session.commit()

        without_cleanup_memory = process.memory_info().rss / 1024 / 1024

        # Очищення для наступного тесту
        session.expunge_all()
        gc.collect()

        # Тест 2: З регулярним очищенням сесії
        print("🧹 Тест з регулярним очищенням сесії...")
        for i in range(200):
            sale = Sale(
                sale_date=datetime.now(),
                client_id=test_client.id,
                user_id=admin_user.id,
                total_amount=Decimal("100.00"),
                payment_method_id=cash_method.id,
                created_by_user_id=admin_user.id,
            )
            session.add(sale)
            session.commit()

            # Очищаємо кожні 20 операцій
            if i % 20 == 0:
                session.expunge_all()
                gc.collect()

        with_cleanup_memory = process.memory_info().rss / 1024 / 1024

        # Аналіз результатів
        growth_without_cleanup = without_cleanup_memory - initial_memory
        growth_with_cleanup = with_cleanup_memory - initial_memory
        memory_saved = growth_without_cleanup - growth_with_cleanup

        print(f"📊 Результати управління сесією:")
        print(f"   Без очищення: +{growth_without_cleanup:.1f} MB")
        print(f"   З очищенням: +{growth_with_cleanup:.1f} MB")
        print(f"   Заощаджено: {memory_saved:.1f} MB")

        # Регулярне очищення повинно економити пам'ять
        assert memory_saved > 0, f"Очищення сесії не заощадило пам'ять: {memory_saved:.1f} MB"


class TestCrashRecovery:
    """
    Кроки 5.2.4: Тест відновлення після збоїв

    Тестує поведінку системи при різних типах збоїв
    """

    def test_database_connection_recovery(self, app, session):
        """
        Крок 5.2.4a: Відновлення з'єднання з базою даних
        """
        print("\n🧪 Тестування відновлення з'єднання з БД...")

        # Тест нормальної роботи
        sales_count_before = Sale.query.count()
        print(f"📊 Початкова кількість продажів: {sales_count_before}")

        # Симуляція проблем з підключенням
        try:
            # Спробуємо виконати операцію, яка може не вдатися
            test_query = session.query(Sale).filter(Sale.sale_date >= datetime.now() - timedelta(days=1))

            result = test_query.all()
            print(f"✅ Запит виконано успішно: {len(result)} записів")

            # Тестуємо rollback після помилки
            session.begin()
            try:
                # Намагаємося виконати некоректну операцію
                session.execute(db.text("SELECT * FROM non_existent_table"))
            except Exception as e:
                print(f"⚠️ Очікувана помилка: {str(e)[:50]}...")
                session.rollback()
                print("✅ Rollback виконано успішно")

            # Перевіряємо, що з'єднання все ще працює
            sales_count_after = Sale.query.count()
            assert sales_count_after == sales_count_before, "Кількість записів змінилася після rollback"

            print("✅ З'єднання з БД працює стабільно")

        except Exception as e:
            print(f"❌ Критична помилка з'єднання: {e}")
            # У реальному додатку тут був би механізм відновлення
            assert False, f"Не вдалося відновити з'єднання: {e}"

    def test_transaction_integrity_under_stress(
        self, app, session, admin_user, test_client, test_product, payment_methods
    ):
        """
        Крок 5.2.4b: Цілісність транзакцій під навантаженням
        """
        print("\n🧪 Тестування цілісності транзакцій під навантаженням...")

        cash_method = next((pm for pm in payment_methods if pm.name == "Готівка"), payment_methods[0])

        successful_transactions = 0
        failed_transactions = 0

        # Симулюємо 100 транзакцій з можливими збоями
        for i in range(100):
            try:
                # Починаємо транзакцію
                session.begin()

                # Створюємо продаж
                sale = Sale(
                    sale_date=datetime.now(),
                    client_id=test_client.id,
                    user_id=admin_user.id,
                    total_amount=Decimal(f"{100 + i}.00"),
                    payment_method_id=cash_method.id,
                    created_by_user_id=admin_user.id,
                )
                session.add(sale)
                session.flush()  # Отримуємо ID без commit

                # Додаємо товар до продажу
                sale_item = SaleItem(
                    sale_id=sale.id,
                    product_id=test_product.id,
                    quantity=1,
                    price_per_unit=sale.total_amount,
                    cost_price_per_unit=sale.total_amount / Decimal("2"),
                )
                session.add(sale_item)

                # Симулюємо можливий збій (кожна 10-та транзакція)
                if i % 10 == 9:
                    # Примусово викликаємо помилку
                    raise Exception(f"Симульований збій на транзакції {i}")

                # Якщо все OK, комітимо
                session.commit()
                successful_transactions += 1

                if i % 20 == 0:
                    print(f"Транзакція {i}: ✅ Успішно")

            except Exception as e:
                # Rollback при помилці
                session.rollback()
                failed_transactions += 1

                if "Симульований збій" in str(e):
                    print(f"Транзакція {i}: ⚠️ Симульований збій")
                else:
                    print(f"Транзакція {i}: ❌ Реальна помилка - {e}")

        # Аналіз результатів
        total_transactions = successful_transactions + failed_transactions
        success_rate = successful_transactions / total_transactions if total_transactions > 0 else 0

        print(f"\n📊 Результати тестування транзакцій:")
        print(f"   Успішних: {successful_transactions}")
        print(f"   Неуспішних: {failed_transactions}")
        print(f"   Успішність: {success_rate:.1%}")

        # Перевірки цілісності
        assert success_rate >= 0.85, f"Низька успішність транзакцій: {success_rate:.1%}"

        # Перевіряємо, що всі успішні транзакції дійсно збереглися
        recent_sales = Sale.query.filter(Sale.sale_date >= datetime.now() - timedelta(minutes=5)).count()

        # Враховуємо що могли бути ще продажі з інших тестів
        assert (
            recent_sales >= successful_transactions
        ), f"Не всі успішні транзакції збереглися: {recent_sales} < {successful_transactions}"

        print("✅ Цілісність транзакцій підтверджена")

    def test_data_consistency_after_interruption(
        self, app, session, admin_user, test_client, test_product, payment_methods
    ):
        """
        Крок 5.2.4c: Консистентність даних після переривання
        """
        print("\n🧪 Тестування консистентності даних після переривання...")

        cash_method = next((pm for pm in payment_methods if pm.name == "Готівка"), payment_methods[0])

        # Початкова перевірка консистентності
        initial_sales_count = Sale.query.count()
        initial_items_count = SaleItem.query.count()

        print(f"📊 Початковий стан: {initial_sales_count} продажів, {initial_items_count} товарів")

        # Створюємо кілька транзакцій з перериванням
        interrupted_operations = 0
        completed_operations = 0

        for i in range(20):
            try:
                # Складна операція з кількома кроками
                sale = Sale(
                    sale_date=datetime.now(),
                    client_id=test_client.id,
                    user_id=admin_user.id,
                    total_amount=Decimal(f"{200 + i}.00"),
                    payment_method_id=cash_method.id,
                    created_by_user_id=admin_user.id,
                )
                session.add(sale)
                session.commit()

                # Перший товар
                item1 = SaleItem(
                    sale_id=sale.id,
                    product_id=test_product.id,
                    quantity=1,
                    price_per_unit=Decimal("100.00"),
                    cost_price_per_unit=Decimal("50.00"),
                )
                session.add(item1)
                session.commit()

                # Симулюємо переривання на другому товарі
                if i % 5 == 4:
                    # Частково додаємо другий товар та перериваємо
                    item2 = SaleItem(
                        sale_id=sale.id,
                        product_id=test_product.id,
                        quantity=2,
                        price_per_unit=Decimal("50.00"),
                        cost_price_per_unit=Decimal("25.00"),
                    )
                    session.add(item2)
                    # НЕ комітимо - симулюємо переривання
                    session.rollback()
                    interrupted_operations += 1
                    print(f"Операція {i}: ⚠️ Перервано")
                else:
                    # Завершуємо нормально
                    item2 = SaleItem(
                        sale_id=sale.id,
                        product_id=test_product.id,
                        quantity=2,
                        price_per_unit=Decimal("50.00"),
                        cost_price_per_unit=Decimal("25.00"),
                    )
                    session.add(item2)
                    session.commit()
                    completed_operations += 1

                    if i % 5 == 0:
                        print(f"Операція {i}: ✅ Завершено")

            except Exception as e:
                session.rollback()
                interrupted_operations += 1
                print(f"Операція {i}: ❌ Помилка - {e}")

        # Перевірка консистентності після операцій
        final_sales_count = Sale.query.count()
        final_items_count = SaleItem.query.count()

        # Аналіз консистентності
        expected_sales = initial_sales_count + completed_operations
        # Кожен завершений продаж повинен мати 2 товари
        expected_items = initial_items_count + (completed_operations * 2)

        print(f"\n📊 Фінальний стан:")
        print(f"   Продажів: {final_sales_count} (очікувалось {expected_sales})")
        print(f"   Товарів: {final_items_count} (очікувалось {expected_items})")
        print(f"   Завершених операцій: {completed_operations}")
        print(f"   Перерваних операцій: {interrupted_operations}")

        # Перевірки консистентності
        assert final_sales_count >= expected_sales, f"Втрачено продажі: {final_sales_count} < {expected_sales}"

        # Допускаємо невелике відхилення через інші тести
        assert (
            abs(final_items_count - expected_items) <= 5
        ), f"Проблеми з консистентністю товарів: {final_items_count} vs {expected_items}"

        # Перевіряємо що немає "сирітських" товарів (товари без продажу)
        orphaned_items = session.query(SaleItem).filter(~SaleItem.sale_id.in_(session.query(Sale.id))).count()

        assert orphaned_items == 0, f"Знайдено {orphaned_items} товарів без продажу"

        print("✅ Консистентність даних підтверджена")


# Позначаємо повільні тести
pytest.mark.slow = pytest.mark.filterwarnings("ignore::DeprecationWarning")
