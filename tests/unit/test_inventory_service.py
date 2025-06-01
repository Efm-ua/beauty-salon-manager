"""Tests for inventory service with FIFO write-off logic."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models import (Brand, GoodsReceipt, GoodsReceiptItem, Product,
                        ProductWriteOff, ProductWriteOffItem, StockLevel, User,
                        WriteOffReason, db)
from app.services.inventory_service import (InsufficientStockError,
                                            InventoryService,
                                            ProductNotFoundError,
                                            WriteOffItemData,
                                            WriteOffReasonNotFoundError)


class TestWriteOffItemData:
    """Test cases for WriteOffItemData class."""

    def test_create_write_off_item_data(self):
        """Test creating WriteOffItemData."""
        item_data = WriteOffItemData(product_id=1, quantity=5)
        assert item_data.product_id == 1
        assert item_data.quantity == 5

    def test_write_off_item_data_zero_quantity(self):
        """Test that zero quantity raises error."""
        with pytest.raises(ValueError, match="Кількість повинна бути більше 0"):
            WriteOffItemData(product_id=1, quantity=0)

    def test_write_off_item_data_negative_quantity(self):
        """Test that negative quantity raises error."""
        with pytest.raises(ValueError, match="Кількість повинна бути більше 0"):
            WriteOffItemData(product_id=1, quantity=-1)


class TestInventoryServiceWriteOffReasons:
    """Test cases for write-off reason management."""

    def test_get_active_write_off_reasons(self, app, test_db):
        """Test getting active write-off reasons."""
        with app.app_context():
            # Create reasons
            reason1 = WriteOffReason(name="Active Reason", is_active=True)
            reason2 = WriteOffReason(name="Inactive Reason", is_active=False)
            reason3 = WriteOffReason(name="Another Active", is_active=True)
            db.session.add_all([reason1, reason2, reason3])
            db.session.commit()

            active_reasons = InventoryService.get_active_write_off_reasons()

            assert len(active_reasons) == 2
            active_names = [reason.name for reason in active_reasons]
            assert "Active Reason" in active_names
            assert "Another Active" in active_names
            assert "Inactive Reason" not in active_names

    def test_get_all_write_off_reasons(self, app, test_db):
        """Test getting all write-off reasons."""
        with app.app_context():
            # Create reasons
            reason1 = WriteOffReason(name="First Reason", is_active=True)
            reason2 = WriteOffReason(name="Second Reason", is_active=False)
            db.session.add_all([reason1, reason2])
            db.session.commit()

            all_reasons = InventoryService.get_all_write_off_reasons()

            assert len(all_reasons) == 2
            reason_names = [reason.name for reason in all_reasons]
            assert "First Reason" in reason_names
            assert "Second Reason" in reason_names

    def test_create_write_off_reason(self, app, test_db):
        """Test creating a new write-off reason."""
        with app.app_context():
            reason = InventoryService.create_write_off_reason("New Reason")

            assert reason.name == "New Reason"
            assert reason.is_active is True
            assert reason.id is not None

    def test_create_write_off_reason_duplicate_name(self, app, test_db):
        """Test that creating duplicate reason raises error."""
        with app.app_context():
            # Create first reason
            InventoryService.create_write_off_reason("Duplicate")

            # Try to create another with same name
            with pytest.raises(ValueError, match="Причина списання з назвою 'Duplicate' вже існує"):
                InventoryService.create_write_off_reason("Duplicate")

    def test_update_write_off_reason(self, app, test_db):
        """Test updating a write-off reason."""
        with app.app_context():
            reason = WriteOffReason(name="Original Name", is_active=True)
            db.session.add(reason)
            db.session.commit()

            updated_reason = InventoryService.update_write_off_reason(reason.id, "Updated Name", False)

            assert updated_reason.name == "Updated Name"
            assert updated_reason.is_active is False

    def test_update_write_off_reason_not_found(self, app, test_db):
        """Test updating non-existent reason raises error."""
        with app.app_context():
            with pytest.raises(WriteOffReasonNotFoundError):
                InventoryService.update_write_off_reason(9999, "New Name", True)

    def test_update_write_off_reason_duplicate_name(self, app, test_db):
        """Test updating reason to duplicate name raises error."""
        with app.app_context():
            reason1 = WriteOffReason(name="Reason 1", is_active=True)
            reason2 = WriteOffReason(name="Reason 2", is_active=True)
            db.session.add_all([reason1, reason2])
            db.session.commit()

            with pytest.raises(ValueError, match="Причина списання з назвою 'Reason 1' вже існує"):
                InventoryService.update_write_off_reason(reason2.id, "Reason 1", True)


class TestInventoryServiceWriteOffs:
    """Test cases for write-off creation and management."""

    def test_create_write_off_basic(self, app, test_db, sample_user, sample_product_with_stock):
        """Test basic write-off creation."""
        product_id, stock_level_id, receipt_id = sample_product_with_stock

        with app.app_context():
            reason = WriteOffReason(name="Test Reason", is_active=True)
            db.session.add(reason)
            db.session.commit()

            write_off_items = [WriteOffItemData(product_id=product_id, quantity=5)]

            write_off = InventoryService.create_write_off(
                user_id=sample_user.id, reason_id=reason.id, write_off_items=write_off_items, notes="Test write-off"
            )

            assert write_off.id is not None
            assert write_off.user_id == sample_user.id
            assert write_off.reason_id == reason.id
            assert write_off.notes == "Test write-off"
            # Query items to check length and access by index
            items = ProductWriteOffItem.query.filter_by(product_write_off_id=write_off.id).all()
            assert len(items) == 1
            assert items[0].quantity == 5

    def test_create_write_off_with_date(self, app, test_db, sample_user, sample_product_with_stock):
        """Test write-off creation with specific date."""
        product_id, stock_level_id, receipt_id = sample_product_with_stock

        with app.app_context():
            reason = WriteOffReason(name="Test Reason", is_active=True)
            db.session.add(reason)
            db.session.commit()

            write_off_date = date(2025, 6, 1)
            write_off_items = [WriteOffItemData(product_id=product_id, quantity=3)]

            write_off = InventoryService.create_write_off(
                user_id=sample_user.id,
                reason_id=reason.id,
                write_off_items=write_off_items,
                write_off_date=write_off_date,
            )

            assert write_off.write_off_date == write_off_date

    def test_create_write_off_insufficient_stock(self, app, test_db, sample_user, sample_product_with_stock):
        """Test write-off with insufficient stock raises error."""
        product_id, stock_level_id, receipt_id = sample_product_with_stock

        with app.app_context():
            reason = WriteOffReason(name="Test Reason", is_active=True)
            db.session.add(reason)
            db.session.commit()

            # Try to write off more than available
            write_off_items = [WriteOffItemData(product_id=product_id, quantity=500)]

            with pytest.raises(InsufficientStockError) as exc_info:
                InventoryService.create_write_off(
                    user_id=sample_user.id, reason_id=reason.id, write_off_items=write_off_items
                )

            product = Product.query.get(product_id)
            assert product.name in str(exc_info.value)

    def test_create_write_off_nonexistent_product(self, app, test_db, sample_user):
        """Test write-off with non-existent product raises error."""
        with app.app_context():
            reason = WriteOffReason(name="Test Reason", is_active=True)
            db.session.add(reason)
            db.session.commit()

            write_off_items = [WriteOffItemData(product_id=9999, quantity=1)]

            with pytest.raises(ProductNotFoundError):
                InventoryService.create_write_off(
                    user_id=sample_user.id, reason_id=reason.id, write_off_items=write_off_items
                )

    def test_create_write_off_nonexistent_reason(self, app, test_db, sample_user, sample_product_with_stock):
        """Test write-off with non-existent reason raises error."""
        product_id, stock_level_id, receipt_id = sample_product_with_stock

        with app.app_context():
            write_off_items = [WriteOffItemData(product_id=product_id, quantity=1)]

            with pytest.raises(WriteOffReasonNotFoundError):
                InventoryService.create_write_off(
                    user_id=sample_user.id, reason_id=9999, write_off_items=write_off_items
                )

    def test_create_write_off_inactive_reason(self, app, test_db, sample_user, sample_product_with_stock):
        """Test write-off with inactive reason raises error."""
        product_id, stock_level_id, receipt_id = sample_product_with_stock

        with app.app_context():
            reason = WriteOffReason(name="Inactive Reason", is_active=False)
            db.session.add(reason)
            db.session.commit()

            write_off_items = [WriteOffItemData(product_id=product_id, quantity=1)]

            with pytest.raises(ValueError, match="неактивна"):
                InventoryService.create_write_off(
                    user_id=sample_user.id, reason_id=reason.id, write_off_items=write_off_items
                )

    def test_create_write_off_empty_items(self, app, test_db, sample_user):
        """Test write-off with empty items list raises error."""
        with app.app_context():
            reason = WriteOffReason(name="Test Reason", is_active=True)
            db.session.add(reason)
            db.session.commit()

            with pytest.raises(ValueError, match="Список товарів не може бути порожнім"):
                InventoryService.create_write_off(user_id=sample_user.id, reason_id=reason.id, write_off_items=[])

    def test_create_write_off_fifo_cost_calculation(self, app, test_db, sample_user, sample_product_with_stock):
        """Test FIFO cost calculation in write-offs."""
        product_id, stock_level_id, receipt_id = sample_product_with_stock

        with app.app_context():
            # Get the stock level to update it
            stock_level = StockLevel.query.get(stock_level_id)

            # Update the first receipt item to have an earlier date
            first_receipt_item = GoodsReceiptItem.query.filter_by(product_id=product_id).first()
            first_receipt_item.receipt_date = datetime.now(timezone.utc) - timedelta(hours=2)

            # Create additional receipt with different cost and later date
            new_receipt = GoodsReceipt()
            new_receipt.user_id = sample_user.id
            new_receipt.receipt_date = datetime.now(timezone.utc).date()
            new_receipt.receipt_number = "TEST_RECEIPT_002"
            db.session.add(new_receipt)
            db.session.flush()

            # Add new receipt item with higher cost and later receipt date
            new_receipt_item = GoodsReceiptItem()
            new_receipt_item.receipt_id = new_receipt.id
            new_receipt_item.product_id = product_id
            new_receipt_item.quantity_received = 10
            new_receipt_item.quantity_remaining = 10
            new_receipt_item.cost_price_per_unit = Decimal("15.00")  # Higher than original 10.00
            # Use a later receipt date to ensure FIFO ordering
            new_receipt_item.receipt_date = datetime.now(timezone.utc)
            db.session.add(new_receipt_item)

            # Update stock level
            stock_level.quantity += 10
            db.session.commit()

            reason = WriteOffReason(name="Test Reason", is_active=True)
            db.session.add(reason)
            db.session.commit()

            # Write off 5 units (should use only from first batch at 10.00)
            write_off_items = [WriteOffItemData(product_id=product_id, quantity=5)]

            write_off = InventoryService.create_write_off(
                user_id=sample_user.id, reason_id=reason.id, write_off_items=write_off_items
            )

            # Expected cost should be 10.00 (from first batch only)
            expected_cost = Decimal("10.00")

            items = ProductWriteOffItem.query.filter_by(product_write_off_id=write_off.id).all()
            assert len(items) == 1
            assert items[0].cost_price_per_unit == expected_cost

    def test_create_write_off_updates_stock_level(self, app, test_db, sample_user, sample_product_with_stock):
        """Test that write-off properly updates stock level."""
        product_id, stock_level_id, receipt_id = sample_product_with_stock

        with app.app_context():
            stock_level = StockLevel.query.get(stock_level_id)
            original_quantity = stock_level.quantity

            reason = WriteOffReason(name="Test Reason", is_active=True)
            db.session.add(reason)
            db.session.commit()

            write_off_items = [WriteOffItemData(product_id=product_id, quantity=3)]

            InventoryService.create_write_off(
                user_id=sample_user.id, reason_id=reason.id, write_off_items=write_off_items
            )

            # Refresh stock level
            db.session.refresh(stock_level)
            assert stock_level.quantity == original_quantity - 3

    def test_get_write_off_by_id(self, app, test_db, sample_user, sample_product_with_stock):
        """Test getting write-off by ID."""
        product_id, stock_level_id, receipt_id = sample_product_with_stock

        with app.app_context():
            reason = WriteOffReason(name="Test Reason", is_active=True)
            db.session.add(reason)
            db.session.commit()

            write_off_items = [WriteOffItemData(product_id=product_id, quantity=2)]

            created_write_off = InventoryService.create_write_off(
                user_id=sample_user.id, reason_id=reason.id, write_off_items=write_off_items
            )

            retrieved_write_off = InventoryService.get_write_off_by_id(created_write_off.id)

            assert retrieved_write_off is not None
            assert retrieved_write_off.id == created_write_off.id
            assert retrieved_write_off.user_id == sample_user.id

    def test_get_write_off_by_id_not_found(self, app, test_db):
        """Test getting non-existent write-off returns None."""
        with app.app_context():
            write_off = InventoryService.get_write_off_by_id(9999)
            assert write_off is None

    def test_get_write_offs_by_date_range(self, app, test_db, sample_user, sample_product_with_stock):
        """Test getting write-offs by date range."""
        product_id, stock_level_id, receipt_id = sample_product_with_stock

        with app.app_context():
            reason = WriteOffReason(name="Test Reason", is_active=True)
            db.session.add(reason)
            db.session.commit()

            # Create write-offs on different dates
            write_off_items = [WriteOffItemData(product_id=product_id, quantity=1)]

            write_off1 = InventoryService.create_write_off(
                user_id=sample_user.id,
                reason_id=reason.id,
                write_off_items=write_off_items,
                write_off_date=date(2025, 6, 1),
            )

            write_off2 = InventoryService.create_write_off(
                user_id=sample_user.id,
                reason_id=reason.id,
                write_off_items=write_off_items,
                write_off_date=date(2025, 6, 15),
            )

            write_off3 = InventoryService.create_write_off(
                user_id=sample_user.id,
                reason_id=reason.id,
                write_off_items=write_off_items,
                write_off_date=date(2025, 7, 1),
            )

            # Get write-offs for June 2025
            write_offs = InventoryService.get_write_offs_by_date_range(date(2025, 6, 1), date(2025, 6, 30))

            assert len(write_offs) == 2
            write_off_ids = [wo.id for wo in write_offs]
            assert write_off1.id in write_off_ids
            assert write_off2.id in write_off_ids
            assert write_off3.id not in write_off_ids

    def test_get_write_offs_by_date_range_with_filters(self, app, test_db, sample_user, sample_product_with_stock):
        """Test getting write-offs by date range with reason and user filters."""
        product_id, stock_level_id, receipt_id = sample_product_with_stock

        with app.app_context():
            # Create two different reasons
            reason1 = WriteOffReason(name="Reason 1", is_active=True)
            reason2 = WriteOffReason(name="Reason 2", is_active=True)
            db.session.add_all([reason1, reason2])
            db.session.commit()

            # Create another user
            user2 = User(username="testuser2", password="password123", full_name="Test User 2", is_admin=True)
            db.session.add(user2)
            db.session.commit()

            write_off_items = [WriteOffItemData(product_id=product_id, quantity=1)]
            test_date = date(2025, 6, 1)

            # Create write-offs with different combinations
            write_off1 = InventoryService.create_write_off(
                user_id=sample_user.id, reason_id=reason1.id, write_off_items=write_off_items, write_off_date=test_date
            )

            write_off2 = InventoryService.create_write_off(
                user_id=sample_user.id, reason_id=reason2.id, write_off_items=write_off_items, write_off_date=test_date
            )

            write_off3 = InventoryService.create_write_off(
                user_id=user2.id, reason_id=reason1.id, write_off_items=write_off_items, write_off_date=test_date
            )

            # Filter by reason
            write_offs_reason1 = InventoryService.get_write_offs_by_date_range(
                test_date, test_date, reason_id=reason1.id
            )
            assert len(write_offs_reason1) == 2
            reason1_ids = [wo.id for wo in write_offs_reason1]
            assert write_off1.id in reason1_ids
            assert write_off3.id in reason1_ids

            # Filter by user
            write_offs_user1 = InventoryService.get_write_offs_by_date_range(
                test_date, test_date, user_id=sample_user.id
            )
            assert len(write_offs_user1) == 2
            user1_ids = [wo.id for wo in write_offs_user1]
            assert write_off1.id in user1_ids
            assert write_off2.id in user1_ids

            # Filter by both reason and user
            write_offs_filtered = InventoryService.get_write_offs_by_date_range(
                test_date, test_date, reason_id=reason1.id, user_id=sample_user.id
            )
            assert len(write_offs_filtered) == 1
            assert write_offs_filtered[0].id == write_off1.id


@pytest.fixture
def sample_user(test_db):
    """Create a sample user for testing."""
    user = User(username="testuser", password="password123", full_name="Test User", is_admin=True)
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def sample_brand(test_db):
    """Create a sample brand for testing."""
    brand = Brand(name="Test Brand")
    db.session.add(brand)
    db.session.commit()
    return brand


@pytest.fixture
def sample_product(test_db, sample_brand):
    """Create a sample product for testing."""
    product = Product(
        name="Test Product", brand_id=sample_brand.id, sku="TEST001", current_sale_price=Decimal("123.45")
    )
    db.session.add(product)
    db.session.commit()
    return product


@pytest.fixture
def sample_product_with_stock(app, test_db, sample_user, sample_brand):
    """Create a product with stock for testing."""
    with app.app_context():
        # Create product
        product = Product(
            name="Test Product", brand_id=sample_brand.id, sku="TEST001", current_sale_price=Decimal("123.45")
        )
        db.session.add(product)
        db.session.flush()

        # Create goods receipt
        receipt = GoodsReceipt()
        receipt.user_id = sample_user.id
        receipt.receipt_date = datetime.now(timezone.utc).date()
        receipt.receipt_number = "TEST_RECEIPT_001"
        db.session.add(receipt)
        db.session.flush()

        # Create receipt item
        receipt_item = GoodsReceiptItem()
        receipt_item.receipt_id = receipt.id
        receipt_item.product_id = product.id
        receipt_item.quantity_received = 100
        receipt_item.quantity_remaining = 100
        receipt_item.cost_price_per_unit = Decimal("10.00")
        receipt_item.receipt_date = datetime.now(timezone.utc)
        db.session.add(receipt_item)

        # Get the auto-created stock level and update it
        stock_level = StockLevel.query.filter_by(product_id=product.id).first()
        stock_level.quantity = 100
        db.session.commit()

        # Return IDs instead of objects to avoid DetachedInstanceError
        return product.id, stock_level.id, receipt.id
