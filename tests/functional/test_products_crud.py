from decimal import Decimal
from typing import Any

from app.models import Brand, Product, StockLevel


class TestBrandsCRUD:
    """Functional tests for brands CRUD operations."""

    def test_brands_list_page(self, admin_auth_client: Any, session: Any) -> None:
        """Test brands listing page."""
        # Create some test brands using session
        brand1 = Brand()
        brand1.name = "Test Brand 1"
        brand2 = Brand()
        brand2.name = "Test Brand 2"
        session.add_all([brand1, brand2])
        session.commit()

        # Visit brands page (already authenticated)
        response = admin_auth_client.get("/products/brands")
        assert response.status_code == 200
        assert "Test Brand 1" in response.get_data(as_text=True)
        assert "Test Brand 2" in response.get_data(as_text=True)

    def test_create_brand_get(self, admin_auth_client: Any) -> None:
        """Test brand creation form display."""
        # Visit create brand page
        response = admin_auth_client.get("/products/brands/create")
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        assert "Створити бренд" in response_text or "Додати бренд" in response_text

    def test_create_brand_post(self, admin_auth_client: Any, session: Any) -> None:
        """Test brand creation via POST."""
        # Create brand
        response = admin_auth_client.post(
            "/products/brands/create", data={"name": "New Test Brand"}, follow_redirects=True
        )
        assert response.status_code == 200

        # Check brand was created
        brand = session.query(Brand).filter_by(name="New Test Brand").first()
        assert brand is not None

    def test_edit_brand(self, admin_auth_client: Any, session: Any) -> None:
        """Test brand editing."""
        # Create test brand
        brand = Brand()
        brand.name = "Original Brand"
        session.add(brand)
        session.commit()
        brand_id = brand.id

        # Edit brand
        response = admin_auth_client.post(
            f"/products/brands/{brand_id}/edit", data={"name": "Updated Brand"}, follow_redirects=True
        )
        assert response.status_code == 200

        # Check brand was updated
        session.refresh(brand)  # Refresh from database
        assert brand.name == "Updated Brand"

    def test_delete_brand(self, admin_auth_client: Any, session: Any) -> None:
        """Test brand deletion."""
        # Create test brand
        brand = Brand()
        brand.name = "Brand to Delete"
        session.add(brand)
        session.commit()
        brand_id = brand.id

        # Delete brand
        response = admin_auth_client.post(f"/products/brands/{brand_id}/delete", follow_redirects=True)
        assert response.status_code == 200

        # Check brand was deleted
        brand = session.get(Brand, brand_id)
        assert brand is None

    def test_create_brand_requires_admin(self, auth_client: Any) -> None:
        """Test that regular users cannot create brands."""
        # Try to access create brand page as regular user
        response = auth_client.get("/products/brands/create")
        # Should redirect to index due to lack of admin privileges
        assert response.status_code == 302

    def test_delete_brand_button_functionality(self, admin_auth_client: Any, session: Any) -> None:
        """Test that delete brand button is present and functional in the UI."""
        # Create test brand without products
        brand = Brand()
        brand.name = "Brand for UI Delete Test"
        session.add(brand)
        session.commit()
        brand_id = brand.id

        # Visit brands list page
        response = admin_auth_client.get("/products/brands")
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)

        # Check that brand is displayed
        assert "Brand for UI Delete Test" in response_text

        # Check that delete button/form is present for brands without products
        assert f"/products/brands/{brand_id}/delete" in response_text
        assert 'type="submit"' in response_text
        assert "Видалити" in response_text

        # Check that CSRF token is present in the form with correct format
        assert 'name="csrf_token"' in response_text
        assert 'value="' in response_text

        # Test actual deletion via POST request with CSRF token
        # Try to get CSRF token from the client's session or generate it
        from flask_wtf.csrf import generate_csrf

        with admin_auth_client.application.test_request_context():
            csrf_token = generate_csrf()

        # Perform deletion with CSRF token
        delete_response = admin_auth_client.post(
            f"/products/brands/{brand_id}/delete", data={"csrf_token": csrf_token}, follow_redirects=True
        )
        assert delete_response.status_code == 200

        # Verify brand was deleted
        brand = session.get(Brand, brand_id)
        assert brand is None

    def test_delete_brand_button_disabled_with_products(self, admin_auth_client: Any, session: Any) -> None:
        """Test that delete brand button shows error message for brands with products."""
        # Create brand with a product
        brand = Brand()
        brand.name = "Brand with Products"
        session.add(brand)
        session.commit()

        product = Product()
        product.name = "Test Product"
        product.sku = "TEST001"
        product.brand_id = brand.id
        session.add(product)
        session.commit()
        brand_id = brand.id

        # Visit brands list page
        response = admin_auth_client.get("/products/brands")
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)

        # Check that brand is displayed
        assert "Brand with Products" in response_text

        # Check that delete button is now ACTIVE (not disabled)
        assert f"/products/brands/{brand_id}/delete" in response_text
        assert 'type="submit"' in response_text
        assert "Видалити" in response_text

        # Test that attempting to delete shows error message
        from flask_wtf.csrf import generate_csrf

        with admin_auth_client.application.test_request_context():
            csrf_token = generate_csrf()

        # Try to delete the brand with products
        delete_response = admin_auth_client.post(
            f"/products/brands/{brand_id}/delete", data={"csrf_token": csrf_token}, follow_redirects=True
        )
        assert delete_response.status_code == 200

        # Check that error message is shown
        response_text = delete_response.get_data(as_text=True)
        assert "Неможливо видалити бренд" in response_text
        assert "має" in response_text and "товар" in response_text

        # Verify brand was NOT deleted
        brand_check = session.get(Brand, brand_id)
        assert brand_check is not None


