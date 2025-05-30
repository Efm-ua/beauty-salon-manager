#!/usr/bin/env python3
"""Debug script to investigate user creation issues."""

import os
import sys

# Add the project directory to the Python path
sys.path.insert(0, os.path.abspath("."))

from app import create_app, db
from app.models import User
from app.routes.auth import RegistrationForm
from flask_login import login_user


def debug_user_creation():
    """Debug user creation process."""

    # Create app with testing config
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SECRET_KEY"] = "test"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    with app.app_context():
        # Create tables
        db.create_all()

        # Create an admin user first
        admin = User(
            username="admin_test",
            full_name="Admin Test",
            password="password_hash",
            is_admin=True,
            is_active_master=False,
        )
        db.session.add(admin)

        # Create an existing user with schedule_display_order=1 to simulate the conflict
        existing_user = User(
            username="existing_master",
            full_name="Existing Master",
            password="password_hash",
            is_admin=False,
            is_active_master=True,
            schedule_display_order=1,
        )
        db.session.add(existing_user)
        db.session.commit()

        # Check existing users and their schedule_display_order values
        print("Existing users:")
        for user in User.query.all():
            print(
                f"  - {user.username}: schedule_display_order={user.schedule_display_order}, "
                f"is_active_master={user.is_active_master}"
            )

        # Create test client
        client = app.test_client()

        # Try with schedule_display_order=1 (should conflict)
        form_data_conflict = {
            "username": "new_master_conflict",
            "full_name": "New Master Conflict",
            "password": "password123",
            "password2": "password123",
            "is_admin": "",
            "is_active_master": "y",
            "schedule_display_order": 1,  # This should conflict
        }

        print(f"\nTesting with conflicting schedule_display_order=1:")
        with app.test_request_context(method="POST", data=form_data_conflict):
            form = RegistrationForm(data=form_data_conflict)
            print(f"Form validate(): {form.validate()}")
            if not form.validate():
                print(f"Form errors: {form.errors}")

        # Try with schedule_display_order=2 (should work)
        form_data_valid = {
            "username": "new_master_valid",
            "full_name": "New Master Valid",
            "password": "password123",
            "password2": "password123",
            "is_admin": "",
            "is_active_master": "y",
            "schedule_display_order": 2,  # This should work
        }

        print(f"\nTesting with non-conflicting schedule_display_order=2:")
        with app.test_request_context(method="POST", data=form_data_valid):
            form = RegistrationForm(data=form_data_valid)
            print(f"Form validate(): {form.validate()}")
            if not form.validate():
                print(f"Form errors: {form.errors}")
            else:
                print("Form validation passed!")

        # Try the actual endpoint with proper session for valid data
        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin.id)
            sess["_fresh"] = True

        response = client.post("/auth/register", data=form_data_valid, follow_redirects=True)
        print(f"\nResponse status: {response.status_code}")
        response_text = response.get_data(as_text=True)
        if "успішно зареєстрований" in response_text:
            print("SUCCESS: User registration successful!")
        else:
            print("FAILURE: User registration failed")
            print(f"Response data (first 500 chars): {response_text[:500]}")

        # Check if user was created
        new_user = User.query.filter_by(username="new_master_valid").first()
        print(f"\nUser created: {new_user}")
        if new_user:
            print(
                f"User details: username={new_user.username}, "
                f"full_name={new_user.full_name}, is_admin={new_user.is_admin}, "
                f"is_active_master={new_user.is_active_master}, "
                f"schedule_display_order={new_user.schedule_display_order}"
            )


if __name__ == "__main__":
    debug_user_creation()
