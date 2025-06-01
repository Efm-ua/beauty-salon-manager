#!/usr/bin/env python3
"""Check admin user credentials."""

from app import create_app
from app.models import User
from werkzeug.security import check_password_hash

app = create_app()
with app.app_context():
    admin = User.query.filter_by(username="OlgaCHE").first()
    if admin:
        print(f"Admin found: {admin.full_name}")
        print(f"Is admin: {admin.is_admin}")
        print(f"Password hash starts with: {admin.password[:30]}...")

        # Try common passwords
        passwords_to_try = ["admin123", "admin", "password", "123456", "Olga123"]
        for pwd in passwords_to_try:
            if check_password_hash(admin.password, pwd):
                print(f"✅ Correct password found: {pwd}")
                break
        else:
            print("❌ None of the common passwords work")
    else:
        print("❌ Admin user 'OlgaCHE' not found")

    print("\nAll users:")
    for user in User.query.all():
        print(f"  {user.username} - {user.full_name} (Admin: {user.is_admin})")
