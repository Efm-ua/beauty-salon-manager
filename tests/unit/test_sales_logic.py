"""
Unit tests for sales service and FIFO inventory logic.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models import (Brand, Client, GoodsReceipt, GoodsReceiptItem,
                        PaymentMethod, Product, Sale, SaleItem, StockLevel,
                        User, db)
from app.services.sales_service import (InsufficientStockError,
                                        ProductNotFoundError, SaleItemData,
                                        SalesService)


class TestSaleItemData:
    """Test SaleItemData helper class."""

    def test_create_sale_item_data(self):
        """Test creating valid SaleItemData."""
        item_data = SaleItemData(product_id=1, quantity=5)

        assert item_data.product_id == 1
        assert item_data.quantity == 5

    def test_sale_item_data_invalid_quantity(self):
        """Test that invalid quantity raises error."""
        with pytest.raises(ValueError, match="Кількість повинна бути більше 0"):
            SaleItemData(product_id=1, quantity=0)

        with pytest.raises(ValueError, match="Кількість повинна бути більше 0"):
            SaleItemData(product_id=1, quantity=-1)


class TestSalesServiceCreate:
    """Test SalesService.create_sale method."""

    def test_create_simple_sale(
        self, app, session, sample_user, sample_client, sample_payment_method, sample_product_with_stock_and_receipt
    ):
        """Test creating a simple sale with one item."""
        product, stock_level, receipt_item = sample_product_with_stock_and_receipt

        # Create sale items
        sale_items = [SaleItemData(product_id=product.id, quantity=2)]

        # Create sale
        sale = SalesService.create_sale(
            user_id=sample_user.id,
            created_by_user_id=sample_user.id,
            sale_items=sale_items,
            client_id=sample_client.id,
            payment_method_id=sample_payment_method.id,
            notes="Test sale",
        )

        # Verify sale
        assert sale.id is not None
        assert sale.user_id == sample_user.id
        assert sale.created_by_user_id == sample_user.id
        assert sale.client_id == sample_client.id
        assert sale.payment_method_id == sample_payment_method.id
        assert sale.notes == "Test sale"
        assert len(sale.items) == 1

        # Verify sale item
        sale_item = sale.items[0]
        assert sale_item.product_id == product.id
        assert sale_item.quantity == 2
        assert sale_item.price_per_unit == product.current_sale_price
        assert sale_item.cost_price_per_unit == receipt_item.cost_price_per_unit

        # Verify total amount
        expected_total = product.current_sale_price * 2
        assert sale.total_amount == expected_total

        # Verify stock was reduced
        session.refresh(stock_level)
        assert stock_level.quantity == 8  # 10 - 2

        # Verify receipt item was reduced
        session.refresh(receipt_item)
        assert receipt_item.quantity_remaining == 8  # 10 - 2

    def test_create_sale_without_optional_fields(
        self, app, session, sample_user, sample_product_with_stock_and_receipt
    ):
        """Test creating a sale without optional fields."""
        product, stock_level, receipt_item = sample_product_with_stock_and_receipt

        sale_items = [SaleItemData(product_id=product.id, quantity=1)]

        sale = SalesService.create_sale(
            user_id=sample_user.id, created_by_user_id=sample_user.id, sale_items=sale_items
        )

        assert sale.id is not None
        assert sale.client_id is None
        assert sale.appointment_id is None
        assert sale.payment_method_id is None
        assert sale.notes is None
        assert len(sale.items) == 1

    def test_create_sale_with_multiple_items(self, app, session, sample_user, sample_client, sample_payment_method):
        """Test creating a sale with multiple different products."""
        # Create two products with stock
        product1 = self._create_product_with_stock(
            "Product 1", "SKU001", Decimal("20.00"), 5, Decimal("12.00"), session
        )
        product2 = self._create_product_with_stock("Product 2", "SKU002", Decimal("15.00"), 3, Decimal("8.00"), session)

        sale_items = [
            SaleItemData(product_id=product1.id, quantity=2),
            SaleItemData(product_id=product2.id, quantity=1),
        ]

        sale = SalesService.create_sale(
            user_id=sample_user.id,
            created_by_user_id=sample_user.id,
            sale_items=sale_items,
            client_id=sample_client.id,
            payment_method_id=sample_payment_method.id,
        )

        assert len(sale.items) == 2

        # Check total amount: (20.00 * 2) + (15.00 * 1) = 55.00
        expected_total = Decimal("55.00")
        assert sale.total_amount == expected_total

        # Verify stock levels were updated
        stock1 = StockLevel.query.filter_by(product_id=product1.id).first()
        stock2 = StockLevel.query.filter_by(product_id=product2.id).first()
        assert stock1.quantity == 3  # 5 - 2
        assert stock2.quantity == 2  # 3 - 1

    def test_create_sale_insufficient_stock(self, app, session, sample_user, sample_product_with_stock_and_receipt):
        """Test that creating sale with insufficient stock raises error."""
        product, stock_level, receipt_item = sample_product_with_stock_and_receipt

        # Try to sell more than available (10 in stock, trying to sell 15)
        sale_items = [SaleItemData(product_id=product.id, quantity=15)]

        with pytest.raises(InsufficientStockError) as exc_info:
            SalesService.create_sale(user_id=sample_user.id, created_by_user_id=sample_user.id, sale_items=sale_items)

        assert "Недостатньо товару" in str(exc_info.value)
        assert exc_info.value.requested_qty == 15
        assert exc_info.value.available_qty == 10

    def test_create_sale_nonexistent_product(self, app, session, sample_user):
        """Test that creating sale with nonexistent product raises error."""
        sale_items = [SaleItemData(product_id=99999, quantity=1)]

        with pytest.raises(ProductNotFoundError):
            SalesService.create_sale(user_id=sample_user.id, created_by_user_id=sample_user.id, sale_items=sale_items)

    def test_create_sale_nonexistent_user(self, app, session, sample_product_with_stock_and_receipt):
        """Test that creating sale with nonexistent user raises error."""
        product, _, _ = sample_product_with_stock_and_receipt
        sale_items = [SaleItemData(product_id=product.id, quantity=1)]

        with pytest.raises(ValueError, match="Користувач з ID 99999 не знайдений"):
            SalesService.create_sale(user_id=99999, created_by_user_id=99999, sale_items=sale_items)

    def test_create_sale_empty_items(self, app, session, sample_user):
        """Test that creating sale with empty items list raises error."""
        with pytest.raises(ValueError, match="Список товарів не може бути порожнім"):
            SalesService.create_sale(user_id=sample_user.id, created_by_user_id=sample_user.id, sale_items=[])

    def _create_product_with_stock(self, name, sku, sale_price, stock_qty, cost_price, session):
        """Helper method to create a product with stock and receipt item."""
        # Create brand
        brand = Brand()
        brand.name = f"Test Brand for {name}"
        session.add(brand)
        session.flush()

        # Create product
        product = Product()
        product.name = name
        product.sku = sku
        product.brand_id = brand.id
        product.current_sale_price = sale_price
        session.add(product)
        session.flush()

        # Create user for the goods receipt
        user = User()
        user.username = f"test_user_{sku}"
        user.password = "hashed_password"
        user.full_name = f"Test User for {name}"
        user.is_admin = False
        session.add(user)
        session.flush()

        # Create goods receipt first
        goods_receipt = GoodsReceipt()
        goods_receipt.receipt_number = f"GR_{sku}"
        goods_receipt.receipt_date = datetime.now(timezone.utc).date()
        goods_receipt.user_id = user.id
        session.add(goods_receipt)
        session.flush()

        # Update stock level (created automatically by event listener)
        stock_level = StockLevel.query.filter_by(product_id=product.id).first()
        stock_level.quantity = stock_qty

        # Create goods receipt item
        receipt_item = GoodsReceiptItem()
        receipt_item.receipt_id = goods_receipt.id
        receipt_item.product_id = product.id
        receipt_item.quantity_received = stock_qty
        receipt_item.quantity_remaining = stock_qty
        receipt_item.cost_price_per_unit = cost_price
        receipt_item.receipt_date = datetime.now(timezone.utc)
        session.add(receipt_item)

        session.commit()
        return product


class TestFIFOLogic:
    """Test FIFO inventory depletion logic."""

    def test_fifo_single_batch(self, app, session, sample_user, sample_brand):
        """Test FIFO with items from single batch."""
        # Create product
        product = Product()
        product.name = "FIFO Test Product"
        product.sku = "FIFO001"
        product.brand_id = sample_brand.id
        product.current_sale_price = Decimal("25.00")
        session.add(product)
        session.flush()

        # Create goods receipt first
        goods_receipt = GoodsReceipt()
        goods_receipt.receipt_number = "GR_FIFO001"
        goods_receipt.receipt_date = datetime(2025, 1, 1, tzinfo=timezone.utc).date()
        goods_receipt.user_id = sample_user.id
        session.add(goods_receipt)
        session.flush()

        # Create single receipt batch
        receipt_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        receipt_item = GoodsReceiptItem()
        receipt_item.receipt_id = goods_receipt.id
        receipt_item.product_id = product.id
        receipt_item.quantity_received = 20
        receipt_item.quantity_remaining = 20
        receipt_item.cost_price_per_unit = Decimal("15.00")
        receipt_item.receipt_date = receipt_date
        session.add(receipt_item)

        # Update stock
        stock_level = StockLevel.query.filter_by(product_id=product.id).first()
        stock_level.quantity = 20
        session.commit()

        # Create sale
        sale_items = [SaleItemData(product_id=product.id, quantity=5)]
        sale = SalesService.create_sale(
            user_id=sample_user.id, created_by_user_id=sample_user.id, sale_items=sale_items
        )

        # Verify cost price matches the single batch
        sale_item = sale.items[0]
        assert sale_item.cost_price_per_unit == Decimal("15.00")

        # Verify quantities
        session.refresh(receipt_item)
        session.refresh(stock_level)
        assert receipt_item.quantity_remaining == 15  # 20 - 5
        assert stock_level.quantity == 15

    def test_fifo_multiple_batches_weighted_average(self, app, session, sample_user, sample_brand):
        """Test FIFO with items from multiple batches - weighted average cost."""
        # Create product
        product = Product()
        product.name = "FIFO Multi Test"
        product.sku = "FIFO002"
        product.brand_id = sample_brand.id
        product.current_sale_price = Decimal("30.00")
        session.add(product)
        session.flush()

        # Create goods receipt for batch 1
        goods_receipt1 = GoodsReceipt()
        goods_receipt1.receipt_number = "GR_FIFO002_1"
        goods_receipt1.receipt_date = datetime(2025, 1, 1, tzinfo=timezone.utc).date()
        goods_receipt1.user_id = sample_user.id
        session.add(goods_receipt1)
        session.flush()

        # Create goods receipt for batch 2
        goods_receipt2 = GoodsReceipt()
        goods_receipt2.receipt_number = "GR_FIFO002_2"
        goods_receipt2.receipt_date = datetime(2025, 1, 15, tzinfo=timezone.utc).date()
        goods_receipt2.user_id = sample_user.id
        session.add(goods_receipt2)
        session.flush()

        # Create multiple receipt batches with different dates and costs
        # Batch 1 (older)
        receipt1 = GoodsReceiptItem()
        receipt1.receipt_id = goods_receipt1.id
        receipt1.product_id = product.id
        receipt1.quantity_received = 10
        receipt1.quantity_remaining = 10
        receipt1.cost_price_per_unit = Decimal("12.00")
        receipt1.receipt_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
        session.add(receipt1)

        # Batch 2 (newer)
        receipt2 = GoodsReceiptItem()
        receipt2.receipt_id = goods_receipt2.id
        receipt2.product_id = product.id
        receipt2.quantity_received = 15
        receipt2.quantity_remaining = 15
        receipt2.cost_price_per_unit = Decimal("18.00")
        receipt2.receipt_date = datetime(2025, 1, 15, tzinfo=timezone.utc)
        session.add(receipt2)

        # Update stock
        stock_level = StockLevel.query.filter_by(product_id=product.id).first()
        stock_level.quantity = 25
        session.commit()

        # Sell 15 items (should deplete all of batch 1 + 5 from batch 2)
        sale_items = [SaleItemData(product_id=product.id, quantity=15)]
        sale = SalesService.create_sale(
            user_id=sample_user.id, created_by_user_id=sample_user.id, sale_items=sale_items
        )

        # Calculate expected weighted average cost:
        # 10 items at 12.00 = 120.00
        # 5 items at 18.00 = 90.00
        # Total: 210.00 / 15 = 14.00
        expected_cost = Decimal("14.00")

        sale_item = sale.items[0]
        assert sale_item.cost_price_per_unit == expected_cost

        # Verify remaining quantities
        session.refresh(receipt1)
        session.refresh(receipt2)
        session.refresh(stock_level)

        assert receipt1.quantity_remaining == 0  # Fully depleted
        assert receipt2.quantity_remaining == 10  # 15 - 5 = 10
        assert stock_level.quantity == 10  # 25 - 15

    def test_fifo_exact_batch_depletion(self, app, session, sample_user, sample_brand):
        """Test FIFO when selling exactly matches a batch quantity."""
        # Create product
        product = Product()
        product.name = "FIFO Exact Test"
        product.sku = "FIFO003"
        product.brand_id = sample_brand.id
        product.current_sale_price = Decimal("20.00")
        session.add(product)
        session.flush()

        # Create goods receipt first
        goods_receipt = GoodsReceipt()
        goods_receipt.receipt_number = "GR_FIFO003"
        goods_receipt.receipt_date = datetime.now(timezone.utc).date()
        goods_receipt.user_id = sample_user.id
        session.add(goods_receipt)
        session.flush()

        # Create batch
        receipt_item = GoodsReceiptItem()
        receipt_item.receipt_id = goods_receipt.id
        receipt_item.product_id = product.id
        receipt_item.quantity_received = 8
        receipt_item.quantity_remaining = 8
        receipt_item.cost_price_per_unit = Decimal("10.00")
        receipt_item.receipt_date = datetime.now(timezone.utc)
        session.add(receipt_item)

        # Update stock
        stock_level = StockLevel.query.filter_by(product_id=product.id).first()
        stock_level.quantity = 8
        session.commit()

        # Sell exactly the batch quantity
        sale_items = [SaleItemData(product_id=product.id, quantity=8)]
        sale = SalesService.create_sale(
            user_id=sample_user.id, created_by_user_id=sample_user.id, sale_items=sale_items
        )

        # Verify cost price
        sale_item = sale.items[0]
        assert sale_item.cost_price_per_unit == Decimal("10.00")

        # Verify complete depletion
        session.refresh(receipt_item)
        session.refresh(stock_level)
        assert receipt_item.quantity_remaining == 0
        assert stock_level.quantity == 0


# Fixtures
@pytest.fixture
def sample_user(session):
    """Create a sample user for testing."""
    user = User()
    user.username = "test_sales_logic_user"
    user.password = "hashed_password"
    user.full_name = "Test Sales Logic User"
    user.is_admin = False

    session.add(user)
    session.commit()
    return user


@pytest.fixture
def sample_client(session):
    """Create a sample client for testing."""
    client = Client()
    client.name = "Test Sales Logic Client"
    client.phone = "+380888888888"
    client.email = "test_logic@example.com"

    session.add(client)
    session.commit()
    return client


@pytest.fixture
def sample_brand(session):
    """Create a sample brand for testing."""
    brand = Brand()
    brand.name = "Test Sales Logic Brand"

    session.add(brand)
    session.commit()
    return brand


@pytest.fixture
def sample_payment_method(session):
    """Create a sample payment method for testing."""
    payment_method = PaymentMethod()
    payment_method.name = "Test Logic Payment Method"
    payment_method.is_active = True

    session.add(payment_method)
    session.commit()
    return payment_method


@pytest.fixture
def sample_product_with_stock_and_receipt(app, session, sample_brand):
    """Create a product with stock and receipt item for testing."""
    # Create user for the goods receipt
    user = User()
    user.username = "test_fixture_user_receipt"
    user.password = "hashed_password"
    user.full_name = "Test Fixture User Receipt"
    user.is_admin = False
    session.add(user)
    session.flush()

    # Create product
    product = Product()
    product.name = "Test Product"
    product.sku = "TEST001"
    product.brand_id = sample_brand.id
    product.current_sale_price = Decimal("29.99")
    session.add(product)
    session.flush()

    # Create goods receipt first
    goods_receipt = GoodsReceipt()
    goods_receipt.receipt_number = "GR_TEST001"
    goods_receipt.receipt_date = datetime.now(timezone.utc).date()
    goods_receipt.user_id = user.id
    session.add(goods_receipt)
    session.flush()

    # Get auto-created stock level
    stock_level = StockLevel.query.filter_by(product_id=product.id).first()
    stock_level.quantity = 10

    # Create goods receipt item
    receipt_item = GoodsReceiptItem()
    receipt_item.receipt_id = goods_receipt.id
    receipt_item.product_id = product.id
    receipt_item.quantity_received = 10
    receipt_item.quantity_remaining = 10
    receipt_item.cost_price_per_unit = Decimal("18.50")
    receipt_item.receipt_date = datetime.now(timezone.utc)
    session.add(receipt_item)

    session.commit()
    return product, stock_level, receipt_item
