"""Tests for write-off models."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models import ProductWriteOff, ProductWriteOffItem, WriteOffReason


class TestWriteOffReason:
    """Test cases for WriteOffReason model."""

    def test_create_write_off_reason(self, app, test_db):
        """Test creating a write-off reason."""
        with app.app_context():
            reason = WriteOffReason(name="Test Reason")
            test_db.add(reason)
            test_db.commit()

            assert reason.id is not None
            assert reason.name == "Test Reason"
            assert reason.is_active is True  # Default value
            assert reason.created_at is not None
            assert isinstance(reason.created_at, datetime)

    def test_write_off_reason_repr(self, app, test_db):
        """Test WriteOffReason string representation."""
        with app.app_context():
            reason = WriteOffReason(name="Damage")
            assert str(reason) == "<WriteOffReason Damage>"

    def test_write_off_reason_unique_name(self, app, test_db):
        """Test that write-off reason names must be unique."""
        with app.app_context():
            reason1 = WriteOffReason(name="Expired")
            test_db.add(reason1)
            test_db.commit()

            # Try to create another reason with the same name
            reason2 = WriteOffReason(name="Expired")
            test_db.add(reason2)

            with pytest.raises(Exception):  # Should raise IntegrityError
                test_db.commit()

    def test_write_off_reason_inactive(self, app, test_db):
        """Test creating an inactive write-off reason."""
        with app.app_context():
            reason = WriteOffReason(name="Inactive Reason", is_active=False)
            test_db.add(reason)
            test_db.commit()

            assert reason.is_active is False

    def test_write_off_reason_relationship_with_write_offs(self, app, test_db, regular_user, test_product):
        """Test relationship between WriteOffReason and ProductWriteOff."""
        with app.app_context():
            reason = WriteOffReason(name="Test Reason")
            test_db.add(reason)
            test_db.flush()

            write_off = ProductWriteOff(reason_id=reason.id, user_id=regular_user.id, write_off_date=date.today())
            test_db.add(write_off)
            test_db.commit()

            # Test the relationship
            write_offs_list = WriteOffReason.query.get(reason.id).write_offs
            assert len(write_offs_list) == 1
            assert write_offs_list[0] == write_off
            assert write_off.reason == reason


class TestProductWriteOff:
    """Test cases for ProductWriteOff model."""

    def test_create_product_write_off(self, app, test_db, regular_user):
        """Test creating a product write-off."""
        with app.app_context():
            reason = WriteOffReason(name="Test Reason")
            test_db.add(reason)
            test_db.flush()

            write_off = ProductWriteOff(
                reason_id=reason.id, user_id=regular_user.id, write_off_date=date(2025, 5, 31), notes="Test notes"
            )
            test_db.add(write_off)
            test_db.commit()

            assert write_off.id is not None
            assert write_off.reason_id == reason.id
            assert write_off.user_id == regular_user.id
            assert write_off.write_off_date == date(2025, 5, 31)
            assert write_off.notes == "Test notes"
            assert write_off.created_at is not None

    def test_product_write_off_default_date(self, app, test_db, regular_user):
        """Test that write-off date defaults to today."""
        with app.app_context():
            reason = WriteOffReason(name="Test Reason")
            test_db.add(reason)
            test_db.flush()

            write_off = ProductWriteOff(reason_id=reason.id, user_id=regular_user.id)
            test_db.add(write_off)
            test_db.commit()

            assert write_off.write_off_date == date.today()

    def test_product_write_off_repr(self, app, test_db, regular_user):
        """Test ProductWriteOff string representation."""
        with app.app_context():
            reason = WriteOffReason(name="Test Reason")
            test_db.add(reason)
            test_db.flush()

            write_off_date = date(2025, 5, 31)
            write_off = ProductWriteOff(reason_id=reason.id, user_id=regular_user.id, write_off_date=write_off_date)
            test_db.add(write_off)
            test_db.commit()

            expected = f"<ProductWriteOff {write_off.id} - {write_off_date}>"
            assert str(write_off) == expected

    def test_product_write_off_relationships(self, app, test_db, regular_user):
        """Test ProductWriteOff relationships."""
        with app.app_context():
            reason = WriteOffReason(name="Test Reason")
            test_db.add(reason)
            test_db.flush()

            write_off = ProductWriteOff(reason_id=reason.id, user_id=regular_user.id)
            test_db.add(write_off)
            test_db.commit()

            # Test reason relationship
            assert write_off.reason == reason

            # Test user relationship
            assert write_off.user == regular_user

    def test_product_write_off_total_cost_empty(self, app, test_db, regular_user):
        """Test total_cost property with no items."""
        with app.app_context():
            reason = WriteOffReason(name="Test Reason")
            test_db.add(reason)
            test_db.flush()

            write_off = ProductWriteOff(reason_id=reason.id, user_id=regular_user.id)
            test_db.add(write_off)
            test_db.commit()

            assert write_off.total_cost == Decimal("0.00")

    def test_product_write_off_total_cost_with_items(self, app, test_db, regular_user, test_product):
        """Test total_cost property with items."""
        with app.app_context():
            reason = WriteOffReason(name="Test Reason")
            test_db.add(reason)
            test_db.flush()

            write_off = ProductWriteOff(reason_id=reason.id, user_id=regular_user.id)
            test_db.add(write_off)
            test_db.flush()

            # Add write-off items
            item1 = ProductWriteOffItem(
                product_write_off_id=write_off.id,
                product_id=test_product.id,
                quantity=5,
                cost_price_per_unit=Decimal("10.50"),
            )
            item2 = ProductWriteOffItem(
                product_write_off_id=write_off.id,
                product_id=test_product.id,
                quantity=3,
                cost_price_per_unit=Decimal("15.00"),
            )
            test_db.add_all([item1, item2])
            test_db.commit()

            expected_total = (5 * Decimal("10.50")) + (3 * Decimal("15.00"))
            assert write_off.total_cost == expected_total


class TestProductWriteOffItem:
    """Test cases for ProductWriteOffItem model."""

    def test_create_product_write_off_item(self, app, test_db, regular_user, test_product):
        """Test creating a product write-off item."""
        with app.app_context():
            reason = WriteOffReason(name="Test Reason")
            test_db.add(reason)
            test_db.flush()

            write_off = ProductWriteOff(reason_id=reason.id, user_id=regular_user.id)
            test_db.add(write_off)
            test_db.flush()

            item = ProductWriteOffItem(
                product_write_off_id=write_off.id,
                product_id=test_product.id,
                quantity=10,
                cost_price_per_unit=Decimal("25.75"),
            )
            test_db.add(item)
            test_db.commit()

            assert item.id is not None
            assert item.product_write_off_id == write_off.id
            assert item.product_id == test_product.id
            assert item.quantity == 10
            assert item.cost_price_per_unit == Decimal("25.75")

    def test_product_write_off_item_repr(self, app, test_db, regular_user, test_product):
        """Test ProductWriteOffItem string representation."""
        with app.app_context():
            reason = WriteOffReason(name="Test Reason")
            test_db.add(reason)
            test_db.flush()

            write_off = ProductWriteOff(reason_id=reason.id, user_id=regular_user.id)
            test_db.add(write_off)
            test_db.flush()

            item = ProductWriteOffItem(
                product_write_off_id=write_off.id,
                product_id=test_product.id,
                quantity=5,
                cost_price_per_unit=Decimal("12.50"),
            )
            test_db.add(item)
            test_db.commit()

            expected = f"<ProductWriteOffItem {test_product.name}: 5>"
            assert str(item) == expected

    def test_product_write_off_item_relationships(self, app, test_db, regular_user, test_product):
        """Test ProductWriteOffItem relationships."""
        with app.app_context():
            reason = WriteOffReason(name="Test Reason")
            test_db.add(reason)
            test_db.flush()

            write_off = ProductWriteOff(reason_id=reason.id, user_id=regular_user.id)
            test_db.add(write_off)
            test_db.flush()

            item = ProductWriteOffItem(
                product_write_off_id=write_off.id,
                product_id=test_product.id,
                quantity=3,
                cost_price_per_unit=Decimal("8.25"),
            )
            test_db.add(item)
            test_db.commit()

            # Test product relationship
            assert item.product == test_product

            # Test write-off relationship
            assert item.product_write_off == write_off

            # Test reverse relationship
            items_list = ProductWriteOffItem.query.filter_by(product_write_off_id=write_off.id).all()
            assert len(items_list) == 1
            assert items_list[0] == item

    def test_product_write_off_item_total_cost(self, app, test_db, regular_user, test_product):
        """Test total_cost property calculation."""
        with app.app_context():
            reason = WriteOffReason(name="Test Reason")
            test_db.add(reason)
            test_db.flush()

            write_off = ProductWriteOff(reason_id=reason.id, user_id=regular_user.id)
            test_db.add(write_off)
            test_db.flush()

            item = ProductWriteOffItem(
                product_write_off_id=write_off.id,
                product_id=test_product.id,
                quantity=7,
                cost_price_per_unit=Decimal("15.25"),
            )
            test_db.add(item)
            test_db.commit()

            expected_total = 7 * Decimal("15.25")
            assert item.total_cost == expected_total

    def test_product_write_off_item_zero_cost(self, app, test_db, regular_user, test_product):
        """Test item with zero cost price."""
        with app.app_context():
            reason = WriteOffReason(name="Test Reason")
            test_db.add(reason)
            test_db.flush()

            write_off = ProductWriteOff(reason_id=reason.id, user_id=regular_user.id)
            test_db.add(write_off)
            test_db.flush()

            item = ProductWriteOffItem(
                product_write_off_id=write_off.id,
                product_id=test_product.id,
                quantity=5,
                cost_price_per_unit=Decimal("0.00"),
            )
            test_db.add(item)
            test_db.commit()

            assert item.total_cost == Decimal("0.00")

    def test_product_write_off_item_foreign_key_constraints(self, app, test_db):
        """Test foreign key constraints."""
        with app.app_context():
            # Try to create item with non-existent write-off
            item = ProductWriteOffItem(
                product_write_off_id=9999,  # Non-existent
                product_id=1,
                quantity=1,
                cost_price_per_unit=Decimal("10.00"),
            )
            test_db.add(item)

            with pytest.raises(Exception):  # Should raise IntegrityError
                test_db.commit()

    def test_cascade_delete_write_off_items(self, app, test_db, regular_user, test_product):
        """Test that write-off items are deleted when write-off is deleted."""
        with app.app_context():
            reason = WriteOffReason(name="Test Reason")
            test_db.add(reason)
            test_db.flush()

            write_off = ProductWriteOff(reason_id=reason.id, user_id=regular_user.id)
            test_db.add(write_off)
            test_db.flush()

            item = ProductWriteOffItem(
                product_write_off_id=write_off.id,
                product_id=test_product.id,
                quantity=3,
                cost_price_per_unit=Decimal("5.00"),
            )
            test_db.add(item)
            test_db.commit()

            write_off_id = write_off.id
            item_id = item.id

            # Delete the write-off
            test_db.delete(write_off)
            test_db.commit()

            # Check that the item was also deleted
            deleted_item = test_db.get(ProductWriteOffItem, item_id)
            assert deleted_item is None
