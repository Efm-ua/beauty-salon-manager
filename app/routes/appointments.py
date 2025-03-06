from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    DateField,
    TimeField,
    SelectField,
    TextAreaField,
    SubmitField,
    FloatField,
    FieldList,
    FormField,
)
from wtforms.validators import DataRequired, Optional
from datetime import datetime, time, date

from app.models import db, Appointment, Client, User, Service, AppointmentService

# Створення Blueprint
bp = Blueprint("appointments", __name__, url_prefix="/appointments")


# Форма для запису
class AppointmentForm(FlaskForm):
    client_id = SelectField("Клієнт", coerce=int, validators=[DataRequired()])
    master_id = SelectField("Майстер", coerce=int, validators=[DataRequired()])
    date = DateField("Дата", validators=[DataRequired()], default=date.today)
    start_time = TimeField(
        "Час початку", validators=[DataRequired()], default=time(9, 0)
    )
    end_time = TimeField(
        "Час закінчення", validators=[DataRequired()], default=time(10, 0)
    )
    notes = TextAreaField("Примітки", validators=[Optional()])
    submit = SubmitField("Зберегти")


# Форма для додавання послуги до запису
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


# Створення нового запису
@bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    form = AppointmentForm()

    # Заповнення варіантів вибору
    form.client_id.choices = [
        (c.id, f"{c.name} ({c.phone})")
        for c in Client.query.order_by(Client.name).all()
    ]
    form.master_id.choices = [
        (u.id, u.full_name) for u in User.query.order_by(User.full_name).all()
    ]

    # Встановлення поточного користувача як майстра за замовчуванням
    if request.method == "GET":
        form.master_id.data = current_user.id

    if form.validate_on_submit():
        appointment = Appointment(
            client_id=form.client_id.data,
            master_id=form.master_id.data,
            date=form.date.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            notes=form.notes.data,
            status="scheduled",
        )
        db.session.add(appointment)
        db.session.commit()

        flash("Запис успішно створено!", "success")
        return redirect(url_for("appointments.view", id=appointment.id))

    return render_template("appointments/create.html", title="Новий запис", form=form)


# Перегляд запису
@bp.route("/<int:id>")
@login_required
def view(id):
    appointment = Appointment.query.get_or_404(id)

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
    form = AppointmentForm(obj=appointment)

    # Заповнення варіантів вибору
    form.client_id.choices = [
        (c.id, f"{c.name} ({c.phone})")
        for c in Client.query.order_by(Client.name).all()
    ]
    form.master_id.choices = [
        (u.id, u.full_name) for u in User.query.order_by(User.full_name).all()
    ]

    if form.validate_on_submit():
        form.populate_obj(appointment)
        db.session.commit()

        flash("Запис успішно оновлено!", "success")
        return redirect(url_for("appointments.view", id=appointment.id))

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
    form = ServiceForm()

    # Заповнення варіантів вибору
    form.service_id.choices = [
        (s.id, f"{s.name} ({s.duration} хв.)")
        for s in Service.query.order_by(Service.name).all()
    ]

    if form.validate_on_submit():
        service = Service.query.get(form.service_id.data)

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

    # Перевірка, чи послуга дійсно належить цьому запису
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

    # Перевірка, чи послуга дійсно належить цьому запису
    if appointment_service.appointment_id != appointment_id:
        flash("Неправильний запит!", "danger")
        return redirect(url_for("appointments.view", id=appointment_id))

    new_price = request.form.get("price", type=float)
    if new_price is None or new_price < 0:
        flash("Невірна ціна!", "danger")
        return redirect(url_for("appointments.view", id=appointment_id))

    appointment_service.price = new_price
    db.session.commit()

    flash(f"Ціну послуги оновлено!", "success")
    return redirect(url_for("appointments.view", id=appointment_id))


# API для отримання інформації про записи в форматі JSON
@bp.route("/api/dates/<date_str>")
@login_required
def api_appointments_by_date(date_str):
    try:
        filter_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    appointments = (
        Appointment.query.filter(Appointment.date == filter_date)
        .order_by(Appointment.start_time)
        .all()
    )

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

    # Отримання майстра для фільтрації
    filter_master = request.args.get("master_id")
    if filter_master and filter_master.isdigit():
        filter_master = int(filter_master)
    else:
        filter_master = current_user.id

    # Отримання записів для цього майстра на вказану дату
    appointments = (
        Appointment.query.filter(
            Appointment.date == filter_date,
            Appointment.master_id == filter_master,
            Appointment.status == "completed",
        )
        .order_by(Appointment.start_time)
        .all()
    )

    # Розрахунок загальної суми
    total_sum = 0
    for appointment in appointments:
        for service in appointment.services:
            total_sum += service.price

    # Отримання списку майстрів для фільтра
    masters = User.query.all()

    return render_template(
        "appointments/daily_summary.html",
        title="Щоденний підсумок",
        filter_date=filter_date,
        filter_master=filter_master,
        appointments=appointments,
        total_sum=total_sum,
        masters=masters,
    )
