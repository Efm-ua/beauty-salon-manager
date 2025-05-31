# type: ignore
import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Union

from flask import (Blueprint, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import (DateField, FloatField, HiddenField, IntegerField,
                     SelectField, SelectMultipleField, StringField,
                     SubmitField, TextAreaField, TimeField)
from wtforms.validators import (DataRequired, NumberRange, Optional,
                                ValidationError)

from app.models import Appointment, AppointmentService, Client
from app.models import PaymentMethod as PaymentMethodModel
from app.models import PaymentMethodEnum as PaymentMethod
from app.models import Service, User, db

# Set up logging
logger = logging.getLogger(__name__)

# Створення Blueprint
bp = Blueprint("appointments", __name__, url_prefix="/appointments")


# Forms
class AppointmentForm(FlaskForm):
    client_id = SelectField("Клієнт", coerce=int, validators=[DataRequired()])
    master_id = SelectField("Майстер", coerce=int, validators=[DataRequired()])
    date = DateField("Дата", validators=[DataRequired()])
    start_time = TimeField("Час початку", validators=[DataRequired()])
    services = SelectMultipleField("Послуги", coerce=int, validators=[DataRequired()])
    discount_percentage = FloatField("Знижка (%)", validators=[Optional(), NumberRange(min=0, max=100)])
    amount_paid = FloatField("Сплачено", validators=[Optional(), NumberRange(min=0)])
    payment_method = SelectField("Спосіб оплати", validators=[Optional()])
    notes = TextAreaField("Примітки", validators=[Optional()])
    submit = SubmitField("Зберегти")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Populate choices
        clients = Client.query.order_by(Client.name).all()
        self.client_id.choices = [(c.id, c.name) for c in clients]  # type: ignore

        masters = User.query.filter_by(is_active_master=True).order_by(User.full_name).all()
        self.master_id.choices = [(u.id, u.full_name) for u in masters]  # type: ignore

        services = Service.query.order_by(Service.name).all()
        self.services.choices = [(s.id, s.name) for s in services]  # type: ignore

        # Payment method choices
        payment_methods = PaymentMethodModel.query.filter_by(is_active=True).all()
        self.payment_method.choices = [("", "Не вибрано")] + [
            (str(pm.id), pm.name) for pm in payment_methods
        ]  # type: ignore

    def validate_date(self, field):
        if field.data and field.data < date.today():
            raise ValidationError("Неможливо створити запис на дату та час у минулому.")

    def validate_master_id(self, field):
        if field.data:
            master = User.query.get(field.data)
            if not master or not master.is_active_master:
                raise ValidationError("Вибраний майстер не є активним.")


class AddServiceForm(FlaskForm):
    service_id = SelectField("Послуга", coerce=int, validators=[DataRequired()])
    price = FloatField("Ціна", validators=[DataRequired(), NumberRange(min=0)])
    notes = TextAreaField("Примітки", validators=[Optional()])
    submit = SubmitField("Додати послугу")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service_id.choices = [(s.id, s.name) for s in Service.query.order_by(Service.name).all()]


class CompleteAppointmentForm(FlaskForm):
    payment_method = SelectField("Спосіб оплати", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Завершити запис")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        payment_methods = PaymentMethodModel.query.filter_by(is_active=True).all()
        self.payment_method.choices = [(pm.id, pm.name) for pm in payment_methods]


# Routes
@bp.route("/")
@login_required
def index() -> Any:
    """Головна сторінка записів"""
    # Get filter parameters
    filter_date_str = request.args.get("date")
    filter_master_id = request.args.get("master_id")

    logger.info("=== APPOINTMENT FILTERING DEBUG ===")
    logger.info(f"URL parameters - date: {filter_date_str}, master_id: {filter_master_id}")
    logger.info(f"Current user: {current_user.id}, is_admin: {current_user.is_admin}")

    # Parse date
    try:
        if filter_date_str:
            filter_date = datetime.strptime(filter_date_str, "%Y-%m-%d").date()
        else:
            filter_date = date.today()
    except ValueError:
        filter_date = date.today()

    logger.info(f"Parsed filter_date: {filter_date}")

    # Parse master_id
    try:
        filter_master_id = int(filter_master_id) if filter_master_id else None
    except (ValueError, TypeError):
        filter_master_id = None

    logger.info(f"Parsed filter_master_id after conversion: {filter_master_id}")

    # For non-admins, restrict to their own appointments
    if not current_user.is_admin:
        logger.info(f"User is NOT admin - overriding filter_master_id from {filter_master_id} to {current_user.id}")
        filter_master_id = current_user.id
    else:
        logger.info(f"User IS admin - keeping filter_master_id as: {filter_master_id}")

    # Get list of masters for the form
    masters = User.query.filter_by(is_active_master=True).order_by(User.full_name).all()
    logger.info(f"Available masters: {[(m.id, m.full_name) for m in masters]}")

    # Base query for appointments
    query = Appointment.query.filter(Appointment.date == filter_date)
    logger.info(f"Base query filtering by date {filter_date}")

    # Count appointments before master filter
    appointments_by_date = query.count()
    logger.info(f"Appointments found for date {filter_date}: {appointments_by_date}")

    # Filter by master
    if filter_master_id:
        logger.info(f"Applying master filter: Appointment.master_id == {filter_master_id}")
        query = query.filter(Appointment.master_id == filter_master_id)
        appointments_after_master_filter = query.count()
        logger.info(f"Appointments found after master filter: {appointments_after_master_filter}")
    else:
        logger.info("No master filter applied (filter_master_id is None)")

    appointments = query.order_by(Appointment.start_time).all()
    logger.info(f"Final appointments count: {len(appointments)}")
    logger.info(f"Final appointments: {[(a.id, a.master_id, a.start_time, a.client.name) for a in appointments]}")
    logger.info("=== END APPOINTMENT FILTERING DEBUG ===")

    return render_template(
        "appointments/index.html",
        title="Записи",
        filter_date=filter_date,
        filter_master=filter_master_id,
        masters=masters,
        appointments=appointments,
        is_admin=current_user.is_admin,
    )


@bp.route("/view/<int:id>")
@login_required
def view(id: int) -> Any:
    """Перегляд конкретного запису"""
    appointment = Appointment.query.get_or_404(id)

    # Check access permissions
    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу до цього запису.", "error")
        return redirect(url_for("appointments.index"))

    # Check if we came from schedule
    from_schedule = request.args.get("from_schedule")
    formatted_date = appointment.date.strftime("%Y-%m-%d")

    # Calculate totals
    total_price = appointment.get_total_price()
    total_discounted = appointment.get_discounted_price()

    return render_template(
        "appointments/view.html",
        title="Перегляд запису",
        appointment=appointment,
        is_admin=current_user.is_admin,
        from_schedule=from_schedule,
        formatted_date=formatted_date,
        total_price=total_price,
        total_discounted=total_discounted,
    )


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create() -> Any:
    """Створення нового запису"""
    form = AppointmentForm()

    # Force refresh choices to ensure they're current
    form.client_id.choices = [(c.id, c.name) for c in Client.query.order_by(Client.name).all()]  # type: ignore
    form.master_id.choices = [
        (u.id, u.full_name) for u in User.query.filter_by(is_active_master=True).order_by(User.full_name).all()
    ]  # type: ignore
    form.services.choices = [(s.id, s.name) for s in Service.query.order_by(Service.name).all()]  # type: ignore

    # Payment method choices
    payment_methods = PaymentMethodModel.query.filter_by(is_active=True).all()
    form.payment_method.choices = [("", "Не вибрано")] + [
        (str(pm.id), pm.name) for pm in payment_methods
    ]  # type: ignore

    # Pre-populate form fields from URL parameters
    if request.method == "GET":
        date_arg = request.args.get("date")
        if date_arg:
            try:
                form.date.data = datetime.strptime(date_arg, "%Y-%m-%d").date()
            except ValueError:
                pass

        master_id_arg = request.args.get("master_id")
        if master_id_arg:
            try:
                form.master_id.data = int(master_id_arg)
            except (ValueError, TypeError):
                pass

        time_arg = request.args.get("time")
        if time_arg:
            try:
                form.start_time.data = datetime.strptime(time_arg, "%H:%M").time()
            except ValueError:
                pass

    if form.validate_on_submit():
        try:
            # Check if user can create appointment for this master
            if not current_user.is_admin and form.master_id.data != current_user.id:
                flash("Ви можете створювати записи тільки для себе.", "error")
                return render_template("appointments/create.html", title="Створити запис", form=form)

            # Calculate end time based on services duration
            total_duration = 0
            for service_id in form.services.data:
                service = Service.query.get(service_id)
                if service:
                    total_duration += service.duration

            start_datetime = datetime.combine(form.date.data, form.start_time.data)
            end_datetime = start_datetime + timedelta(minutes=total_duration or 60)  # Default 60 min

            # Create appointment
            payment_method_id = None
            if form.payment_method.data and form.payment_method.data.strip():
                try:
                    payment_method_id = int(form.payment_method.data)
                except (ValueError, TypeError):
                    payment_method_id = None

            appointment = Appointment(
                client_id=form.client_id.data,
                master_id=form.master_id.data,
                date=form.date.data,
                start_time=form.start_time.data,
                end_time=end_datetime.time(),
                discount_percentage=form.discount_percentage.data or 0,
                amount_paid=Decimal(str(form.amount_paid.data or 0)),
                payment_method_id=payment_method_id,
                notes=form.notes.data or "",
            )

            db.session.add(appointment)
            db.session.flush()  # Get the appointment ID

            # Add services
            for service_id in form.services.data:
                service = Service.query.get(service_id)
                if service:
                    appointment_service = AppointmentService(
                        appointment_id=appointment.id, service_id=service_id, price=service.base_price or 0, notes=""
                    )
                    db.session.add(appointment_service)

            # Update payment status after services are updated, so total price calculation is correct
            appointment.update_payment_status()

            db.session.commit()
            flash("Запис успішно створено!", "success")

            # Redirect based on from_schedule parameter
            if request.args.get("from_schedule"):
                return redirect(url_for("main.schedule", date=form.date.data.strftime("%Y-%m-%d")))
            else:
                return redirect(url_for("appointments.view", id=appointment.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Помилка при створенні запису: {str(e)}", "error")

    return render_template(
        "appointments/create.html", title="Створити запис", form=form, from_schedule=request.args.get("from_schedule")
    )


@bp.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit(id: int) -> str:
    """Редагування запису"""
    appointment = Appointment.query.get_or_404(id)

    # Check access permissions
    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу до редагування цього запису.", "error")
        return redirect(url_for("appointments.index"))

    form = AppointmentForm(obj=appointment)

    # Force refresh choices to ensure they're current
    form.client_id.choices = [(c.id, c.name) for c in Client.query.order_by(Client.name).all()]  # type: ignore
    form.master_id.choices = [
        (u.id, u.full_name) for u in User.query.filter_by(is_active_master=True).order_by(User.full_name).all()
    ]  # type: ignore
    form.services.choices = [(s.id, s.name) for s in Service.query.order_by(Service.name).all()]  # type: ignore

    # Payment method choices
    payment_methods = PaymentMethodModel.query.filter_by(is_active=True).all()
    form.payment_method.choices = [("", "Не вибрано")] + [
        (str(pm.id), pm.name) for pm in payment_methods
    ]  # type: ignore

    # Pre-populate services
    if request.method == "GET":
        form.services.data = [service.service_id for service in appointment.services]

    if form.validate_on_submit():
        try:
            # Check if user can edit appointment for this master
            if not current_user.is_admin and form.master_id.data != current_user.id:
                flash("Ви можете редагувати записи тільки для себе.", "error")
                return render_template(
                    "appointments/edit.html", title="Редагувати запис", form=form, appointment=appointment
                )

            # Calculate end time based on services duration
            total_duration = 0
            for service_id in form.services.data:
                service = Service.query.get(service_id)
                if service:
                    total_duration += service.duration

            start_datetime = datetime.combine(form.date.data, form.start_time.data)
            end_datetime = start_datetime + timedelta(minutes=total_duration or 60)

            # Update appointment
            payment_method_id = None
            if form.payment_method.data and form.payment_method.data.strip():
                try:
                    payment_method_id = int(form.payment_method.data)
                except (ValueError, TypeError):
                    payment_method_id = None

            appointment.client_id = form.client_id.data
            appointment.master_id = form.master_id.data
            appointment.date = form.date.data
            appointment.start_time = form.start_time.data
            appointment.end_time = end_datetime.time()
            appointment.discount_percentage = form.discount_percentage.data or 0
            appointment.amount_paid = Decimal(str(form.amount_paid.data or 0))
            appointment.payment_method_id = payment_method_id
            appointment.notes = form.notes.data or ""

            # Remove existing services
            AppointmentService.query.filter_by(appointment_id=appointment.id).delete()

            # Add new services
            for service_id in form.services.data:
                service = Service.query.get(service_id)
                if service:
                    appointment_service = AppointmentService(
                        appointment_id=appointment.id, service_id=service_id, price=service.base_price or 0, notes=""
                    )
                    db.session.add(appointment_service)

            # Update payment status after services are updated, so total price calculation is correct
            appointment.update_payment_status()

            db.session.commit()
            flash("Запис успішно оновлено!", "success")

            # Redirect based on from_schedule parameter
            if request.form.get("from_schedule") or request.args.get("from_schedule"):
                return redirect(url_for("main.schedule", date=form.date.data.strftime("%Y-%m-%d")))
            else:
                return redirect(url_for("appointments.view", id=appointment.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Помилка при оновленні запису: {str(e)}", "error")

    return render_template(
        "appointments/edit.html",
        title="Редагувати запис",
        form=form,
        appointment=appointment,
        from_schedule=request.args.get("from_schedule"),
    )


@bp.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete(id: int) -> str:
    """Видалення запису"""
    appointment = Appointment.query.get_or_404(id)

    # Check permissions - more detailed logic
    if not current_user.is_admin:
        # Non-admin users can only delete their own appointments
        if appointment.master_id != current_user.id:
            flash("Ви можете видаляти тільки свої записи.", "error")
            return redirect(url_for("appointments.index"))

        # Non-admin users cannot delete completed appointments
        if appointment.status == "completed":
            flash("Ви не можете видаляти завершені записи.", "error")
            return redirect(url_for("appointments.view", id=id))

    try:
        db.session.delete(appointment)
        db.session.commit()
        flash("Запис успішно видалено!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Помилка при видаленні запису: {str(e)}", "error")

    if request.form.get("from_schedule"):
        return redirect(url_for("main.schedule", date=appointment.date.strftime("%Y-%m-%d")))
    else:
        return redirect(url_for("appointments.index"))


@bp.route("/change-status/<int:id>/<new_status>", methods=["POST", "GET"])
@login_required
def change_status(id: int, new_status: str) -> str:
    """Зміна статусу запису"""
    appointment = Appointment.query.get_or_404(id)

    # Check permissions
    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу до зміни статусу цього запису.", "error")
        return redirect(url_for("appointments.view", id=id))

    if new_status not in ["scheduled", "completed", "cancelled"]:
        flash("Недійсний статус.", "error")
        return redirect(url_for("appointments.view", id=id))

    try:
        # Handle payment method if completing appointment
        if new_status == "completed":
            # For GET requests, redirect to the complete form
            if request.method == "GET":
                return redirect(url_for("appointments.complete", id=id))

            payment_method_data = request.form.get("payment_method") or request.args.get("payment_method")

            if not payment_method_data:
                flash("Будь ласка, виберіть тип оплати для завершення запису.", "error")
                return redirect(url_for("appointments.view", id=id))

            # Handle case where payment_method_data might be a list
            if isinstance(payment_method_data, list):
                payment_method_data = payment_method_data[0]

            # Find payment method by name (string value)
            payment_method = PaymentMethodModel.query.filter_by(name=payment_method_data).first()
            if not payment_method:
                flash("Невідомий метод оплати.", "error")
                return redirect(url_for("appointments.view", id=id))

            appointment.payment_method_id = payment_method.id

            # Logic for payment completion
            if payment_method.name == "Борг":
                # Debt payment method - amount stays 0, payment_status remains unpaid
                appointment.amount_paid = 0
            else:
                # Non-debt payment method - set amount_paid to full discounted price
                appointment.amount_paid = appointment.get_discounted_price()

        # Set status based on new_status
        if new_status == "cancelled":
            appointment.payment_method_id = None
        elif new_status == "scheduled" and appointment.status == "completed":
            # Changing from completed back to scheduled - clear payment method
            appointment.payment_method_id = None

        appointment.status = new_status

        # Update payment status based on new values
        appointment.update_payment_status()

        db.session.commit()

        flash(f"Статус запису змінено на '{new_status}'.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Помилка при зміні статусу: {str(e)}", "error")

    return redirect(url_for("appointments.view", id=id))


@bp.route("/complete/<int:id>", methods=["GET", "POST"])
@login_required
def complete(id: int) -> str:
    """Завершення запису з вибором способу оплати"""
    appointment = Appointment.query.get_or_404(id)

    # Check permissions
    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу до завершення цього запису.", "error")
        return redirect(url_for("appointments.view", id=id))

    form = CompleteAppointmentForm()

    if form.validate_on_submit():
        try:
            appointment.status = "completed"
            appointment.payment_method_id = form.payment_method.data

            # Logic for payment completion
            payment_method = PaymentMethodModel.query.get(form.payment_method.data)
            if payment_method and payment_method.name == "Борг":
                appointment.amount_paid = 0
            else:
                appointment.amount_paid = appointment.get_discounted_price()

            # Update payment status based on new values
            appointment.update_payment_status()

            db.session.commit()
            flash("Запис успішно завершено!", "success")
            return redirect(url_for("appointments.view", id=id))
        except Exception as e:
            db.session.rollback()
            flash(f"Помилка при завершенні запису: {str(e)}", "error")

    return render_template(
        "appointments/complete_form.html", title="Завершення запису", form=form, appointment=appointment
    )


@bp.route("/add-service/<int:id>", methods=["GET", "POST"])
@login_required
def add_service(id: int) -> str:
    """Додавання послуги до запису"""
    appointment = Appointment.query.get_or_404(id)

    # Check permissions
    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу до редагування цього запису.", "error")
        return redirect(url_for("appointments.view", id=id))

    form = AddServiceForm()

    if form.validate_on_submit():
        try:
            appointment_service = AppointmentService(
                appointment_id=appointment.id,
                service_id=form.service_id.data,
                price=form.price.data,
                notes=form.notes.data or "",
            )
            db.session.add(appointment_service)
            db.session.commit()
            flash("Послугу успішно додано!", "success")
            return redirect(url_for("appointments.view", id=id))
        except Exception as e:
            db.session.rollback()
            flash(f"Помилка при додаванні послуги: {str(e)}", "error")

    return render_template("appointments/add_service.html", title="Додати послугу", form=form, appointment=appointment)


@bp.route("/remove-service/<int:appointment_id>/<int:service_id>", methods=["POST"])
@login_required
def remove_service(appointment_id: int, service_id: int) -> str:
    """Видалення послуги з запису"""
    appointment = Appointment.query.get_or_404(appointment_id)

    # Check permissions
    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу до редагування цього запису.", "error")
        return redirect(url_for("appointments.view", id=appointment_id))

    try:
        appointment_service = AppointmentService.query.filter_by(
            appointment_id=appointment_id, service_id=service_id
        ).first()

        if appointment_service:
            db.session.delete(appointment_service)
            db.session.commit()
            flash("Послугу успішно видалено!", "success")
        else:
            flash("Послугу не знайдено.", "error")
    except Exception as e:
        db.session.rollback()
        flash(f"Помилка при видаленні послуги: {str(e)}", "error")

    return redirect(url_for("appointments.view", id=appointment_id))


@bp.route("/edit-service-price/<int:appointment_id>/<int:service_id>", methods=["POST"])
@login_required
def edit_service_price(appointment_id: int, service_id: int) -> str:
    """Редагування ціни послуги"""
    appointment = Appointment.query.get_or_404(appointment_id)

    # Check permissions
    if not current_user.is_admin and appointment.master_id != current_user.id:
        return jsonify({"error": "Доступ заборонено"}), 403

    try:
        new_price = float(request.form.get("price", 0))

        appointment_service = AppointmentService.query.filter_by(
            appointment_id=appointment_id, service_id=service_id
        ).first()

        if appointment_service:
            appointment_service.price = new_price
            db.session.commit()
            return jsonify({"success": True, "new_price": new_price})
        else:
            return jsonify({"error": "Послугу не знайдено"}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/api/by-date")
@login_required
def api_by_date():
    """API для отримання записів за датою"""
    date_str = request.args.get("date")

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid date format"}), 400

    query = Appointment.query.filter(Appointment.date == target_date)

    # For non-admins, restrict to their own appointments
    if not current_user.is_admin:
        query = query.filter(Appointment.master_id == current_user.id)

    appointments = query.order_by(Appointment.start_time).all()

    result = []
    for appointment in appointments:
        result.append(
            {
                "id": appointment.id,
                "client_name": appointment.client.name,
                "master_name": appointment.master.full_name,
                "start_time": appointment.start_time.strftime("%H:%M"),
                "end_time": appointment.end_time.strftime("%H:%M"),
                "status": appointment.status,
                "services": [service.service.name for service in appointment.services],
            }
        )

    return jsonify(result)


@bp.route("/daily-summary")
@login_required
def daily_summary() -> str:
    """Щоденний підсумок записів"""
    # Отримання параметрів з запиту
    filter_date_str = request.args.get("date")
    filter_master_id = request.args.get("master_id")

    # Парсинг дати
    try:
        if filter_date_str:
            filter_date = datetime.strptime(filter_date_str, "%Y-%m-%d").date()
        else:
            filter_date = date.today()
    except ValueError:
        filter_date = date.today()

    # Парсинг master_id
    try:
        filter_master_id = int(filter_master_id) if filter_master_id else None
    except (ValueError, TypeError):
        filter_master_id = None

    # Для неадміністраторів обмежуємо до їх власних записів
    if not current_user.is_admin:
        filter_master_id = current_user.id

    # Отримання списку майстрів для форми
    masters = User.query.filter_by(is_active_master=True).order_by(User.full_name).all()

    # Базовий запит для записів
    # Для показу всіх записів (не тільки completed)
    all_appointments_query = Appointment.query.filter(Appointment.date == filter_date)

    # Запит для completed записів (для розрахунку сум)
    completed_query = Appointment.query.filter(Appointment.date == filter_date, Appointment.status == "completed")

    # Фільтрація за майстром
    if filter_master_id:
        all_appointments_query = all_appointments_query.filter(Appointment.master_id == filter_master_id)
        completed_query = completed_query.filter(Appointment.master_id == filter_master_id)
        appointments = all_appointments_query.order_by(Appointment.start_time).all()
        completed_appointments = completed_query.order_by(Appointment.start_time).all()
        master_stats = None
    else:
        appointments = all_appointments_query.order_by(Appointment.start_time).all()
        completed_appointments = completed_query.order_by(Appointment.start_time).all()

        # Статистика по майстрах (тільки для адміністраторів)
        if current_user.is_admin:
            master_stats = []
            masters_with_appointments = (
                db.session.query(User.id, User.full_name, func.count(Appointment.id).label("appointments_count"))
                .join(Appointment, User.id == Appointment.master_id)
                .filter(Appointment.date == filter_date, Appointment.status == "completed")
                .group_by(User.id, User.full_name)
                .all()
            )

            for master_id, name, appointments_count in masters_with_appointments:
                # Розрахунок суми для майстра (тільки completed записи)
                master_completed_appointments = [a for a in completed_appointments if a.master_id == master_id]
                total_sum = 0.0

                for appointment in master_completed_appointments:
                    if appointment.amount_paid is not None and float(appointment.amount_paid) > 0:
                        total_sum += float(appointment.amount_paid)
                    else:
                        services_amount = sum(service.price for service in appointment.services)
                        if appointment.discount_percentage:
                            discounted_amount = services_amount * (1 - float(appointment.discount_percentage) / 100)
                        else:
                            discounted_amount = services_amount
                        total_sum += discounted_amount

                master_stats.append(
                    {"id": master_id, "name": name, "appointments_count": appointments_count, "total_sum": total_sum}
                )
        else:
            master_stats = None

    # Розрахунок загальної суми (тільки completed записи)
    total_sum = 0.0
    for appointment in completed_appointments:
        if appointment.amount_paid is not None and float(appointment.amount_paid) > 0:
            total_sum += float(appointment.amount_paid)
        else:
            services_amount = sum(service.price for service in appointment.services)
            if appointment.discount_percentage:
                discounted_amount = services_amount * (1 - float(appointment.discount_percentage) / 100)
            else:
                discounted_amount = services_amount
            total_sum += discounted_amount

    return render_template(
        "appointments/daily_summary.html",
        title="Щоденний підсумок",
        filter_date=filter_date,
        filter_master=filter_master_id,
        masters=masters,
        appointments=appointments,
        master_stats=master_stats,
        total_sum=total_sum,
    )


@bp.route("/<int:id>")
@login_required
def view_alternative(id: int) -> str:
    """Альтернативний маршрут для перегляду запису (для сумісності з тестами)"""
    # Redirect to the canonical view URL with preserved query parameters
    return redirect(url_for("appointments.view", id=id, **request.args))


@bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_alternative(id: int) -> str:
    """Альтернативний маршрут для редагування запису (для сумісності з тестами)"""
    if request.method == "GET":
        # For GET requests, redirect to canonical edit URL
        return redirect(url_for("appointments.edit", id=id))
    else:
        # For POST requests, handle the edit and redirect properly
        result = edit(id)
        # If the edit function returns a redirect, we need to modify the redirect URL
        if hasattr(result, "location") and "/appointments/view/" in result.location:
            # Change the redirect to use the alternative URL format
            appointment_id = result.location.split("/")[-1]
            return redirect(url_for("appointments.view_alternative", id=appointment_id))
        return result


@bp.route("/<int:id>/delete", methods=["POST"])
@login_required
def delete_alternative(id: int) -> str:
    """Альтернативний маршрут для видалення запису (для сумісності з тестами)"""
    result = delete(id)
    # Handle redirect properly if needed
    return result


@bp.route("/<int:id>/status/<new_status>", methods=["POST", "GET"])
@login_required
def status(id: int, new_status: str) -> str:
    """Зміна статусу запису (альтернативний маршрут для сумісності з тестами)"""
    return change_status(id, new_status)


@bp.route("/<int:appointment_id>/edit_service/<int:service_id>", methods=["POST"])
@login_required
def edit_service(appointment_id: int, service_id: int) -> str:
    """Редагування послуги в записі"""
    appointment = Appointment.query.get_or_404(appointment_id)

    # Check permissions
    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу до редагування цього запису.", "error")
        return redirect(url_for("appointments.view", id=appointment_id))

    # Check if appointment is in scheduled status
    if appointment.status != "scheduled":
        flash("Редагування ціни можливе тільки для запланованих записів", "error")
        return redirect(url_for("appointments.view", id=appointment_id))

    try:
        new_price = float(request.form.get("price", 0))

        if new_price < 0:
            flash("Невірна ціна!", "error")
            return redirect(url_for("appointments.view", id=appointment_id))

        appointment_service = AppointmentService.query.filter_by(appointment_id=appointment_id, id=service_id).first()

        if not appointment_service:
            flash("Послугу не знайдено.", "error")
            return redirect(url_for("appointments.view", id=appointment_id))

        appointment_service.price = new_price

        # Update payment status based on new total
        appointment.update_payment_status()

        db.session.commit()
        flash("Ціну послуги оновлено!", "success")

    except ValueError:
        flash("Невірна ціна!", "error")
    except Exception as e:
        db.session.rollback()
        flash(f"Помилка при оновленні ціни: {str(e)}", "error")

    return redirect(url_for("appointments.view", id=appointment_id))


@bp.route("/<int:appointment_id>/add_service", methods=["GET", "POST"])
@login_required
def add_service_alternative(appointment_id: int) -> str:
    """Альтернативний маршрут для додавання послуги (для сумісності з тестами)"""
    return add_service(appointment_id)


@bp.route("/<int:appointment_id>/remove_service/<int:service_id>", methods=["POST"])
@login_required
def remove_service_alternative(appointment_id: int, service_id: int) -> str:
    """Альтернативний маршрут для видалення послуги (для сумісності з тестами)"""
    appointment = Appointment.query.get_or_404(appointment_id)

    # Check permissions
    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу до редагування цього запису.", "error")
        return redirect(url_for("appointments.view", id=appointment_id))

    try:
        appointment_service = AppointmentService.query.filter_by(appointment_id=appointment_id, id=service_id).first()

        if appointment_service:
            db.session.delete(appointment_service)
            db.session.commit()
            flash("Послугу успішно видалено!", "success")
        else:
            flash("Послугу не знайдено.", "error")
    except Exception as e:
        db.session.rollback()
        flash(f"Помилка при видаленні послуги: {str(e)}", "error")

    return redirect(url_for("appointments.view", id=appointment_id))


@bp.route("/api/dates/<date_str>")
@login_required
def api_dates(date_str: str):
    """API для отримання записів за конкретною датою"""
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date format"}), 400

    query = Appointment.query.filter(Appointment.date == target_date)

    # For non-admins, restrict to their own appointments
    if not current_user.is_admin:
        query = query.filter(Appointment.master_id == current_user.id)

    appointments = query.order_by(Appointment.start_time).all()

    result = []
    for appointment in appointments:
        result.append(
            {
                "id": appointment.id,
                "client_name": appointment.client.name,
                "master_name": appointment.master.full_name,
                "start_time": appointment.start_time.strftime("%H:%M"),
                "end_time": appointment.end_time.strftime("%H:%M"),
                "status": appointment.status,
                "services": [service.service.name for service in appointment.services],
            }
        )

    return jsonify(result)


@bp.route("/<int:id>/complete", methods=["GET"])
@login_required
def complete_get(id: int) -> str:
    """GET маршрут для завершення запису з параметрами URL"""
    appointment = Appointment.query.get_or_404(id)

    # Check permissions
    if not current_user.is_admin and appointment.master_id != current_user.id:
        flash("У вас немає доступу до завершення цього запису.", "error")
        return redirect(url_for("appointments.view", id=id))

    payment_method_name = request.args.get("payment_method")

    if not payment_method_name:
        # If no payment method specified, redirect to the form
        return redirect(url_for("appointments.complete", id=id))

    try:
        # Find payment method by name
        payment_method = PaymentMethodModel.query.filter_by(name=payment_method_name).first()
        if not payment_method:
            flash("Невідомий метод оплати.", "error")
            return redirect(url_for("appointments.view", id=id))

        appointment.status = "completed"
        appointment.payment_method_id = payment_method.id

        # Logic for payment completion
        if payment_method.name == "Борг":
            appointment.amount_paid = 0
        else:
            appointment.amount_paid = appointment.get_discounted_price()

        # Update payment status based on new values
        appointment.update_payment_status()

        db.session.commit()
        flash("Запис успішно завершено!", "success")
        return redirect(url_for("appointments.view", id=id))
    except Exception as e:
        db.session.rollback()
        flash(f"Помилка при завершенні запису: {str(e)}", "error")
        return redirect(url_for("appointments.view", id=id))
