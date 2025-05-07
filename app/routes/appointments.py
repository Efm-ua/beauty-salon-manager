from datetime import date, datetime, time, timedelta
from decimal import Decimal

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    DecimalField,
    FloatField,
    SelectField,
    SelectMultipleField,
    SubmitField,
    TextAreaField,
    TimeField,
)
from wtforms.validators import DataRequired, NumberRange, Optional

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


# Форма для додавання послуги до запису (залишається без змін)
class ServiceForm(FlaskForm):
    service_id = SelectField("Послуга", coerce=int, validators=[DataRequired()])
    price = FloatField("Ціна", validators=[DataRequired()])
    notes = TextAreaField("Примітки", validators=[Optional()])
    submit = SubmitField("Додати послугу")


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

    # Додавання фільтрації за майстром
    if filter_master:
        query = query.filter(Appointment.master_id == filter_master)
    elif not current_user.is_admin:
        query = query.filter(Appointment.master_id == current_user.id)

    # Отримання записів
    appointments = query.order_by(Appointment.start_time).all()

    # Отримання списку майстрів для фільтра
    masters = User.query.all()

    return render_template(
        "appointments/index.html",
        title="Записи",
        appointments=appointments,
        filter_date=filter_date,
        filter_master=filter_master,
        masters=masters,
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
    form.master_id.choices = [
        (u.id, u.full_name) for u in User.query.order_by(User.full_name).all()
    ]
    form.services.choices = [
        (s.id, f"{s.name} ({s.duration} хв.)")
        for s in Service.query.order_by(Service.name).all()
    ]

    # Встановлення значень за замовчуванням з параметрів запиту
    if request.method == "GET":
        # Встановлення майстра
        master_id = request.args.get("master_id")
        if master_id and master_id.isdigit():
            form.master_id.data = int(master_id)
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

        # Перевірка, чи має право користувач створити запис для вибраного майстра
        if not current_user.is_admin and form.master_id.data != current_user.id:
            flash("Ви можете створювати записи тільки для себе", "danger")
            return redirect(url_for("appointments.create"))

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
            master_id=form.master_id.data,
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
                        price=float(service.duration),
                        notes="",
                    )
                    db.session.add(appointment_service)

        # Логування перед commit
        print(
            f"DEBUG ROUTE CREATE: Before commit - appointment ID={appointment.id}, "
            f"is_transient={inspect(appointment).transient}, "
            f"is_pending={inspect(appointment).pending}, "
            f"is_detached={inspect(appointment).detached}"
        )

        if hasattr(appointment, "master") and appointment.master:
            print(
                f"DEBUG ROUTE CREATE: Before commit - master ID={appointment.master.id}, "
                f"username={appointment.master.username}, "
                f"is_detached={inspect(appointment.master).detached}"
            )

        appointment.update_payment_status()  # Оновлюємо payment_status
        db.session.commit()

        # Логування після commit
        print(
            f"DEBUG ROUTE CREATE: After commit - appointment ID={appointment.id}, "
            f"is_transient={inspect(appointment).transient}, "
            f"is_pending={inspect(appointment).pending}, "
            f"is_detached={inspect(appointment).detached}"
        )

        if hasattr(appointment, "master") and appointment.master:
            print(
                f"DEBUG ROUTE CREATE: After commit - master ID={appointment.master.id}, "
                f"username={appointment.master.username}, "
                f"is_detached={inspect(appointment.master).detached}"
            )

        # Ensure data is fresh for debugging purposes
        refreshed_appointment = db.session.get(Appointment, appointment.id)
        print(
            f"Refreshed appointment services after commit: {refreshed_appointment.services}"
        )

        flash("Запис успішно створено!", "success")

        # Перевіряємо, чи був запит з розкладу майстрів
        from_schedule = request.args.get("from_schedule")

        # Логування перед redirect
        print(
            f"DEBUG ROUTE CREATE: Before redirect - appointment ID={appointment.id}, "
            f"is_transient={inspect(appointment).transient}, "
            f"is_pending={inspect(appointment).pending}, "
            f"is_detached={inspect(appointment).detached}"
        )

        if hasattr(appointment, "master") and appointment.master:
            print(
                f"DEBUG ROUTE CREATE: Before redirect - master ID={appointment.master.id}, "
                f"username={appointment.master.username}, "
                f"is_detached={inspect(appointment.master).detached}"
            )

        if from_schedule:
            return redirect(
                url_for("main.schedule", date=appointment.date.strftime("%Y-%m-%d"))
            )
        else:
            return redirect(url_for("appointments.view", id=appointment.id))

    return render_template(
        "appointments/create.html",
        title="Новий запис",
        form=form,
        from_schedule=request.args.get("from_schedule"),
    )


