from datetime import datetime

import pytest
from flask_login import login_user
from werkzeug.security import generate_password_hash


def test_direct_login_logout(client, regular_user):
    """
    Tests direct login and logout using the User model and flask_login.

    1. Login the user directly through the API
    2. Verify access to protected page
    3. Logout
    4. Verify protected page is no longer accessible
    """
    # Use the test client context
    with client:
        # Login the user directly
        login_user(regular_user)

        # Access protected page
        response = client.get("/clients/")
        assert response.status_code == 200
        assert "Клієнти" in response.text

        # Logout
        response = client.get("/auth/logout", follow_redirects=True)

        # Verify logout success
        assert response.status_code == 200
        assert "Ви вийшли з системи" in response.text

        # Try to access protected page again
        response = client.get("/clients/", follow_redirects=True)

        # Should be redirected to login page
        assert response.status_code == 200
        assert "Вхід" in response.text


def test_form_based_login(client, regular_user):
    """
    Tests form-based login.

    1. Use a form to login with valid credentials
    2. Verify access to protected page
    """
    # Login with valid credentials through form
    with client:
        response = client.post(
            "/auth/login",
            data={
                "username": regular_user.username,
                "password": "user_password",
                "remember_me": "y",
            },
            follow_redirects=True,
        )

        # Verify login success by checking access to protected page
        response = client.get("/clients/")
        assert response.status_code == 200
        assert "Клієнти" in response.text
