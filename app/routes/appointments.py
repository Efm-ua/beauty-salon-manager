from datetime import date, datetime, time, timedelta
from decimal import Decimal

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    DecimalField,
    FloatField,
    RadioField,
    SelectField,
    SelectMultipleField,
    SubmitField,
    TextAreaField,
    TimeField,
)
from wtforms.validators import DataRequired, NumberRange, Optional, ValidationError

from app.models import (
    Appointment,
    AppointmentService,
    Client,
    PaymentMethod,
    Service,
    User,
    db,
)

# Створення Blueprint
bp = Blueprint("appointments", __name__, url_prefix="/appointments")


# Форма для запису з можливістю вибору декількох послуг
class AppointmentForm(FlaskForm):
    client_id = SelectField("Клієнт", coerce=int, validators=[DataRequired()])
    master_id = SelectField("Майстер", coerce=int, validators=[DataRequired()])
    date = DateField("Дата", validators=[DataRequired()], default=date.today)
    start_time = TimeField(
        "Час початку", validators=[DataRequired()], default=time(9, 0)
    )
    services = SelectMultipleField("Послуги", coerce=int, validators=[DataRequired()])
    discount_percentage = DecimalField(
        "Знижка, %",
        validators=[Optional(), NumberRange(min=0, max=100)],
        render_kw={"placeholder": "0.00"},
        default=Decimal("0.0"),
    )
    amount_paid = DecimalField(
        "Сплачено",
        validators=[Optional(), NumberRange(min=0)],
        render_kw={"placeholder": "0.00"},
    )
    payment_method = SelectField(
        "Метод оплати",
        choices=[("", "Виберіть метод оплати...")]
        + [(pm.value, pm.value) for pm in PaymentMethod],
        validators=[Optional()],
    )
    notes = TextAreaField("Примітки", validators=[Optional()])
    submit = SubmitField("Зберегти")

    def validate_master_id(self, field):
        """Перевіряє, чи є вибраний майстер активним."""
        # Отримуємо об'єкт майстра
        master = db.session.get(User, field.data)
        if master and not master.is_active_master:
            raise ValidationError("Вибраний майстер не є активним")

    def validate_date(self, field):
        """Перевіряє, що дата не в минулому."""
        today = date.today()
        if field.data < today:
            raise ValidationError("Дата повинна бути сьогодні або в майбутньому")


# Форма для додавання послуги до запису (залишається без змін)
class ServiceForm(FlaskForm):
    service_id = SelectField("Послуга", coerce=int, validators=[DataRequired()])
    price = FloatField("Ціна", validators=[DataRequired()])
    notes = TextAreaField("Примітки", validators=[Optional()])
    submit = SubmitField("Додати послугу")


# Форма для зміни статусу запису з можливістю вибору методу оплати
class AppointmentStatusPaymentForm(FlaskForm):
    payment_method = RadioField(
        "Метод оплати",
        choices=[(pm.value, pm.value) for pm in PaymentMethod],
        validators=[
            DataRequired(
                message="Будь ласка, виберіть тип оплати для завершення запису."
            )
        ],
    )
    submit = SubmitField("Зберегти")


# Список всіх записів
@bp.route("/")
@login_required
def index():
    # Отримання дати для фільтрації
    filter_date = request.args.get("date")
    if filter_date:
        try:
            filter_date = datetime.strptime(filter_date, "%Y-%m-%d").date()
        except ValueError:
            filter_date = datetime.now().date()
    else:
        filter_date = datetime.now().date()

    # Отримання майстра для фільтрації
    filter_master = request.args.get("master_id")
    if filter_master and filter_master.isdigit():
        filter_master = int(filter_master)
    else:
        filter_master = None

    # Базовий запит
    query = Appointment.query.filter(Appointment.date == filter_date)

    # Додавання фільтрації за майстром (з урахуванням ролі)
    if filter_master and (current_user.is_admin or filter_master == current_user.id):
        # Адміністратор може фільтрувати по будь-якому майстру
        # Майстер може фільтрувати тільки по собі
        query = query.filter(Appointment.master_id == filter_master)
    elif not current_user.is_admin:
        # Якщо це не адміністратор і немає явного фільтра, показуємо тільки його записи
        query = query.filter(Appointment.master_id == current_user.id)

    # Отримання записів
    appointments = query.order_by(Appointment.start_time).all()

    # Отримання списку майстрів для фільтра
    masters = User.query.filter_by(is_active_master=True).all()

    return render_template(
        "appointments/index.html",
        title="Записи",
        appointments=appointments,
        filter_date=filter_date,
        filter_master=filter_master,
        masters=masters,
        is_admin=current_user.is_admin,
    )


