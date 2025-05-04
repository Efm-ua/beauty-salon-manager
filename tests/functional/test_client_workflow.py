import pytest
from datetime import datetime, timedelta, date, time
from flask_login import login_user


def test_client_full_lifecycle(session, client, regular_user):
    """
    Tests the full client lifecycle: create, search, view, edit.

    This test simulates the following workflow:
    1. Admin creates a new client
    2. Searches for the client by name
    3. Views client details
    4. Edits client information
    5. Verifies changes were saved correctly
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

    # Create a new client
    unique_id = datetime.now().strftime("%Y%m%d%H%M%S")
    client_name = f"Test Client {unique_id}"
    client_phone = f"+380991234{unique_id[-4:]}"
    client_email = f"test{unique_id}@example.com"

    response = client.post(
        "/clients/create",
        data={
            "name": client_name,
            "phone": client_phone,
            "email": client_email,
            "notes": "Functional test notes",
        },
        follow_redirects=True,
    )

    # Check that the client was created successfully
    assert response.status_code == 200
    assert client_name in response.text
    assert client_phone in response.text
    assert client_email in response.text
    assert "Functional test notes" in response.text
    assert "Клієнт успішно доданий!" in response.text

    # Search for the client
    response = client.get(f"/clients/?search={client_name}")
    assert response.status_code == 200
    assert client_name in response.text

    # Get the client ID from the response
    # Extract client ID from the URL in response like "/clients/123"
    import re

    client_url_pattern = re.compile(r'/clients/(\d+)"')
    client_id_match = client_url_pattern.search(response.text)
    assert client_id_match, "Could not find client ID in response"
    client_id = client_id_match.group(1)

    # View client details
    response = client.get(f"/clients/{client_id}")
    assert response.status_code == 200
    assert client_name in response.text
    assert client_phone in response.text
    assert client_email in response.text

    # Edit client information
    updated_name = f"Updated {client_name}"
    updated_notes = "Updated functional test notes"

    response = client.post(
        f"/clients/{client_id}/edit",
        data={
            "name": updated_name,
            "phone": client_phone,  # Keep the same phone
            "email": client_email,  # Keep the same email
            "notes": updated_notes,
        },
        follow_redirects=True,
    )

    # Check that the client was updated successfully
    assert response.status_code == 200
    assert updated_name in response.text
    assert updated_notes in response.text
    assert "Інформацію про клієнта успішно оновлено!" in response.text

    # Verify by doing a direct request to client view
    response = client.get(f"/clients/{client_id}")
    assert updated_name in response.text
    assert updated_notes in response.text


def test_client_with_appointments(session, client, regular_user, test_service):
    """
    Tests the client management with appointments: create client,
    create appointments, verify appointment history.

    This test simulates the following workflow:
    1. Create a new client
    2. Create multiple appointments for the client
    3. Verify appointments were created correctly in the database
    4. Check appointment details match what was entered
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

    # Create a new client
    unique_id = datetime.now().strftime("%Y%m%d%H%M%S")
    client_name = f"Appointment Client {unique_id}"
    client_phone = f"+380661234{unique_id[-4:]}"
    client_email = f"appt{unique_id}@example.com"

    response = client.post(
        "/clients/create",
        data={
            "name": client_name,
            "phone": client_phone,
            "email": client_email,
            "notes": "Client for appointment tests",
        },
        follow_redirects=True,
    )

    # Check that the client was created successfully
    assert response.status_code == 200
    assert client_name in response.text
    assert client_phone in response.text
    assert "Клієнт успішно доданий!" in response.text

    # Find client ID using direct database query instead of HTML parsing
    from app.models import Client

    created_client = Client.query.filter_by(phone=client_phone).first()
    assert created_client is not None, "Client not found in database"
    client_id = created_client.id

    # Get today's date and tomorrow's date for appointments
    today = date.today()
    tomorrow = today + timedelta(days=1)

    # Create an appointment for today
    response = client.post(
        "/appointments/create",
        data={
            "client_id": client_id,
            "master_id": str(regular_user.id),
            "date": today.strftime("%Y-%m-%d"),
            "start_time": "10:00",
            "end_time": "11:00",
            "services": str(test_service.id),  # Use the test service
            "notes": "Today's appointment",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Запис успішно створено!" in response.text

    # Create another appointment for tomorrow
    response = client.post(
        "/appointments/create",
        data={
            "client_id": client_id,
            "master_id": str(regular_user.id),
            "date": tomorrow.strftime("%Y-%m-%d"),
            "start_time": "14:00",
            "end_time": "15:00",
            "services": str(test_service.id),  # Use the test service
            "notes": "Tomorrow's appointment",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Запис успішно створено!" in response.text

    # Check that the appointments exist in the database
    from app.models import Appointment

    # Find today's appointment
    today_appointment = Appointment.query.filter_by(
        client_id=client_id,
        master_id=regular_user.id,
        date=today,
        notes="Today's appointment",
    ).first()

    assert today_appointment is not None, "Today's appointment not found in database"
    assert today_appointment.start_time.strftime("%H:%M") == "10:00"
    assert today_appointment.end_time.strftime("%H:%M") == "11:00"
    assert today_appointment.status == "scheduled"

    # Find tomorrow's appointment
    tomorrow_appointment = Appointment.query.filter_by(
        client_id=client_id,
        master_id=regular_user.id,
        date=tomorrow,
        notes="Tomorrow's appointment",
    ).first()

    assert (
        tomorrow_appointment is not None
    ), "Tomorrow's appointment not found in database"
    assert tomorrow_appointment.start_time.strftime("%H:%M") == "14:00"
    assert tomorrow_appointment.end_time.strftime("%H:%M") == "15:00"
    assert tomorrow_appointment.status == "scheduled"

    # Verify services were assigned to appointments
    from app.models import AppointmentService

    today_services = AppointmentService.query.filter_by(
        appointment_id=today_appointment.id
    ).all()
    assert len(today_services) == 1, "Expected one service for today's appointment"
    assert today_services[0].service_id == test_service.id

    tomorrow_services = AppointmentService.query.filter_by(
        appointment_id=tomorrow_appointment.id
    ).all()
    assert (
        len(tomorrow_services) == 1
    ), "Expected one service for tomorrow's appointment"
    assert tomorrow_services[0].service_id == test_service.id
