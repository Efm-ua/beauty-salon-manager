from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest

from app.models import Appointment


def test_schedule_payment_status_display(
    session, client, admin_user, test_client, regular_user
):
    """
    Tests that appointment payment status is correctly displayed in the schedule view.

    This test verifies:
    1. Appointments with different payment statuses are displayed with appropriate CSS classes
    2. Paid amount is displayed for appointments with amount_paid values
    """
    # Login first - use a direct GET request to make sure we're logged out
    client.get("/auth/logout", follow_redirects=True)

    # Then login as admin (required to access schedule view)
    response = client.post(
        "/auth/login",
        data={
            "username": admin_user.username,
            "password": "admin_password",
            "remember_me": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    # Create a test date
    test_date = date.today()

    # Create an unpaid appointment
    unpaid_appointment = Appointment(
        client_id=test_client.id,
        master_id=regular_user.id,
        date=test_date,
        start_time=time(10, 0),  # 10:00
        end_time=time(11, 0),  # 11:00
        status="scheduled",
        payment_status="unpaid",
        amount_paid=None,
        notes="Unpaid test appointment",
    )
    session.add(unpaid_appointment)

    # Create a paid appointment with amount
    paid_appointment = Appointment(
        client_id=test_client.id,
        master_id=regular_user.id,
        date=test_date,
        start_time=time(12, 0),  # 12:00
        end_time=time(13, 0),  # 13:00
        status="scheduled",
        payment_status="paid",
        amount_paid=Decimal("250.50"),
        notes="Paid test appointment",
    )
    session.add(paid_appointment)
    session.commit()

    # Access the schedule view for the test date
    response = client.get(f"/schedule?date={test_date.strftime('%Y-%m-%d')}")
    assert response.status_code == 200

    # Check that the unpaid appointment has the correct class
    # Using 'in' to make the test more flexible with potential additional classes
    assert 'class="schedule-appointment status-unpaid' in response.text

    # Check that the paid appointment has the correct class
    assert 'class="schedule-appointment status-paid' in response.text

    # Check that the paid amount is displayed
    assert "250.50 грн" in response.text

    # The unpaid appointment should not show an amount
    # Find the unpaid appointment div by finding its class first
    unpaid_index = response.text.find('class="schedule-appointment status-unpaid')
    # Find the closing div tag
    unpaid_div_end = response.text.find("</div>", unpaid_index)
    # Extract the div content
    unpaid_div_content = response.text[unpaid_index:unpaid_div_end]
    # Verify amount is not displayed for unpaid appointment
    assert "грн" not in unpaid_div_content

    # Also verify that the amount is displayed correctly for the paid appointment
    paid_index = response.text.find('class="schedule-appointment status-paid')
    paid_div_end = response.text.find("</div>", paid_index)
    paid_div_content = response.text[paid_index:paid_div_end]
    assert "250.50 грн" in paid_div_content


def test_multi_booking_client_highlight(
    session, client, admin_user, test_client, regular_user
):
    """
    Tests that clients with multiple bookings on the same day are highlighted correctly.

    This test verifies:
    1. Appointments belonging to clients with multiple bookings have the 'multi-booking' class
    2. Appointments belonging to clients with only one booking don't have the 'multi-booking' class
    """
    # Login first - use a direct GET request to make sure we're logged out
    client.get("/auth/logout", follow_redirects=True)

    # Then login as admin (required to access schedule view)
    response = client.post(
        "/auth/login",
        data={
            "username": admin_user.username,
            "password": "admin_password",
            "remember_me": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    # Create a test date
    test_date = date.today()

    # Create a client with multiple appointments
    multi_booking_appointment1 = Appointment(
        client_id=test_client.id,
        master_id=regular_user.id,
        date=test_date,
        start_time=time(10, 0),  # 10:00
        end_time=time(11, 0),  # 11:00
        status="scheduled",
        payment_status="unpaid",
        notes="First appointment for multi-booking client",
    )
    session.add(multi_booking_appointment1)

    multi_booking_appointment2 = Appointment(
        client_id=test_client.id,
        master_id=regular_user.id,
        date=test_date,
        start_time=time(14, 0),  # 14:00
        end_time=time(15, 0),  # 15:00
        status="scheduled",
        payment_status="unpaid",
        notes="Second appointment for multi-booking client",
    )
    session.add(multi_booking_appointment2)

    # Create a different client with only one appointment
    from app.models import Client

    single_booking_client = Client(
        name="Single Booking Client",
        phone="1234567891",
        email="single@example.com",
    )
    session.add(single_booking_client)
    session.flush()  # To get the ID

    single_booking_appointment = Appointment(
        client_id=single_booking_client.id,
        master_id=regular_user.id,
        date=test_date,
        start_time=time(12, 0),  # 12:00
        end_time=time(13, 0),  # 13:00
        status="scheduled",
        payment_status="unpaid",
        notes="Appointment for single-booking client",
    )
    session.add(single_booking_appointment)
    session.commit()

    # Access the schedule view for the test date
    response = client.get(f"/schedule?date={test_date.strftime('%Y-%m-%d')}")
    assert response.status_code == 200

    # Check that appointments for the client with multiple bookings have the 'multi-booking' class
    assert 'class="schedule-appointment status-unpaid multi-booking"' in response.text

    # Check that the appointment for the client with a single booking doesn't have the 'multi-booking' class
    # This is harder to test directly, so we'll check for the client's name and the absence of multi-booking in the same div

    # Find the div containing the single-booking client's name
    single_client_index = response.text.find(f"{single_booking_client.name}</strong>")

    # Get the preceding div opening tag
    div_start = response.text.rfind("<div", 0, single_client_index)
    div_end = response.text.find(">", div_start) + 1
    div_class_attr = response.text[div_start:div_end]

    # Check that this div doesn't have the multi-booking class
    assert "multi-booking" not in div_class_attr


def test_schedule_new_appointment_button_date_parameter(
    session, client, admin_user, test_client, regular_user
):
    """
    Tests that the "New Appointment" button on the schedule page correctly includes the date parameter.

    This test verifies:
    1. The href of the "New Appointment" button includes the date parameter with the current schedule date
    2. The date parameter is correctly formatted as YYYY-MM-DD
    """
    # Login first - use a direct GET request to make sure we're logged out
    client.get("/auth/logout", follow_redirects=True)

    # Then login as admin (required to access schedule view)
    response = client.post(
        "/auth/login",
        data={
            "username": admin_user.username,
            "password": "admin_password",
            "remember_me": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    # Create a test date for tomorrow (to ensure it's not using today's date by default)
    test_date = date.today() + timedelta(days=1)
    formatted_date = test_date.strftime("%Y-%m-%d")

    # Access the schedule view for the test date
    response = client.get(f"/schedule?date={formatted_date}")
    assert response.status_code == 200

    # Check for the date parameter in the URL
    assert (
        f'href="/appointments/create?date={formatted_date}"' in response.text
        or f"href='/appointments/create?date={formatted_date}'" in response.text
    )
