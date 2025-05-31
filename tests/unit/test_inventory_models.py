from decimal import Decimal
from typing import Any
from unittest.mock import patch

import pytest

from app.models import Brand, Product, StockLevel


class TestBrandModel:
    """Test cases for Brand model."""

    def test_brand_creation(self, app: Any, db: Any) -> None:
        """Test brand creation and basic properties."""
        with app.app_context():
            brand = Brand()
            brand.name = "Test Brand"
            db.session.add(brand)
            db.session.commit()

            assert brand.id is not None
            assert brand.name == "Test Brand"
            # Test that products collection exists (may be empty)
            assert hasattr(brand, "products")

    def test_brand_repr(self, app: Any, db: Any) -> None:
        """Test brand string representation."""
        with app.app_context():
            brand = Brand()
            brand.name = "Test Brand"
            assert repr(brand) == "<Brand Test Brand>"

    def test_brand_unique_name_constraint(self, app: Any, db: Any) -> None:
        """Test that brand names must be unique."""
        with app.app_context():
            brand1 = Brand()
            brand1.name = "Duplicate Brand"
            brand2 = Brand()
            brand2.name = "Duplicate Brand"

            db.session.add(brand1)
            db.session.commit()

            db.session.add(brand2)
            with pytest.raises(Exception):  # IntegrityError
                db.session.commit()

    def test_brand_products_relationship(self, app: Any, db: Any) -> None:
        """Test that brand has proper relationship with products."""
        with app.app_context():
            brand = Brand()
            brand.name = "Beauty Brand"
            db.session.add(brand)
            db.session.commit()

            product = Product(name="Test Product", sku="UNIQUE123", brand_id=brand.id, min_stock_level=5)
            db.session.add(product)
            db.session.commit()

            # Refresh the brand to get updated relationships
            db.session.refresh(brand)
            assert len(brand.products) == 1
            assert brand.products[0] == product  # type: ignore[index]
            assert product.brand == brand


class TestProductModel:
    """Test cases for Product model."""

    def test_product_creation(self, app: Any, db: Any) -> None:
        """Test product creation with all fields."""
        with app.app_context():
            brand = Brand()
            brand.name = "Test Brand"
            db.session.add(brand)
            db.session.commit()

            product = Product(
                name="Test Product",
                sku="TEST001",
                volume_value=250.0,
                volume_unit="мл",
                description="Test product description",
                min_stock_level=10,
                current_sale_price=Decimal("29.99"),
                last_cost_price=Decimal("15.50"),
                brand_id=brand.id,
            )
            db.session.add(product)
            db.session.commit()

            assert product.id is not None
            assert product.name == "Test Product"
            assert product.sku == "TEST001"
            assert product.volume_value == 250.0
            assert product.volume_unit == "мл"
            assert product.description == "Test product description"
            assert product.min_stock_level == 10
            assert product.current_sale_price == Decimal("29.99")
            assert product.last_cost_price == Decimal("15.50")
            assert product.brand_id == brand.id
            assert product.created_at is not None

    def test_product_repr(self, app: Any, db: Any) -> None:
        """Test product string representation."""
        with app.app_context():
            brand = Brand()
            brand.name = "Test Brand"
            db.session.add(brand)
            db.session.commit()

            product = Product(name="Test Product", sku="TEST001", brand_id=brand.id)
            assert repr(product) == "<Product Test Product (TEST001)>"

    def test_product_unique_sku_constraint(self, app: Any, db: Any) -> None:
        """Test that product SKUs must be unique."""
        with app.app_context():
            brand = Brand()
            brand.name = "Test Brand"
            db.session.add(brand)
            db.session.commit()

            product1 = Product(name="Product 1", sku="DUPLICATE", brand_id=brand.id)
            product2 = Product(name="Product 2", sku="DUPLICATE", brand_id=brand.id)

            db.session.add(product1)
            db.session.commit()

            db.session.add(product2)
            with pytest.raises(Exception):  # IntegrityError
                db.session.commit()

    def test_generate_sku_basic(self, app: Any, db: Any) -> None:
        """Test basic SKU generation."""
        with app.app_context():
            sku = Product.generate_sku("TestBrand", "TestProduct")
            assert len(sku) >= 6  # At least 3 brand + 3 product + counter
            assert sku.startswith("TES")  # First 3 letters of TestBrand
            assert "TES" in sku  # Product part should be in SKU

    def test_generate_sku_short_names(self, app: Any, db: Any) -> None:
        """Test SKU generation with short names."""
        with app.app_context():
            sku = Product.generate_sku("AB", "XY")
            assert len(sku) >= 6  # Should be padded to minimum length

    def test_generate_sku_special_characters(self, app: Any, db: Any) -> None:
        """Test SKU generation with special characters."""
        with app.app_context():
            sku = Product.generate_sku("Test-Brand!", "Product@123")
            # Should only contain letters and numbers
            assert all(c.isalnum() for c in sku)

    def test_generate_sku_uniqueness(self, app: Any, db: Any) -> None:
        """Test that generated SKUs are unique."""
        with app.app_context():
            brand = Brand()
            brand.name = "Test Brand"
            db.session.add(brand)
            db.session.commit()

            # Create a product with generated SKU
            sku1 = Product.generate_sku("TestBrand", "TestProduct")
            product1 = Product(name="Test Product 1", sku=sku1, brand_id=brand.id)
            db.session.add(product1)
            db.session.commit()

            # Generate another SKU with same names - should be different
            sku2 = Product.generate_sku("TestBrand", "TestProduct")
            assert sku1 != sku2

    @patch("app.models.Product.query")
    def test_generate_sku_collision_handling(self, mock_query: Any, app: Any, db: Any) -> None:
        """Test SKU generation handles collisions properly."""
        with app.app_context():
            # Mock existing products to simulate collisions
            mock_existing = Product(name="Existing", sku="TESTEST001")
            mock_query.filter_by.return_value.first.side_effect = [
                mock_existing,  # First attempt finds existing
                None,  # Second attempt is unique
            ]

            sku = Product.generate_sku("TestBrand", "TestProduct")
            # Should return TESTEST002 (next available)
            assert sku.endswith("002")


