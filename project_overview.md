# Огляд проекту: Beauty Salon Manager

**Останнє оновлення:** {08.05.2025} (Будь ласка, замініть на актуальну дату/час UTC)

## 1. Загальна інформація

- **Назва:** Beauty Salon Manager
- **Опис:** Веб-додаток для управління записами, клієнтами, послугами та персоналом салону краси.
- **Статус:** В розробці
- **Розгорнуто на:** PythonAnywhere
- **URL (PythonAnywhere):** https://mil2212.pythonanywhere.com/
- **Репозиторій GitHub:** https://github.com/Efm-ua/beauty-salon-manager

## 2. Технологічний стек

- **Мова:** Python (3.13.1 (з локального venv))
- **Фреймворк:** Flask (3.1.0)
- **ORM:** SQLAlchemy (2.0.38)
- **База даних:** SQLite
  - **Розташування (локально):** `instance/beauty_salon.db`
  - **Розташування (PythonAnywhere):** `/home/mil2212/beauty-salon-manager/instance/beauty_salon.db`
- **Міграції БД:** Flask-Migrate / Alembic (Flask-Migrate: 4.1.0, Alembic: 1.15.2)
  - **Поточна ревізія БД (HEAD):** `16585a9dda8f`
- **Форми:** Flask-WTF (1.2.2)
- **Автентифікація:** Flask-Login (0.6.3)
- **Шаблонізатор:** Jinja2 (3.1.6)
- **Фронтенд:** HTML, CSS (Bootstrap 5.3.0-alpha1), JavaScript
- **Тестування:** Pytest (8.3.5)
  - Плагіни: pytest-flask (1.3.0), pytest-cov (6.1.1), pytest-mock (3.14.0)
- **Якість коду:**
  - Black (25.1.0)
  - isort (6.0.1)
  - flake8 (7.2.0)
  - mypy (1.15.0)
- **Залежності (основні):**
  - Flask==3.1.0
  - SQLAlchemy==2.0.38
  - Flask-Migrate==4.1.0
  - Flask-Login==0.6.3
  - Flask-WTF==1.2.2
  - pytest==8.3.5
  - python-dotenv==1.0.1
- **Середовище розробки:** Windows (PowerShell)
- **Віртуальне середовище (локально):** `venv` в корені проекту.
- **Віртуальне середовище (PythonAnywhere):** `/home/mil2212/venv_app`

## 3. Структура проекту

- **`app/`**: Основний код додатку
  - **`__init__.py`**: Фабрика додатку (`create_app`)
  - **`config.py`**: Класи конфігурації
  - **`models/__init__.py`**: Моделі SQLAlchemy
  - **`routes/`**: Маршрути Flask (Blueprints: `auth.py`, `main.py`, `appointments.py`, `clients.py`, `services.py`, `reports.py`)
  - **`static/`**: Статичні файли
  - **`templates/`**: Шаблони Jinja2
  - **`commands.py`**: Кастомні CLI команди Flask (`create-admin`) - _Перевірити наявність та актуальність_
- **`migrations/`**: Файли міграцій Alembic
  - **`versions/`**: Скрипти міграцій
- **`tests/`**: Тести Pytest
  - **`conftest.py`**: Фікстури та конфігурація тестів
  - `unit/`, `integration/`, `functional/`
- **`instance/`**: Конфігураційні файли, БД SQLite (`beauty_salon.db`) (Не в Git)
- **`run.py`**: Точка входу для локального запуску.
- **`requirements.txt`**: Залежності Python.
- **`.env`**: Змінні середовища.
- **`.gitignore`**: Правила Git.
- **`wsgi.py` (PythonAnywhere):** `/var/www/mil2212_pythonanywhere_com_wsgi.py` (Поза репозиторієм).

## 4. Ключові компоненти та логіка

- **Автентифікація:** Flask-Login, модель `User`. Ролі: `is_admin` (boolean), `is_active_master` (boolean). Користувач є або адміністратором, або майстром (визначається `not User.is_admin`).
- **Записи (Appointments):** Модель `Appointment`, зв'язок з `Client`, `User` (майстер), `Service` (M2M через `AppointmentServiceLink`).
- **Клієнти (Clients):** Модель `Client`.
- **Послуги (Services):** Модель `Service`.
- **Майстри (Masters):** Модель `User` з `is_active_master=True`.
- **Ціноутворення:** Динамічне (`get_total_price`, `get_discounted_price` в моделі `Appointment`).
- **Звіти (Reports):** Фінансовий, Зарплатний.
- **CLI команди:** `flask create-admin`. (Перевірити `app/commands.py` на інші команди).

## 5. Розгортання та оточення

- **Платформа:** PythonAnywhere (Тип акаунту:Paid)
- **База даних:** SQLite (`instance/beauty_salon.db`).
- **Оновлення коду:** GitHub webhook.
- **WSGI сервер:** Налаштовано PythonAnywhere.
- **Залежності PythonAnywhere:** Синхронізуються з `requirements.txt` в `/home/mil2212/venv_app`.
- **Міграції на PythonAnywhere:** Ручний запуск `flask db upgrade` в консолі PA.

## 6. Процес розробки та тестування

- **Контроль версій:** Git / GitHub.
- **Гілки:** `* main` (локальна)
- **Тестування:** Pytest (локально). CI/CD: Не виявлено (директорія `.github/workflows/` відсутня)
- **Якість коду:** Black, isort, flake8, mypy (перед комітами).
- **Менторство:** AI-ментор (Gemini) + Cursor AI.

## 7. Поточні завдання / Проблеми

- - Залишилися попередження SQLAlchemy `Query.get()` deprecation. -> Потребує рефакторингу.
- Залишилися попередження `flake8` щодо довжини рядків. -> Потребує форматування.

## 8. Додаткові нотатки / Контекст

- (Сюди можна додати будь-яку іншу релевантну інформацію)
