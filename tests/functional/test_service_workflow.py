from datetime import datetime

from app.models import db


def test_service_full_lifecycle(session, client, admin_user):
    """
    Tests the full service lifecycle: create, view, edit, delete.

    This test simulates the following workflow:
    1. Admin creates a new service
    2. Views service details in the list
    3. Edits service information
    4. Verifies changes were saved correctly
    5. Deletes the service
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
    response = client.get("/services/")
    assert response.status_code == 200
    assert "Послуги" in response.text  # Services page title

    # Create a new service
    unique_id = datetime.now().strftime("%Y%m%d%H%M%S")
    service_name = f"Test Service {unique_id}"
    service_description = "Service for functional testing"
    service_duration = 60

    response = client.post(
        "/services/create",
        data={
            "name": service_name,
            "description": service_description,
            "duration": service_duration,
        },
        follow_redirects=True,
    )

    # Check that the service was created successfully
    assert response.status_code == 200
    assert "Послугу успішно додано!" in response.text
    assert service_name in response.text

    # Find service ID using direct database query
    from app.models import Service

    created_service = Service.query.filter_by(name=service_name).first()
    assert created_service is not None, "Service not found in database"
    service_id = created_service.id

    # Verify service details
    assert created_service.description == service_description
    assert created_service.duration == service_duration

    # Edit service information
    updated_name = f"Updated {service_name}"
    updated_description = "Updated service description"
    updated_duration = 90

    response = client.post(
        f"/services/{service_id}/edit",
        data={
            "name": updated_name,
            "description": updated_description,
            "duration": updated_duration,
        },
        follow_redirects=True,
    )

    # Check that the service was updated successfully
    assert response.status_code == 200
    assert "Послугу успішно оновлено!" in response.text
    assert updated_name in response.text

    # Verify service details in database
    session.refresh(created_service)
    assert created_service.name == updated_name
    assert created_service.description == updated_description
    assert created_service.duration == updated_duration

    # Delete the service
    response = client.post(
        f"/services/{service_id}/delete",
        follow_redirects=True,
    )

    # Check that the service was deleted successfully
    assert response.status_code == 200
    assert "Послугу успішно видалено!" in response.text

    # Verify service is no longer in the database
    deleted_service = Service.query.filter_by(id=service_id).first()
    assert deleted_service is None, "Service was not deleted from database"


def test_service_with_appointments(session, client, admin_user, test_client):
    """
    Tests the service management with appointments:
    1. Create a new service
    2. Create an appointment using the service directly in the database
    3. Verify service cannot be deleted when it has appointments
    4. Manually delete the appointment service association
    5. Delete the service after removing appointment associations
    """
    # Login first
    client.get("/auth/logout", follow_redirects=True)
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

    # Create a new service
    unique_id = datetime.now().strftime("%Y%m%d%H%M%S")
    service_name = f"Appointment Service {unique_id}"

    response = client.post(
        "/services/create",
        data={
            "name": service_name,
            "description": "Service for appointment testing",
            "duration": 45,
        },
        follow_redirects=True,
    )
    assert "Послугу успішно додано!" in response.text

    # Find service ID using direct database query
    from app.models import Service

    created_service = Service.query.filter_by(name=service_name).first()
    assert created_service is not None, "Service not found in database"
    service_id = created_service.id

    # Create an appointment directly in the database
    from datetime import date, time, timedelta

    from app.models import Appointment, AppointmentService

    tomorrow = date.today() + timedelta(days=1)

    # Create the appointment
    appointment = Appointment(
        client_id=test_client.id,
        master_id=admin_user.id,
        date=tomorrow,
        start_time=time(14, 0),
        end_time=time(15, 0),
        status="scheduled",
        payment_status="unpaid",
        notes="Service test appointment",
    )
    session.add(appointment)
    session.flush()  # Flush to get the ID

    # Add service to the appointment
    appointment_service = AppointmentService(
        appointment_id=appointment.id,
        service_id=service_id,
        price=100.0,
    )
    session.add(appointment_service)
    session.commit()

    # Verify appointment exists
    appointment_exists = Appointment.query.filter_by(
        client_id=test_client.id,
        master_id=admin_user.id,
        notes="Service test appointment",
    ).first()
    assert appointment_exists is not None, "Appointment not found in database"
    appointment_id = appointment_exists.id

    # Try to delete the service while it has an appointment
    response = client.post(
        f"/services/{service_id}/delete",
        follow_redirects=True,
    )

    # Service should not be deleted because it has appointments
    assert "Не можна видалити послугу" in response.text

    # Verify service still exists in the database
    service_check = Service.query.filter_by(id=service_id).first()
    assert service_check is not None, "Service was incorrectly deleted"

    # Instead of cancelling the appointment, we'll manually remove the appointment service
    # This simulates the user removing the service from the appointment
    appointment_service = AppointmentService.query.filter_by(
        appointment_id=appointment_id, service_id=service_id
    ).first()
    assert appointment_service is not None, "AppointmentService not found"

    # Delete the appointment service association
    db.session.delete(appointment_service)
    db.session.commit()

    # Now try to delete the service again
    response = client.post(
        f"/services/{service_id}/delete",
        follow_redirects=True,
    )

    # Check that the service was deleted successfully
    assert response.status_code == 200
    assert "Послугу успішно видалено!" in response.text

    # Verify service is no longer in the database
    deleted_service = Service.query.filter_by(id=service_id).first()
    assert deleted_service is None, "Service was not deleted from database"
