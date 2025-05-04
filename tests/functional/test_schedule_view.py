import pytest
from datetime import datetime, timedelta, date, time
from decimal import Decimal
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
    assert 'class="schedule-appointment status-unpaid"' in response.text

    # Check that the paid appointment has the correct class
    assert 'class="schedule-appointment status-paid"' in response.text

    # Check that the paid amount is displayed
    assert "250.50 грн" in response.text

    # The unpaid appointment should not show an amount
    # This test verifies indirectly by checking the appointment's div doesn't contain the amount format
    unpaid_index = response.text.find(f'class="schedule-appointment status-unpaid"')
    paid_index = response.text.find(f'class="schedule-appointment status-paid"')

    # Get the div content for the unpaid appointment
    unpaid_div_end = response.text.find("</div>", unpaid_index)
    unpaid_div_content = response.text[unpaid_index:unpaid_div_end]

    # Verify amount is not displayed for unpaid appointment
    assert "грн" not in unpaid_div_content

    # Also verify that the amount is displayed correctly for the paid appointment
    paid_div_end = response.text.find("</div>", paid_index)
    paid_div_content = response.text[paid_index:paid_div_end]

    assert "250.50 грн" in paid_div_content
