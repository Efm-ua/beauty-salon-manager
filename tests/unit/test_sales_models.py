"""
Unit tests for sales models: PaymentMethod, Sale, SaleItem, GoodsReceiptItem
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models import (Appointment, Brand, Client, GoodsReceipt,
                        GoodsReceiptItem, PaymentMethod, Product, Sale,
                        SaleItem, StockLevel, User, db)


class TestPaymentMethodModel:
    """Test PaymentMethod model functionality."""

    def test_create_payment_method(self, app, session):
        """Test creating a payment method."""
        payment_method = PaymentMethod()
        payment_method.name = "Готівка"
        payment_method.is_active = True

        session.add(payment_method)
        session.commit()

        assert payment_method.id is not None
        assert payment_method.name == "Готівка"
        assert payment_method.is_active is True

    def test_payment_method_unique_name(self, app, session):
        """Test that payment method names must be unique."""
        # Create first payment method
        pm1 = PaymentMethod()
        pm1.name = "Картка"
        session.add(pm1)
        session.commit()

        # Try to create second with same name
        pm2 = PaymentMethod()
        pm2.name = "Картка"
        session.add(pm2)

        with pytest.raises(Exception):  # Should raise IntegrityError
            session.commit()

    def test_payment_method_repr(self, app, session):
        """Test PaymentMethod string representation."""
        payment_method = PaymentMethod()
        payment_method.name = "Онлайн оплата"

        assert repr(payment_method) == "<PaymentMethod Онлайн оплата>"


class TestGoodsReceiptItemModel:
    """Test GoodsReceiptItem model functionality."""

    def test_create_goods_receipt_item(self, app, session, sample_product):
        """Test creating a goods receipt item."""
        receipt_date = datetime.now(timezone.utc)
        expiry_date = date(2025, 12, 31)

        # First create a user for the goods receipt
        user = User()
        user.username = "test_goods_user"
        user.password = "hashed_password"
        user.full_name = "Test Goods User"
        user.is_admin = False
        session.add(user)
        session.flush()  # Get user ID

        # Create a goods receipt first
        goods_receipt = GoodsReceipt()
        goods_receipt.receipt_number = "GR001"
        goods_receipt.receipt_date = receipt_date.date()
        goods_receipt.user_id = user.id
        session.add(goods_receipt)
        session.flush()  # Get receipt ID

        # Now create the goods receipt item
        goods_receipt_item = GoodsReceiptItem()
        goods_receipt_item.receipt_id = goods_receipt.id
        goods_receipt_item.product_id = sample_product.id
        goods_receipt_item.quantity_received = 100
        goods_receipt_item.quantity_remaining = 100
        goods_receipt_item.cost_price_per_unit = Decimal("15.50")
        goods_receipt_item.receipt_date = receipt_date
        goods_receipt_item.expiry_date = expiry_date
        goods_receipt_item.batch_number = "BATCH001"
        goods_receipt_item.supplier_info = "Supplier ABC"

        session.add(goods_receipt_item)
        session.commit()

        assert goods_receipt_item.id is not None
        assert goods_receipt_item.receipt_id == goods_receipt.id
        assert goods_receipt_item.product_id == sample_product.id
        assert goods_receipt_item.quantity_received == 100
        assert goods_receipt_item.quantity_remaining == 100
        assert goods_receipt_item.cost_price_per_unit == Decimal("15.50")
        assert goods_receipt_item.receipt_date.replace(tzinfo=None) == receipt_date.replace(tzinfo=None)
        assert goods_receipt_item.expiry_date == expiry_date
        assert goods_receipt_item.batch_number == "BATCH001"
        assert goods_receipt_item.supplier_info == "Supplier ABC"
        assert goods_receipt_item.created_at is not None

    def test_goods_receipt_item_repr(self, app, session, sample_product):
        """Test GoodsReceiptItem string representation."""
        goods_receipt = GoodsReceiptItem()
        goods_receipt.product_id = sample_product.id
        goods_receipt.quantity_received = 50
        goods_receipt.quantity_remaining = 30

        expected_repr = f"<GoodsReceiptItem Product: {sample_product.id}, " f"Received: 50, Remaining: 30>"
        assert repr(goods_receipt) == expected_repr


class TestSaleModel:
    """Test Sale model functionality."""

    def test_create_sale(self, app, session, sample_user, sample_client, sample_payment_method):
        """Test creating a sale."""
        sale_date = datetime.now(timezone.utc)

        sale = Sale()
        sale.sale_date = sale_date
        sale.client_id = sample_client.id
        sale.user_id = sample_user.id
        sale.created_by_user_id = sample_user.id
        sale.total_amount = Decimal("100.50")
        sale.payment_method_id = sample_payment_method.id
        sale.notes = "Test sale"

        session.add(sale)
        session.commit()

        assert sale.id is not None
        assert sale.sale_date.replace(tzinfo=None) == sale_date.replace(tzinfo=None)
        assert sale.client_id == sample_client.id
        assert sale.user_id == sample_user.id
        assert sale.created_by_user_id == sample_user.id
        assert sale.total_amount == Decimal("100.50")
        assert sale.payment_method_id == sample_payment_method.id
        assert sale.notes == "Test sale"
        assert sale.created_at is not None

    def test_sale_without_optional_fields(self, app, session, sample_user):
        """Test creating a sale without optional fields."""
        sale = Sale()
        sale.user_id = sample_user.id
        sale.created_by_user_id = sample_user.id
        sale.total_amount = Decimal("50.00")

        session.add(sale)
        session.commit()

        assert sale.id is not None
        assert sale.client_id is None
        assert sale.appointment_id is None
        assert sale.payment_method_id is None
        assert sale.notes is None
        assert sale.total_amount == Decimal("50.00")

    def test_sale_repr(self, app, session, sample_user):
        """Test Sale string representation."""
        sale_date = datetime(2025, 5, 30, 14, 30, 0)

        sale = Sale()
        sale.id = 1
        sale.sale_date = sale_date
        sale.total_amount = Decimal("123.45")
        sale.user_id = sample_user.id
        sale.created_by_user_id = sample_user.id

        session.add(sale)
        session.commit()

        expected_repr = f"<Sale {sale.id} - {sale_date} - Total: 123.45>"
        assert repr(sale) == expected_repr


class TestSaleItemModel:
    """Test SaleItem model functionality."""

    def test_create_sale_item(self, app, session, sample_sale, sample_product):
        """Test creating a sale item."""
        sale_item = SaleItem()
        sale_item.sale_id = sample_sale.id
        sale_item.product_id = sample_product.id
        sale_item.quantity = 3
        sale_item.price_per_unit = Decimal("25.00")
        sale_item.cost_price_per_unit = Decimal("15.00")

        session.add(sale_item)
        session.commit()

        assert sale_item.id is not None
        assert sale_item.sale_id == sample_sale.id
        assert sale_item.product_id == sample_product.id
        assert sale_item.quantity == 3
        assert sale_item.price_per_unit == Decimal("25.00")
        assert sale_item.cost_price_per_unit == Decimal("15.00")

    def test_sale_item_total_price(self, app, session, sample_sale, sample_product):
        """Test SaleItem total_price property."""
        sale_item = SaleItem()
        sale_item.sale_id = sample_sale.id
        sale_item.product_id = sample_product.id
        sale_item.quantity = 4
        sale_item.price_per_unit = Decimal("12.50")
        sale_item.cost_price_per_unit = Decimal("8.00")

        expected_total = Decimal("50.00")  # 4 * 12.50
        assert sale_item.total_price == expected_total

    def test_sale_item_total_cost(self, app, session, sample_sale, sample_product):
        """Test SaleItem total_cost property."""
        sale_item = SaleItem()
        sale_item.sale_id = sample_sale.id
        sale_item.product_id = sample_product.id
        sale_item.quantity = 5
        sale_item.price_per_unit = Decimal("20.00")
        sale_item.cost_price_per_unit = Decimal("12.00")

        expected_total_cost = Decimal("60.00")  # 5 * 12.00
        assert sale_item.total_cost == expected_total_cost

    def test_sale_item_profit(self, app, session, sample_sale, sample_product):
        """Test SaleItem profit property."""
        sale_item = SaleItem()
        sale_item.sale_id = sample_sale.id
        sale_item.product_id = sample_product.id
        sale_item.quantity = 2
        sale_item.price_per_unit = Decimal("30.00")
        sale_item.cost_price_per_unit = Decimal("18.00")

        expected_profit = Decimal("24.00")  # (30.00 - 18.00) * 2
        assert sale_item.profit == expected_profit

    def test_sale_item_repr(self, app, session, sample_sale, sample_product):
        """Test SaleItem string representation."""
        sale_item = SaleItem()
        sale_item.sale_id = sample_sale.id
        sale_item.product_id = sample_product.id
        sale_item.quantity = 7

        expected_repr = f"<SaleItem Sale: {sample_sale.id}, Product: {sample_product.id}, Qty: 7>"
        assert repr(sale_item) == expected_repr


# Fixtures for the tests - need to add these to use existing fixtures from conftest.py
@pytest.fixture
def sample_user(session):
    """Create a sample user for testing."""
    user = User()
    user.username = "test_sales_user"
    user.password = "hashed_password"
    user.full_name = "Test Sales User"
    user.is_admin = False

    session.add(user)
    session.commit()
    return user


@pytest.fixture
def sample_client(session):
    """Create a sample client for testing."""
    client = Client()
    client.name = "Test Sales Client"
    client.phone = "+380999999999"
    client.email = "test_sales@example.com"

    session.add(client)
    session.commit()
    return client


@pytest.fixture
def sample_brand(session):
    """Create a sample brand for testing."""
    brand = Brand()
    brand.name = "Test Sales Brand"

    session.add(brand)
    session.commit()
    return brand


@pytest.fixture
def sample_product(session, sample_brand):
    """Create a sample product for testing."""
    product = Product()
    product.name = "Test Sales Product"
    product.sku = "TSP001"
    product.brand_id = sample_brand.id
    product.current_sale_price = Decimal("25.00")

    session.add(product)
    session.commit()
    return product


@pytest.fixture
def sample_payment_method(session):
    """Create a sample payment method for testing."""
    payment_method = PaymentMethod()
    payment_method.name = "Test Payment Method"
    payment_method.is_active = True

    session.add(payment_method)
    session.commit()
    return payment_method


@pytest.fixture
def sample_sale(session, sample_user, sample_client, sample_payment_method):
    """Create a sample sale for testing."""
    sale = Sale()
    sale.user_id = sample_user.id
    sale.created_by_user_id = sample_user.id
    sale.client_id = sample_client.id
    sale.payment_method_id = sample_payment_method.id
    sale.total_amount = Decimal("100.00")
    sale.notes = "Test sale"

    session.add(sale)
    session.commit()
    return sale


@pytest.fixture
def sample_goods_receipt_item(session, sample_product):
    """Create a sample goods receipt item for testing."""
    # First create a user for the goods receipt
    user = User()
    user.username = "test_fixture_user"
    user.password = "hashed_password"
    user.full_name = "Test Fixture User"
    user.is_admin = False
    session.add(user)
    session.flush()  # Get user ID

    # Create a goods receipt first
    goods_receipt = GoodsReceipt()
    goods_receipt.receipt_number = "GR_FIXTURE_001"
    goods_receipt.receipt_date = datetime.now(timezone.utc).date()
    goods_receipt.user_id = user.id
    session.add(goods_receipt)
    session.flush()  # Get receipt ID

    # Now create the goods receipt item
    goods_receipt_item = GoodsReceiptItem()
    goods_receipt_item.receipt_id = goods_receipt.id
    goods_receipt_item.product_id = sample_product.id
    goods_receipt_item.quantity_received = 50
    goods_receipt_item.quantity_remaining = 50
    goods_receipt_item.cost_price_per_unit = Decimal("10.00")
    goods_receipt_item.receipt_date = datetime.now(timezone.utc)
    goods_receipt_item.batch_number = "TEST_BATCH"

    session.add(goods_receipt_item)
    session.commit()
    return goods_receipt_item