# Створення нового запису (оновлений маршрут)
@bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    form = AppointmentForm()

    # Заповнення варіантів вибору для клієнтів, майстрів та послуг
    form.client_id.choices = [
        (c.id, f"{c.name} ({c.phone})")
        for c in Client.query.order_by(Client.name).all()
    ]

    # Майстер може створювати записи тільки для себе
    if current_user.is_admin:
        form.master_id.choices = [
            (u.id, u.full_name)
            for u in User.query.filter_by(is_active_master=True)
            .order_by(User.full_name)
            .all()
        ]
    else:
        form.master_id.choices = [(current_user.id, current_user.full_name)]
        # Автоматично встановлюємо поточного майстра
        form.master_id.data = current_user.id
        # Блокуємо поле вибору майстра для редагування
        form.master_id.render_kw = {"disabled": "disabled"}

    form.services.choices = [
        (s.id, f"{s.name} ({s.duration} хв.)")
        for s in Service.query.order_by(Service.name).all()
    ]

    # Встановлення значень за замовчуванням з параметрів запиту
    if request.method == "GET":
        # Встановлення майстра
        master_id = request.args.get("master_id")
        if master_id and master_id.isdigit():
            # Майстер може створювати записи тільки для себе
            if current_user.is_admin or int(master_id) == current_user.id:
                form.master_id.data = int(master_id)
            else:
                form.master_id.data = current_user.id
        else:
            form.master_id.data = current_user.id

        # Встановлення дати
        date_str = request.args.get("date")
        if date_str:
            try:
                form.date.data = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                form.date.data = datetime.now().date()
        else:
            form.date.data = datetime.now().date()

        # Встановлення часу
        time_str = request.args.get("time")
        if time_str:
            try:
                start_time = datetime.strptime(time_str, "%H:%M").time()
                form.start_time.data = start_time
            except ValueError:
                form.start_time.data = time(9, 0)  # Default time if parsing fails
        else:
            form.start_time.data = time(9, 0)  # Default time if not provided

    if form.validate_on_submit():
        # Додаємо логування стану current_user
        from sqlalchemy import inspect

        print(
            f"DEBUG ROUTE CREATE: current_user - ID={current_user.id}, "
            f"username={current_user.username}, "
            f"is_detached={inspect(current_user).detached if hasattr(inspect(current_user), 'detached') else 'N/A'}, "
            f"session_id={inspect(current_user).session_id if hasattr(inspect(current_user), 'session_id') else 'N/A'}"
        )

        # Перевірка, що дата та час не в минулому
        now = datetime.now()
        appointment_datetime = datetime.combine(form.date.data, form.start_time.data)
        if appointment_datetime < now:
            flash("Неможливо створити запис на дату та час у минулому", "danger")
            return render_template(
                "appointments/create.html",
                title="Новий запис",
                form=form,
                is_admin=current_user.is_admin,
            )

        # Для майстрів, завжди використовуємо їх ідентифікатор
        if not current_user.is_admin:
            master_id = current_user.id
        else:
            master_id = form.master_id.data

        # Отримуємо першу послугу для розрахунку end_time
        if form.services.data:
            service = db.session.get(Service, form.services.data[0])
            # Розраховуємо end_time на основі start_time та тривалості послуги
            start_datetime = datetime.combine(form.date.data, form.start_time.data)
            end_datetime = start_datetime + timedelta(minutes=service.duration)
            end_time = end_datetime.time()
        else:
            # На випадок, якщо валідація пропустила запис без послуг
            end_time = form.start_time.data  # Встановлюємо такий же час як і початок

        appointment = Appointment(
            client_id=form.client_id.data,
            master_id=master_id,
            date=form.date.data,
            start_time=form.start_time.data,
            end_time=end_time,
            notes=form.notes.data,
            status="scheduled",
            payment_status="unpaid",  # За замовчуванням "unpaid"
            discount_percentage=form.discount_percentage.data or Decimal("0.0"),
        )

        # Логування після створення екземпляра appointment
        print(
            f"DEBUG ROUTE CREATE: After instance creation - appointment ID={appointment.id if hasattr(appointment, 'id') else 'None'}, "
            f"is_transient={inspect(appointment).transient if hasattr(inspect(appointment), 'transient') else 'N/A'}, "
            f"is_pending={inspect(appointment).pending if hasattr(inspect(appointment), 'pending') else 'N/A'}, "
            f"is_detached={inspect(appointment).detached if hasattr(inspect(appointment), 'detached') else 'N/A'}"
        )

        if hasattr(appointment, "master") and appointment.master:
            print(
                f"DEBUG ROUTE CREATE: After instance creation - master ID={appointment.master.id}, "
                f"username={appointment.master.username}, "
                f"is_detached={inspect(appointment.master).detached}"
            )

        db.session.add(appointment)
        db.session.flush()  # отримуємо ID запису

        # Логування після db.session.flush()
        print(
            f"DEBUG ROUTE CREATE: After flush - appointment ID={appointment.id}, "
            f"is_transient={inspect(appointment).transient}, "
            f"is_pending={inspect(appointment).pending}, "
            f"is_detached={inspect(appointment).detached}"
        )

        if hasattr(appointment, "master") and appointment.master:
            print(
                f"DEBUG ROUTE CREATE: After flush - master ID={appointment.master.id}, "
                f"username={appointment.master.username}, "
                f"is_detached={inspect(appointment.master).detached}"
            )

        # Додавання вибраних послуг
        if form.services.data:
            for service_id in form.services.data:
                service = db.session.get(Service, service_id)
                if service:
                    # Встановлюємо базову ціну послуги (тут можна змінити логіку розрахунку)
                    appointment_service = AppointmentService(
                        appointment_id=appointment.id,
                        service_id=service_id,
                        price=(
                            float(service.base_price)
                            if service.base_price is not None
                            else 0.0
                        ),
                        notes="",
                    )
                    db.session.add(appointment_service)

        try:
            db.session.commit()
            flash("Запис успішно створено!", "success")

            # Перевіряємо, чи було запит зроблено з розкладу
            from_schedule = request.args.get("from_schedule") == "1"

            if from_schedule:
                # Якщо так, повертаємось на сторінку розкладу з тією ж датою
                return redirect(
                    url_for("main.schedule", date=form.date.data.strftime("%Y-%m-%d"))
                )
            else:
                # Інакше показуємо створений запис
                return redirect(url_for("appointments.view", id=appointment.id))
        except Exception as e:
            db.session.rollback()
            flash(f"Помилка при створенні запису: {str(e)}", "danger")
            return redirect(url_for("appointments.create"))

    return render_template(
        "appointments/create.html",
        title="Новий запис",
        form=form,
        is_admin=current_user.is_admin,
    )


