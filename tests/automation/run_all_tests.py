#!/usr/bin/env python3
"""
Запуск всіх автоматизованих тестів Beauty Salon Manager
Автоматично виконує підготовку, backend тести, UI тести та перевірку результатів.
"""

import subprocess
import sys
import time
import os
from pathlib import Path


# Кольори для виводу
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_header(text):
    """Виводить заголовок з кольором."""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{text.center(60)}{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.END}")


def print_step(step_num, text):
    """Виводить номер кроку."""
    print(f"\n{Colors.YELLOW}{Colors.BOLD}📋 Крок {step_num}: {text}{Colors.END}")


def print_success(text):
    """Виводить повідомлення про успіх."""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_error(text):
    """Виводить повідомлення про помилку."""
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_warning(text):
    """Виводить попередження."""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


def run_script(script_path, description):
    """Запускає Python скрипт та повертає True при успіху."""
    print(f"\n{Colors.BLUE}🚀 Запуск: {description}{Colors.END}")
    print(f"   Команда: python {script_path}")

    try:
        # Переходимо в корінь проекту для запуску скриптів
        original_dir = os.getcwd()
        project_root = Path(__file__).parent.parent.parent
        os.chdir(project_root)

        result = subprocess.run([sys.executable, script_path], capture_output=True, text=True, cwd=project_root)

        os.chdir(original_dir)

        if result.returncode == 0:
            print_success(f"{description} - Завершено успішно")
            if result.stdout.strip():
                # Показати останні кілька рядків виводу
                lines = result.stdout.strip().split("\n")
                for line in lines[-3:]:
                    if line.strip():
                        print(f"   {Colors.WHITE}{line}{Colors.END}")
            return True
        else:
            print_error(f"{description} - Помилка!")
            if result.stderr:
                print(f"   Помилка: {result.stderr}")
            if result.stdout:
                print(f"   Вивід: {result.stdout}")
            return False

    except Exception as e:
        print_error(f"{description} - Виняток: {e}")
        return False


