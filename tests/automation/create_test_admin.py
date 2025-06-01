#!/usr/bin/env python3
"""Create test admin user for automated testing."""

from app import create_app
from app.models import User, db
from werkzeug.security import generate_password_hash

app = create_app()
with app.app_context():
    # Check if test admin already exists
    test_admin = User.query.filter_by(username="TestAdminAuto").first()

    if test_admin:
        print("Test admin already exists, updating password...")
        test_admin.password = generate_password_hash("test123admin")
        db.session.commit()
        print("✅ Test admin password updated")
    else:
        print("Creating new test admin...")
        test_admin = User(
            username="TestAdminAuto",
            full_name="Тестовий Адміністратор для Автотестів",
            password=generate_password_hash("test123admin"),
            is_admin=True,
            is_active_master=False,
            configurable_commission_rate=10.00,
        )
        db.session.add(test_admin)
        db.session.commit()
        print("✅ Test admin created")

    print("Test admin credentials:")
    print("  Username: TestAdminAuto")
    print("  Password: test123admin")
    print(f"  Full name: {test_admin.full_name}")
    print(f"  Is admin: {test_admin.is_admin}")