# Перегляд запису
@bp.route("/<int:id>")
@login_required
def view(id):
    # Отримання запису
    appointment = Appointment.query.get_or_404(id)

    # Перевірка, чи має право користувач переглядати цей запис
    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("Ви можете переглядати тільки свої записи", "danger")
        return redirect(url_for("appointments.index"))

    # Розрахунок фінансової інформації
    total_price = appointment.get_total_price()
    total_discounted = appointment.get_discounted_price()

    # Перевіряємо, чи був запит з розкладу
    from_schedule = request.args.get("from_schedule") == "1"

    return render_template(
        "appointments/view.html",
        title=f"Запис: {appointment.client.name} {appointment.date}",
        appointment=appointment,
        total_price=total_price,
        total_discounted=total_discounted,
        payment_methods=[method for method in PaymentMethod],
        is_admin=current_user.is_admin,
        from_schedule=from_schedule,
        formatted_date=appointment.date.strftime("%Y-%m-%d"),
    )


# Редагування запису
@bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id):
    # Use eager loading for related objects
    appointment = (
        Appointment.query.options(
            db.joinedload(Appointment.client), db.joinedload(Appointment.master)
        )
        .options(
            db.joinedload(Appointment.services).joinedload(AppointmentService.service)
        )
        .filter_by(id=id)
        .first_or_404()
    )

    # Перевірка прав на редагування
    if not current_user.is_admin and current_user.id != appointment.master_id:
        flash(
            "Ви не можете редагувати цей запис. Він належить іншому майстру.",
            "danger",
        )
        return redirect(url_for("appointments.index"))

    # Перевіряємо, чи був запит з розкладу
    from_schedule = request.args.get("from_schedule") == "1"

    form = AppointmentForm(obj=appointment)

    # Заповнення списку клієнтів, майстрів та послуг
    form.client_id.choices = [
        (c.id, f"{c.name} ({c.phone})")
        for c in Client.query.order_by(Client.name).all()
    ]

    # Майстер може створювати записи тільки для себе
    if current_user.is_admin:
        form.master_id.choices = [
            (u.id, u.full_name)
            for u in User.query.filter_by(is_active_master=True)
            .order_by(User.full_name)
            .all()
        ]
    else:
        # Для майстра - тільки його власний ідентифікатор
        form.master_id.choices = [(current_user.id, current_user.full_name)]
        form.master_id.render_kw = {"disabled": "disabled"}

    form.services.choices = [
        (s.id, f"{s.name} ({s.duration} хв.)")
        for s in Service.query.order_by(Service.name).all()
    ]

    # Для GET запиту ініціалізуємо початкові значення форми
    if request.method == "GET":
        # Встановлюємо обрані послуги
        form.services.data = [service.service_id for service in appointment.services]
        # Встановлюємо суму оплати, якщо вона є
        if appointment.amount_paid is not None:
            form.amount_paid.data = appointment.amount_paid
        # Встановлюємо метод оплати
        if appointment.payment_method:
            form.payment_method.data = appointment.payment_method.value

    if form.validate_on_submit():
        # Для майстрів, зберігаємо початкового клієнта і майстра
        if not current_user.is_admin:
            client_id = appointment.client_id
            master_id = appointment.master_id
        else:
            client_id = form.client_id.data
            master_id = form.master_id.data

        # Оновлюємо базові поля запису
        appointment.client_id = client_id
        appointment.master_id = master_id
        appointment.date = form.date.data
        appointment.start_time = form.start_time.data
        appointment.discount_percentage = form.discount_percentage.data or Decimal(
            "0.0"
        )
        appointment.notes = form.notes.data

        # Перевірка, чи вказана сума оплати
        if form.amount_paid.data is not None:
            appointment.amount_paid = form.amount_paid.data
        else:
            appointment.amount_paid = None

        # Перевірка, чи вказаний метод оплати
        if form.payment_method.data:
            appointment.payment_method = PaymentMethod(form.payment_method.data)
        else:
            appointment.payment_method = None

        # Обчислення end_time на основі тривалості першої послуги
        if form.services.data:
            service = db.session.get(Service, form.services.data[0])
            start_datetime = datetime.combine(form.date.data, form.start_time.data)
            end_datetime = start_datetime + timedelta(minutes=service.duration)
            appointment.end_time = end_datetime.time()

        # Оновлення статусу оплати
        appointment.update_payment_status()

        # Видалення існуючих послуг
        for service in appointment.services:
            db.session.delete(service)

        # Додавання нових послуг
        if form.services.data:
            for service_id in form.services.data:
                service = db.session.get(Service, service_id)
                appointment_service = AppointmentService(
                    appointment_id=appointment.id,
                    service_id=service_id,
                    price=(
                        float(service.base_price)
                        if service.base_price is not None
                        else 0.0
                    ),
                    notes="",
                )
                db.session.add(appointment_service)

        # Збереження змін
        try:
            db.session.commit()
            flash("Запис успішно оновлено!", "success")

            # Якщо редагування було зроблено зі сторінки розкладу, повертаємося до розкладу
            if from_schedule or request.form.get("from_schedule") == "1":
                return redirect(
                    url_for("main.schedule", date=form.date.data.strftime("%Y-%m-%d"))
                )
            else:
                return redirect(url_for("appointments.view", id=appointment.id))
        except Exception as e:
            db.session.rollback()
            flash(f"Помилка при оновленні запису: {str(e)}", "danger")

    return render_template(
        "appointments/edit.html",
        title="Редагування запису",
        form=form,
        appointment=appointment,
        is_admin=current_user.is_admin,
        from_schedule=from_schedule,
    )