def check_flask_server():
    """Перевіряє чи запущений Flask сервер."""
    try:
        import requests

        response = requests.get("http://127.0.0.1:5000", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def main():
    """Основна функція запуску всіх тестів."""
    print_header("🧪 АВТОМАТИЗОВАНІ ТЕСТИ BEAUTY SALON MANAGER")

    start_time = time.time()
    success_count = 0
    print("🚀 Запускаємо всі автоматизовані тести...")
    print("=" * 80)

    total_steps = 10  # Збільшуємо кількість кроків до 10
    current_step = 1

    # Крок 1: Підготовка тестового адміна
    print_step(1, "Створення тестового адміністратора")
    if run_script("tests/automation/create_test_admin.py", "Створення TestAdminAuto"):
        success_count += 1

    # Крок 2: Підготовка тестових даних
    print_step(2, "Створення тестових даних")
    if run_script("tests/automation/create_test_data.py", "Ініціалізація тестових даних"):
        success_count += 1

    # Крок 3: Backend тести
    print_step(3, "Backend тестування")
    if run_script("tests/automation/backend_tests_simple.py", "Тестування моделей та логіки"):
        success_count += 1

    # Крок 4: UI тести Частини 1 (перевірка сервера)
    print_step(4, "UI тестування - Частина 1: Управління користувачами")
    if not check_flask_server():
        print_warning("Flask сервер не запущений на http://127.0.0.1:5000")
        print(f"   {Colors.WHITE}Запустіть: python run.py{Colors.END}")
        print_error("UI тести пропущено")
    else:
        print_success("Flask сервер доступний")
        if run_script("tests/automation/automated_ui_test.py", "Автоматизовані UI тести - Частина 1"):
            success_count += 1

    # Крок 5: UI тести Частини 2
    print_step(5, "UI тестування - Частина 2: Каталог товарів та інвентаризація")
    if not check_flask_server():
        print_warning("Flask сервер не запущений для Частини 2")
        print_error("UI тести Частини 2 пропущено")
    else:
        if run_script("tests/automation/automated_part2_inventory.py", "Автоматизовані UI тести - Частина 2"):
            success_count += 1

    # Крок 6: UI тести Частини 3
    print_step(6, "UI тестування - Частина 3: Процес продажів товарів")
    if not check_flask_server():
        print_warning("Flask сервер не запущений для Частини 3")
        print_error("UI тести Частини 3 пропущено")
    else:
        if run_script("tests/automation/automated_part3_sales.py", "Автоматизовані UI тести - Частина 3"):
            success_count += 1

    # Крок 7: Частина 3 - Процес Продажів Товарів
    print(f"\n📊 Крок 7/{total_steps}: Частина 3 - Процес Продажів Товарів")
    print("-" * 60)
    try:
        from tests.automation.automated_part3_sales import AutomatedSalesTester

        sales_tester = AutomatedSalesTester()
        if sales_tester.run_all_tests():
            print("✅ Частина 3 (Продажі) - всі тести пройдені!")
            success_count += 1
        else:
            print("❌ Частина 3 (Продажі) - деякі тести не пройдені")
    except Exception as e:
        print(f"❌ Помилка в Частині 3: {e}")

    # Крок 8: Частина 4 - Інтеграція Продажів у Картці Запису
    print(f"\n🔗 Крок 8/{total_steps}: Частина 4 - Інтеграція Продажів у Картці Запису")
    print("-" * 60)
    try:
        from tests.automation.automated_part4_appointment_integration import AutomatedAppointmentIntegrationTester

        integration_tester = AutomatedAppointmentIntegrationTester()
        if integration_tester.run_all_tests():
            print("✅ Частина 4 (Інтеграція продажів) - всі тести пройдені!")
            success_count += 1
        else:
            print("❌ Частина 4 (Інтеграція продажів) - деякі тести не пройдені")
    except Exception as e:
        print(f"❌ Помилка в Частині 4: {e}")

    # Крок 9: Частина 5 - Розширений Складський Облік
    print(f"\n🏭 Крок 9/{total_steps}: Частина 5 - Розширений Складський Облік")
    print("-" * 60)
    try:
        from tests.automation.automated_part5_warehouse import AutomatedWarehouseTester

        warehouse_tester = AutomatedWarehouseTester()
        if warehouse_tester.run_all_tests():
            print("✅ Частина 5 (Складський облік) - всі тести пройдені!")
            success_count += 1
        else:
            print("❌ Частина 5 (Складський облік) - деякі тести не пройдені")
    except Exception as e:
        print(f"❌ Помилка в Частині 5: {e}")

    # Крок 10: Частина 6 - Звітність
    print(f"\n📊 Крок 10/{total_steps}: Частина 6 - Звітність")
    print("-" * 60)
    try:
        from tests.automation.automated_part6_reports import AutomatedReportsTester

        reports_tester = AutomatedReportsTester()
        if reports_tester.run_all_tests():
            print("✅ Частина 6 (Звітність) - всі тести пройдені!")
            success_count += 1
        else:
            print("❌ Частина 6 (Звітність) - деякі тести не пройдені")
    except Exception as e:
        print(f"❌ Помилка в Частині 6: {e}")

    # Підсумок
    end_time = time.time()
    duration = end_time - start_time

    print_header("ПІДСУМОК ТЕСТУВАННЯ")
    print(f"⏱️  Тривалість: {duration:.1f} секунд")
    print(f"📈 Результат: {success_count}/{total_steps} кроків успішно")

    if success_count == total_steps:
        print_success("🎉 Всі тести пройшли успішно!")
        return 0
    elif success_count >= total_steps - 2:  # Дозволяємо 1-2 пропущених тести
        print_warning("⚠️  Майже всі тести пройшли (можливо сервер не запущений)")
        return 1
    else:
        print_error("❌ Деякі тести не пройшли. Перевірте вивід вище.")
        return 2


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
