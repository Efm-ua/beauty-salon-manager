from datetime import date, datetime, time, timedelta

from flask import (Blueprint, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import (DateField, FieldList, FloatField, FormField, SelectField,
                     SelectMultipleField, StringField, SubmitField,
                     TextAreaField, TimeField)
from wtforms.validators import DataRequired, Optional

from app.models import (Appointment, AppointmentService, Client, Service, User,
                        db)

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

        # Встановлення часу
        time_str = request.args.get("time")
        if time_str:
            try:
                start_time = datetime.strptime(time_str, "%H:%M").time()
                form.start_time.data = start_time
            except ValueError:
                pass

    if form.validate_on_submit():
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
        )
        db.session.add(appointment)
        db.session.flush()  # отримуємо ID запису

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

        db.session.commit()

        flash("Запис успішно створено!", "success")

        # Перевіряємо, чи був запит з розкладу майстрів
        from_schedule = request.args.get("from_schedule")
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
    appointment = Appointment.query.get_or_404(id)

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
    )


# Редагування запису
@bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id):
    appointment = Appointment.query.get_or_404(id)

    # Перевірка доступу: тільки адміністратор або майстер цього запису можуть редагувати
    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу до редагування цього запису", "danger")
        return redirect(url_for("appointments.index"))

    form = AppointmentForm(obj=appointment)

    # Заповнення варіантів вибору
    form.client_id.choices = [
        (c.id, f"{c.name} ({c.phone})")
        for c in Client.query.order_by(Client.name).all()
    ]
    form.services.choices = [
        (s.id, f"{s.name} ({s.duration} хв.)")
        for s in Service.query.order_by(Service.name).all()
    ]
    if current_user.is_admin:
        form.master_id.choices = [
            (u.id, u.full_name) for u in User.query.order_by(User.full_name).all()
        ]
    else:
        form.master_id.choices = [(current_user.id, current_user.full_name)]
        form.master_id.data = current_user.id

    # При відображенні форми, встановити поточні послуги
    if request.method == "GET":
        form.services.data = [service.service_id for service in appointment.services]

    if form.validate_on_submit():
        # Початок редагування
        if not current_user.is_admin and form.master_id.data != current_user.id:
            flash("Ви не можете змінити майстра запису", "danger")
            return redirect(url_for("appointments.edit", id=id))

        # Розрахунок end_time на основі start_time та тривалості першої послуги
        if appointment.services:
            # Використовуємо тривалість першої пов'язаної послуги
            service_duration = appointment.services[0].service.duration
            # Розраховуємо end_time
            start_datetime = datetime.combine(form.date.data, form.start_time.data)
            end_datetime = start_datetime + timedelta(minutes=service_duration)
            end_time = end_datetime.time()
        else:
            # На випадок, якщо запис немає послуг, встановлюємо такий же час як і початок
            end_time = form.start_time.data

        # Оновлення даних запису
        appointment.client_id = form.client_id.data
        appointment.master_id = form.master_id.data
        appointment.date = form.date.data
        appointment.start_time = form.start_time.data
        appointment.end_time = end_time
        appointment.notes = form.notes.data
        # Збереження поточних значень для payment_status, amount_paid та payment_method

        db.session.commit()
        flash("Запис успішно оновлено!", "success")

        # Перевіряємо, чи був запит з розкладу майстрів
        from_schedule = request.args.get("from_schedule")
        if from_schedule:
            return redirect(
                url_for("main.schedule", date=appointment.date.strftime("%Y-%m-%d"))
            )
        else:
            return redirect(url_for("appointments.view", id=id))

    return render_template(
        "appointments/edit.html",
        title=f"Редагування запису #{id}",
        form=form,
        appointment=appointment,
    )


# Зміна статусу запису
@bp.route("/<int:id>/status/<status>", methods=["POST"])
@login_required
def change_status(id, status):
    appointment = Appointment.query.get_or_404(id)

    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу до зміни статусу цього запису", "danger")
        return redirect(url_for("appointments.index"))

    if status not in ["scheduled", "completed", "cancelled"]:
        flash("Невірний статус!", "danger")
        return redirect(url_for("appointments.view", id=id))

    appointment.status = status
    db.session.commit()

    flash(f'Статус запису змінено на "{status}"', "success")
    return redirect(url_for("appointments.view", id=id))


# Додавання послуги до запису
@bp.route("/<int:id>/add_service", methods=["GET", "POST"])
@login_required
def add_service(id):
    appointment = Appointment.query.get_or_404(id)

    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу до редагування цього запису", "danger")
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

        flash(f'Послугу "{service.name}" додано!', "success")
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
    appointment_service = AppointmentService.query.get_or_404(service_id)
    appointment = Appointment.query.get_or_404(appointment_id)

    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу до редагування цього запису", "danger")
        return redirect(url_for("appointments.index"))

    if appointment_service.appointment_id != appointment_id:
        flash("Неправильний запит!", "danger")
        return redirect(url_for("appointments.view", id=appointment_id))

    service_name = appointment_service.service.name
    db.session.delete(appointment_service)
    db.session.commit()

    flash(f'Послугу "{service_name}" видалено!', "success")
    return redirect(url_for("appointments.view", id=appointment_id))


# Редагування ціни послуги
@bp.route("/<int:appointment_id>/edit_service/<int:service_id>", methods=["POST"])
@login_required
def edit_service_price(appointment_id, service_id):
    appointment_service = AppointmentService.query.get_or_404(service_id)
    appointment = Appointment.query.get_or_404(appointment_id)

    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу до редагування цього запису", "danger")
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

    query = Appointment.query.filter(Appointment.date == filter_date)

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