# Зміна статусу запису
@bp.route("/<int:id>/status/<new_status>", methods=["GET", "POST"])
@login_required
def change_status(id, new_status):
    # Перевірка, чи статус допустимий
    valid_statuses = ["scheduled", "completed", "cancelled"]
    if new_status not in valid_statuses:
        flash(f"Недопустимий статус: {new_status}", "danger")
        return redirect(url_for("appointments.view", id=id))

    # Отримання запису
    appointment = Appointment.query.get_or_404(id)

    print(
        f"DEBUG CHANGE_STATUS: Request to change status of appointment {id} to {new_status}"
    )
    print(f"DEBUG CHANGE_STATUS: Current appointment status: {appointment.status}")
    print(f"DEBUG CHANGE_STATUS: Form data: {request.form}")

    # Перевірка, чи має право користувач змінювати статус цього запису
    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("Ви можете змінювати статус тільки своїх записів", "danger")
        return redirect(url_for("appointments.index"))

    # Збереження попереднього статусу для перевірки
    previous_status = appointment.status

    # Не дозволяємо змінювати статус з "completed" на будь-який інший статус (окрім scheduled для тесту)
    if (
        previous_status == "completed"
        and new_status != "completed"
        and new_status != "scheduled"
    ):
        flash("Не можна змінити статус завершеного запису", "danger")
        return redirect(url_for("appointments.view", id=id))

    # Якщо змінюємо статус на "completed", потрібно ввести тип оплати
    if new_status == "completed":
        form = AppointmentStatusPaymentForm()

        print("DEBUG CHANGE_STATUS: Attempting to change status to completed")
        print(f"DEBUG CHANGE_STATUS: Request method: {request.method}")

        # GET запит - показуємо форму для вибору методу оплати
        if request.method == "GET":
            return render_template(
                "appointments/complete_form.html", form=form, appointment=appointment
            )

        # POST запит - обробляємо форму
        if not form.validate_on_submit():
            # Якщо форма невалідна, повертаємо помилку
            print(f"DEBUG CHANGE_STATUS: Form validation failed. Errors: {form.errors}")
            for field, errors in form.errors.items():
                for error in errors:
                    flash(error, "danger")
            return render_template(
                "appointments/complete_form.html", form=form, appointment=appointment
            )

        print("DEBUG CHANGE_STATUS: Form validated successfully")

        # Оновлення даних про оплату
        # Конвертуємо рядкове значення форми в об'єкт PaymentMethod enum
        payment_method_value = form.payment_method.data

        print(
            f"DEBUG CHANGE_STATUS: Payment method from form: {payment_method_value}, type: {type(payment_method_value)}"
        )

        # Додаємо перевірку на випадок, якщо payment_method_value є списком
        if isinstance(payment_method_value, list):
            if payment_method_value:  # перевіряємо, що список не порожній
                payment_method_value = payment_method_value[0]  # беремо перший елемент
                print(
                    f"DEBUG CHANGE_STATUS: Payment method is a list, taking first element: {payment_method_value}"
                )
            else:
                flash(
                    "Не вдалося отримати метод оплати. Використовуємо значення за замовчуванням.",
                    "warning",
                )
                payment_method_value = next(iter(PaymentMethod)).value
                print(
                    f"DEBUG CHANGE_STATUS: Payment method list is empty, using default: {payment_method_value}"
                )

        try:
            payment_method_enum = next(
                pm for pm in PaymentMethod if pm.value == payment_method_value
            )
            appointment.payment_method = payment_method_enum
            print(f"DEBUG CHANGE_STATUS: Set payment method to: {payment_method_enum}")

            # Виправлення логіки оплати
            # Встановлюємо amount_paid на основі методу оплати
            from decimal import Decimal

            if payment_method_enum == PaymentMethod.DEBT:
                # Якщо метод оплати "Борг", встановлюємо amount_paid = 0
                appointment.amount_paid = Decimal("0.00")
                print(
                    "DEBUG CHANGE_STATUS: Set amount_paid to 0.00 (DEBT payment method)"
                )
            else:
                # Для всіх інших методів оплати, встановлюємо amount_paid = повна вартість з урахуванням знижки
                appointment.amount_paid = appointment.get_discounted_price()
                print(
                    f"DEBUG CHANGE_STATUS: Set amount_paid to {appointment.amount_paid} (full discounted price)"
                )

        except StopIteration:
            # Якщо значення не знайдено в enum, використовуємо перший доступний метод
            flash(
                f"Метод оплати '{payment_method_value}' не знайдено. Використовуємо значення за замовчуванням.",
                "warning",
            )
            appointment.payment_method = next(iter(PaymentMethod))
            print(
                f"DEBUG CHANGE_STATUS: Payment method not found, using default: {appointment.payment_method}"
            )

        # Встановлення payment_status на основі суми послуг та сплаченої суми
        appointment.update_payment_status()
        print(
            f"DEBUG CHANGE_STATUS: Updated payment status to: {appointment.payment_status}"
        )

    # Для статусу 'cancelled' очищаємо payment_method
    if new_status == "cancelled":
        appointment.payment_method = None
        appointment.payment_status = "not_applicable"
        print("DEBUG CHANGE_STATUS: Status set to cancelled, cleared payment method")

    # Якщо змінюємо статус з 'completed' на 'scheduled', очищаємо payment_method
    if previous_status == "completed" and new_status == "scheduled":
        appointment.payment_method = None
        appointment.payment_status = "paid"
        print(
            "DEBUG CHANGE_STATUS: Changed from completed to scheduled, cleared payment method"
        )

    # Оновлення статусу
    appointment.status = new_status
    print(f"DEBUG CHANGE_STATUS: Set appointment status to: {appointment.status}")

    db.session.commit()
    print("DEBUG CHANGE_STATUS: Committed changes to database")

    # Double-check that the change was saved
    refreshed_appointment = db.session.get(Appointment, id)
    print(
        f"DEBUG CHANGE_STATUS: After commit, appointment status is: {refreshed_appointment.status}"
    )

    flash(f"Статус запису змінено на '{new_status}'", "success")
    return redirect(url_for("appointments.view", id=id))


