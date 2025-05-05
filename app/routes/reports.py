from datetime import date

from flask import Blueprint, render_template
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import DateField, SelectField, SubmitField
from wtforms.validators import DataRequired

from app import db
from app.models import Appointment, AppointmentService, PaymentMethod, User

# Blueprint creation
bp = Blueprint("reports", __name__, url_prefix="/reports")


# Salary report form
class DailySalaryReportForm(FlaskForm):
    report_date = DateField(
        "Date",
        validators=[DataRequired()],
        default=date.today,
    )
    master_id = SelectField(
        "Master",
        coerce=int,
        validators=[DataRequired()],
    )
    submit = SubmitField("Generate Report")


# Salary report route
@bp.route("/salary", methods=["GET", "POST"])
@login_required
def salary_report():
    form = DailySalaryReportForm()

    # Fill masters list
    form.master_id.choices = [
        (u.id, u.full_name) for u in User.query.order_by(User.full_name).all()
    ]

    # If user is not admin, limit selection to current user
    if not current_user.is_admin:
        form.master_id.data = current_user.id
        form.master_id.render_kw = {"disabled": "disabled"}

    appointments = []
    total_services_cost = 0
    selected_date = None
    selected_master = None

    if form.validate_on_submit():
        selected_date = form.report_date.data
        master_id = form.master_id.data

        # Check if user is allowed to view this master's report
        if not current_user.is_admin and current_user.id != master_id:
            return render_template(
                "reports/salary_report.html",
                title="Master Salary Report",
                form=form,
                error="You can only view your own reports",
            )

        # Get master for name display
        selected_master = db.session.get(User, master_id)

        # Query completed appointments
        appointments = (
            Appointment.query.filter(
                Appointment.date == selected_date,
                Appointment.master_id == master_id,
                Appointment.status == "completed",
            )
            .order_by(Appointment.start_time)
            .all()
        )

        # Calculate total service cost
        for appointment in appointments:
            for service in appointment.services:
                total_services_cost += service.price

    return render_template(
        "reports/salary_report.html",
        title="Master Salary Report",
        form=form,
        appointments=appointments,
        total_services_cost=total_services_cost,
        selected_date=selected_date,
        selected_master=selected_master,
    )


# Financial report route
@bp.route("/financial", methods=["GET", "POST"])
@login_required
def financial_report():
    # Create form first so it's available for all template renderings
    form = DailySalaryReportForm()

    # Fill masters list (not used for this report but required for the form)
    form.master_id.choices = [
        (u.id, u.full_name) for u in User.query.order_by(User.full_name).all()
    ]

    # Debug the admin status
    print(f"User {current_user.username} is_admin: {current_user.is_admin}")
    print(
        f"User {current_user.username} is_administrator(): {current_user.is_administrator()}"
    )

    # Only admins should see financial data, but everyone gets the form
    error_message = None
    if not current_user.is_admin:
        error_message = "Тільки адміністратори мають доступ до цього звіту"

    total_amount = 0
    payment_breakdown = []
    selected_date = None

    # Only process form if user is admin
    if current_user.is_admin and form.validate_on_submit():
        selected_date = form.report_date.data

        # Query for completed appointments on selected date
        completed_appointments = Appointment.query.filter(
            Appointment.date == selected_date, Appointment.status == "completed"
        ).all()

        # Calculate total amount from all appointment services
        appointment_ids = [appointment.id for appointment in completed_appointments]

        if appointment_ids:
            # Calculate total income for the day (now considering discount)
            total_income_query = (
                db.session.query(
                    func.sum(
                        AppointmentService.price
                        * (1 - func.coalesce(Appointment.discount_percentage, 0) / 100)
                    )
                )
                .join(Appointment, Appointment.id == AppointmentService.appointment_id)
                .filter(AppointmentService.appointment_id.in_(appointment_ids))
            )

            total_amount_result = total_income_query.scalar()
            total_amount = total_amount_result or 0

            # Get breakdown by payment method (with discount)
            payment_breakdown_query = (
                db.session.query(
                    Appointment.payment_method,
                    func.sum(
                        AppointmentService.price
                        * (1 - func.coalesce(Appointment.discount_percentage, 0) / 100)
                    ),
                )
                .join(
                    AppointmentService,
                    AppointmentService.appointment_id == Appointment.id,
                )
                .filter(Appointment.id.in_(appointment_ids))
                .group_by(Appointment.payment_method)
                .all()
            )

            # Format results for display
            payment_breakdown = []
            for payment_method, amount in payment_breakdown_query:
                method_name = (
                    "Не вказано" if payment_method is None else payment_method.value
                )
                payment_breakdown.append((method_name, amount))

            # Add any missing payment methods with zero values
            existing_methods = {item[0] for item in payment_breakdown}
            for method in PaymentMethod:
                if method.value not in existing_methods:
                    payment_breakdown.append((method.value, 0))

            # Add "Not specified" if it's not already included
            if "Не вказано" not in existing_methods and None not in existing_methods:
                payment_breakdown.append(("Не вказано", 0))

            # Sort by payment method name
            payment_breakdown.sort(key=lambda x: x[0])

    return render_template(
        "reports/financial_report.html",
        title="Фінансовий звіт",
        form=form,
        total_amount=total_amount,
        payment_breakdown=payment_breakdown,
        selected_date=selected_date,
        error=error_message,
    )
