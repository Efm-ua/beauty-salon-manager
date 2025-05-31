import click
from flask import Flask, current_app
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from .models import PaymentMethod, User, db


@click.command("create-admin")  # type: ignore[misc]
@with_appcontext  # type: ignore[misc]
def create_admin_command() -> None:
    """Create an admin user if no users exist."""
    if User.query.count() == 0:
        admin_username = current_app.config.get("ADMIN_USERNAME", "admin")
        admin_password = current_app.config.get("ADMIN_PASSWORD", "admin")
        admin_full_name = current_app.config.get("ADMIN_FULL_NAME", "Administrator")

        click.echo(f"Creating admin user: {admin_username}")

        admin = User(
            username=admin_username,
            password=generate_password_hash(admin_password),
            full_name=admin_full_name,
            is_admin=True,
        )
        db.session.add(admin)
        db.session.commit()

        click.echo("Admin user created successfully!")
    else:
        click.echo("Admin user already exists. No new user created.")


@click.command()  # type: ignore[misc]
@with_appcontext  # type: ignore[misc]
def init_db() -> None:
    """Initialize the database."""
    db.create_all()
    print("Database initialized.")


@click.command()  # type: ignore[misc]
@with_appcontext  # type: ignore[misc]
def create_payment_methods() -> None:
    """Create default payment methods."""
    payment_methods = ["Готівка", "Малібу", "ФОП", "Приват", "MONO", "Борг"]

    for method_name in payment_methods:
        # Check if method already exists
        existing = PaymentMethod.query.filter_by(name=method_name).first()
        if not existing:
            payment_method = PaymentMethod()
            payment_method.name = method_name
            payment_method.is_active = True
            db.session.add(payment_method)
            print(f"Created payment method: {method_name}")
        else:
            print(f"Payment method already exists: {method_name}")

    db.session.commit()
    print("Payment methods initialized.")


def init_app(app: Flask) -> None:
    """Register CLI commands with the Flask application."""
    app.cli.add_command(create_admin_command)
    app.cli.add_command(init_db)
    app.cli.add_command(create_payment_methods)
