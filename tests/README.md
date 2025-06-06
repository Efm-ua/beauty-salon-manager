# Тести для Класіко Manager

Цей каталог містить тести для системи управління Класіко.

## Структура тестів

- **conftest.py** - Загальні фікстури та налаштування для тестів
- **functional/** - Функціональні тести бізнес-процесів
- **integration/** - Інтеграційні тести між компонентами
- **unit/** - Юніт-тести для окремих функцій та класів

## Функціональні тести

Функціональні тести перевіряють повні бізнес-процеси системи від початку до кінця. Вони призначені для перевірки роботи системи з точки зору кінцевого користувача.

### Тести клієнтів

- **test_client_workflow.py**
  - `test_client_full_lifecycle` - Тестує повний життєвий цикл клієнта: створення, пошук, перегляд, редагування
  - `test_client_with_appointments` - Тестує процес створення клієнта та запису для нього

### Тести записів

- **test_appointment_flow.py**
  - `test_appointment_complete_flow` - Тестує повний цикл запису від створення до завершення
  - `test_appointment_filtering` - Тестує функціональність фільтрації записів
  - `test_appointment_pricing` - Тестує розрахунок цін записів

### Тести послуг

- **test_service_workflow.py**
  - `test_service_full_lifecycle` - Тестує повний життєвий цикл послуги: створення, перегляд, редагування, видалення
  - `test_service_with_appointments` - Тестує обмеження на видалення послуг з активними записами

### Тести авторизації

- **test_user_auth.py**
  - `test_direct_login_logout` - Тестує прямий вхід та вихід користувача через Flask-Login API
  - `test_form_based_login` - Тестує вхід через форму з валідними даними

## Запуск тестів

Для запуску всіх тестів використовуйте команду:

```
pytest
```

Для запуску тільки функціональних тестів:

```
pytest tests/functional/
```

Для запуску конкретного тесту:

```
pytest tests/functional/test_client_workflow.py::test_client_full_lifecycle -v
```

## Покриття тестами

Перевірка покриття тестами:

```
pytest --cov=app
```

Генерація звіту про покриття:

```
pytest --cov=app --cov-report=html
```
