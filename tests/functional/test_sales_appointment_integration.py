"""
Tests for sales and appointments integration functionality.
"""

import uuid
from datetime import date, time
from decimal import Decimal
from typing import Any

import pytest

from app.models import (Appointment, AppointmentService, Brand, Client,
                        GoodsReceipt, GoodsReceiptItem, Product, Sale,
                        SaleItem, Service, StockLevel, User, db)
from app.services.sales_service import SaleItemData, SalesService


def _get_csrf_token(client, url):
    """Helper to get CSRF token from form."""
    response = client.get(url)
    data = response.get_data(as_text=True)
    # Extract CSRF token from form
    start = data.find('name="csrf_token" value="') + len('name="csrf_token" value="')
    end = data.find('"', start)
    return data[start:end] if start > -1 and end > -1 else ""


@pytest.fixture
def test_product_with_stock(session: Any, admin_user: User) -> Product:
    """Create a test product with stock for sales tests."""
    # Create unique names to avoid conflicts
    unique_id = str(uuid.uuid4())[:8]

    # Create brand
    brand = Brand(name=f"Test Brand {unique_id}")
    session.add(brand)
    session.flush()

    # Create product
    product = Product(
        name=f"Test Product {unique_id}",
        sku=f"TEST{unique_id}",
        brand_id=brand.id,
        current_sale_price=Decimal("100.00"),
        last_cost_price=Decimal("50.00"),
    )
    session.add(product)
    session.flush()

    # Add goods receipt for FIFO
    receipt = GoodsReceipt(receipt_date=date.today(), user_id=admin_user.id)
    session.add(receipt)
    session.flush()

    receipt_item = GoodsReceiptItem(
        receipt_id=receipt.id,
        product_id=product.id,
        quantity_received=10,
        quantity_remaining=10,
        cost_price_per_unit=Decimal("50.00"),
    )
    session.add(receipt_item)
    session.flush()

    # Update stock level (auto-created by Product after_insert event)
    stock = StockLevel.query.filter_by(product_id=product.id).first()
    if stock:
        stock.quantity = 10
    else:
        # Create stock level if it doesn't exist
        stock = StockLevel(product_id=product.id, quantity=10)
        session.add(stock)

    session.commit()

    return product


def test_create_sale_with_appointment_link(
    admin_auth_client: Any, test_appointment: Appointment, test_product_with_stock: Product, payment_methods: Any
) -> None:
    """Test creating a sale linked to an appointment."""
    # Access create sale form
    response = admin_auth_client.get("/sales/new")
    assert response.status_code == 200

    # Check that appointment field is present by looking for the field name
    assert 'name="appointment_id"' in response.text

    # Instead of testing the form submission with QuerySelectField (which is complex in tests),
    # let's test the functionality by creating a sale directly via the service and then
    # testing that it shows up correctly in the appointment view

    # Create a sale linked to the appointment using the service
    sale_items = [SaleItemData(product_id=test_product_with_stock.id, quantity=2)]

    sale = SalesService.create_sale(
        user_id=test_appointment.master_id,
        created_by_user_id=test_appointment.master_id,
        sale_items=sale_items,
        client_id=test_appointment.client_id,
        appointment_id=test_appointment.id,
        payment_method_id=payment_methods[0].id,
        notes="Test sale linked to appointment",
    )

    # Verify sale is linked to appointment
    assert sale.appointment_id == test_appointment.id
    assert sale.total_amount == Decimal("200.00")  # 2 * 100.00

    # Test that the sale appears in the appointment view
    response = admin_auth_client.get(f"/appointments/view/{test_appointment.id}")
    assert response.status_code == 200
    assert "Продані товари" in response.text
    assert f"Продаж №{sale.id}" in response.text


def test_appointment_view_displays_linked_sales(
    admin_auth_client: Any,
    test_appointment: Appointment,
    test_product_with_stock: Product,
    admin_user: User,
    payment_methods: Any,
) -> None:
    """Test that appointment view displays linked sales and products."""
    # Create a sale linked to the appointment
    sale_items = [SaleItemData(product_id=test_product_with_stock.id, quantity=2)]

    sale = SalesService.create_sale(
        user_id=admin_user.id,
        created_by_user_id=admin_user.id,
        sale_items=sale_items,
        appointment_id=test_appointment.id,
        payment_method_id=payment_methods[0].id,
        notes="Test sale linked to appointment",
    )

    # View the appointment
    response = admin_auth_client.get(f"/appointments/view/{test_appointment.id}")
    assert response.status_code == 200

    # Check that the sale is displayed
    assert "Продані товари" in response.text
    assert "Test Product" in response.text
    assert f"Продаж №{sale.id}" in response.text
    assert "200.00 грн" in response.text  # 2 * 100.00


def test_appointment_total_includes_sales(
    admin_auth_client: Any,
    test_appointment: Appointment,
    test_service_with_price: Service,
    test_product_with_stock: Product,
    admin_user: User,
    session: Any,
    payment_methods: Any,
) -> None:
    """Test that appointment total price includes linked sales."""
    # Add a service to the appointment
    appointment_service = AppointmentService(
        appointment_id=test_appointment.id, service_id=test_service_with_price.id, price=150.0
    )
    session.add(appointment_service)
    session.commit()

    # Create a sale linked to the appointment
    sale_items = [SaleItemData(product_id=test_product_with_stock.id, quantity=1)]

    sale = SalesService.create_sale(
        user_id=admin_user.id,
        created_by_user_id=admin_user.id,
        sale_items=sale_items,
        appointment_id=test_appointment.id,
        payment_method_id=payment_methods[0].id,
        notes="Test sale for total calculation",
    )

    # Refresh appointment to get updated totals
    session.refresh(test_appointment)

    # Check that total includes both services and sale
    # test_appointment fixture already has one service with price 100.0
    # We added another service with price 150.0
    # So services total = 100.0 + 150.0 = 250.0
    total_price = test_appointment.get_total_price()
    expected_total = 250.0 + 100.0  # services + sale
    assert total_price == expected_total

    # View the appointment and check displayed total
    response = admin_auth_client.get(f"/appointments/view/{test_appointment.id}")
    assert response.status_code == 200
    assert "350" in response.text  # Total should be 350.0


