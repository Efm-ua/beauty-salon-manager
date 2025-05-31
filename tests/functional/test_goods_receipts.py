from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from flask import url_for

from app.models import GoodsReceipt, GoodsReceiptItem, Product, StockLevel, db


def test_goods_receipts_list_access(client, admin_user, regular_user):
    """Test access to goods receipts list page"""
    # Unauthorized access should redirect to login
    response = client.get(url_for("products.goods_receipts_list"))
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]

    # Regular user should be redirected to main page
    client.post(
        url_for("auth.login"),
        data={"username": regular_user.username, "password": "user_password"},
        follow_redirects=True,
    )
    response = client.get(url_for("products.goods_receipts_list"))
    assert response.status_code == 302
    assert "/" in response.headers["Location"]  # Redirect to main.index (/)

    # Logout regular user before admin login
    client.get(url_for("auth.logout"))

    # Admin should have access
    client.post(
        url_for("auth.login"),
        data={"username": admin_user.username, "password": "admin_password"},
        follow_redirects=True,
    )
    response = client.get(url_for("products.goods_receipts_list"))
    assert response.status_code == 200
    assert "Надходження товарів".encode("utf-8") in response.data


def test_create_goods_receipt_access(client, admin_user, regular_user):
    """Test access to create goods receipt page"""
    # Unauthorized access should redirect to login
    response = client.get(url_for("products.goods_receipts_create"))
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]

    # Regular user should be redirected to main page
    client.post(
        url_for("auth.login"),
        data={"username": regular_user.username, "password": "user_password"},
        follow_redirects=True,
    )
    response = client.get(url_for("products.goods_receipts_create"))
    assert response.status_code == 302
    assert "/" in response.headers["Location"]  # Redirect to main.index (/)

    # Logout regular user before admin login
    client.get(url_for("auth.logout"))

    # Admin should have access
    client.post(
        url_for("auth.login"),
        data={"username": admin_user.username, "password": "admin_password"},
        follow_redirects=True,
    )
    response = client.get(url_for("products.goods_receipts_create"))
    assert response.status_code == 200
    assert "Нове надходження".encode("utf-8") in response.data


def test_create_goods_receipt(client, admin_user, test_product):
    """Test creating a new goods receipt"""
    # Login as admin
    client.post(
        url_for("auth.login"),
        data={"username": admin_user.username, "password": "admin_password"},
        follow_redirects=True,
    )

    # Initial stock level
    initial_stock = StockLevel.query.filter_by(product_id=test_product.id).first()
    initial_quantity = initial_stock.quantity if initial_stock else 0

    # Create goods receipt
    response = client.post(
        url_for("products.goods_receipts_create"),
        data={
            "receipt_number": "TEST-001",
            "receipt_date": date.today().strftime("%Y-%m-%d"),
            "items-0-product_id": test_product.id,
            "items-0-quantity": 5,
            "items-0-cost_price": "100.50",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Надходження товарів успішно збережено".encode("utf-8") in response.data

    # Check database records
    receipt = GoodsReceipt.query.filter_by(receipt_number="TEST-001").first()
    assert receipt is not None
    assert receipt.user_id == admin_user.id
    assert receipt.receipt_date == date.today()

    receipt_item = GoodsReceiptItem.query.filter_by(product_id=test_product.id).first()
    assert receipt_item is not None
    assert receipt_item.quantity_received == 5
    assert receipt_item.quantity_remaining == 5
    assert receipt_item.cost_price_per_unit == Decimal("100.50")

    # Check stock level update
    updated_stock = StockLevel.query.filter_by(product_id=test_product.id).first()
    assert updated_stock is not None
    assert updated_stock.quantity == initial_quantity + 5

    # Check product cost price update
    updated_product = db.session.get(Product, test_product.id)
    assert updated_product.last_cost_price == Decimal("100.50")


def test_view_goods_receipt(client, admin_user, test_goods_receipt):
    """Test viewing goods receipt details"""
    # Login as admin
    client.post(
        url_for("auth.login"),
        data={"username": admin_user.username, "password": "admin_password"},
        follow_redirects=True,
    )

    # View receipt details
    response = client.get(url_for("products.goods_receipts_view", id=test_goods_receipt.id))
    assert response.status_code == 200
    assert test_goods_receipt.receipt_number.encode("utf-8") in response.data

    # Check if items are displayed
    for item in test_goods_receipt.items:
        assert item.product.name.encode("utf-8") in response.data
        assert str(item.quantity_received).encode("utf-8") in response.data
        assert str(float(item.cost_price_per_unit)).encode("utf-8") in response.data


@pytest.fixture
def test_goods_receipt(admin_user, test_product):
    """Fixture to create a test goods receipt"""
    receipt = GoodsReceipt(
        receipt_number="TEST-001",
        receipt_date=date.today(),
        user_id=admin_user.id,
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(receipt)

    item = GoodsReceiptItem(
        product_id=test_product.id,
        quantity_received=5,
        quantity_remaining=5,
        cost_price_per_unit=Decimal("100.50"),
        receipt_date=date.today(),
    )
    receipt.items.append(item)

    db.session.commit()
    return receipt
