#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Діагностичний скрипт для проблеми з відображенням методів оплати у формі
"""

import os
import sys
import inspect
import traceback

# Додаємо кореневу директорію проекту до Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def print_section_header(title):
    """Виводить заголовок секції з рамкою"""
    print(f"\n{'='*50}")
    print(f"=== {title} ===")
    print(f"{'='*50}")


def print_subsection_header(title):
    """Виводить заголовок підсекції"""
    print(f"\n--- {title} ---")


def safe_getattr(obj, attr, default="ATTRIBUTE_NOT_FOUND"):
    """Безпечно отримує атрибут об'єкта"""
    try:
        return getattr(obj, attr, default)
    except Exception as e:
        return f"ERROR_ACCESSING_ATTRIBUTE: {e}"


def main():
    print_section_header("ДІАГНОСТИКА МЕТОДІВ ОПЛАТИ")
    print("Дата/час запуску:", __import__("datetime").datetime.now())

    try:
        # Спробуємо створити Flask додаток
        print_subsection_header("Ініціалізація Flask додатку")

        from app import create_app, db

        app = create_app()

        with app.app_context():
            print("✓ Flask додаток успішно ініціалізовано")
            print("✓ App context активовано")

            # 1. Виведення визначення моделі PaymentMethod
            print_section_header("Model Definition: PaymentMethod")

            try:
                from app.models import PaymentMethod

                # Отримуємо вихідний код класу
                try:
                    source = inspect.getsource(PaymentMethod)
                    print("Визначення класу PaymentMethod:")
                    print(source)
                except Exception as e:
                    print(f"Не вдалось отримати вихідний код: {e}")

                # Виводимо атрибути класу
                print("\nАтрибути класу PaymentMethod:")
                for attr in dir(PaymentMethod):
                    if not attr.startswith("_"):
                        try:
                            attr_value = getattr(PaymentMethod, attr)
                            attr_type = type(attr_value).__name__
                            print(f"  {attr}: {attr_type}")
                        except Exception as e:
                            print(f"  {attr}: ERROR - {e}")

                # Перевіряємо наявність поля is_default
                has_is_default = hasattr(PaymentMethod, "is_default")
                print(f"\nНаявність поля 'is_default': {has_is_default}")

                # Отримуємо колонки таблиці
                try:
                    table = PaymentMethod.__table__
                    print(f"\nКолонки таблиці {table.name}:")
                    for column in table.columns:
                        print(f"  {column.name}: {column.type} (nullable={column.nullable}, default={column.default})")
                except Exception as e:
                    print(f"Помилка при отриманні інформації про таблицю: {e}")

            except ImportError as e:
                print(f"Помилка імпорту PaymentMethod: {e}")

            # 2. Діагностика даних PaymentMethod з БД
            print_section_header("DB Query: All PaymentMethods")

            try:
                from app.models import PaymentMethod

                all_payment_methods = PaymentMethod.query.all()
                print(f"Кількість записів у таблиці PaymentMethod: {len(all_payment_methods)}")

                print("\nВсі записи PaymentMethod:")
                for pm in all_payment_methods:
                    pm_id = safe_getattr(pm, "id")
                    pm_name = safe_getattr(pm, "name")
                    pm_is_active = safe_getattr(pm, "is_active")
                    print(f"  ID: {pm_id}, Name: '{pm_name}', Active: {pm_is_active}")

            except Exception as e:
                print(f"Помилка при отриманні всіх PaymentMethod: {e}")
                traceback.print_exc()

            print_section_header("DB Query: Active PaymentMethods")

            try:
                from app.models import PaymentMethod

                active_payment_methods = PaymentMethod.query.filter_by(is_active=True).all()
                print(f"Кількість активних записів PaymentMethod: {len(active_payment_methods)}")

                print("\nАктивні записи PaymentMethod:")
                for pm in active_payment_methods:
                    pm_id = safe_getattr(pm, "id")
                    pm_name = safe_getattr(pm, "name")
                    print(f"  ID: {pm_id}, Name: '{pm_name}'")

            except Exception as e:
                print(f"Помилка при отриманні активних PaymentMethod: {e}")
                traceback.print_exc()

            # 3. Діагностика AppointmentForm
            print_section_header("Form Diagnosis: AppointmentForm")

            try:
                # Імпортуємо необхідні класи
                from app.models import PaymentMethod as PaymentMethodModel
                from app.models import Appointment, Client, User, Service

                print("✓ Успішно імпортовано PaymentMethodModel")

                # Створюємо test request context для тестування форм
                print_subsection_header("Form Init: створення request context")

                with app.test_request_context():
                    print("✓ Test request context створено")

                    # Вимикаємо CSRF для тестування
                    app.config["WTF_CSRF_ENABLED"] = False

                    try:
                        from app.routes.appointments import AppointmentForm

                        print("✓ Успішно імпортовано AppointmentForm")

                        # Спробуємо створити форму без obj
                        form = AppointmentForm()
                        print("✓ AppointmentForm створено успішно (без obj)")

                    except Exception as e:
                        print(f"Помилка при створенні AppointmentForm: {e}")
                        traceback.print_exc()
                        form = None

                    if form:
                        # Діагностуємо отримання активних методів оплати в формі
                        print_subsection_header("Form Init: active_payment_methods logic")

                        try:
                            # Імітуємо логіку з __init__ методу форми
                            active_payment_methods = (
                                PaymentMethodModel.query.filter_by(is_active=True)
                                .order_by(PaymentMethodModel.name)
                                .all()
                            )

                            print(f"Кількість активних методів оплати для форми: {len(active_payment_methods)}")

                            print("Активні методи оплати для форми:")
                            for pm in active_payment_methods:
                                pm_id = safe_getattr(pm, "id")
                                pm_name = safe_getattr(pm, "name")
                                pm_is_active = safe_getattr(pm, "is_active")
                                print(f"  ID: {pm_id}, Name: '{pm_name}', Active: {pm_is_active}")

                        except Exception as e:
                            print(f"Помилка при отриманні активних методів оплати для форми: {e}")
                            traceback.print_exc()

                        # Виводимо фінальні choices
                        print_subsection_header("Form Init: final choices")

                        try:
                            choices = form.payment_method.choices
                            print(f"Кількість choices у form.payment_method: {len(choices) if choices else 0}")
                            print("form.payment_method.choices:")
                            if choices:
                                for choice in choices:
                                    print(f"  {choice}")
                            else:
                                print("  CHOICES IS EMPTY OR NONE")

                        except Exception as e:
                            print(f"Помилка при отриманні choices: {e}")
                            traceback.print_exc()

                        # Виводимо початкове значення form data
                        print_subsection_header("Form Init: initial data")

                        try:
                            data = form.payment_method.data
                            print(f"form.payment_method.data: {data}")

                        except Exception as e:
                            print(f"Помилка при отриманні data: {e}")
                            traceback.print_exc()

                    # Тест з існуючим об'єктом Appointment
                    print_subsection_header("Form Init: тест з існуючим appointment")

                    try:
                        # Знаходимо будь-який існуючий appointment
                        existing_appointment = Appointment.query.first()

                        if existing_appointment:
                            print(f"Знайдено appointment ID: {existing_appointment.id}")

                            # Перевіряємо payment_method_id у appointment
                            pm_id = safe_getattr(existing_appointment, "payment_method_id")
                            print(f"existing_appointment.payment_method_id: {pm_id}")

                            # Створюємо форму з об'єктом
                            form_with_obj = AppointmentForm(obj=existing_appointment)
                            print("✓ AppointmentForm створено з існуючим appointment")

                            # Перевіряємо form data після ініціалізації з obj
                            form_data = form_with_obj.payment_method.data
                            print(f"form_with_obj.payment_method.data: {form_data}")

                            # Перевіряємо choices
                            form_choices = form_with_obj.payment_method.choices
                            print(
                                f"form_with_obj.payment_method.choices count: {len(form_choices) if form_choices else 0}"
                            )

                            # Детальний аналіз choices з obj
                            print("form_with_obj.payment_method.choices:")
                            if form_choices:
                                for choice in form_choices:
                                    print(f"  {choice}")

                        else:
                            print("Жодного appointment не знайдено в БД")

                    except Exception as e:
                        print(f"Помилка при тестуванні форми з існуючим appointment: {e}")
                        traceback.print_exc()

            except ImportError as e:
                print(f"Помилка імпорту: {e}")
                traceback.print_exc()
            except Exception as e:
                print(f"Загальна помилка при діагностиці форми: {e}")
                traceback.print_exc()

            # 4. Додаткова діагностика
            print_section_header("Additional Diagnostics")

            try:
                # Перевіряємо стан БД
                print_subsection_header("Database Connection")

                result = db.session.execute(db.text("SELECT 1"))
                print(f"✓ З'єднання з БД працює: {result.scalar()}")

                # Перевіряємо назву БД файлу
                try:
                    db_url = app.config.get("SQLALCHEMY_DATABASE_URI", "NOT_SET")
                    print(f"SQLALCHEMY_DATABASE_URI: {db_url}")
                except Exception as e:
                    print(f"Помилка при отриманні DATABASE_URI: {e}")

                # Перевіряємо кількість записів у основних таблицях
                print_subsection_header("Table Counts")

                tables_to_check = [
                    ("PaymentMethod", PaymentMethod),
                    ("Client", Client),
                    ("User", User),
                    ("Service", Service),
                    ("Appointment", Appointment),
                ]

                for table_name, model_class in tables_to_check:
                    try:
                        count = model_class.query.count()
                        print(f"  {table_name}: {count} записів")
                    except Exception as e:
                        print(f"  {table_name}: ERROR - {e}")

                # Додаткова діагностика: перевіряємо unwind relationships
                print_subsection_header("PaymentMethod Relationships Analysis")

                try:
                    # Перевіряємо які appointment мають payment_method_id
                    appointments_with_payment = Appointment.query.filter(
                        Appointment.payment_method_id.is_not(None)
                    ).all()

                    print(f"Appointments з payment_method_id: {len(appointments_with_payment)}")

                    if appointments_with_payment:
                        print("Перші 5 appointments з payment_method_id:")
                        for apt in appointments_with_payment[:5]:
                            print(f"  Appointment ID: {apt.id}, payment_method_id: {apt.payment_method_id}")

                            # Спробуємо отримати payment_method через relationship
                            try:
                                pm_obj = apt.payment_method_ref
                                if pm_obj:
                                    print(f"    -> PaymentMethod: {pm_obj.name}")
                                else:
                                    print(f"    -> PaymentMethod: None")
                            except Exception as e:
                                print(f"    -> Помилка доступу до payment_method_ref: {e}")

                except Exception as e:
                    print(f"Помилка аналізу relationships: {e}")
                    traceback.print_exc()

            except Exception as e:
                print(f"Помилка при додатковій діагностиці: {e}")
                traceback.print_exc()

    except Exception as e:
        print(f"КРИТИЧНА ПОМИЛКА: {e}")
        traceback.print_exc()

    print_section_header("ДІАГНОСТИКА ЗАВЕРШЕНА")
    print("Для детального аналізу перенаправте вивід у файл:")
    print("python diagnose_payment_methods.py > diagnosis_output.txt 2>&1")


if __name__ == "__main__":
    main()
