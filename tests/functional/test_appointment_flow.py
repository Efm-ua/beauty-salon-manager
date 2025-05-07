from datetime import date, datetime, time, timedelta

from flask import url_for


def test_appointment_complete_flow(
    session, client, test_client, test_service, regular_user
):
    """
    Tests a complete appointment flow from creation to completion.

    This test simulates the following workflow:
    1. Create a new appointment with a service
    2. View the appointment details
    3. Add an additional service to the appointment
    4. Edit a service price
    5. Change appointment status to completed
    6. Verify all changes and status in the database
    """
    # Login first - use a direct GET request to make sure we're logged out
    client.get("/auth/logout", follow_redirects=True)

    # Then login
    response = client.post(
        "/auth/login",
        data={
            "username": regular_user.username,
            "password": "user_password",
            "remember_me": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    # Verify login was successful by accessing a protected page
    response = client.get("/clients/")
    assert response.status_code == 200
    assert "Клієнти" in response.text  # Clients page title

    # Get today's date for the appointment
    today = date.today()

    # Create a new appointment
    response = client.post(
        "/appointments/create",
        data={
            "client_id": test_client.id,
            "master_id": regular_user.id,
            "date": today.strftime("%Y-%m-%d"),
            "start_time": "13:00",
            "services": str(test_service.id),
            "notes": "Flow test appointment",
        },
        follow_redirects=True,
    )

    # Check that the appointment was created successfully
    assert response.status_code == 200
    assert "Запис успішно створено!" in response.text

    # Find the appointment using database query
    from app.models import Appointment

    appointment = (
        Appointment.query.filter_by(
            client_id=test_client.id,
            master_id=regular_user.id,
            notes="Flow test appointment",
        )
        .order_by(Appointment.id.desc())
        .first()
    )

    assert appointment is not None, "Appointment not found in database"
    appointment_id = appointment.id

    # Verify initial appointment state
    assert appointment.status == "scheduled"
    assert appointment.start_time.strftime("%H:%M") == "13:00"

    # Calculate the expected end_time using the service duration
    start_datetime = datetime.combine(today, time(13, 0))
    expected_end_datetime = start_datetime + timedelta(minutes=test_service.duration)
    expected_end_time = expected_end_datetime.time()

    assert appointment.end_time.hour == expected_end_time.hour
    assert appointment.end_time.minute == expected_end_time.minute

    # Create a second test service for adding to the appointment
    from app.models import Service

    service_name = f"Additional Service {datetime.now().strftime('%Y%m%d%H%M%S')}"
    response = client.post(
        "/services/create",
        data={
            "name": service_name,
            "description": "Service for appointment flow test",
            "duration": "30",
        },
        follow_redirects=True,
    )

    # Find the service using database query
    additional_service = Service.query.filter_by(name=service_name).first()
    assert additional_service is not None, "Additional service not found in database"
    new_service_id = additional_service.id

    # Add the additional service to the appointment
    response = client.post(
        f"/appointments/{appointment_id}/add_service",
        data={
            "service_id": new_service_id,
            "price": "75.50",
            "notes": "Additional service notes",
        },
        follow_redirects=True,
    )

    # Verify the service was added in the database
    from app.models import AppointmentService

    added_service = AppointmentService.query.filter_by(
        appointment_id=appointment_id,
        service_id=new_service_id,
    ).first()
    assert (
        added_service is not None
    ), "Additional service was not added to the appointment"
    assert added_service.price == 75.50
    assert added_service.notes == "Additional service notes"

    # Find the original service assignment using database query
    original_service = AppointmentService.query.filter_by(
        appointment_id=appointment_id,
        service_id=test_service.id,
    ).first()
    assert (
        original_service is not None
    ), "Original appointment service not found in database"
    service_id = original_service.id

    # Update the price of the original service
    new_price = 120.00
    response = client.post(
        f"/appointments/{appointment_id}/edit_service/{service_id}",
        data={"price": str(new_price)},
        follow_redirects=True,
    )

    # Verify the price was updated in the database
    session.refresh(original_service)
    assert original_service.price == new_price, "Service price was not updated"

    # Change appointment status to completed
    response = client.post(
        f"/appointments/{appointment_id}/status/completed",
        data={"payment_method": "Готівка"},
        follow_redirects=True,
    )

    # Verify the status was updated in the database
    session.refresh(appointment)
    assert (
        appointment.status == "completed"
    ), "Appointment status was not updated to completed"

    # Перевірка, що тип оплати також збережено
    from app.models import PaymentMethod

    assert appointment.payment_method == PaymentMethod.CASH

    # Calculate and verify total price
    appointment_services = AppointmentService.query.filter_by(
        appointment_id=appointment_id
    ).all()
    total_price = sum(service.price for service in appointment_services)
    assert total_price == 120.00 + 75.50, "Total price calculation is incorrect"


def test_appointment_filtering(
    session, client, test_client, test_service, regular_user
):
    """
    Tests appointment filtering functionality.

    This test simulates the following workflow:
    1. Create multiple appointments with different dates, masters, and statuses
    2. Filter appointments by date
    3. Verify correct appointments are returned from the database
    """
    # Login first - use a direct GET request to make sure we're logged out
    client.get("/auth/logout", follow_redirects=True)

    # Then login
    response = client.post(
        "/auth/login",
        data={
            "username": regular_user.username,
            "password": "user_password",
            "remember_me": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    # Verify login was successful by accessing a protected page
    response = client.get("/clients/")
    assert response.status_code == 200
    assert "Клієнти" in response.text  # Clients page title

    # Create appointments for different dates
    today = date.today()
    tomorrow = today + timedelta(days=1)

    # Create appointment for today
    response = client.post(
        "/appointments/create",
        data={
            "client_id": test_client.id,
            "master_id": regular_user.id,
            "date": today.strftime("%Y-%m-%d"),
            "start_time": "09:00",
            "services": str(test_service.id),
            "notes": "Today's filter test appointment",
        },
        follow_redirects=True,
    )

    assert "Запис успішно створено!" in response.text

    # Create appointment for tomorrow
    response = client.post(
        "/appointments/create",
        data={
            "client_id": test_client.id,
            "master_id": regular_user.id,
            "date": tomorrow.strftime("%Y-%m-%d"),
            "start_time": "11:00",
            "services": str(test_service.id),
            "notes": "Tomorrow's filter test appointment",
        },
        follow_redirects=True,
    )

    assert "Запис успішно створено!" in response.text

    # Verify appointments exist in the database
    from app.models import Appointment

    # Find today's appointment
    today_appointment = Appointment.query.filter_by(
        client_id=test_client.id,
        master_id=regular_user.id,
        date=today,
        notes="Today's filter test appointment",
    ).first()

    assert today_appointment is not None, "Today's appointment not found in database"
    assert today_appointment.start_time.strftime("%H:%M") == "09:00"

    # Calculate expected end_time for today's appointment
    start_datetime = datetime.combine(today, time(9, 0))
    expected_end_datetime = start_datetime + timedelta(minutes=test_service.duration)
    expected_end_time = expected_end_datetime.time()

    assert today_appointment.end_time.hour == expected_end_time.hour
    assert today_appointment.end_time.minute == expected_end_time.minute

    # Find tomorrow's appointment
    tomorrow_appointment = Appointment.query.filter_by(
        client_id=test_client.id,
        master_id=regular_user.id,
        date=tomorrow,
        notes="Tomorrow's filter test appointment",
    ).first()

    assert (
        tomorrow_appointment is not None
    ), "Tomorrow's appointment not found in database"
    assert tomorrow_appointment.start_time.strftime("%H:%M") == "11:00"

    # Calculate expected end_time for tomorrow's appointment
    start_datetime = datetime.combine(tomorrow, time(11, 0))
    expected_end_datetime = start_datetime + timedelta(minutes=test_service.duration)
    expected_end_time = expected_end_datetime.time()

    assert tomorrow_appointment.end_time.hour == expected_end_time.hour
    assert tomorrow_appointment.end_time.minute == expected_end_time.minute

    # Query appointments by date and verify filtering works
    today_appointments = Appointment.query.filter_by(date=today).all()
    assert (
        today_appointment in today_appointments
    ), "Today's appointment not found in filtered results"
    assert (
        tomorrow_appointment not in today_appointments
    ), "Tomorrow's appointment found in today's filtered results"

    # Query appointments by tomorrow's date
    tomorrow_appointments = Appointment.query.filter_by(date=tomorrow).all()
    assert (
        tomorrow_appointment in tomorrow_appointments
    ), "Tomorrow's appointment not found in filtered results"
    assert (
        today_appointment not in tomorrow_appointments
    ), "Today's appointment found in tomorrow's filtered results"

    # Query appointments by master
    master_appointments = Appointment.query.filter_by(master_id=regular_user.id).all()
    assert (
        today_appointment in master_appointments
    ), "Today's appointment not found in master's appointments"
    assert (
        tomorrow_appointment in master_appointments
    ), "Tomorrow's appointment not found in master's appointments"


def test_appointment_pricing(session, client, test_client, test_service, regular_user):
    """
    Tests appointment pricing functionality.

    This test simulates the following workflow:
    1. Create an appointment with multiple services
    2. Add and modify service prices
    3. Verify correct price calculation in the database
    4. Test price totals are calculated correctly
    """
    # Login first - use a direct GET request to make sure we're logged out
    client.get("/auth/logout", follow_redirects=True)

    # Then login
    response = client.post(
        "/auth/login",
        data={
            "username": regular_user.username,
            "password": "user_password",
            "remember_me": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    # Verify login was successful by accessing a protected page
    response = client.get("/clients/")
    assert response.status_code == 200
    assert "Клієнти" in response.text  # Clients page title

    # Create a new appointment
    today = date.today()
    response = client.post(
        "/appointments/create",
        data={
            "client_id": test_client.id,
            "master_id": regular_user.id,
            "date": today.strftime("%Y-%m-%d"),
            "start_time": "15:00",
            "services": str(test_service.id),
            "notes": "Pricing test appointment",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200

    # Find the appointment using database query
    from app.models import Appointment

    appointment = (
        Appointment.query.filter_by(
            client_id=test_client.id,
            master_id=regular_user.id,
            notes="Pricing test appointment",
        )
        .order_by(Appointment.id.desc())
        .first()
    )

    assert appointment is not None, "Appointment not found in database"
    appointment_id = appointment.id

    # Create several additional services with different prices
    from app.models import Service

    service_names = ["Haircut", "Styling", "Hair Coloring"]
    service_prices = [150.00, 75.50, 300.00]
    service_durations = [30, 15, 60]

    service_objects = []
    for i, (name, duration) in enumerate(zip(service_names, service_durations)):
        unique_name = f"{name} {datetime.now().strftime('%Y%m%d%H%M%S')}"
        response = client.post(
            "/services/create",
            data={
                "name": unique_name,
                "description": f"Service for pricing test {i+1}",
                "duration": str(duration),
            },
            follow_redirects=True,
        )

        # Find the service using database query
        service = Service.query.filter_by(name=unique_name).first()
        assert service is not None, f"Service {name} not found in database"
        service_objects.append(service)

    # Add all services to the appointment with their respective prices
    from app.models import AppointmentService

    for i, service in enumerate(service_objects):
        response = client.post(
            f"/appointments/{appointment_id}/add_service",
            data={
                "service_id": service.id,
                "price": str(service_prices[i]),
                "notes": f"Price test service {i+1}",
            },
            follow_redirects=True,
        )

        # Verify service was added with correct price
        added_service = AppointmentService.query.filter_by(
            appointment_id=appointment_id, service_id=service.id
        ).first()

        assert (
            added_service is not None
        ), f"Service {service.name} was not added to appointment"
        assert (
            added_service.price == service_prices[i]
        ), f"Price for {service.name} is incorrect"
        assert (
            added_service.notes == f"Price test service {i+1}"
        ), f"Notes for {service.name} are incorrect"

    # Find the original service (the one added during appointment creation)
    original_service = AppointmentService.query.filter_by(
        appointment_id=appointment_id, service_id=test_service.id
    ).first()

    assert original_service is not None, "Original service not found"
    original_price = original_service.price

    # Calculate expected total price
    total_price = original_price + sum(service_prices)

    # Get all services and verify total
    all_services = AppointmentService.query.filter_by(
        appointment_id=appointment_id
    ).all()
    assert len(all_services) == 4, "Expected 4 services (original + 3 added)"

    calculated_total = sum(service.price for service in all_services)
    assert (
        calculated_total == total_price
    ), f"Total price calculation incorrect. Expected {total_price}, got {calculated_total}"

    # Verify appointment's get_total_price method works correctly
    assert (
        appointment.get_total_price() == total_price
    ), "Appointment.get_total_price() calculated incorrectly"


def test_appointment_redirect_to_schedule_date(
    session, client, test_client, regular_user, test_service
):
    """
    Tests that appointments created or edited from the schedule view redirect back to the schedule

    with the same date as the appointment.
    """
    # Login
    client.get("/auth/logout", follow_redirects=True)
    client.post(
        "/auth/login",
        data={
            "username": regular_user.username,
            "password": "user_password",
            "remember_me": "y",
        },
    )

    # Get a future date for the appointment
    future_date = (date.today() + timedelta(days=7)).strftime("%Y-%m-%d")

    # Create an appointment from the schedule view (don't follow redirects)
    response = client.post(
        "/appointments/create?from_schedule=1",
        data={
            "client_id": test_client.id,
            "master_id": regular_user.id,
            "date": future_date,
            "start_time": "14:00",
            "notes": "Appointment with redirect test",
            "services": str(test_service.id),  # Services are required now
        },
        follow_redirects=False,
    )

    # Check redirection location contains the appointment date
    assert response.status_code == 302
    redirect_location = response.headers["Location"]
    assert f"date={future_date}" in redirect_location

    # Test that updating an appointment from schedule view also redirects back to schedule
    # First find the appointment
    from app.models import Appointment

    appointment = (
        Appointment.query.filter_by(
            client_id=test_client.id,
            master_id=regular_user.id,
            notes="Appointment with redirect test",
        )
        .order_by(Appointment.id.desc())
        .first()
    )

    # Now edit the appointment from the schedule view
    response = client.post(
        f"/appointments/{appointment.id}/edit?from_schedule=1",
        data={
            "client_id": test_client.id,
            "master_id": regular_user.id,
            "date": future_date,
            "start_time": "15:00",  # Changed time
            "notes": "Appointment with redirect test",
            "services": str(test_service.id),  # Services are required now
        },
        follow_redirects=False,
    )

    # Check redirection
    assert response.status_code == 302
    redirect_location = response.headers["Location"]
    assert f"date={future_date}" in redirect_location


def test_appointment_form_uses_date_parameter(
    session, client, test_client, regular_user, test_service
):
    """
    Tests that the appointment creation form uses the date parameter from the URL.

    This test verifies:
    1. When accessing the appointment creation page with a date parameter,
       the form's date field is pre-populated with that date
    2. The date is correctly formatted in the form field
    """
    # Login first - use a direct GET request to make sure we're logged out
    client.get("/auth/logout", follow_redirects=True)

    # Then login
    response = client.post(
        "/auth/login",
        data={
            "username": regular_user.username,
            "password": "user_password",
            "remember_me": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    # Create a test date for next week (to ensure it's not using today's date by default)
    test_date = date.today() + timedelta(days=7)
    formatted_date = test_date.strftime("%Y-%m-%d")

    # Access the appointment creation page with the date parameter
    response = client.get(f"/appointments/create?date={formatted_date}")

    # Check the page loads successfully
    assert response.status_code == 200

    # Verify the form's date field is pre-populated with the correct date
    assert f'value="{formatted_date}"' in response.text

    # Test that it carries the date to form submission
    response = client.post(
        f"/appointments/create?date={formatted_date}",
        data={
            "client_id": test_client.id,
            "master_id": regular_user.id,
            "date": formatted_date,
            "start_time": "10:00",
            "services": str(test_service.id),  # Services are required now
            "notes": "Test appointment with date parameter",
        },
        follow_redirects=True,
    )

    # Check that the appointment was created with the correct date
    assert response.status_code == 200
    assert "Запис успішно створено!" in response.text

    # Find the appointment and verify date
    from app.models import Appointment

    appointment = (
        Appointment.query.filter_by(
            client_id=test_client.id,
            master_id=regular_user.id,
            notes="Test appointment with date parameter",
        )
        .order_by(Appointment.id.desc())
        .first()
    )

    assert appointment is not None, "Appointment not found in database"
    assert appointment.date == test_date


def test_appointment_back_to_schedule_button_includes_date(
    session, client, test_client, regular_user, admin_user, test_service
):
    """
    Tests that the "Back to schedule" button on the appointment details page
    includes the appointment date as a parameter.

    This test verifies:
    1. When viewing appointment details for a date X, the "Back to schedule"
       button href contains the date parameter with value X
    2. The date is correctly formatted as YYYY-MM-DD
    """
    # Login first as admin (required for viewing schedule)
    client.get("/auth/logout", follow_redirects=True)
    response = client.post(
        "/auth/login",
        data={
            "username": admin_user["username"],
            "password": "admin_password",
            "remember_me": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    # Create a test date for a future date (not today)
    test_date = date.today() + timedelta(days=5)
    formatted_date = test_date.strftime("%Y-%m-%d")

    # Create a new appointment for the test date
    response = client.post(
        "/appointments/create",
        data={
            "client_id": test_client.id,
            "master_id": regular_user.id,
            "date": formatted_date,
            "start_time": "14:00",
            "notes": "Test appointment for back button",
            "services": str(test_service.id),  # Services are required now
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Запис успішно створено!" in response.text

    # Get the newly created appointment
    from app.models import Appointment

    appointment = (
        Appointment.query.filter_by(
            client_id=test_client.id,
            master_id=regular_user.id,
            date=test_date,
            notes="Test appointment for back button",
        )
        .order_by(Appointment.id.desc())
        .first()
    )
    assert appointment is not None, "Appointment not found in database"

    # View the appointment details with a from_schedule parameter
    response = client.get(
        f"/appointments/{appointment.id}?from_schedule=1",
        follow_redirects=False,
    )

    # Check that the page includes a back button with the correct date
    assert response.status_code == 200
    assert "Назад до розкладу" in response.text

    # Extract the href attribute of the "Back to schedule" button using regex or other means
    # For simplicity, we'll just check if the HTML contains the correct URL
    href_content = f'href="{url_for("main.schedule")}?date={formatted_date}"'
    assert (
        href_content in response.text or href_content.replace('"', "'") in response.text
    )