# Додавання послуги до запису
@bp.route("/<int:id>/add_service", methods=["GET", "POST"])
@login_required
def add_service(id):
    # Use eager loading to avoid detached objects
    appointment = (
        db.session.query(Appointment)
        .options(
            db.joinedload(Appointment.master),
            db.joinedload(Appointment.client),
            db.joinedload(Appointment.services).joinedload(AppointmentService.service),
        )
        .get(id)
    )

    if not appointment:
        flash("Запис не знайдено", "danger")
        return redirect(url_for("appointments.index"))

    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу", "danger")
        return redirect(url_for("appointments.index"))

    form = ServiceForm()
    form.service_id.choices = [
        (s.id, f"{s.name} ({s.duration} хв.)")
        for s in Service.query.order_by(Service.name).all()
    ]

    if form.validate_on_submit():
        service = db.session.get(Service, form.service_id.data)

        appointment_service = AppointmentService(
            appointment_id=appointment.id,
            service_id=form.service_id.data,
            price=form.price.data,
            notes=form.notes.data,
        )
        db.session.add(appointment_service)
        db.session.commit()

        flash(f'Послугу успішно додано: "{service.name}"', "success")
        return redirect(url_for("appointments.view", id=appointment.id))

    return render_template(
        "appointments/add_service.html",
        title=f"Додати послугу до запису #{id}",
        form=form,
        appointment=appointment,
    )


