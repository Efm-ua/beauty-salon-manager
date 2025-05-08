"""
Tests for the user management functionality.
"""

import pytest
from flask import url_for

from app.models import User


def test_user_list_access_admin(admin_auth_client):
    """Verify admins can access the user list."""
    response = admin_auth_client.get(url_for("auth.users"))
    assert response.status_code == 200
    assert "Список користувачів" in response.get_data(as_text=True)


def test_user_list_access_denied_for_master(auth_client):
    """Verify masters cannot access the user list."""
    response = auth_client.get(url_for("auth.users"), follow_redirects=True)
    assert response.status_code == 200
    assert "Тільки адміністратори мають доступ до цієї сторінки" in response.get_data(
        as_text=True
    )


def test_create_user_as_admin(admin_auth_client, session):
    """Test creating a new user as an admin."""
    response = admin_auth_client.post(
        url_for("auth.register"),
        data={
            "username": "new_master",
            "full_name": "New Master",
            "password": "password123",
            "password2": "password123",
            "is_admin": "",  # Not checked, so it will be a master
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Користувач New Master успішно зареєстрований!" in response.get_data(
        as_text=True
    )

    # Verify the user was created
    new_user = User.query.filter_by(username="new_master").first()
    assert new_user is not None
    assert new_user.full_name == "New Master"
    assert not new_user.is_admin  # Should be a master (not admin)


def test_create_admin_as_admin(admin_auth_client, session):
    """Test creating a new admin as an admin."""
    response = admin_auth_client.post(
        url_for("auth.register"),
        data={
            "username": "new_admin",
            "full_name": "New Admin",
            "password": "password123",
            "password2": "password123",
            "is_admin": "y",  # Checked, so it will be an admin
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Користувач New Admin успішно зареєстрований!" in response.get_data(
        as_text=True
    )

    # Verify the user was created as an admin
    new_user = User.query.filter_by(username="new_admin").first()
    assert new_user is not None
    assert new_user.full_name == "New Admin"
    assert new_user.is_admin  # Should be an admin


def test_edit_user_as_admin(admin_auth_client, regular_user, session):
    """Test editing a user as an admin."""
    response = admin_auth_client.post(
        url_for("auth.edit_user", id=regular_user.id),
        data={
            "full_name": "Updated Master Name",
            "is_admin": "",  # Not checked, remains a master
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Користувач Updated Master Name успішно оновлений!" in response.get_data(
        as_text=True
    )

    # Verify user was updated
    updated_user = User.query.get(regular_user.id)
    assert updated_user.full_name == "Updated Master Name"
    assert not updated_user.is_admin


def test_toggle_admin_status(admin_auth_client, regular_user, session):
    """Test toggling admin status as an admin."""
    # Master to Admin
    assert not regular_user.is_admin  # Start as a master

    response = admin_auth_client.post(
        url_for("auth.toggle_admin", id=regular_user.id),
        follow_redirects=True,
    )
    assert response.status_code == 200

    # Verify admin status changed
    updated_user = User.query.get(regular_user.id)
    assert updated_user.is_admin  # Now an admin

    # Admin to Master (toggle back)
    response = admin_auth_client.post(
        url_for("auth.toggle_admin", id=regular_user.id),
        follow_redirects=True,
    )
    assert response.status_code == 200

    # Verify admin status changed back
    updated_user = User.query.get(regular_user.id)
    assert not updated_user.is_admin  # Back to master


def test_cannot_toggle_own_admin_status(admin_auth_client, admin_user, session):
    """Test that an admin cannot toggle their own admin status."""
    # Try to toggle own admin status
    response = admin_auth_client.post(
        url_for("auth.toggle_admin", id=admin_user.id),
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert (
        "Ви не можете змінити свій власний статус адміністратора"
        in response.get_data(as_text=True)
    )

    # Verify admin status did not change
    updated_user = User.query.get(admin_user.id)
    assert updated_user.is_admin  # Still an admin


def test_change_password(auth_client, regular_user, session):
    """Test password change functionality for users."""
    response = auth_client.post(
        url_for("auth.change_password"),
        data={
            "current_password": "user_password",  # The password from conftest fixture
            "new_password": "new_password123",
            "new_password2": "new_password123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Ваш пароль успішно змінено!" in response.get_data(as_text=True)

    # Try to login with the new password
    auth_client.get(url_for("auth.logout"), follow_redirects=True)  # Logout first

    login_response = auth_client.post(
        url_for("auth.login"),
        data={
            "username": regular_user.username,
            "password": "new_password123",
            "remember_me": False,
        },
        follow_redirects=True,
    )
    assert login_response.status_code == 200
    assert "Ласкаво просимо" in login_response.get_data(as_text=True)


def test_change_password_wrong_current(auth_client):
    """Test that changing password fails with wrong current password."""
    response = auth_client.post(
        url_for("auth.change_password"),
        data={
            "current_password": "wrong_password",  # Wrong password
            "new_password": "new_password123",
            "new_password2": "new_password123",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Невірний поточний пароль" in response.get_data(as_text=True)


# Tests for is_active_master functionality
def test_admin_can_view_is_active_master_status(admin_auth_client, regular_user):
    """Test that an admin can see the is_active_master field on the user edit page."""
    response = admin_auth_client.get(url_for("auth.edit_user", id=regular_user.id))
    assert response.status_code == 200
    # Check if the is_active_master checkbox appears in the form
    assert 'name="is_active_master"' in response.text
    assert 'type="checkbox"' in response.text


def test_admin_can_set_user_is_active_master_true(
    admin_auth_client, regular_user, session
):
    """Test that an admin can set is_active_master=True for a user."""
    # Set is_active_master to False first (to test changing it to True)
    regular_user.is_active_master = False
    session.commit()

    response = admin_auth_client.post(
        url_for("auth.edit_user", id=regular_user.id),
        data={
            "full_name": regular_user.full_name,
            "is_admin": "",  # Not checked, remains a master
            "is_active_master": "y",  # Checked, should be set to True
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    # Verify user was updated
    updated_user = User.query.get(regular_user.id)
    assert updated_user.is_active_master is True


def test_admin_can_set_user_is_active_master_false(
    admin_auth_client, regular_user, session
):
    """Test that an admin can set is_active_master=False for a user."""
    # Set is_active_master to True first (to test changing it to False)
    regular_user.is_active_master = True
    session.commit()

    response = admin_auth_client.post(
        url_for("auth.edit_user", id=regular_user.id),
        data={
            "full_name": regular_user.full_name,
            "is_admin": "",  # Not checked, remains a master
            "is_active_master": "",  # Not checked, should be set to False
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    # Verify user was updated
    updated_user = User.query.get(regular_user.id)
    assert updated_user.is_active_master is False


def test_user_creation_form_sets_is_active_master_correctly_for_new_master(
    admin_auth_client, session
):
    """Test that when creating a Master through the admin form, is_active_master is set to True."""
    response = admin_auth_client.post(
        url_for("auth.register"),
        data={
            "username": "new_master",
            "full_name": "New Master",
            "password": "password123",
            "password2": "password123",
            "is_admin": "",  # Not checked, so it will be a master
            # Not sending is_active_master, should default to True for masters
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    # Verify the user was created with is_active_master=True
    new_user = User.query.filter_by(username="new_master").first()
    assert new_user is not None
    assert not new_user.is_admin  # Should be a master (not admin)
    assert new_user.is_active_master is True  # Should be active master by default


def test_user_creation_form_sets_is_active_master_correctly_for_new_admin(
    admin_auth_client, session
):
    """Test that when creating an Admin through the admin form, is_active_master is set to False."""
    response = admin_auth_client.post(
        url_for("auth.register"),
        data={
            "username": "new_admin",
            "full_name": "New Admin",
            "password": "password123",
            "password2": "password123",
            "is_admin": "y",  # Checked, so it will be an admin
            # Not sending is_active_master, should default to False for admins
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    # Verify the user was created with is_active_master=False
    new_user = User.query.filter_by(username="new_admin").first()
    assert new_user is not None
    assert new_user.is_admin  # Should be an admin
    assert new_user.is_active_master is False  # Should not be active master by default