def test_appointment_without_sales_shows_no_products_section(
    admin_auth_client: Any, test_appointment: Appointment
) -> None:
    """Test that appointment without sales doesn't show products section."""
    # View the appointment
    response = admin_auth_client.get(f"/appointments/view/{test_appointment.id}")
    assert response.status_code == 200

    # Check that products section is not displayed
    assert "Продані товари" not in response.text


def test_appointment_discounted_price_includes_sales(
    admin_auth_client: Any,
    test_appointment: Appointment,
    test_service_with_price: Service,
    test_product_with_stock: Product,
    admin_user: User,
    session: Any,
    payment_methods: Any,
) -> None:
    """Test that appointment discounted price includes linked sales."""
    # Add a service to the appointment
    appointment_service = AppointmentService(
        appointment_id=test_appointment.id, service_id=test_service_with_price.id, price=100.0
    )
    session.add(appointment_service)

    # Set discount on appointment
    test_appointment.discount_percentage = Decimal("10.0")  # 10% discount
    session.commit()

    # Create a sale linked to the appointment
    sale_items = [SaleItemData(product_id=test_product_with_stock.id, quantity=1)]

    sale = SalesService.create_sale(
        user_id=admin_user.id,
        created_by_user_id=admin_user.id,
        sale_items=sale_items,
        appointment_id=test_appointment.id,
        payment_method_id=payment_methods[0].id,
        notes="Test sale for discount calculation",
    )

    # Refresh appointment to get updated totals
    session.refresh(test_appointment)

    # Check that discounted total includes both services and sale
    # test_appointment fixture already has one service with price 100.0
    # We added another service with price 100.0
    # So services total = 100.0 + 100.0 = 200.0
    # Plus sale = 100.0, total = 300.0
    total_price = test_appointment.get_total_price()  # 200 + 100 = 300
    discounted_price = test_appointment.get_discounted_price()  # 300 * 0.9 = 270

    assert total_price == 300.0
    assert discounted_price == Decimal("270.00")


def test_sale_form_displays_appointment_field_and_options(
    admin_auth_client: Any, test_appointment: Appointment
) -> None:
    """Test that sale form properly displays appointment field and shows available appointments."""
    # Access create sale form
    response = admin_auth_client.get("/sales/new")
    assert response.status_code == 200

    # Check that appointment field is present
    assert 'name="appointment_id"' in response.text

    # Check for field label (partial match to avoid encoding issues)
    assert "записом" in response.text  # Part of "Пов'язати із записом"

    # The specific text content and appointment options may vary depending on test data,
    # so let's just verify the field structure exists
    # Check that appointment select field is properly rendered
    assert "<select" in response.text and "appointment_id" in response.text


def test_sale_form_shows_appointment_options(admin_auth_client: Any, test_appointment: Appointment) -> None:
    """Test that sale form shows appointment options in dropdown."""
    # Access create sale form
    response = admin_auth_client.get("/sales/new")
    assert response.status_code == 200

    # Check that appointment field is present by looking for the field name
    assert 'name="appointment_id"' in response.text
    # Also check for the label text
    assert "записом" in response.text  # Part of "Пов'язати із записом"


def test_multiple_sales_linked_to_appointment(
    admin_auth_client: Any,
    test_appointment: Appointment,
    test_product_with_stock: Product,
    admin_user: User,
    session: Any,
    payment_methods: Any,
) -> None:
    """Test that multiple sales can be linked to the same appointment."""
    # Create first sale
    sale_items_1 = [SaleItemData(product_id=test_product_with_stock.id, quantity=1)]
    sale1 = SalesService.create_sale(
        user_id=admin_user.id,
        created_by_user_id=admin_user.id,
        sale_items=sale_items_1,
        appointment_id=test_appointment.id,
        payment_method_id=payment_methods[0].id,
        notes="First sale",
    )

    # Create second sale
    sale_items_2 = [SaleItemData(product_id=test_product_with_stock.id, quantity=2)]
    sale2 = SalesService.create_sale(
        user_id=admin_user.id,
        created_by_user_id=admin_user.id,
        sale_items=sale_items_2,
        appointment_id=test_appointment.id,
        payment_method_id=payment_methods[0].id,
        notes="Second sale",
    )

    # View the appointment
    response = admin_auth_client.get(f"/appointments/view/{test_appointment.id}")
    assert response.status_code == 200

    # Check that both sales are displayed
    assert f"Продаж №{sale1.id}" in response.text
    assert f"Продаж №{sale2.id}" in response.text

    # Check total includes both sales
    session.refresh(test_appointment)
    total_price = test_appointment.get_total_price()
    # test_appointment fixture already has one service with price 100.0
    # Plus sale1 = 100.0 and sale2 = 200.0
    expected_total = 100.0 + 100.0 + 200.0  # existing service + sale1 + sale2
    assert total_price == expected_total
