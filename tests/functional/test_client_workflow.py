from datetime import date, datetime, timedelta


def test_client_full_lifecycle(session, client, admin_user):
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
            "username": admin_user.username,
            "password": "admin_password",
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

    # Check that the client was created successfully and we're on the view page
    assert response.status_code == 200
    assert client_name in response.text
    assert client_phone in response.text
    assert client_email in response.text
    assert "Functional test notes" in response.text
    assert "Інформація про клієнта" in response.text
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


def test_client_with_appointments(session, client, admin_user, test_service):
    """
    Tests the client management with appointments.

    This test simulates the following workflow:
    1. Create a new client
    2. Verify client was created correctly in the database
    """
    # Login first - use a direct GET request to make sure we're logged out
    client.get("/auth/logout", follow_redirects=True)

    # Then login as admin
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

    # Check that the client was created successfully and we're on the view page
    assert response.status_code == 200
    assert client_name in response.text
    assert client_phone in response.text
    assert client_email in response.text
    assert "Client for appointment tests" in response.text
    assert "Інформація про клієнта" in response.text
    assert "Клієнт успішно доданий!" in response.text

    # Find client ID using direct database query to verify database operations
    from app.models import Client

    created_client = Client.query.filter_by(phone=client_phone).first()
    assert created_client is not None, "Client not found in database"
    assert created_client.name == client_name
    assert created_client.phone == client_phone
    assert created_client.email == client_email
    assert created_client.notes == "Client for appointment tests"
