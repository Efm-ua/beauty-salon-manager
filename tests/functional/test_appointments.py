def test_appointment_complete_with_payment_method(
    client, test_appointment, regular_user
):
    """
    Тестує процес завершення запису з вибором типу оплати.

    Цей тест перевіряє:
    1. Доступність сторінки деталей запису
    2. Наявність чекбоксів для вибору типу оплати
    3. Успішну зміну статусу та збереження типу оплати при виборі коректного типу
    4. Відображення обраного типу оплати на сторінці деталей
    """
    # Логін
    client.post(
        "/auth/login",
        data={
            "username": regular_user.username,
            "password": "user_password",
            "remember_me": "y",
        },
        follow_redirects=True,
    )

    # Відкриваємо сторінку запису
    response = client.get(f"/appointments/{test_appointment.id}")
    assert response.status_code == 200

    # Перевіряємо наявність чекбоксів для вибору типу оплати
    assert 'value="Готівка"' in response.text
    assert 'value="Малібу"' in response.text
    assert 'value="ФОП"' in response.text
    assert 'value="Приват"' in response.text
    assert 'value="MONO"' in response.text
    assert 'value="Борг"' in response.text

    # Перевіряємо наявність кнопки "Виконано" з атрибутом disabled
    assert 'id="complete-button"' in response.text
    assert "disabled" in response.text

    # Позначаємо запис як виконаний з типом оплати "Готівка"
    response = client.post(
        f"/appointments/{test_appointment.id}/status/completed",
        data={"payment_method": "Готівка"},
        follow_redirects=True,
    )
    assert response.status_code == 200

    # Перевіряємо успішність операції
    assert "Виконано" in response.text
    assert "Готівка" in response.text

    # Перевіряємо, що новий статус збережено у базі даних
    from app.models import Appointment, PaymentMethod

    updated_appointment = Appointment.query.get(test_appointment.id)
    assert updated_appointment.status == "completed"
    assert updated_appointment.payment_method == PaymentMethod.CASH

    # Перевіряємо неможливість зміни статусу без вибору типу оплати
    client.get(
        f"/appointments/{test_appointment.id}/status/scheduled", follow_redirects=True
    )
    response = client.post(
        f"/appointments/{test_appointment.id}/status/completed",
        follow_redirects=True,
    )
    assert "Помилка: будь ласка, виберіть рівно один тип оплати" in response.text
