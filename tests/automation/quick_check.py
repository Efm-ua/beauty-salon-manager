#!/usr/bin/env python3
"""Quick verification script for UI testing."""

import sys
from app import create_app
from app.models import User, WriteOffReason, PaymentMethod


def check_user(username):
    """Check specific user by username."""
    app = create_app()
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        if user:
            print(f"✅ User: {user.full_name}")
            print(f"   Admin: {user.is_admin}")
            print(f"   Active Master: {user.is_active_master}")
            print(f"   Schedule Order: {user.schedule_display_order}")
            print(f"   Commission Rate: {user.configurable_commission_rate}%")
        else:
            print(f"❌ User '{username}' not found")


def check_write_off_reason(name):
    """Check specific write-off reason by name."""
    app = create_app()
    with app.app_context():
        reason = WriteOffReason.query.filter_by(name=name).first()
        if reason:
            print(f"✅ Write-off Reason: {reason.name}")
            print(f"   Active: {reason.is_active}")
            print(f"   Created: {reason.created_at}")
        else:
            print(f"❌ Write-off reason '{name}' not found")


def check_latest_user():
    """Check the latest created user."""
    app = create_app()
    with app.app_context():
        user = User.query.order_by(User.id.desc()).first()
        if user:
            print(f"✅ Latest User: {user.full_name} ({user.username})")
            print(f"   Admin: {user.is_admin}")
            print(f"   Active Master: {user.is_active_master}")
            print(f"   Commission Rate: {user.configurable_commission_rate}%")
        else:
            print("❌ No users found")


def check_latest_reason():
    """Check the latest created write-off reason."""
    app = create_app()
    with app.app_context():
        reason = WriteOffReason.query.order_by(WriteOffReason.id.desc()).first()
        if reason:
            print(f"✅ Latest Reason: {reason.name}")
            print(f"   Active: {reason.is_active}")
        else:
            print("❌ No write-off reasons found")


def show_counts():
    """Show current counts of all entities."""
    app = create_app()
    with app.app_context():
        users = User.query.count()
        admins = User.query.filter_by(is_admin=True).count()
        masters = User.query.filter_by(is_active_master=True).count()
        reasons = WriteOffReason.query.count()
        active_reasons = WriteOffReason.query.filter_by(is_active=True).count()
        payment_methods = PaymentMethod.query.filter_by(is_active=True).count()

        print("📊 Current System State:")
        print(f"   Users: {users} (Admins: {admins}, Masters: {masters})")
        print(f"   Write-off Reasons: {reasons} (Active: {active_reasons})")
        print(f"   Payment Methods: {payment_methods} (active)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python quick_check.py counts                    - Show system counts")
        print("  python quick_check.py user <username>           - Check specific user")
        print("  python quick_check.py reason <reason_name>      - Check specific reason")
        print("  python quick_check.py latest-user               - Check latest user")
        print("  python quick_check.py latest-reason             - Check latest reason")
        sys.exit(1)

    command = sys.argv[1]

    if command == "counts":
        show_counts()
    elif command == "user" and len(sys.argv) > 2:
        check_user(sys.argv[2])
    elif command == "reason" and len(sys.argv) > 2:
        check_write_off_reason(" ".join(sys.argv[2:]))
    elif command == "latest-user":
        check_latest_user()
    elif command == "latest-reason":
        check_latest_reason()
    else:
        print("❌ Invalid command or missing arguments")
        sys.exit(1)