class TestProductsCRUD:
    """Functional tests for products CRUD operations."""

    def test_products_list_page(self, admin_auth_client: Any, session: Any) -> None:
        """Test products listing page."""
        # Create test data
        brand = Brand()
        brand.name = "Test Brand"
        session.add(brand)
        session.commit()

        product1 = Product()
        product1.name = "Test Product 1"
        product1.sku = "TEST001"
        product1.brand_id = brand.id
        product2 = Product()
        product2.name = "Test Product 2"
        product2.sku = "TEST002"
        product2.brand_id = brand.id
        session.add_all([product1, product2])
        session.commit()

        # Visit products page
        response = admin_auth_client.get("/products/")
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        assert "Test Product 1" in response_text
        assert "Test Product 2" in response_text

    def test_create_product_get(self, admin_auth_client: Any, session: Any) -> None:
        """Test product creation form display."""
        # Create test brand
        brand = Brand()
        brand.name = "Test Brand"
        session.add(brand)
        session.commit()

        # Visit create product page
        response = admin_auth_client.get("/products/create")
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        assert "Створити товар" in response_text or "Додати товар" in response_text

    def test_create_product_post(self, admin_auth_client: Any, session: Any) -> None:
        """Test product creation via POST."""
        # Create test brand
        brand = Brand()
        brand.name = "Test Brand"
        session.add(brand)
        session.commit()
        brand_id = brand.id

        # Create product
        response = admin_auth_client.post(
            "/products/create",
            data={
                "name": "New Test Product",
                "brand_id": brand_id,
                "volume_value": "250",
                "volume_unit": "мл",
                "description": "Test product description",
                "min_stock_level": "5",
                "current_sale_price": "29.99",
                "last_cost_price": "15.50",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        # Check product was created
        product = session.query(Product).filter_by(name="New Test Product").first()
        assert product is not None

    def test_view_product(self, admin_auth_client: Any, session: Any) -> None:
        """Test product detail view."""
        # Create test data
        brand = Brand()
        brand.name = "Test Brand"
        session.add(brand)
        session.commit()

        product = Product()
        product.name = "Test Product"
        product.sku = "TEST001"
        product.brand_id = brand.id
        product.description = "Test description"
        product.current_sale_price = Decimal("25.99")
        session.add(product)
        session.commit()
        product_id = product.id

        # View product
        response = admin_auth_client.get(f"/products/{product_id}/view")
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        assert "Test Product" in response_text

    def test_edit_product(self, admin_auth_client: Any, session: Any) -> None:
        """Test product editing."""
        # Create test data
        brand = Brand()
        brand.name = "Test Brand"
        session.add(brand)
        session.commit()

        product = Product()
        product.name = "Original Product"
        product.sku = "ORIG001"
        product.brand_id = brand.id
        session.add(product)
        session.commit()
        product_id = product.id
        brand_id = brand.id  # Store brand_id while in session

        # Edit product
        response = admin_auth_client.post(
            f"/products/{product_id}/edit",
            data={
                "name": "Updated Product",
                "brand_id": brand_id,
                "description": "Updated description",
                "min_stock_level": "10",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        # Check product was updated
        session.refresh(product)  # Refresh from database
        assert product.name == "Updated Product"

    def test_delete_product(self, admin_auth_client: Any, session: Any) -> None:
        """Test product deletion."""
        # Create test data
        brand = Brand()
        brand.name = "Test Brand"
        session.add(brand)
        session.commit()

        product = Product()
        product.name = "Product to Delete"
        product.sku = "DEL001"
        product.brand_id = brand.id
        session.add(product)
        session.commit()
        product_id = product.id

        # Delete product with CSRF token
        from flask_wtf.csrf import generate_csrf

        with admin_auth_client.application.test_request_context():
            csrf_token = generate_csrf()

        response = admin_auth_client.post(
            f"/products/{product_id}/delete", data={"csrf_token": csrf_token}, follow_redirects=True
        )
        assert response.status_code == 200

        # Check product was deleted
        product = session.get(Product, product_id)
        assert product is None

    def test_create_product_requires_admin(self, auth_client: Any) -> None:
        """Test that regular users cannot create products."""
        # Try to access create product page as regular user
        response = auth_client.get("/products/create")
        # Should redirect to index due to lack of admin privileges
        assert response.status_code == 302


class TestStockLevels:
    """Tests for stock levels functionality."""

    def test_stock_levels_page(self, admin_auth_client: Any, session: Any) -> None:
        """Test stock levels listing page."""
        # Create test data
        brand = Brand()
        brand.name = "Test Brand"
        session.add(brand)
        session.commit()

        product = Product()
        product.name = "Test Product"
        product.sku = "TEST001"
        product.brand_id = brand.id
        session.add(product)
        session.commit()

        # StockLevel is automatically created by event listener, just update it
        stock_level = session.query(StockLevel).filter_by(product_id=product.id).first()
        assert stock_level is not None  # Should exist due to auto-creation
        stock_level.quantity = 10
        session.commit()

        # Visit stock levels page
        response = admin_auth_client.get("/products/stock")
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        assert "Test Product" in response_text

    def test_stock_search_functionality(self, admin_auth_client: Any, session: Any) -> None:
        """Test stock levels search functionality."""
        # Create test data
        brand = Brand()
        brand.name = "Test Brand"
        session.add(brand)
        session.commit()

        product1 = Product()
        product1.name = "Searchable Product"
        product1.sku = "SEARCH001"
        product1.brand_id = brand.id
        product2 = Product()
        product2.name = "Other Product"
        product2.sku = "OTHER001"
        product2.brand_id = brand.id
        session.add_all([product1, product2])
        session.commit()

        # Update auto-created stock levels instead of creating new ones
        stock1 = session.query(StockLevel).filter_by(product_id=product1.id).first()
        stock2 = session.query(StockLevel).filter_by(product_id=product2.id).first()
        assert stock1 is not None and stock2 is not None  # Should exist due to auto-creation
        stock1.quantity = 5
        stock2.quantity = 10
        session.commit()

        # Search for specific product
        response = admin_auth_client.get("/products/stock?search=Searchable")
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        assert "Searchable Product" in response_text
        # Note: we may see "Other Product" in navigation/filters, so we just check main product is there

    def test_stock_brand_filter(self, admin_auth_client: Any, session: Any) -> None:
        """Test stock levels brand filtering."""
        # Create test data
        brand1 = Brand()
        brand1.name = "Brand One"
        brand2 = Brand()
        brand2.name = "Brand Two"
        session.add_all([brand1, brand2])
        session.commit()

        product1 = Product()
        product1.name = "Product from Brand One"
        product1.sku = "BRAND1001"
        product1.brand_id = brand1.id
        product2 = Product()
        product2.name = "Product from Brand Two"
        product2.sku = "BRAND2001"
        product2.brand_id = brand2.id
        session.add_all([product1, product2])
        session.commit()

        # Update auto-created stock levels instead of creating new ones
        stock1 = session.query(StockLevel).filter_by(product_id=product1.id).first()
        stock2 = session.query(StockLevel).filter_by(product_id=product2.id).first()
        assert stock1 is not None and stock2 is not None  # Should exist due to auto-creation
        stock1.quantity = 5
        stock2.quantity = 10
        session.commit()

        brand1_id = brand1.id  # Store ID while in session

        # Filter by brand
        response = admin_auth_client.get(f"/products/stock?brand={brand1_id}")
        assert response.status_code == 200
        response_text = response.get_data(as_text=True)
        assert "Product from Brand One" in response_text


class TestInventoryIntegration:
    """Tests for inventory integration features."""

    def test_automatic_sku_generation(self, admin_auth_client: Any, session: Any) -> None:
        """Test that SKUs are automatically generated when creating products."""
        # Create test brand
        brand = Brand()
        brand.name = "AutoSKU Brand"
        session.add(brand)
        session.commit()
        brand_id = brand.id

        # Create product without specifying SKU
        response = admin_auth_client.post(
            "/products/create",
            data={"name": "AutoSKU Product", "brand_id": brand_id, "min_stock_level": "1"},
            follow_redirects=True,
        )
        assert response.status_code == 200

        # Check that SKU was auto-generated
        product = session.query(Product).filter_by(name="AutoSKU Product").first()
        assert product is not None
        assert product.sku is not None
        assert len(product.sku) > 0

    def test_stock_level_auto_creation(self, admin_auth_client: Any, session: Any) -> None:
        """Test that stock levels are automatically created with new products."""
        # Create test brand
        brand = Brand()
        brand.name = "Stock Test Brand"
        session.add(brand)
        session.commit()
        brand_id = brand.id

        # Create product
        response = admin_auth_client.post(
            "/products/create",
            data={"name": "Stock Test Product", "brand_id": brand_id, "min_stock_level": "5"},
            follow_redirects=True,
        )
        assert response.status_code == 200

        # Check that stock level was auto-created
        product = session.query(Product).filter_by(name="Stock Test Product").first()
        assert product is not None
        assert product.min_stock_level == 5  # min_stock_level is on Product model

        stock_level = session.query(StockLevel).filter_by(product_id=product.id).first()
        assert stock_level is not None  # StockLevel should be auto-created
        assert stock_level.quantity == 0  # Auto-created with quantity 0

    def test_product_deletion_cascades_to_stock(self, admin_auth_client: Any, session: Any) -> None:
        """Test that deleting a product also deletes its stock level."""
        # Create test data
        brand = Brand()
        brand.name = "Cascade Test Brand"
        session.add(brand)
        session.commit()

        product = Product()
        product.name = "Cascade Test Product"
        product.sku = "CASCADE001"
        product.brand_id = brand.id
        session.add(product)
        session.commit()
        product_id = product.id

        # Verify stock level exists
        stock_level = session.query(StockLevel).filter_by(product_id=product_id).first()
        assert stock_level is not None

        # Delete product with CSRF token
        from flask_wtf.csrf import generate_csrf

        with admin_auth_client.application.test_request_context():
            csrf_token = generate_csrf()

        response = admin_auth_client.post(
            f"/products/{product_id}/delete", data={"csrf_token": csrf_token}, follow_redirects=True
        )
        assert response.status_code == 200

        # Check that both product and stock level are deleted
        product = session.get(Product, product_id)
        assert product is None

        stock_level = session.query(StockLevel).filter_by(product_id=product_id).first()
        assert stock_level is None
