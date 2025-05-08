from app import create_app, db
from app.models import Service


def migrate_db():
    app = create_app()
    with app.app_context():
        db.create_all()
        print("Database schema updated successfully!")


if __name__ == "__main__":
    migrate_db()