# Видалення послуги з запису
@bp.route("/<int:appointment_id>/remove_service/<int:service_id>", methods=["POST"])
@login_required
def remove_service(appointment_id, service_id):
    # Use eager loading
    appointment = (
        db.session.query(Appointment)
        .options(db.joinedload(Appointment.master), db.joinedload(Appointment.services))
        .get(appointment_id)
    )

    if not appointment:
        flash("Запис не знайдено", "danger")
        return redirect(url_for("appointments.index"))

    appointment_service = (
        db.session.query(AppointmentService)
        .options(db.joinedload(AppointmentService.service))
        .get(service_id)
    )

    if not appointment_service:
        flash("Послугу не знайдено", "danger")
        return redirect(url_for("appointments.view", id=appointment_id))

    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу", "danger")
        return redirect(url_for("appointments.index"))

    if appointment_service.appointment_id != appointment_id:
        flash("Неправильний запит!", "danger")
        return redirect(url_for("appointments.view", id=appointment_id))

    service_name = appointment_service.service.name
    db.session.delete(appointment_service)
    db.session.commit()

    # Refresh the appointment to keep it attached to the session
    db.session.refresh(appointment)

    flash(f'Послугу "{service_name}" видалено!', "success")
    return redirect(url_for("appointments.view", id=appointment_id))


