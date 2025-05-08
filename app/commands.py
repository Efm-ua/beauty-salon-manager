import click
from flask import current_app
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from .models import User, db


@click.command("create-admin")
@with_appcontext
def create_admin_command():
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


def init_app(app):
    """Register CLI commands with the Flask application."""
    app.cli.add_command(create_admin_command)
