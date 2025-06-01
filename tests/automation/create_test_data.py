#!/usr/bin/env python3
"""Script to create test data for testing purposes."""

from app import create_app
from app.models import db, WriteOffReason, User
from werkzeug.security import generate_password_hash
from decimal import Decimal


def create_test_data():
    app = create_app()

    with app.app_context():
        print("=== Creating Test Data ===")

        # Create test write-off reasons
        print("\n--- Creating Write-off Reasons ---")
        test_reasons = [
            ("Пошкодження", True),
            ("Закінчення терміну придатності", True),
            ("Тестова причина (активна)", True),
            ("Тестова причина (неактивна)", False),
        ]

        for reason_name, is_active in test_reasons:
            existing = WriteOffReason.query.filter_by(name=reason_name).first()
            if not existing:
                reason = WriteOffReason(name=reason_name, is_active=is_active)
                db.session.add(reason)
                print(f"  Created: {reason_name} (Active: {is_active})")
            else:
                print(f"  Already exists: {reason_name}")

        # Set commission rates for existing users
        print("\n--- Setting Commission Rates ---")
        users = User.query.all()
        for user in users:
            if user.configurable_commission_rate is None:
                if user.is_admin:
                    user.configurable_commission_rate = Decimal("10.00")  # Base rate for admin
                else:
                    user.configurable_commission_rate = Decimal("30.00")  # Default for masters
                print(f"  Set commission {user.configurable_commission_rate}% for {user.full_name}")

        db.session.commit()
        print("\n✅ Test data created successfully!")


if __name__ == "__main__":
    create_test_data()
