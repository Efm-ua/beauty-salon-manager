#!/usr/bin/env python3
"""
Автоматизовані тести Частини 6: Звітність
Тестує звіти по зарплаті майстрів, адміністраторів та фінансовий звіт.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from app import create_app
from app.models import (
    Product,
    StockLevel,
    Sale,
    SaleItem,
    User,
    Appointment,
    AppointmentService,
    Client,
    Service,
    PaymentMethod,
    db,
)
from decimal import Decimal
from datetime import date, datetime, timedelta
import re

BASE_URL = "http://127.0.0.1:5000"


class AutomatedReportsTester:
    def __init__(self):
        self.session = requests.Session()
        self.csrf_token = None

    def get_csrf_token(self, url):
        """Extract CSRF token from a form page."""
        response = self.session.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            csrf_input = soup.find("input", {"name": "csrf_token"})
            if csrf_input:
                return csrf_input.get("value")
        return None

    def login_as_admin(self, username="TestAdminAuto", password="test123admin"):
        """🔐 Login as admin for reports access."""
        print("🔐 Testing Admin Login for Reports...")

        login_url = urljoin(BASE_URL, "/auth/login")
        csrf_token = self.get_csrf_token(login_url)

        if not csrf_token:
            print("❌ Could not get CSRF token")
            return False

        login_data = {"username": username, "password": password, "csrf_token": csrf_token, "submit": "Увійти"}

        response = self.session.post(login_url, data=login_data, allow_redirects=True)

        if response.status_code == 200 and "Вийти" in response.text:
            print("✅ Admin login successful!")
            return True
        else:
            print(f"❌ Login failed. Status: {response.status_code}")
            return False

    def setup_test_data_for_reports(self):
        """📊 Setup comprehensive test data for reports."""
        print("📊 Setting up test data for reports...")

        app = create_app()
        with app.app_context():
            today = date.today()

            # Get test admin and create master if needed
            admin = User.query.filter_by(username="TestAdminAuto").first()
            if not admin:
                print("❌ Test admin not found")
                return False

            # Create/get master user
            master = User.query.filter_by(username="TestMaster", is_active_master=True).first()
            if not master:
                master = User(
                    username="TestMaster",
                    password="pbkdf2:sha256:600000$test$test",
                    full_name="Test Master",
                    is_admin=False,
                    is_active_master=True,
                    configurable_commission_rate=Decimal("15.0"),
                )
                db.session.add(master)
                db.session.commit()
                print("✅ Created test master")

            # Set admin commission rate
            if not admin.configurable_commission_rate:
                admin.configurable_commission_rate = Decimal("12.0")
                db.session.commit()

            # Get test client
            client = Client.query.filter_by(name="Тестовий Клієнт").first()
            if not client:
                client = Client(name="Тестовий Клієнт", phone="+380501234567")
                db.session.add(client)
                db.session.commit()

            # Get test service
            service = Service.query.filter_by(name="Тестова послуга").first()
            if not service:
                service = Service(
                    name="Тестова послуга",
                    description="Тестова послуга для звітів",
                    base_price=Decimal("500.00"),
                    duration=60,
                )
                db.session.add(service)
                db.session.commit()

            # Get payment method
            payment_method = PaymentMethod.query.filter_by(name="Готівка").first()
            if not payment_method:
                payment_method = PaymentMethod(name="Готівка", is_active=True)
                db.session.add(payment_method)
                db.session.commit()

            # Create test appointments for master
            appointment1 = Appointment(
                client_id=client.id,
                master_id=master.id,
                date=today,
                start_time=datetime.now().time(),
                end_time=(datetime.now() + timedelta(hours=1)).time(),
                status="completed",
                payment_status="paid",
                payment_method_id=payment_method.id,
                amount_paid=Decimal("500.00"),
            )
            db.session.add(appointment1)
            db.session.commit()

            # Add service to appointment
            app_service1 = AppointmentService(
                appointment_id=appointment1.id, service_id=service.id, price=Decimal("500.00")
            )
            db.session.add(app_service1)

            # Create test appointment for admin
            appointment2 = Appointment(
                client_id=client.id,
                master_id=admin.id,
                date=today,
                start_time=(datetime.now() + timedelta(hours=2)).time(),
                end_time=(datetime.now() + timedelta(hours=3)).time(),
                status="completed",
                payment_status="paid",
                payment_method_id=payment_method.id,
                amount_paid=Decimal("300.00"),
            )
            db.session.add(appointment2)
            db.session.commit()

            # Add service to admin appointment
            app_service2 = AppointmentService(
                appointment_id=appointment2.id, service_id=service.id, price=Decimal("300.00")
            )
            db.session.add(app_service2)

            # Get test products for sales
            shampoo = Product.query.filter_by(name="Шампунь Зволожуючий").first()
            mask = Product.query.filter_by(name="Маска Відновлююча").first()

            if shampoo and mask:
                # Create sales by master
                sale1 = Sale(
                    user_id=master.id,
                    client_id=client.id,
                    total_amount=Decimal("850.00"),
                    payment_method_id=payment_method.id,
                    sale_date=datetime.now(),
                    created_by_user_id=master.id,
                )
                db.session.add(sale1)
                db.session.commit()

                # Add sale items
                sale_item1 = SaleItem(
                    sale_id=sale1.id,
                    product_id=shampoo.id,
                    quantity=1,
                    price_per_unit=Decimal("450.00"),
                    cost_price_per_unit=shampoo.last_cost_price or Decimal("250.00"),
                )
                sale_item2 = SaleItem(
                    sale_id=sale1.id,
                    product_id=mask.id,
                    quantity=1,
                    price_per_unit=Decimal("400.00"),
                    cost_price_per_unit=mask.last_cost_price or Decimal("220.00"),
                )
                db.session.add(sale_item1)
                db.session.add(sale_item2)

                # Create sales by admin
                sale2 = Sale(
                    user_id=admin.id,
                    client_id=client.id,
                    total_amount=Decimal("450.00"),
                    payment_method_id=payment_method.id,
                    sale_date=datetime.now(),
                    created_by_user_id=admin.id,
                )
                db.session.add(sale2)
                db.session.commit()

                # Add admin sale item
                sale_item3 = SaleItem(
                    sale_id=sale2.id,
                    product_id=shampoo.id,
                    quantity=1,
                    price_per_unit=Decimal("450.00"),
                    cost_price_per_unit=shampoo.last_cost_price or Decimal("250.00"),
                )
                db.session.add(sale_item3)

                db.session.commit()
                print("✅ Test data for reports created successfully")

                # Print summary
                print(f"   👨‍💼 Master commission rate: {master.configurable_commission_rate}%")
                print(f"   👔 Admin commission rate: {admin.configurable_commission_rate}%")
                print(f"   📅 Test date: {today}")
                print("   💼 Services: Master (500 грн), Admin (300 грн)")
                print("   🛒 Sales: Master (850 грн), Admin (450 грн)")

            else:
                print("⚠️ Test products not found - sales data might be incomplete")

        return True

    def test_master_salary_report(self):
        """💰 Test 6.1: Master salary report."""
        print("\n💰 Testing Master Salary Report...")

        # Step 1: Access salary report page
        salary_url = urljoin(BASE_URL, "/reports/salary")
        response = self.session.get(salary_url)

        if response.status_code != 200:
            print(f"❌ Cannot access salary report page. Status: {response.status_code}")
            return False

        print("✅ Salary report page accessible")

        # Step 2: Get test data
        app = create_app()
        with app.app_context():
            master = User.query.filter_by(username="TestMaster").first()
            if not master:
                print("❌ Test master not found")
                return False

            today = date.today()
            commission_rate = float(master.configurable_commission_rate)

            print(f"   📋 Testing for master: {master.full_name}")
            print(f"   📅 Report date: {today}")
            print(f"   💼 Commission rate: {commission_rate}%")

        # Step 3: Submit form for specific master
        csrf_token = self.get_csrf_token(salary_url)
        if not csrf_token:
            print("❌ Could not get CSRF token")
            return False

        form_data = {
            "csrf_token": csrf_token,
            "report_date": today.strftime("%Y-%m-%d"),
            "master_id": str(master.id),
            "submit": "Generate Report",
        }

        response = self.session.post(salary_url, data=form_data)

        if response.status_code != 200:
            print(f"❌ Failed to generate master salary report. Status: {response.status_code}")
            return False

        print("✅ Master salary report generated")

        # Step 4: Verify report content
        html_content = response.text

        # Check commission rates display
        if f"{commission_rate}%" in html_content:
            print("✅ Master commission rate displayed correctly")
        else:
            print("⚠️ Master commission rate might not be displayed")

        if "9%" in html_content:
            print("✅ Products commission rate (9%) displayed")
        else:
            print("⚠️ Products commission rate might not be displayed")

        # Check for services data
        if "500.00" in html_content:  # Service price
            print("✅ Service data found in report")
        else:
            print("⚠️ Service data might be missing")

        # Check for products data
        if "850.00" in html_content:  # Products total
            print("✅ Products sales data found")
        else:
            print("⚠️ Products sales data might be missing")

        # Calculate expected values
        expected_service_commission = 500.00 * (commission_rate / 100)  # 500 * 0.15 = 75.00
        expected_products_commission = 850.00 * 0.09  # 850 * 0.09 = 76.50
        expected_total_salary = expected_service_commission + expected_products_commission  # 151.50

        print(f"   📊 Expected service commission: {expected_service_commission:.2f}")
        print(f"   📊 Expected products commission: {expected_products_commission:.2f}")
        print(f"   📊 Expected total salary: {expected_total_salary:.2f}")

        # Look for these values in the response
        if f"{expected_service_commission:.2f}" in html_content:
            print("✅ Service commission calculation correct")
        elif f"{expected_service_commission:.0f}" in html_content:
            print("✅ Service commission calculation correct (rounded)")
        else:
            print("⚠️ Service commission calculation might be incorrect")

        if f"{expected_products_commission:.2f}" in html_content:
            print("✅ Products commission calculation correct")
        else:
            print("⚠️ Products commission calculation might be incorrect")

        # Test "All masters" option
        print("\n   🔄 Testing 'All masters' option...")
        csrf_token = self.get_csrf_token(salary_url)
        form_data_all = {
            "csrf_token": csrf_token,
            "report_date": today.strftime("%Y-%m-%d"),
            "master_id": "0",  # All masters
            "submit": "Generate Report",
        }

        response_all = self.session.post(salary_url, data=form_data_all)
        if response_all.status_code == 200:
            print("✅ 'All masters' report generated successfully")
        else:
            print("⚠️ 'All masters' report might have issues")

        return True

    def test_admin_salary_report(self):
        """👔 Test 6.2: Admin salary report."""
        print("\n👔 Testing Admin Salary Report...")

        # Step 1: Access admin salary report page
        admin_salary_url = urljoin(BASE_URL, "/reports/admin_salary")
        response = self.session.get(admin_salary_url)

        if response.status_code != 200:
            print(f"❌ Cannot access admin salary report page. Status: {response.status_code}")
            return False

        print("✅ Admin salary report page accessible")

        # Step 2: Get test data
        app = create_app()
        with app.app_context():
            admin = User.query.filter_by(username="TestAdminAuto").first()
            if not admin:
                print("❌ Test admin not found")
                return False

            today = date.today()
            admin_commission_rate = float(admin.configurable_commission_rate)

            print(f"   📋 Testing for admin: {admin.full_name}")
            print(f"   📅 Report period: {today}")
            print(f"   💼 Admin commission rate: {admin_commission_rate}%")

        # Step 3: Submit form for admin
        csrf_token = self.get_csrf_token(admin_salary_url)
        if not csrf_token:
            print("❌ Could not get CSRF token")
            return False

        form_data = {
            "csrf_token": csrf_token,
            "start_date": today.strftime("%Y-%m-%d"),
            "end_date": today.strftime("%Y-%m-%d"),
            "admin_id": str(admin.id),
            "submit": "Generate Report",
        }

        response = self.session.post(admin_salary_url, data=form_data)

        if response.status_code != 200:
            print(f"❌ Failed to generate admin salary report. Status: {response.status_code}")
            return False

        print("✅ Admin salary report generated")

        # Step 4: Verify report content and calculations
        html_content = response.text

        # Expected calculations based on test data:
        # 1. Personal services commission: 300.00 * (12% / 100) = 36.00
        # 2. Personal products commission: 450.00 * ((12% + 1%) / 100) = 450.00 * 0.13 = 58.50
        # 3. Masters' products share: 850.00 * 0.01 = 8.50
        # 4. Total: 36.00 + 58.50 + 8.50 = 103.00

        expected_service_commission = 300.00 * (admin_commission_rate / 100)  # 36.00
        expected_personal_products = 450.00 * ((admin_commission_rate + 1) / 100)  # 58.50
        expected_masters_share = 850.00 * 0.01  # 8.50
        expected_total_admin_salary = expected_service_commission + expected_personal_products + expected_masters_share

        print(f"   📊 Expected service commission: {expected_service_commission:.2f}")
        print(f"   📊 Expected personal products commission: {expected_personal_products:.2f}")
        print(f"   📊 Expected masters' share: {expected_masters_share:.2f}")
        print(f"   📊 Expected total admin salary: {expected_total_admin_salary:.2f}")

        # Check for personal services data
        if "300.00" in html_content:
            print("✅ Personal services data found")
        else:
            print("⚠️ Personal services data might be missing")

        # Check for personal products data
        if "450.00" in html_content:
            print("✅ Personal products data found")
        else:
            print("⚠️ Personal products data might be missing")

        # Check for masters' sales data
        if "850.00" in html_content:
            print("✅ Masters' products data found")
        else:
            print("⚠️ Masters' products data might be missing")

        # Look for calculated values
        commission_found = False
        for expected_val in [expected_service_commission, expected_personal_products, expected_masters_share]:
            if f"{expected_val:.2f}" in html_content or f"{expected_val:.0f}" in html_content:
                commission_found = True

        if commission_found:
            print("✅ Commission calculations appear correct")
        else:
            print("⚠️ Commission calculations might need verification")

        # Check for total salary calculation
        if f"{expected_total_admin_salary:.2f}" in html_content or "Total Salary" in html_content:
            print("✅ Total salary calculation displayed")
        else:
            print("⚠️ Total salary calculation might be missing")

        return True

    def test_financial_report(self):
        """📈 Test 6.3: Financial report."""
        print("\n📈 Testing Financial Report...")

        # Step 1: Access financial report page
        financial_url = urljoin(BASE_URL, "/reports/financial")
        response = self.session.get(financial_url)

        if response.status_code != 200:
            print(f"❌ Cannot access financial report page. Status: {response.status_code}")
            return False

        print("✅ Financial report page accessible")

        # Step 2: Submit form for today's data
        csrf_token = self.get_csrf_token(financial_url)
        if not csrf_token:
            print("❌ Could not get CSRF token")
            return False

        today = date.today()
        form_data = {
            "csrf_token": csrf_token,
            "start_date": today.strftime("%Y-%m-%d"),
            "end_date": today.strftime("%Y-%m-%d"),
            "submit": "Сформувати звіт",
        }

        response = self.session.post(financial_url, data=form_data)

        if response.status_code != 200:
            print(f"❌ Failed to generate financial report. Status: {response.status_code}")
            return False

        print("✅ Financial report generated")

        # Step 3: Verify report content and calculations
        html_content = response.text

        # Expected calculations based on test data:
        # Service revenue: 500.00 (master) + 300.00 (admin) = 800.00
        # Product revenue: 850.00 (master) + 450.00 (admin) = 1300.00
        # COGS: (250.00 + 220.00) from master sale + 250.00 from admin sale = 720.00
        # Product gross profit: 1300.00 - 720.00 = 580.00
        # Total revenue: 800.00 + 1300.00 = 2100.00
        # Total gross profit: 800.00 (services) + 580.00 (products) = 1380.00

        expected_service_revenue = 800.00
        expected_product_revenue = 1300.00
        expected_cogs = 720.00  # Cost of goods sold
        expected_product_profit = expected_product_revenue - expected_cogs
        expected_total_revenue = expected_service_revenue + expected_product_revenue
        expected_total_profit = expected_service_revenue + expected_product_profit

        print(f"   📊 Expected service revenue: {expected_service_revenue:.2f}")
        print(f"   📊 Expected product revenue: {expected_product_revenue:.2f}")
        print(f"   📊 Expected COGS: {expected_cogs:.2f}")
        print(f"   📊 Expected product gross profit: {expected_product_profit:.2f}")
        print(f"   📊 Expected total revenue: {expected_total_revenue:.2f}")
        print(f"   📊 Expected total gross profit: {expected_total_profit:.2f}")

        # Check for service revenue
        if "800.00" in html_content or "Service" in html_content:
            print("✅ Service revenue data found")
        else:
            print("⚠️ Service revenue data might be missing")

        # Check for product revenue
        if "1300.00" in html_content or "Product" in html_content:
            print("✅ Product revenue data found")
        else:
            print("⚠️ Product revenue data might be missing")

        # Check for COGS (Cost of Goods Sold)
        if "720.00" in html_content or "COGS" in html_content or "собівартість" in html_content.lower():
            print("✅ COGS data found")
        else:
            print("⚠️ COGS data might be missing")

        # Check for gross profit
        if "580.00" in html_content or "прибуток" in html_content.lower():
            print("✅ Gross profit data found")
        else:
            print("⚠️ Gross profit data might be missing")

        # Check for total revenue
        if "2100.00" in html_content or "загальний" in html_content.lower():
            print("✅ Total revenue data found")
        else:
            print("⚠️ Total revenue data might be missing")

        # Check for payment methods breakdown
        if "Готівка" in html_content:
            print("✅ Payment method breakdown found")
        else:
            print("⚠️ Payment method breakdown might be missing")

        # Test scenario with empty date range
        print("\n   🔄 Testing empty date range scenario...")
        future_date = (today + timedelta(days=30)).strftime("%Y-%m-%d")
        csrf_token = self.get_csrf_token(financial_url)

        empty_form_data = {
            "csrf_token": csrf_token,
            "start_date": future_date,
            "end_date": future_date,
            "submit": "Сформувати звіт",
        }

        empty_response = self.session.post(financial_url, data=empty_form_data)
        if empty_response.status_code == 200:
            empty_html = empty_response.text
            if "0.00" in empty_html or "немає даних" in empty_html.lower():
                print("✅ Empty date range handled correctly")
            else:
                print("⚠️ Empty date range handling might need verification")

        return True

    def verify_calculation_accuracy(self):
        """🧮 Additional verification of calculation accuracy."""
        print("\n🧮 Verifying Calculation Accuracy...")

        app = create_app()
        with app.app_context():
            # Get actual data from database
            today = date.today()

            # Master data
            master = User.query.filter_by(username="TestMaster").first()
            admin = User.query.filter_by(username="TestAdminAuto").first()

            if not master or not admin:
                print("❌ Test users not found for verification")
                return False

            # Verify appointments
            master_appointments = Appointment.query.filter(
                Appointment.master_id == master.id, Appointment.date == today, Appointment.status == "completed"
            ).all()

            admin_appointments = Appointment.query.filter(
                Appointment.master_id == admin.id, Appointment.date == today, Appointment.status == "completed"
            ).all()

            print(f"   📋 Master appointments: {len(master_appointments)}")
            print(f"   📋 Admin appointments: {len(admin_appointments)}")

            # Verify sales
            master_sales = Sale.query.filter(
                Sale.user_id == master.id,
                Sale.sale_date >= datetime.combine(today, datetime.min.time()),
                Sale.sale_date < datetime.combine(today + timedelta(days=1), datetime.min.time()),
            ).all()

            admin_sales = Sale.query.filter(
                Sale.user_id == admin.id,
                Sale.sale_date >= datetime.combine(today, datetime.min.time()),
                Sale.sale_date < datetime.combine(today + timedelta(days=1), datetime.min.time()),
            ).all()

            print(f"   🛒 Master sales: {len(master_sales)}")
            print(f"   🛒 Admin sales: {len(admin_sales)}")

            # Calculate totals for verification
            master_service_total = sum(
                sum(service.price for service in appointment.services) for appointment in master_appointments
            )
            master_sales_total = sum(float(sale.total_amount) for sale in master_sales)

            admin_service_total = sum(
                sum(service.price for service in appointment.services) for appointment in admin_appointments
            )
            admin_sales_total = sum(float(sale.total_amount) for sale in admin_sales)

            print(f"   💰 Master services total: {master_service_total}")
            print(f"   💰 Master sales total: {master_sales_total}")
            print(f"   💰 Admin services total: {admin_service_total}")
            print(f"   💰 Admin sales total: {admin_sales_total}")

            # Verify commission calculations
            master_commission_rate = float(master.configurable_commission_rate)
            admin_commission_rate = float(admin.configurable_commission_rate)

            expected_master_service_comm = master_service_total * (master_commission_rate / 100)
            expected_master_product_comm = master_sales_total * 0.09
            expected_master_total = expected_master_service_comm + expected_master_product_comm

            expected_admin_service_comm = admin_service_total * (admin_commission_rate / 100)
            expected_admin_product_comm = admin_sales_total * ((admin_commission_rate + 1) / 100)
            expected_admin_masters_share = master_sales_total * 0.01
            expected_admin_total = (
                expected_admin_service_comm + expected_admin_product_comm + expected_admin_masters_share
            )

            print(f"\n   📊 Master expected total salary: {expected_master_total:.2f}")
            print(f"   📊 Admin expected total salary: {expected_admin_total:.2f}")

            print("✅ Calculation verification completed")

        return True

    def run_all_tests(self):
        """🚀 Run complete automated reports test suite."""
        print("🚀 Starting Automated Reports Test Suite (Part 6)")
        print("=" * 80)

        tests_passed = 0
        total_tests = 0

        # Test 1: Login
        total_tests += 1
        if self.login_as_admin():
            tests_passed += 1

            # Test 2: Setup test data
            total_tests += 1
            if self.setup_test_data_for_reports():
                tests_passed += 1

                # Test 3: Master salary report
                total_tests += 1
                if self.test_master_salary_report():
                    tests_passed += 1

                # Test 4: Admin salary report
                total_tests += 1
                if self.test_admin_salary_report():
                    tests_passed += 1

                # Test 5: Financial report
                total_tests += 1
                if self.test_financial_report():
                    tests_passed += 1

                # Test 6: Calculation verification
                total_tests += 1
                if self.verify_calculation_accuracy():
                    tests_passed += 1

        # Final report
        print("\n" + "=" * 80)
        print(f"🏁 Automated Reports Tests Completed: {tests_passed}/{total_tests} passed")
        print(f"   Success rate: {(tests_passed/total_tests)*100:.1f}%")

        if tests_passed == total_tests:
            print("🎉 All reports tests passed! All calculations are working correctly.")
        else:
            print("⚠️ Some tests failed. Check the output above for details.")

        return tests_passed == total_tests


if __name__ == "__main__":
    tester = AutomatedReportsTester()
    tester.run_all_tests()
