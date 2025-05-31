"""
Functional tests for sales interface.
Tests for creating, viewing, and listing sales through the web interface.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from werkzeug.security import generate_password_hash

from app.models import (Brand, Client, GoodsReceipt, GoodsReceiptItem,
                        PaymentMethod, Product, Sale, SaleItem, StockLevel,
                        User, db)
from app.services.sales_service import SaleItemData, SalesService


class TestSalesInterface:
    """Test sales interface functionality."""

    @pytest.fixture(autouse=True)
    def setup_test_data(self, session):
        """Set up test data for sales interface tests."""
        # Create admin user
        self.admin_user = User(
            username="admin_sales",
            password=generate_password_hash("password123"),
            full_name="Sales Admin",
            is_admin=True,
            is_active_master=True,
        )
        session.add(self.admin_user)

        # Create regular master user
        self.master_user = User(
            username="master_sales",
            password=generate_password_hash("password123"),
            full_name="Master User",
            is_admin=False,
            is_active_master=True,
        )
        session.add(self.master_user)

        # Create client
        self.client_data = Client(
            name="Test Client",
            phone="+380123456789",
            email="client@test.com",
        )
        session.add(self.client_data)

        # Create payment method
        self.payment_method = PaymentMethod(
            name="Готівка",
            is_active=True,
        )
        session.add(self.payment_method)

        # Create brand
        self.brand = Brand(name="Test Brand")
        session.add(self.brand)

        # Create products with stock
        self.product1 = Product(
            name="Test Product 1",
            sku="TEST001",
            brand_id=1,  # Will be set after flush
            current_sale_price=Decimal("100.00"),
            last_cost_price=Decimal("50.00"),
        )
        self.product2 = Product(
            name="Test Product 2",
            sku="TEST002",
            brand_id=1,  # Will be set after flush
            current_sale_price=Decimal("200.00"),
            last_cost_price=Decimal("100.00"),
        )

        session.flush()  # Get IDs

        # Set brand IDs correctly
        self.product1.brand_id = self.brand.id
        self.product2.brand_id = self.brand.id

        session.add_all([self.product1, self.product2])
        session.flush()

        # Create goods receipts first
        goods_receipt1 = GoodsReceipt(
            receipt_number="GR_TEST001",
            receipt_date=datetime.now(timezone.utc).date(),
            user_id=self.admin_user.id,
        )
        goods_receipt2 = GoodsReceipt(
            receipt_number="GR_TEST002",
            receipt_date=datetime.now(timezone.utc).date(),
            user_id=self.admin_user.id,
        )
        session.add_all([goods_receipt1, goods_receipt2])
        session.flush()

        # Add stock with FIFO data
        goods_receipt_item1 = GoodsReceiptItem(
            receipt_id=goods_receipt1.id,
            product_id=self.product1.id,
            quantity_received=100,
            quantity_remaining=100,
            cost_price_per_unit=Decimal("50.00"),
            receipt_date=datetime.now(timezone.utc),
        )
        goods_receipt_item2 = GoodsReceiptItem(
            receipt_id=goods_receipt2.id,
            product_id=self.product2.id,
            quantity_received=50,
            quantity_remaining=50,
            cost_price_per_unit=Decimal("100.00"),
            receipt_date=datetime.now(timezone.utc),
        )

        session.add_all([goods_receipt_item1, goods_receipt_item2])

        # Update stock levels
        stock1 = StockLevel.query.filter_by(product_id=self.product1.id).first()
        stock2 = StockLevel.query.filter_by(product_id=self.product2.id).first()
        stock1.quantity = 100
        stock2.quantity = 50

        session.commit()

    def test_sales_list_access_admin(self, admin_auth_client):
        """Test that admin can access sales list."""
        # Access sales list
        response = admin_auth_client.get("/sales/")
        assert response.status_code == 200
        assert "Продажі" in response.get_data(as_text=True)
        assert "Новий продаж" in response.get_data(as_text=True)

    def test_sales_list_access_denied_master(self, client):
        """Test that non-admin users cannot access sales list."""
        # Login as master (non-admin)
        client.post(
            "/auth/login",
            data={"username": "master_sales", "password": "password123"},
            follow_redirects=True,
        )

        # Try to access sales list
        response = client.get("/sales/", follow_redirects=True)
        assert response.status_code == 200
        assert "Доступ заборонено" in response.get_data(as_text=True)

    def test_create_sale_form_access(self, admin_auth_client):
        """Test access to create sale form."""
        # Access create sale form
        response = admin_auth_client.get("/sales/new")
        assert response.status_code == 200

        data = response.get_data(as_text=True)
        assert "Новий продаж" in data
        assert "Test Product 1" in data
        assert "Test Product 2" in data
        assert "Test Client" in data
        assert "Анонімний клієнт" in data

    def test_create_sale_single_product_success(self, admin_auth_client):
        """Test successful creation of sale with single product."""
        # Create sale with single product
        response = admin_auth_client.post(
            "/sales/new",
            data={
                "csrf_token": self._get_csrf_token(admin_auth_client, "/sales/new"),
                "client_id": self.client_data.id,
                "user_id": self.admin_user.id,
                "payment_method_id": self.payment_method.id,
                "sale_items-0-product_id": self.product1.id,
                "sale_items-0-quantity": "2",
                "notes": "Test sale",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert "успішно створено" in response.get_data(as_text=True)

        # Verify sale in database
        sale = Sale.query.first()
        assert sale is not None
        assert sale.total_amount == 200.00  # 2 * 100.00
        assert len(sale.items) == 1
        assert sale.items[0].quantity == 2

    def test_create_sale_multiple_products_success(self, admin_auth_client):
        """Test successful creation of sale with multiple products."""
        # Create sale with multiple products
        response = admin_auth_client.post(
            "/sales/new",
            data={
                "csrf_token": self._get_csrf_token(admin_auth_client, "/sales/new"),
                "client_id": "",  # Anonymous client
                "user_id": self.master_user.id,
                "payment_method_id": self.payment_method.id,
                "sale_items-0-product_id": self.product1.id,
                "sale_items-0-quantity": "1",
                "sale_items-1-product_id": self.product2.id,
                "sale_items-1-quantity": "3",
                "notes": "Multiple products sale",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert "успішно створено" in response.get_data(as_text=True)

        # Verify sale in database
        sale = Sale.query.first()
        assert sale is not None
        assert sale.total_amount == 700.00  # 1 * 100.00 + 3 * 200.00
        assert len(sale.items) == 2

    def test_create_sale_insufficient_stock(self, admin_auth_client):
        """Test sale creation with insufficient stock."""
        # Try to create sale with more stock than available
        response = admin_auth_client.post(
            "/sales/new",
            data={
                "csrf_token": self._get_csrf_token(admin_auth_client, "/sales/new"),
                "user_id": self.admin_user.id,
                "payment_method_id": self.payment_method.id,
                "sale_items-0-product_id": self.product1.id,
                "sale_items-0-quantity": "200",  # More than available (100)
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        data = response.get_data(as_text=True)
        assert "Недостатньо товару" in data or "не вистачає" in data.lower()

    def test_create_sale_form_validation(self, admin_auth_client):
        """Test form validation for required fields."""
        # Try to create sale without required fields
        response = admin_auth_client.post(
            "/sales/new",
            data={
                "csrf_token": self._get_csrf_token(admin_auth_client, "/sales/new"),
                # Missing user_id and payment_method_id
                "sale_items-0-product_id": self.product1.id,
                "sale_items-0-quantity": "1",
            },
        )

        assert response.status_code == 200
        data = response.get_data(as_text=True)
        assert "Оберіть продавця" in data or "Оберіть спосіб оплати" in data

    def test_view_sale_details(self, admin_auth_client):
        """Test viewing sale details."""
        # Create a sale using service
        sale = SalesService.create_sale(
            user_id=self.admin_user.id,
            created_by_user_id=self.admin_user.id,
            sale_items=[
                SaleItemData(product_id=self.product1.id, quantity=2),
                SaleItemData(product_id=self.product2.id, quantity=1),
            ],
            client_id=self.client_data.id,
            payment_method_id=self.payment_method.id,
            notes="Test sale for viewing",
        )

        # View sale details
        response = admin_auth_client.get(f"/sales/{sale.id}")
        assert response.status_code == 200

        data = response.get_data(as_text=True)
        assert f"Продаж №{sale.id}" in data
        assert "Test Client" in data
        assert "Sales Admin" in data
        assert "Test Product 1" in data
        assert "Test Product 2" in data
        assert "400.00" in data  # Total: 2*100 + 1*200

    def test_view_nonexistent_sale(self, admin_auth_client):
        """Test viewing non-existent sale returns 404."""
        # Try to view non-existent sale
        response = admin_auth_client.get("/sales/999")
        assert response.status_code == 404

    def test_sales_list_with_data(self, admin_auth_client):
        """Test sales list display with existing sales."""
        # Create multiple sales
        for i in range(3):
            SalesService.create_sale(
                user_id=self.admin_user.id,
                created_by_user_id=self.admin_user.id,
                sale_items=[
                    SaleItemData(product_id=self.product1.id, quantity=1),
                ],
                client_id=self.client_data.id if i % 2 == 0 else None,
                payment_method_id=self.payment_method.id,
                notes=f"Test sale {i+1}",
            )

        # View sales list
        response = admin_auth_client.get("/sales/")
        assert response.status_code == 200

        data = response.get_data(as_text=True)
        assert "Test Client" in data
        assert "Анонімний клієнт" in data
        assert "Sales Admin" in data
        assert "100.00" in data

    def test_sales_navigation_link_admin(self, admin_auth_client):
        """Test that sales navigation link appears for admin."""
        # Check main page for navigation link
        response = admin_auth_client.get("/")
        assert response.status_code == 200

        data = response.get_data(as_text=True)
        assert 'href="/sales/"' in data
        assert "Продажі" in data

    def test_sales_navigation_link_master(self, client):
        """Test that sales navigation link does not appear for non-admin."""
        # Login as master (non-admin)
        client.post(
            "/auth/login",
            data={"username": "master_sales", "password": "password123"},
            follow_redirects=True,
        )

        # Check main page for navigation link
        response = client.get("/")
        assert response.status_code == 200

        data = response.get_data(as_text=True)
        # Should not contain sales link
        assert 'href="/sales/"' not in data

    def test_fifo_cost_calculation(self, admin_auth_client):
        """Test that FIFO cost calculation works correctly in interface."""
        # Create sale
        response = admin_auth_client.post(
            "/sales/new",
            data={
                "csrf_token": self._get_csrf_token(admin_auth_client, "/sales/new"),
                "user_id": self.admin_user.id,
                "payment_method_id": self.payment_method.id,
                "sale_items-0-product_id": self.product1.id,
                "sale_items-0-quantity": "5",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200

        # Verify sale item has correct cost price from FIFO
        sale = Sale.query.first()
        sale_item = sale.items[0]
        assert sale_item.cost_price_per_unit == Decimal("50.00")  # From goods receipt

    def _get_csrf_token(self, client, url):
        """Helper to get CSRF token from form."""
        response = client.get(url)
        data = response.get_data(as_text=True)
        # Extract CSRF token from form (simple approach)
        start = data.find('name="csrf_token" value="') + len('name="csrf_token" value="')
        end = data.find('"', start)
        return data[start:end] if start > -1 and end > -1 else ""


class TestSalesInterfaceEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.fixture(autouse=True)
    def setup_minimal_data(self, session):
        """Set up minimal test data."""
        # Create admin user
        self.admin_user = User(
            username="admin_edge",
            password=generate_password_hash("password123"),
            full_name="Admin Edge",
            is_admin=True,
            is_active_master=True,
        )
        session.add(self.admin_user)
        session.commit()

    def test_create_sale_no_products_available(self, admin_auth_client):
        """Test create sale form when no products are available."""
        # Access create sale form (no products exist)
        response = admin_auth_client.get("/sales/new")
        assert response.status_code == 200
        # Form should still load but have empty product options

    def test_empty_sales_list(self, admin_auth_client):
        """Test sales list when no sales exist."""
        # View empty sales list
        response = admin_auth_client.get("/sales/")
        assert response.status_code == 200

        data = response.get_data(as_text=True)
        assert "Продажі відсутні" in data or "Почніть з створення" in data


class TestSalesAppointmentIntegration:
    """Test sales and appointments integration."""

    @pytest.fixture(autouse=True)
    def setup_integration_data(self, session):
        """Set up test data for integration tests."""
        import uuid
        from datetime import date, time
        from decimal import Decimal

        from werkzeug.security import generate_password_hash

        from app.models import (Appointment, Brand, Client, GoodsReceipt,
                                GoodsReceiptItem, PaymentMethod, Product,
                                Service, StockLevel, User)

        # Create unique ID to avoid conflicts
        unique_id = uuid.uuid4().hex[:8]

        # Create admin user
        self.admin_user = User(
            username=f"admin_integration_{unique_id}",
            password=generate_password_hash("password123"),
            full_name="Admin Integration",
            is_admin=True,
            is_active_master=True,
        )
        session.add(self.admin_user)

        # Create client
        self.client_data = Client(
            name="Integration Client", phone=f"+38050123{unique_id[:4]}", email=f"integration{unique_id[:4]}@test.com"
        )
        session.add(self.client_data)

        # Create service
        self.service = Service(name=f"Integration Service {unique_id}", duration=60, base_price=150.0)
        session.add(self.service)

        # Create payment method
        self.payment_method = PaymentMethod(name="Готівка", is_active=True)
        session.add(self.payment_method)

        # Create brand and product
        self.brand = Brand(name=f"Integration Brand {unique_id}")
        session.add(self.brand)
        session.flush()

        self.product = Product(
            name=f"Integration Product {unique_id}",
            sku=f"INT{unique_id}",
            brand_id=self.brand.id,
            current_sale_price=Decimal("100.00"),
            last_cost_price=Decimal("50.00"),
        )
        session.add(self.product)
        session.flush()

        # Check if StockLevel already exists for this product
        existing_stock = StockLevel.query.filter_by(product_id=self.product.id).first()
        if existing_stock:
            # Update existing stock
            existing_stock.quantity = 10
            self.stock = existing_stock
        else:
            # Add new stock
            self.stock = StockLevel(product_id=self.product.id, quantity=10)
            session.add(self.stock)

        # Add goods receipt for FIFO
        self.receipt = GoodsReceipt(receipt_date=date.today(), user_id=self.admin_user.id)
        session.add(self.receipt)
        session.flush()

        self.receipt_item = GoodsReceiptItem(
            receipt_id=self.receipt.id,
            product_id=self.product.id,
            quantity_received=10,
            quantity_remaining=10,
            cost_price_per_unit=Decimal("50.00"),
        )
        session.add(self.receipt_item)

        # Create appointment
        self.appointment = Appointment(
            client_id=self.client_data.id,
            master_id=self.admin_user.id,
            date=date.today(),
            start_time=time(10, 0),
            end_time=time(11, 0),
            status="scheduled",
        )
        session.add(self.appointment)
        session.commit()

    def test_create_sale_with_appointment_link(self, admin_auth_client):
        """Test creating a sale linked to an appointment."""
        # Access create sale form
        response = admin_auth_client.get("/sales/new")
        assert response.status_code == 200

        # Check that appointment field is present by looking for the field name
        data = response.get_data(as_text=True)
        assert 'name="appointment_id"' in data

        # Create sale linked to appointment
        response = admin_auth_client.post(
            "/sales/new",
            data={
                "csrf_token": self._get_csrf_token(admin_auth_client, "/sales/new"),
                "client_id": self.client_data.id,
                "user_id": self.admin_user.id,
                "appointment_id": self.appointment.id,
                "payment_method_id": self.payment_method.id,
                "sale_items-0-product_id": self.product.id,
                "sale_items-0-quantity": "2",
                "notes": "Test sale linked to appointment",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert "успішно створено" in response.get_data(as_text=True)

        # Verify sale is linked to appointment
        from app.models import Sale

        sale = Sale.query.filter_by(appointment_id=self.appointment.id).first()
        assert sale is not None
        assert sale.appointment_id == self.appointment.id

    def test_sale_form_shows_appointment_options(self, admin_auth_client):
        """Test that sale form shows appointment options."""
        # Access create sale form
        response = admin_auth_client.get("/sales/new")
        assert response.status_code == 200

        data = response.get_data(as_text=True)
        # Check that appointment field is present by looking for the field name
        assert 'name="appointment_id"' in data
        # Also check for the blank text option
        assert "записом" in data  # Part of the label text

    def test_create_sale_without_appointment_link(self, admin_auth_client):
        """Test creating a sale without linking to appointment."""
        # Create sale without appointment link
        response = admin_auth_client.post(
            "/sales/new",
            data={
                "csrf_token": self._get_csrf_token(admin_auth_client, "/sales/new"),
                "client_id": self.client_data.id,
                "user_id": self.admin_user.id,
                "payment_method_id": self.payment_method.id,
                "sale_items-0-product_id": self.product.id,
                "sale_items-0-quantity": "1",
                "notes": "Test sale without appointment",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert "успішно створено" in response.get_data(as_text=True)

        # Verify sale is not linked to appointment
        from app.models import Sale

        sale = Sale.query.first()
        assert sale is not None
        assert sale.appointment_id is None

    def _get_csrf_token(self, client, url):
        """Helper to get CSRF token from form."""
        response = client.get(url)
        data = response.get_data(as_text=True)
        # Extract CSRF token from form (simple approach)
        start = data.find('name="csrf_token" value="') + len('name="csrf_token" value="')
        end = data.find('"', start)
        return data[start:end] if start > -1 and end > -1 else ""