class TestStockLevelModel:
    """Test cases for StockLevel model."""

    def test_stock_level_creation(self, app: Any, db: Any) -> None:
        """Test stock level creation."""
        with app.app_context():
            brand = Brand()
            brand.name = "Test Brand"
            db.session.add(brand)
            db.session.commit()

            product = Product(name="Test Product", sku="TEST001", brand_id=brand.id)
            db.session.add(product)
            db.session.commit()

            # Get the automatically created stock level instead of creating manually
            stock = StockLevel.query.filter_by(product_id=product.id).first()
            assert stock is not None

            # Update the quantity
            stock.quantity = 50
            db.session.commit()

            assert stock.id is not None
            assert stock.product_id == product.id
            assert stock.quantity == 50
            assert stock.last_updated is not None

    def test_stock_level_repr(self, app: Any, db: Any) -> None:
        """Test stock level string representation."""
        with app.app_context():
            stock = StockLevel(product_id=1, quantity=25)
            assert repr(stock) == "<StockLevel Product: 1, Quantity: 25>"

    def test_stock_level_default_quantity(self, app: Any, db: Any) -> None:
        """Test default quantity is 0."""
        with app.app_context():
            brand = Brand()
            brand.name = "Test Brand"
            db.session.add(brand)
            db.session.commit()

            product = Product(name="Test Product", sku="TEST001", brand_id=brand.id)
            db.session.add(product)
            db.session.commit()

            # Get the automatically created stock level
            stock = StockLevel.query.filter_by(product_id=product.id).first()
            assert stock.quantity == 0

    def test_stock_level_unique_product_constraint(self, app: Any, db: Any) -> None:
        """Test that each product can have only one stock level record."""
        with app.app_context():
            brand = Brand()
            brand.name = "Test Brand"
            db.session.add(brand)
            db.session.commit()

            product = Product(name="Test Product", sku="TEST001", brand_id=brand.id)
            db.session.add(product)
            db.session.commit()

            # Product already has auto-created StockLevel, try to create another one
            stock2 = StockLevel(product_id=product.id, quantity=20)
            db.session.add(stock2)

            with pytest.raises(Exception):  # IntegrityError
                db.session.commit()


class TestProductStockLevelIntegration:
    """Test cases for automatic StockLevel creation and Product-StockLevel relationships."""

    def test_automatic_stock_level_creation(self, app: Any, db: Any) -> None:
        """Test that StockLevel is automatically created when Product is created."""
        with app.app_context():
            brand = Brand()
            brand.name = "Test Brand"
            db.session.add(brand)
            db.session.commit()

            # Create product - should automatically create StockLevel
            product = Product(name="Auto Stock Product", sku="AUTO001", brand_id=brand.id)
            db.session.add(product)
            db.session.commit()

            # Verify StockLevel was created
            stock_level = StockLevel.query.filter_by(product_id=product.id).first()
            assert stock_level is not None
            assert stock_level.quantity == 0
            assert stock_level.product_id == product.id

    def test_product_stock_relationship(self, app: Any, db: Any) -> None:
        """Test Product-StockLevel relationship works properly."""
        with app.app_context():
            brand = Brand()
            brand.name = "Test Brand"
            db.session.add(brand)
            db.session.commit()

            product = Product(name="Relationship Test Product", sku="REL001", brand_id=brand.id)
            db.session.add(product)
            db.session.commit()

            # Get the automatically created stock level
            stock_level = StockLevel.query.filter_by(product_id=product.id).first()

            # Test relationships
            assert len(product.stock_records) == 1  # type: ignore[arg-type]
            assert product.stock_records[0] == stock_level  # type: ignore[index]
            assert stock_level.product == product

    def test_cascade_delete_stock_level(self, app: Any, db: Any) -> None:
        """Test that deleting a product also deletes its stock level."""
        with app.app_context():
            brand = Brand()
            brand.name = "Test Brand"
            db.session.add(brand)
            db.session.commit()

            product = Product(name="Delete Test Product", sku="DEL001", brand_id=brand.id)
            db.session.add(product)
            db.session.commit()

            product_id = product.id

            # Verify stock level exists
            stock_level = StockLevel.query.filter_by(product_id=product_id).first()
            assert stock_level is not None

            # Delete product
            db.session.delete(product)
            db.session.commit()

            # Verify stock level was also deleted
            stock_level = StockLevel.query.filter_by(product_id=product_id).first()
            assert stock_level is None

    def test_multiple_products_separate_stock_levels(self, app: Any, db: Any) -> None:
        """Test that multiple products each get their own stock level."""
        with app.app_context():
            brand = Brand()
            brand.name = "Test Brand"
            db.session.add(brand)
            db.session.commit()

            product1 = Product(name="Product 1", sku="MULTI001", brand_id=brand.id)
            product2 = Product(name="Product 2", sku="MULTI002", brand_id=brand.id)

            db.session.add_all([product1, product2])
            db.session.commit()

            # Each should have its own stock level
            stock1 = StockLevel.query.filter_by(product_id=product1.id).first()
            stock2 = StockLevel.query.filter_by(product_id=product2.id).first()

            assert stock1 is not None
            assert stock2 is not None
            assert stock1.id != stock2.id
            assert stock1.product_id == product1.id
            assert stock2.product_id == product2.id