# Перегляд запису
@bp.route("/<int:id>")
@login_required
def view(id):
    # Use eager loading for related objects
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

    # Перевірка доступу: тільки адміністратор або майстер цього запису можуть переглядати
    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу до цього запису", "danger")
        return redirect(url_for("appointments.index"))

    # Отримання послуг для цього запису
    services = appointment.services

    # Розрахунок загальної суми
    total = sum(service.price for service in services)

    return render_template(
        "appointments/view.html",
        title=f"Запис #{id}",
        appointment=appointment,
        services=services,
        total=total,
        payment_methods=PaymentMethod,  # Pass all payment methods to the template
    )


# Редагування запису
@bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id):
    # Use eager loading for related objects
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
        flash("У вас немає доступу до редагування цього запису", "danger")
        return redirect(url_for("appointments.index"))

    # Отримуємо поточні послуги для передачі у форму (для GET)
    current_service_ids = [s.service_id for s in appointment.services]

    # Check if we came from the schedule view
    from_schedule = request.args.get("from_schedule", type=int)
    print(
        f"DEBUG EDIT ROUTE: from_schedule = {from_schedule}, type = {type(from_schedule)}"
    )

    # Логування всіх request.args для більш точної діагностики
    print(f"DEBUG EDIT ROUTE: All request.args = {request.args}")
    print(f"DEBUG EDIT ROUTE: request.url = {request.url}")
    print(f"DEBUG EDIT ROUTE: request.query_string = {request.query_string}")
    print(f"DEBUG EDIT ROUTE: request.method = {request.method}")

    # Create the form
    form = AppointmentForm()

    # Populate choices for dropdowns - do this BEFORE form processing to ensure SelectField validation passes
    form.client_id.choices = [
        (c.id, f"{c.name} ({c.phone})")
        for c in Client.query.order_by(Client.name).all()
    ]
    form.master_id.choices = [
        (m.id, m.full_name) for m in User.query.order_by(User.full_name).all()
    ]
    form.services.choices = [
        (s.id, f"{s.name} ({s.duration} хв.)")
        for s in Service.query.order_by(Service.name).all()
    ]

    if request.method == "POST":
        # Process the form with data from the request
        print(f"DEBUG EDIT ROUTE: POST request received, form data: {request.form}")

        form.process(request.form)

        # Repopulate choices after form.process since it clears them
        form.client_id.choices = [
            (c.id, f"{c.name} ({c.phone})")
            for c in Client.query.order_by(Client.name).all()
        ]
        form.master_id.choices = [
            (m.id, m.full_name) for m in User.query.order_by(User.full_name).all()
        ]
        form.services.choices = [
            (s.id, f"{s.name} ({s.duration} хв.)")
            for s in Service.query.order_by(Service.name).all()
        ]

        # Validate form
        if form.validate_on_submit():
            try:
                # Store the refreshed list of services to add after commit
                original_services = list(appointment.services)

                # Update basic information
                appointment.client_id = form.client_id.data
                appointment.master_id = form.master_id.data
                appointment.date = form.date.data
                appointment.start_time = form.start_time.data

                # Calculate end_time based on services duration
                total_duration = 0
                selected_services = []
                for service_id in form.services.data:
                    service = db.session.get(Service, service_id)
                    if service:
                        total_duration += service.duration
                        selected_services.append(service)

                # Add 15 minutes for each service (transition time)
                if len(selected_services) > 0:
                    total_duration += 15 * (len(selected_services) - 1)

                # Calculate new end time
                start_dt = datetime.combine(form.date.data, form.start_time.data)
                end_dt = start_dt + timedelta(minutes=total_duration)
                appointment.end_time = end_dt.time()

                # Update payment information
                appointment.discount_percentage = (
                    form.discount_percentage.data or Decimal("0.0")
                )
                print(
                    f"DEBUG EDIT ROUTE: Before update - amount_paid={appointment.amount_paid}, payment_method={appointment.payment_method}, payment_status={appointment.payment_status}"
                )

                if form.amount_paid.data is not None:
                    appointment.amount_paid = form.amount_paid.data
                    print(
                        f"DEBUG EDIT ROUTE: Setting amount_paid to {form.amount_paid.data}"
                    )
                else:
                    appointment.amount_paid = Decimal("0.00")
                    print(
                        "DEBUG EDIT ROUTE: Setting amount_paid to 0.00 (None in form)"
                    )

                # Handle payment method
                payment_method_value = form.payment_method.data
                print(
                    f"DEBUG EDIT ROUTE: Payment method from form: {payment_method_value}"
                )

                if payment_method_value:
                    # Find the PaymentMethod enum by its value (display string)
                    for method in PaymentMethod:
                        if method.value == payment_method_value:
                            print(
                                f"DEBUG EDIT ROUTE: Found matching payment method: {method}"
                            )
                            appointment.payment_method = method
                            break
                    else:
                        # If we didn't find a match, don't change
                        print(
                            f"DEBUG EDIT ROUTE: No matching payment method found for: {payment_method_value}"
                        )
                        pass
                else:
                    # If form has empty payment_method, set to None
                    print("DEBUG EDIT ROUTE: Clearing payment method (empty in form)")
                    appointment.payment_method = None

                # Update notes
                appointment.notes = form.notes.data

                # First commit appointment changes
                db.session.commit()

                # Clear existing services and add new ones
                # This avoids the InvalidRequestError due to session state
                for aps in list(appointment.services):
                    db.session.delete(aps)
                db.session.commit()

                # Clear the services in Python
                appointment.services.clear()

                # Now add the newly selected services
                for service_id in form.services.data:
                    service = db.session.get(Service, service_id)
                    if service:
                        # Використовуємо час послуги, помножений на 10 як базову ціну,
                        # якщо атрибута price немає
                        service_price = getattr(service, "price", None)
                        if service_price is None:
                            service_price = (
                                service.duration * 10
                            )  # Використовуємо тривалість у хвилинах як базу для ціни

                        print(
                            f"DEBUG EDIT ROUTE: Service id={service.id}, name={service.name}, duration={service.duration}, price={service_price}"
                        )

                        app_service = AppointmentService(
                            appointment_id=appointment.id,
                            service_id=service_id,
                            price=float(service_price),
                        )
                        db.session.add(app_service)
                        appointment.services.append(app_service)

                # Final commit
                db.session.commit()
                print(
                    f"Refreshed appointment services after commit: {appointment.services}"
                )

                # Update payment status - force recalculation based on current data
                print(
                    f"DEBUG EDIT ROUTE: Before update_payment_status - status={appointment.status}, payment_status={appointment.payment_status}, payment_method={appointment.payment_method}, amount_paid={appointment.amount_paid}"
                )
                print(
                    f"DEBUG EDIT ROUTE: Services: {[s.price for s in appointment.services]}, total_price={appointment.get_total_price()}, discounted_price={appointment.get_discounted_price()}"
                )

                appointment.update_payment_status()
                print(
                    f"DEBUG EDIT ROUTE: After update_payment_status - status={appointment.status}, payment_status={appointment.payment_status}, payment_method={appointment.payment_method}, amount_paid={appointment.amount_paid}"
                )

                db.session.commit()

                flash("Запис успішно оновлено!", "success")

                # If we came from the schedule view, redirect back there with the appointment date
                # Проверяем from_schedule в URL параметрах и в данных формы
                from_schedule_value = request.args.get("from_schedule", type=int)
                # Також перевіряємо, чи є from_schedule в даних форми
                form_from_schedule = request.form.get("from_schedule")

                print(
                    f"DEBUG EDIT ROUTE: Checking from_schedule from URL: {from_schedule_value}"
                )
                print(
                    f"DEBUG EDIT ROUTE: Checking from_schedule from FORM: {form_from_schedule}, type = {type(form_from_schedule)}"
                )
                print(f"DEBUG EDIT ROUTE: POST request.form = {request.form}")
                print(f"DEBUG EDIT ROUTE: POST request.args = {request.args}")
                print(f"DEBUG EDIT ROUTE: POST request.url = {request.url}")
                print(
                    f"DEBUG EDIT ROUTE: POST request.query_string = {request.query_string}"
                )

                # Перетворюємо form_from_schedule у ціле число, якщо можливо
                try:
                    if form_from_schedule:
                        form_from_schedule = int(form_from_schedule)
                    else:
                        form_from_schedule = None
                except (ValueError, TypeError):
                    form_from_schedule = None

                print(
                    f"DEBUG EDIT ROUTE: Converted form_from_schedule = {form_from_schedule}, type = {type(form_from_schedule)}"
                )

                # Проблема в тому, що код після form.validate_on_submit() не виконується, тому заходимо в catch-блок
                # Додаємо прямий доступ до даних форми та формування URL для розкладу
                appointment_date = appointment.date.strftime("%Y-%m-%d")

                if from_schedule_value == 1 or form_from_schedule == 1:
                    redirect_url = url_for("main.schedule", date=appointment_date)
                    print(
                        f"DEBUG EDIT ROUTE: Redirecting to schedule with from_schedule={from_schedule_value or form_from_schedule}, redirect_url={redirect_url}"
                    )
                else:
                    redirect_url = url_for("appointments.view", id=appointment.id)
                    print(
                        f"DEBUG EDIT ROUTE: Redirecting to appointment view with from_schedule={from_schedule_value or form_from_schedule}, redirect_url={redirect_url}"
                    )

                return redirect(redirect_url)

            except Exception as e:
                db.session.rollback()
                print(f"DEBUG EDIT ROUTE: Error updating appointment: {str(e)}")
                print(f"DEBUG EDIT ROUTE: Exception trace: {e.__class__.__name__}")
                flash(f"Помилка при оновленні запису: {str(e)}", "danger")

                # If an error occurs, we still try to redirect to the schedule page if from_schedule is set
                from_schedule_value = request.args.get("from_schedule", type=int)
                form_from_schedule = request.form.get("from_schedule")

                try:
                    if form_from_schedule:
                        form_from_schedule = int(form_from_schedule)
                    else:
                        form_from_schedule = None
                except (ValueError, TypeError):
                    form_from_schedule = None

                if from_schedule_value == 1 or form_from_schedule == 1:
                    appointment_date = appointment.date.strftime("%Y-%m-%d")
                    return redirect(url_for("main.schedule", date=appointment_date))

                return redirect(url_for("appointments.edit", id=id))
    else:
        # For GET request, populate the form with existing data
        form = AppointmentForm(obj=appointment)
        form.services.data = current_service_ids

        # Pre-populate payment method if exists
        if appointment.payment_method:
            form.payment_method.data = appointment.payment_method.value

    return render_template(
        "appointments/edit.html",
        title="Редагувати запис",
        form=form,
        appointment=appointment,
        from_schedule=from_schedule,
    )