# Редагування ціни послуги
@bp.route("/<int:appointment_id>/edit_service/<int:service_id>", methods=["POST"])
@login_required
def edit_service_price(appointment_id, service_id):
    # Use eager loading for appointment and services
    appointment = (
        db.session.query(Appointment)
        .options(
            db.joinedload(Appointment.master),
            db.joinedload(Appointment.services).joinedload(AppointmentService.service),
        )
        .get(appointment_id)
    )

    if not appointment:
        flash("Запис не знайдено", "danger")
        return redirect(url_for("appointments.index"))

    appointment_service = (
        db.session.query(AppointmentService)
        .options(db.joinedload(AppointmentService.service))
        .get(service_id)
    )

    if not appointment_service:
        flash("Послугу не знайдено", "danger")
        return redirect(url_for("appointments.view", id=appointment_id))

    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу", "danger")
        return redirect(url_for("appointments.index"))

    # Check appointment status - allow only for 'scheduled' appointments
    if appointment.status != "scheduled":
        flash("Редагування ціни можливе тільки для запланованих записів", "danger")
        return redirect(url_for("appointments.view", id=appointment_id))

    if appointment_service.appointment_id != appointment_id:
        flash("Неправильний запит!", "danger")
        return redirect(url_for("appointments.view", id=appointment_id))

    new_price = request.form.get("price", type=float)
    if new_price is None or new_price < 0:
        flash("Невірна ціна!", "danger")
        return redirect(url_for("appointments.view", id=appointment_id))

    # Store the old price for verification
    old_price = appointment_service.price
    appointment_service.price = new_price

    # Update payment status based on the new price
    appointment.update_payment_status()

    # Commit changes to the database
    db.session.commit()

    # Refresh the appointment to keep it attached to the session
    db.session.refresh(appointment)

    # Log price change (for debugging or audit)
    print(
        f"Price changed for service {appointment_service.service.name} "
        f"from {old_price} to {new_price}"
    )

    flash("Ціну послуги оновлено!", "success")
    return redirect(url_for("appointments.view", id=appointment_id))


# API для отримання інформації про записи в форматі JSON
@bp.route("/api/dates/<date_str>")
@login_required
def api_appointments_by_date(date_str):
    try:
        filter_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    query = Appointment.query.options(
        db.joinedload(Appointment.master),
        db.joinedload(Appointment.client),
        db.joinedload(Appointment.services),
    ).filter(Appointment.date == filter_date)

    if not current_user.is_admin:
        query = query.filter(Appointment.master_id == current_user.id)

    appointments = query.order_by(Appointment.start_time).all()

    result = []
    for appointment in appointments:
        total = sum(service.price for service in appointment.services)
        appointment_data = {
            "id": appointment.id,
            "client_name": appointment.client.name,
            "client_phone": appointment.client.phone,
            "master_name": appointment.master.full_name,
            "start_time": appointment.start_time.strftime("%H:%M"),
            "end_time": appointment.end_time.strftime("%H:%M"),
            "status": appointment.status,
            "total_price": total,
            "services_count": len(appointment.services),
        }
        result.append(appointment_data)

    return jsonify(result)


