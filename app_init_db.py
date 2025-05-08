import os
import sys
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.security import generate_password_hash

# Import models directly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.models import db, User, Client, Service, Appointment, AppointmentService


def init_db():
    # Create a minimal Flask app
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize the database with the app
    db.init_app(app)

    with app.app_context():
        # Drop all tables
        db.drop_all()
        # Create all tables from scratch
        db.create_all()

        # Create admin user
        admin = User(
            username="admin",
            password=generate_password_hash("admin"),
            full_name="Administrator",
            is_admin=True,
            is_active_master=False,
        )
        db.session.add(admin)

        # Create a regular user (master)
        master = User(
            username="master",
            password=generate_password_hash("master"),
            full_name="Master User",
            is_admin=False,
            is_active_master=True,
        )
        db.session.add(master)

        # Create sample services with base_price
        services = [
            Service(
                name="Haircut",
                description="Basic haircut",
                duration=60,
                base_price=100.0,
            ),
            Service(
                name="Coloring",
                description="Hair coloring",
                duration=120,
                base_price=200.0,
            ),
            Service(
                name="Styling", description="Hair styling", duration=30, base_price=75.0
            ),
            Service(
                name="Manicure",
                description="Basic manicure",
                duration=45,
                base_price=75.0,
            ),
        ]
        for service in services:
            db.session.add(service)

        db.session.commit()
        print("Database initialized successfully!")


if __name__ == "__main__":
    init_db()