# Зміна статусу запису
@bp.route("/<int:id>/status/<new_status>", methods=["POST"])
@login_required
def change_status(id, new_status):
    from flask import current_app
    from sqlalchemy import inspect

    # Load appointment with eager loading for related objects
    appointment = (
        db.session.query(Appointment)
        .options(
            db.joinedload(Appointment.master),
            db.joinedload(Appointment.client),
            db.joinedload(Appointment.services).joinedload(AppointmentService.service),
        )
        .get(id)
    )

    # Додано логування на початку маршруту
    if appointment:
        print(
            f"DEBUG ROUTE CHANGE_STATUS: Initial appointment: ID={appointment.id}, status={appointment.status}, "
            f"payment_status={appointment.payment_status}, payment_method={appointment.payment_method}, "
            f"amount_paid={appointment.amount_paid}, "
            f"is_detached={inspect(appointment).detached}, "
            f"session_id={inspect(appointment).session_id}"
        )
        if appointment.master:
            print(
                f"DEBUG ROUTE: Initial appointment's master: ID={appointment.master.id}, "
                f"name={appointment.master.username}, "
                f"is_detached={inspect(appointment.master).detached}, "
                f"session_id={inspect(appointment.master).session_id}"
            )
        else:
            print("DEBUG ROUTE: Appointment has no master.")
    else:
        print(f"DEBUG ROUTE: Appointment with ID={id} not found.")

    if not appointment:
        flash("Запис не знайдено", "danger")
        return redirect(url_for("appointments.index"))

    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу до зміни статусу цього запису", "danger")
        return redirect(url_for("appointments.view", id=id))

    valid_statuses = ["scheduled", "completed", "cancelled"]
    if new_status not in valid_statuses:
        flash("Невірний статус", "danger")
        return redirect(url_for("appointments.view", id=id))

    # Special handling for the 'completed' status
    if new_status == "completed":
        payment_method_str = request.form.get("payment_method")

        # Special case: If amount_paid is 0, we can proceed without requiring payment_method
        if appointment.amount_paid is not None and appointment.amount_paid == Decimal(
            "0.00"
        ):
            # We can proceed without payment_method for unpaid appointments
            # If payment_method was provided in the form, use it; otherwise keep the current one
            if payment_method_str:
                # Check if the payment method value is valid (matches one of the enum values)
                valid_payment_method = False
                method_to_set = None
                for method in PaymentMethod:
                    if method.value == payment_method_str:
                        valid_payment_method = True
                        method_to_set = method
                        break

                if valid_payment_method:
                    appointment.payment_method = method_to_set
        # Normal case - require payment_method if not already set
        elif appointment.payment_method is None:
            if not payment_method_str:
                flash(
                    "Будь ласка, виберіть тип оплати для завершення запису.", "warning"
                )
                return redirect(url_for("appointments.view", id=id))

            # Check if the payment method value is valid (matches one of the enum values)
            valid_payment_method = False
            method_to_set = None
            for method in PaymentMethod:
                if method.value == payment_method_str:
                    valid_payment_method = True
                    method_to_set = method
                    break

            if not valid_payment_method:
                flash(f"Невірний тип оплати: {payment_method_str}", "warning")
                return redirect(url_for("appointments.view", id=id))

            # Set the payment method
            appointment.payment_method = method_to_set

    # Change from completed to another status (reset payment method)
    elif appointment.status == "completed" and new_status != "completed":
        # When changing from completed to another status, clear payment method
        print(
            "DEBUG ROUTE CHANGE_STATUS: Changing from completed to another status, clearing payment_method"
        )
        appointment.payment_method = None

    # For cancelled status, also reset payment method
    elif new_status == "cancelled":
        print(
            "DEBUG ROUTE CHANGE_STATUS: Setting status to cancelled, clearing payment_method"
        )
        appointment.payment_method = None

    # Update the status
    old_status = appointment.status
    print(
        f"DEBUG ROUTE CHANGE_STATUS: Changing status from {old_status} to {new_status}"
    )
    appointment.status = new_status

    # Update payment status
    print(
        f"DEBUG ROUTE CHANGE_STATUS: Before update_payment_status: status={appointment.status}, "
        f"payment_status={appointment.payment_status}, payment_method={appointment.payment_method}"
    )
    appointment.update_payment_status()
    print(
        f"DEBUG ROUTE CHANGE_STATUS: After update_payment_status: status={appointment.status}, "
        f"payment_status={appointment.payment_status}, payment_method={appointment.payment_method}"
    )

    # Додано логування перед commit
    print(
        f"DEBUG ROUTE: Before commit: appointment ID={appointment.id}, "
        f"status={appointment.status}, "
        f"is_detached={inspect(appointment).detached}, "
        f"session_id={inspect(appointment).session_id}"
    )
    if appointment.master:
        print(
            f"DEBUG ROUTE: Before commit: master ID={appointment.master.id}, "
            f"name={appointment.master.username}, "
            f"is_detached={inspect(appointment.master).detached}, "
            f"session_id={inspect(appointment.master).session_id}"
        )

    # Save changes
    try:
        db.session.commit()

        # Додано логування після commit
        print(
            f"DEBUG ROUTE CHANGE_STATUS: After commit: appointment ID={appointment.id}, "
            f"status={appointment.status}, payment_status={appointment.payment_status}, "
            f"payment_method={appointment.payment_method}, amount_paid={appointment.amount_paid}, "
            f"is_detached={inspect(appointment).detached}, "
            f"session_id={inspect(appointment).session_id}"
        )
        if appointment.master:
            print(
                f"DEBUG ROUTE: After commit: master ID={appointment.master.id}, "
                f"name={appointment.master.username}, "
                f"is_detached={inspect(appointment.master).detached}, "
                f"session_id={inspect(appointment.master).session_id}"
            )

        # Refresh the appointment to ensure all relationships are loaded
        db.session.refresh(appointment)

        # Додано логування після refresh
        print(
            f"DEBUG ROUTE CHANGE_STATUS: After refresh: appointment ID={appointment.id}, "
            f"status={appointment.status}, payment_status={appointment.payment_status}, "
            f"payment_method={appointment.payment_method}, amount_paid={appointment.amount_paid}, "
            f"is_detached={inspect(appointment).detached}, "
            f"session_id={inspect(appointment).session_id}"
        )
        if appointment.master:
            print(
                f"DEBUG ROUTE: After refresh: master ID={appointment.master.id}, "
                f"name={appointment.master.username}, "
                f"is_detached={inspect(appointment.master).detached}, "
                f"session_id={inspect(appointment.master).session_id}"
            )

        flash(f"Статус запису змінено на '{new_status}'", "success")
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG ROUTE: Error during commit: {str(e)}")
        flash(f"Помилка при зміні статусу: {str(e)}", "danger")

    # Додано логування перед redirect
    print(
        f"DEBUG ROUTE: Before redirect: appointment ID={appointment.id}, "
        f"status={appointment.status}, "
        f"is_detached={inspect(appointment).detached}, "
        f"session_id={inspect(appointment).session_id}"
    )
    if appointment.master:
        print(
            f"DEBUG ROUTE: Before redirect: master ID={appointment.master.id}, "
            f"name={appointment.master.username}, "
            f"is_detached={inspect(appointment.master).detached}, "
            f"session_id={inspect(appointment.master).session_id}"
        )

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

    new_price = request.form.get("price", type=float)
    if new_price is None or new_price < 0:
        flash("Невірна ціна!", "danger")
        return redirect(url_for("appointments.view", id=appointment_id))

    appointment_service.price = new_price
    db.session.commit()

    # Refresh the appointment to keep it attached to the session
    db.session.refresh(appointment)

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
    filter_date = request.args.get("date")
    if filter_date:
        try:
            filter_date = datetime.strptime(filter_date, "%Y-%m-%d").date()
        except ValueError:
            filter_date = datetime.now().date()
    else:
        filter_date = datetime.now().date()

    filter_master = request.args.get("master_id")
    if filter_master and filter_master.isdigit():
        filter_master = int(filter_master)
    elif not current_user.is_admin:
        filter_master = current_user.id
    else:
        filter_master = None

    query = Appointment.query.filter(
        Appointment.date == filter_date, Appointment.status == "completed"
    )
    if filter_master:
        query = query.filter(Appointment.master_id == filter_master)

    appointments = query.order_by(Appointment.start_time).all()

    total_sum = 0
    for appointment in appointments:
        for service in appointment.services:
            total_sum += service.price

    masters = User.query.all()

    master_stats = []
    if current_user.is_admin and not filter_master:
        master_ids = User.query.with_entities(User.id).all()
        for master_id in master_ids:
            master_id = master_id[0]
            master = db.session.get(User, master_id)

            master_sum = 0
            master_appointments = Appointment.query.filter(
                Appointment.date == filter_date,
                Appointment.master_id == master_id,
                Appointment.status == "completed",
            ).all()

            appointment_count = len(master_appointments)
            for appointment in master_appointments:
                for service in appointment.services:
                    master_sum += service.price

            master_stats.append(
                {
                    "id": master_id,
                    "name": master.full_name,
                    "appointments_count": appointment_count,
                    "total_sum": master_sum,
                }
            )

    return render_template(
        "appointments/daily_summary.html",
        title="Щоденний підсумок",
        filter_date=filter_date,
        filter_master=filter_master,
        appointments=appointments,
        total_sum=total_sum,
        masters=masters,
        master_stats=(
            master_stats if current_user.is_admin and not filter_master else None
        ),
    )