# Отримати щоденні підсумки для майстра
@bp.route("/daily-summary", methods=["GET"])
@login_required
def daily_summary():
    # Отримання дати для фільтрації
    filter_date = request.args.get("date")
    if filter_date:
        try:
            filter_date = datetime.strptime(filter_date, "%Y-%m-%d").date()
        except ValueError:
            filter_date = datetime.now().date()
    else:
        filter_date = datetime.now().date()

    # Перетворення строкової дати в об'єкт date
    try:
        selected_date = datetime.strptime(filter_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        selected_date = datetime.now().date()

    # Отримання всіх записів на вибрану дату
    appointments = Appointment.query.filter_by(date=selected_date).all()

    # Отримання списку всіх майстрів для звіту
    masters = User.query.filter_by(is_active_master=True).all()
    master_stats = {}

    # Ідентифікатори всіх майстрів, включаючи тих, хто не має записів
    master_ids = (
        User.query.filter_by(is_active_master=True).with_entities(User.id).all()
    )
    master_ids = [m.id for m in master_ids]

    for master_id in master_ids:
        master = db.session.get(User, master_id)
        master_sum = 0
        master_appointments = Appointment.query.filter(
            Appointment.date == selected_date,
            Appointment.master_id == master_id,
            Appointment.status == "completed",
        ).all()

        appointment_count = len(master_appointments)
        for appointment in master_appointments:
            # Використовуємо amount_paid, якщо воно доступне, інакше обчислюємо з послуг
            if (
                appointment.amount_paid is not None
                and float(appointment.amount_paid) > 0
            ):
                master_sum += float(appointment.amount_paid)
            else:
                for service in appointment.services:
                    master_sum += service.price

        master_stats[master_id] = {
            "id": master_id,
            "name": master.full_name,
            "appointments_count": appointment_count,
            "total_sum": master_sum,
        }

    return render_template(
        "appointments/daily_summary.html",
        title="Щоденний підсумок",
        filter_date=filter_date,
        filter_master=None,
        appointments=appointments,
        total_sum=sum(
            (
                float(appointment.amount_paid)
                if appointment.amount_paid is not None
                and float(appointment.amount_paid) > 0
                else sum(service.price for service in appointment.services)
            )
            for appointment in appointments
            if appointment.status == "completed"
        ),
        masters=masters,
        master_stats=master_stats.values(),
    )


# Видалення запису
@bp.route("/<int:id>/delete", methods=["POST"])
@login_required
def delete(id):
    appointment = Appointment.query.get_or_404(id)

    # Перевірка, чи має право користувач видаляти цей запис
    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("Ви можете видаляти тільки свої записи", "danger")
        return redirect(url_for("appointments.index"))

    # Перевірка, чи завершений запис (майстри не можуть видаляти завершені записи)
    if not current_user.is_admin and appointment.status == "completed":
        flash("Ви не можете видаляти завершені записи", "danger")
        return redirect(url_for("appointments.view", id=appointment.id))

    # Видалення запису
    try:
        # Видаляємо всі пов'язані послуги
        for service in appointment.services:
            db.session.delete(service)

        # Видаляємо запис
        db.session.delete(appointment)
        db.session.commit()

        flash("Запис успішно видалено!", "success")

        # Перевіряємо, чи був запит з розкладу
        from_schedule = request.args.get("from_schedule")
        if from_schedule:
            return redirect(
                url_for("main.schedule", date=appointment.date.strftime("%Y-%m-%d"))
            )
        else:
            return redirect(url_for("appointments.index"))
    except Exception as e:
        db.session.rollback()
        flash(f"Помилка при видаленні запису: {str(e)}", "danger")
        return redirect(url_for("appointments.view", id=appointment.id))
