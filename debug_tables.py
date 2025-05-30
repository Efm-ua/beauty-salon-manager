#!/usr/bin/env python3
"""
Debug script to check table creation
"""

from app import create_app
from app.models import db, Brand, Product, StockLevel


def debug_tables():
    """Debug table creation"""

    # Create test app
    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret-key",
    }
    app = create_app(test_config=test_config)

    with app.app_context():
        print("Available models:")
        print("Brand:", Brand)
        print("Product:", Product)
        print("StockLevel:", StockLevel)

        print("\nMetadata tables before create_all:")
        for table_name in db.metadata.tables.keys():
            print(f"  - {table_name}")

        print("\nCreating all tables...")
        db.create_all()

        print("\nMetadata tables after create_all:")
        for table_name in db.metadata.tables.keys():
            print(f"  - {table_name}")

        # Check with inspect
        inspector = db.inspect(db.engine)
        actual_tables = inspector.get_table_names()
        print(f"\nActual tables in database: {actual_tables}")

        # Try to create a brand
        try:
            brand = Brand()
            brand.name = "Test Brand"
            db.session.add(brand)
            db.session.commit()
            print("\nBrand created successfully!")
        except Exception as e:
            print(f"\nError creating brand: {e}")


if __name__ == "__main__":
    debug_tables()
