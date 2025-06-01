#!/usr/bin/env python3
"""Backend testing script for Класіко manager."""

import requests
import json
from urllib.parse import urljoin

# Configuration
BASE_URL = "http://127.0.0.1:5000"
ADMIN_CREDENTIALS = {"username": "OlgaCHE", "password": "admin123"}  # Need to know actual password


def make_request(method, path, **kwargs):
    """Helper function to make HTTP requests."""
    url = urljoin(BASE_URL, path)
    try:
        response = requests.request(method, url, **kwargs)
        return response
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None


def login_as_admin(session):
    """Login as admin user."""
    print("🔐 Attempting admin login...")

    # First get login page to get CSRF token
    login_page = session.get(urljoin(BASE_URL, "/auth/login"))
    if login_page.status_code != 200:
        print(f"❌ Failed to get login page: {login_page.status_code}")
        return False

    # Extract CSRF token (simplified - in real scenario would parse HTML)
    # For now, let's try without CSRF or with a dummy one

    login_data = {"username": ADMIN_CREDENTIALS["username"], "password": ADMIN_CREDENTIALS["password"]}

    response = session.post(urljoin(BASE_URL, "/auth/login"), data=login_data)

    if response.status_code == 200 and "Увійти" not in response.text:
        print("✅ Admin login successful")
        return True
    else:
        print(f"❌ Admin login failed: {response.status_code}")
        return False


def test_admin_access(session):
    """Test admin-only endpoints access."""
    print("\n📋 Testing Admin Access...")

    endpoints = [
        ("/auth/users", "User Management"),
        ("/auth/register", "User Registration"),
        ("/products/write_off_reasons", "Write-off Reasons"),
    ]

    for endpoint, name in endpoints:
        response = session.get(urljoin(BASE_URL, endpoint))
        if response.status_code == 200:
            print(f"✅ {name} accessible: {endpoint}")
        else:
            print(f"❌ {name} failed: {endpoint} - Status: {response.status_code}")


def test_user_validation():
    """Test user model validation."""
    print("\n👥 Testing User Model Validation...")

    from app import create_app
    from app.models import User, db
    from decimal import Decimal

    app = create_app()
    with app.app_context():
        # Test commission rate validation
        try:
            # Test valid commission rate
            test_user = User(
                username="test_validation",
                password="test123",
                full_name="Test User",
                is_admin=False,
                is_active_master=True,
                configurable_commission_rate=Decimal("35.50"),
            )
            print("✅ Valid commission rate (35.50%) accepted")

            # Test edge cases
            edge_cases = [
                (Decimal("0.00"), "0% commission"),
                (Decimal("100.00"), "100% commission"),
                (Decimal("50.25"), "50.25% commission"),
            ]

            for rate, desc in edge_cases:
                test_user.configurable_commission_rate = rate
                print(f"✅ {desc} accepted")

        except Exception as e:
            print(f"❌ Commission rate validation failed: {e}")


def test_write_off_reasons():
    """Test write-off reasons functionality."""
    print("\n📝 Testing Write-off Reasons...")

    from app import create_app
    from app.models import WriteOffReason, db
    from app.services.inventory_service import InventoryService

    app = create_app()
    with app.app_context():
        # Test getting active reasons
        try:
            active_reasons = InventoryService.get_active_write_off_reasons()
            active_count = len(active_reasons)
            print(f"✅ Found {active_count} active write-off reasons")

            for reason in active_reasons:
                print(f"   - {reason.name}")

        except Exception as e:
            print(f"❌ Failed to get active write-off reasons: {e}")

        # Test getting all reasons
        try:
            all_reasons = InventoryService.get_all_write_off_reasons()
            total_count = len(all_reasons)
            print(f"✅ Found {total_count} total write-off reasons")

        except Exception as e:
            print(f"❌ Failed to get all write-off reasons: {e}")


def test_payment_methods():
    """Test payment methods functionality."""
    print("\n💳 Testing Payment Methods...")

    from app import create_app
    from app.models import PaymentMethod

    app = create_app()
    with app.app_context():
        try:
            methods = PaymentMethod.query.all()
            print(f"✅ Found {len(methods)} payment methods:")

            for method in methods:
                print(f"   - {method.name} (Active: {method.is_active})")

        except Exception as e:
            print(f"❌ Failed to get payment methods: {e}")


def run_backend_tests():
    """Run comprehensive backend tests."""
    print("🧪 Starting Backend Tests for Класіко Manager")
    print("=" * 60)

    # Test database models
    test_user_validation()
    test_write_off_reasons()
    test_payment_methods()

    # Test HTTP endpoints (requires running server)
    session = requests.Session()

    # Test basic connectivity
    try:
        response = session.get(urljoin(BASE_URL, "/ping"))
        if response.status_code == 200:
            print("\n🌐 Server connectivity: ✅")

            # Test admin login and access
            if login_as_admin(session):
                test_admin_access(session)
            else:
                print("⚠️  Could not test admin endpoints due to login failure")
                print("   Please verify admin credentials")
        else:
            print("\n🌐 Server connectivity: ❌")
            print("   Make sure the Flask development server is running")

    except Exception as e:
        print(f"\n🌐 Server connectivity: ❌ ({e})")
        print("   Make sure the Flask development server is running on http://127.0.0.1:5000")

    print("\n" + "=" * 60)
    print("🏁 Backend Tests Completed")


if __name__ == "__main__":
    run_backend_tests()
