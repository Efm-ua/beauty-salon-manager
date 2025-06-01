"""Functional tests for write-off functionality."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from flask import url_for

from app import db
from app.models import (Brand, GoodsReceipt, GoodsReceiptItem, Product,
                        ProductWriteOff, StockLevel, User, WriteOffReason)
from app.services.inventory_service import InventoryService


@pytest.fixture
def sample_brand(session):
    """Create a sample brand for testing."""
    brand = Brand(name="Test Brand")
    session.add(brand)
    session.commit()
    return brand


@pytest.fixture
def sample_product_with_stock(app, session, admin_user, sample_brand):
    """Create a product with stock for testing."""
    with app.app_context():
        # Create product
        product = Product(
            name="Test Product", brand_id=sample_brand.id, sku="TEST001", current_sale_price=Decimal("123.45")
        )
        session.add(product)
        session.flush()

        # Create goods receipt
        receipt = GoodsReceipt()
        receipt.user_id = admin_user.id
        receipt.receipt_date = datetime.now(timezone.utc).date()
        receipt.receipt_number = "TEST_RECEIPT_001"
        session.add(receipt)
        session.flush()

        # Create receipt item
        receipt_item = GoodsReceiptItem()
        receipt_item.receipt_id = receipt.id
        receipt_item.product_id = product.id
        receipt_item.quantity_received = 100
        receipt_item.quantity_remaining = 100
        receipt_item.cost_price_per_unit = Decimal("10.00")
        receipt_item.receipt_date = datetime.now(timezone.utc)
        session.add(receipt_item)

        # Get the auto-created stock level and update it
        stock_level = StockLevel.query.filter_by(product_id=product.id).first()
        stock_level.quantity = 100
        session.commit()

        # Return IDs instead of objects to avoid DetachedInstanceError
        return product.id, stock_level.id, receipt.id


class TestWriteOffReasonsFunctional:
    """Functional tests for write-off reasons management."""

    def test_create_write_off_reason_active(self, client, admin_user, auth):
        """Test creating an active write-off reason."""
        auth.login_as_admin()

        response = client.get("/products/write_off_reasons/create")
        assert response.status_code == 200

        # Create active reason
        response = client.post(
            "/products/write_off_reasons/create",
            data={"name": "Test Active Reason", "is_active": "1", "submit": "Зберегти"},  # Active
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert "успішно створена" in response.get_data(as_text=True)

        # Verify in database
        reason = WriteOffReason.query.filter_by(name="Test Active Reason").first()
        assert reason is not None
        assert reason.is_active is True

    def test_create_write_off_reason_inactive(self, client, admin_user, auth):
        """Test creating an inactive write-off reason."""
        auth.login_as_admin()

        # Create inactive reason
        response = client.post(
            "/products/write_off_reasons/create",
            data={"name": "Test Inactive Reason", "is_active": "0", "submit": "Зберегти"},  # Inactive
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert "успішно створена" in response.get_data(as_text=True)

        # Verify in database
        reason = WriteOffReason.query.filter_by(name="Test Inactive Reason").first()
        assert reason is not None
        assert reason.is_active is False

    def test_edit_write_off_reason_change_status_to_inactive(self, app, client, admin_user, auth):
        """Test editing a write-off reason to change status from active to inactive."""
        with app.app_context():
            # Create active reason first
            reason = InventoryService.create_write_off_reason("Editable Reason")
            reason_id = reason.id
            assert reason.is_active is True

        auth.login_as_admin()

        # Get edit page
        response = client.get(f"/products/write_off_reasons/{reason_id}/edit")
        assert response.status_code == 200

        # Check that form shows current status (should be 1 for active)
        page_content = response.get_data(as_text=True)
        assert "Editable Reason" in page_content

        # Edit to make inactive
        response = client.post(
            f"/products/write_off_reasons/{reason_id}/edit",
            data={"name": "Editable Reason", "is_active": "0", "submit": "Зберегти"},  # Change to inactive
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert "успішно оновлена" in response.get_data(as_text=True)

        # Verify in database that status changed
        with app.app_context():
            updated_reason = WriteOffReason.query.get(reason_id)
            assert updated_reason is not None
            assert updated_reason.is_active is False

    def test_edit_write_off_reason_change_status_to_active(self, app, client, admin_user, auth):
        """Test editing a write-off reason to change status from inactive to active."""
        with app.app_context():
            # Create inactive reason first
            reason = InventoryService.create_write_off_reason("Initially Inactive")
            reason.is_active = False
            reason_id = reason.id
            db.session.commit()

        auth.login_as_admin()

        # Edit to make active
        response = client.post(
            f"/products/write_off_reasons/{reason_id}/edit",
            data={"name": "Initially Inactive", "is_active": "1", "submit": "Зберегти"},  # Change to active
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert "успішно оновлена" in response.get_data(as_text=True)

        # Verify in database that status changed
        with app.app_context():
            updated_reason = WriteOffReason.query.get(reason_id)
            assert updated_reason is not None
            assert updated_reason.is_active is True

    def test_list_write_off_reasons_displays_status(self, app, client, admin_user, auth):
        """Test that the list page correctly displays the status of write-off reasons."""
        with app.app_context():
            # Create one active and one inactive reason
            active_reason = InventoryService.create_write_off_reason("Active Status Reason")
            inactive_reason = InventoryService.create_write_off_reason("Inactive Status Reason")
            inactive_reason.is_active = False
            db.session.commit()

        auth.login_as_admin()

        # Get list page
        response = client.get("/products/write_off_reasons")
        assert response.status_code == 200

        page_content = response.get_data(as_text=True)

        # Check that both reasons are displayed with correct status
        assert "Active Status Reason" in page_content
        assert "Inactive Status Reason" in page_content

        # Check status badges - they should be present in the HTML
        assert "badge bg-success" in page_content  # Active status badge
        assert "badge bg-secondary" in page_content  # Inactive status badge

        # More specific checks for status text
        assert "Активна" in page_content
        assert "Неактивна" in page_content

    def test_write_off_form_shows_only_active_reasons(self, app, client, admin_user, auth):
        """Test that the write-off creation form shows only active reasons in dropdown."""
        with app.app_context():
            # Create active and inactive reasons
            active_reason = InventoryService.create_write_off_reason("Active for Dropdown")
            inactive_reason = InventoryService.create_write_off_reason("Inactive for Dropdown")
            inactive_reason.is_active = False
            db.session.commit()

        auth.login_as_admin()

        # Get write-off creation page
        response = client.get("/products/write_offs/new")
        assert response.status_code == 200

        page_content = response.get_data(as_text=True)

        # Active reason should be in dropdown
        assert "Active for Dropdown" in page_content

        # Inactive reason should NOT be in dropdown
        assert "Inactive for Dropdown" not in page_content

    def test_cannot_create_write_off_with_inactive_reason(
        self, app, client, admin_user, auth, sample_product_with_stock
    ):
        """Test that you cannot create a write-off using an inactive reason."""
        product_id, stock_level_id, receipt_id = sample_product_with_stock

        with app.app_context():
            # Create inactive reason
            inactive_reason = InventoryService.create_write_off_reason("Inactive Reason Test")
            inactive_reason.is_active = False
            db.session.commit()
            reason_id = inactive_reason.id

        auth.login_as_admin()

        # Try to create write-off with inactive reason (this should fail at service level)
        with app.app_context():
            from app.services.inventory_service import WriteOffItemData

            with pytest.raises(ValueError, match="неактивна"):
                InventoryService.create_write_off(
                    user_id=admin_user.id,
                    reason_id=reason_id,
                    write_off_items=[WriteOffItemData(product_id=product_id, quantity=1)],
                    write_off_date=date.today(),
                )


class TestWriteOffReasonServiceIntegration:
    """Integration tests for write-off reason service methods."""

    def test_get_active_write_off_reasons_filters_correctly(self, app, test_db):
        """Test that get_active_write_off_reasons returns only active reasons."""
        with app.app_context():
            # Create mixed active/inactive reasons
            active1 = InventoryService.create_write_off_reason("Active 1")
            active2 = InventoryService.create_write_off_reason("Active 2")
            inactive1 = InventoryService.create_write_off_reason("Inactive 1")
            inactive2 = InventoryService.create_write_off_reason("Inactive 2")

            # Set some to inactive
            inactive1.is_active = False
            inactive2.is_active = False
            test_db.commit()

            # Get active reasons
            active_reasons = InventoryService.get_active_write_off_reasons()
            active_names = [reason.name for reason in active_reasons]

            # Should only have active ones
            assert len(active_reasons) == 2
            assert "Active 1" in active_names
            assert "Active 2" in active_names
            assert "Inactive 1" not in active_names
            assert "Inactive 2" not in active_names

    def test_get_all_write_off_reasons_returns_all(self, app, test_db):
        """Test that get_all_write_off_reasons returns both active and inactive reasons."""
        with app.app_context():
            # Create mixed active/inactive reasons
            active = InventoryService.create_write_off_reason("All Test Active")
            inactive = InventoryService.create_write_off_reason("All Test Inactive")
            inactive.is_active = False
            test_db.commit()

            # Get all reasons
            all_reasons = InventoryService.get_all_write_off_reasons()
            all_names = [reason.name for reason in all_reasons]

            # Should have both
            assert "All Test Active" in all_names
            assert "All Test Inactive" in all_names
