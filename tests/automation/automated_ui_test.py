#!/usr/bin/env python3
"""Automated UI Testing Script - simulates user actions via HTTP requests."""

import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from app import create_app
from app.models import User, WriteOffReason

BASE_URL = "http://127.0.0.1:5000"


class AutomatedUITester:
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
        """🔐 Test 1.1: Simulate admin login."""
        print("🔐 Testing Admin Login...")

        # Get login page and CSRF token
        login_url = urljoin(BASE_URL, "/auth/login")
        csrf_token = self.get_csrf_token(login_url)

        if not csrf_token:
            print("❌ Could not get CSRF token")
            return False

        # Attempt login
        login_data = {"username": username, "password": password, "csrf_token": csrf_token, "submit": "Увійти"}

        response = self.session.post(login_url, data=login_data, allow_redirects=True)

        # Check if login successful
        if response.status_code == 200 and "Вийти" in response.text:
            print("✅ Admin login successful!")
            print(f"   Final URL: {response.url}")
            return True
        else:
            print(f"❌ Login failed. Status: {response.status_code}")
            if "Увійти" in response.text:
                print("   Still on login page - check credentials")
            return False

    def test_user_management_access(self):
        """📋 Test 1.2.1: Access user management page."""
        print("\n📋 Testing User Management Access...")

        users_url = urljoin(BASE_URL, "/auth/users")
        response = self.session.get(users_url)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            user_rows = soup.find_all("tr")
            user_count = len(user_rows) - 1  # Minus header row

            print("✅ User management accessible")
            print(f"   Found {user_count} users in table")

            # Check for "Add new user" button
            add_button = soup.find("a", href="/auth/register")
            if add_button:
                print("✅ 'Add new user' button found")
            return True
        else:
            print(f"❌ Cannot access user management. Status: {response.status_code}")
            return False

    def create_test_master(self):
        """👥 Test 1.2.2: Create new master user."""
        print("\n👥 Testing Master Creation...")

        register_url = urljoin(BASE_URL, "/auth/register")
        csrf_token = self.get_csrf_token(register_url)

        if not csrf_token:
            print("❌ Could not get CSRF token for registration")
            return False

        # Test data for new master
        user_data = {
            "username": "TestMaster1",
            "full_name": "Тестовий Майстер Перший",
            "password": "test123",
            "password2": "test123",
            "is_admin": False,  # Not admin
            "is_active_master": True,  # Active master
            "schedule_display_order": 10,
            "configurable_commission_rate": 30.00,
            "csrf_token": csrf_token,
            "submit": "Зареєструватися",
        }

        response = self.session.post(register_url, data=user_data, allow_redirects=True)

        if response.status_code == 200:
            if "/auth/users" in response.url or "TestMaster1" in response.text:
                print("✅ Master user created successfully!")
                return True
            elif "вже використовується" in response.text:
                print("⚠️  User already exists, checking in database...")
                return self.verify_user_in_db("TestMaster1")
            else:
                print("❌ User creation failed - unexpected response")
                return False
        else:
            print(f"❌ User creation failed. Status: {response.status_code}")
            return False

    def edit_test_master(self):
        """✏️ Test 1.2.3: Edit the created master."""
        print("\n✏️ Testing Master Editing...")

        # First, find the user ID
        user_id = self.get_user_id_from_db("TestMaster1")
        if not user_id:
            print("❌ Cannot find TestMaster1 to edit")
            return False

        edit_url = urljoin(BASE_URL, f"/auth/users/{user_id}/edit")
        csrf_token = self.get_csrf_token(edit_url)

        if not csrf_token:
            print("❌ Could not get CSRF token for editing")
            return False

        # Updated data
        edit_data = {
            "full_name": "Тестовий Майстер Перший (Змінено)",
            "is_admin": False,
            "is_active_master": True,
            "schedule_display_order": 10,
            "configurable_commission_rate": 35.50,  # Changed commission
            "csrf_token": csrf_token,
            "submit": "Зберегти",
        }

        response = self.session.post(edit_url, data=edit_data, allow_redirects=True)

        if response.status_code == 200 and "успішно оновлений" in response.text:
            print("✅ Master edited successfully!")
            return True
        else:
            print(f"❌ Master editing failed. Status: {response.status_code}")
            return False

    def test_commission_validation(self):
        """🔍 Test 1.2.4: Test commission rate validation."""
        print("\n🔍 Testing Commission Rate Validation...")

        user_id = self.get_user_id_from_db("TestMaster1")
        if not user_id:
            print("❌ Cannot find TestMaster1 for validation test")
            return False

        edit_url = urljoin(BASE_URL, f"/auth/users/{user_id}/edit")

        # Test invalid values
        invalid_values = [(-10, "negative value"), (110, "value over 100"), ("abc", "text value")]

        success_count = 0
        for invalid_value, description in invalid_values:
            csrf_token = self.get_csrf_token(edit_url)

            edit_data = {
                "full_name": "Тестовий Майстер Перший (Змінено)",
                "is_admin": False,
                "is_active_master": True,
                "schedule_display_order": 10,
                "configurable_commission_rate": invalid_value,
                "csrf_token": csrf_token,
                "submit": "Зберегти",
            }

            response = self.session.post(edit_url, data=edit_data, allow_redirects=False)

            # Should stay on edit page with validation error
            if response.status_code == 200 and response.request.url and edit_url in response.request.url:
                print(f"✅ Validation works for {description}")
                success_count += 1
            else:
                print(f"❌ Validation failed for {description}")

        return success_count == len(invalid_values)

    def create_test_admin(self):
        """👑 Test 1.2.5: Create new admin user."""
        print("\n👑 Testing Admin Creation...")

        register_url = urljoin(BASE_URL, "/auth/register")
        csrf_token = self.get_csrf_token(register_url)

        if not csrf_token:
            print("❌ Could not get CSRF token for admin registration")
            return False

        # Test data for new admin
        admin_data = {
            "username": "TestAdmin1",
            "full_name": "Тестовий Адміністратор",
            "password": "admin123",
            "password2": "admin123",
            "is_admin": True,  # Admin
            "is_active_master": False,  # Will be auto-set
            "configurable_commission_rate": 10.00,
            "csrf_token": csrf_token,
            "submit": "Зареєструватися",
        }

        response = self.session.post(register_url, data=admin_data, allow_redirects=True)

        if response.status_code == 200:
            if "/auth/users" in response.url or "TestAdmin1" in response.text:
                print("✅ Admin user created successfully!")
                return True
            elif "вже використовується" in response.text:
                print("⚠️  Admin already exists, checking in database...")
                return self.verify_user_in_db("TestAdmin1")
            else:
                print("❌ Admin creation failed")
                return False
        else:
            print(f"❌ Admin creation failed. Status: {response.status_code}")
            return False

    def test_write_off_reasons_access(self):
        """📝 Test 1.3.1: Access write-off reasons management."""
        print("\n📝 Testing Write-off Reasons Access...")

        reasons_url = urljoin(BASE_URL, "/products/write_off_reasons")
        response = self.session.get(reasons_url)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            # Check for add button
            add_button = soup.find("a", href="/products/write_off_reasons/create")
            if add_button:
                print("✅ Write-off reasons page accessible")
                print("✅ 'Add reason' button found")
                return True
            else:
                print("⚠️  Page accessible but add button not found")
                return False
        else:
            print(f"❌ Cannot access write-off reasons. Status: {response.status_code}")
            return False

    def create_test_write_off_reason(self):
        """📝 Test 1.3.2: Create new write-off reason."""
        print("\n📝 Testing Write-off Reason Creation...")

        create_url = urljoin(BASE_URL, "/products/write_off_reasons/create")
        csrf_token = self.get_csrf_token(create_url)

        if not csrf_token:
            print("❌ Could not get CSRF token for reason creation")
            return False

        reason_data = {
            "name": "Тестова причина списання",
            "is_active": 1,  # Active
            "csrf_token": csrf_token,
            "submit": "Зберегти",
        }

        response = self.session.post(create_url, data=reason_data, allow_redirects=True)

        if response.status_code == 200:
            if "успішно створена" in response.text or "write_off_reasons" in response.url:
                print("✅ Write-off reason created successfully!")
                return True
            elif "вже існує" in response.text:
                print("⚠️  Reason already exists")
                return True
            else:
                print("❌ Reason creation failed")
                return False
        else:
            print(f"❌ Reason creation failed. Status: {response.status_code}")
            return False

    # Helper methods
    def verify_user_in_db(self, username):
        """Verify user exists in database."""
        app = create_app()
        with app.app_context():
            user = User.query.filter_by(username=username).first()
            return user is not None

    def get_user_id_from_db(self, username):
        """Get user ID from database."""
        app = create_app()
        with app.app_context():
            user = User.query.filter_by(username=username).first()
            return user.id if user else None

    def run_all_tests(self):
        """🚀 Run complete automated UI test suite."""
        print("🚀 Starting Automated UI Test Suite")
        print("=" * 60)

        tests_passed = 0
        total_tests = 0

        # Test 1.1: Login
        total_tests += 1
        if self.login_as_admin():
            tests_passed += 1

            # Test 1.2: User Management
            total_tests += 1
            if self.test_user_management_access():
                tests_passed += 1

                # Test 1.2.2: Create Master
                total_tests += 1
                if self.create_test_master():
                    tests_passed += 1

                    # Test 1.2.3: Edit Master
                    total_tests += 1
                    if self.edit_test_master():
                        tests_passed += 1

                    # Test 1.2.4: Validation
                    total_tests += 1
                    if self.test_commission_validation():
                        tests_passed += 1

                # Test 1.2.5: Create Admin
                total_tests += 1
                if self.create_test_admin():
                    tests_passed += 1

            # Test 1.3: Write-off Reasons
            total_tests += 1
            if self.test_write_off_reasons_access():
                tests_passed += 1

                total_tests += 1
                if self.create_test_write_off_reason():
                    tests_passed += 1

        # Final report
        print("\n" + "=" * 60)
        print(f"🏁 Automated UI Tests Completed: {tests_passed}/{total_tests} passed")
        print(f"   Success rate: {(tests_passed/total_tests)*100:.1f}%")

        if tests_passed == total_tests:
            print("🎉 All tests passed! UI is working correctly.")
        else:
            print("⚠️  Some tests failed. Check the output above.")

        return tests_passed == total_tests


if __name__ == "__main__":
    tester = AutomatedUITester()
    tester.run_all_tests()
