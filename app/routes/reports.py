from datetime import date
from typing import Any, Dict, Optional

from flask import Blueprint, render_template
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import DateField, SelectField, SubmitField
from wtforms.validators import DataRequired

from app import db
from app.models import Appointment, AppointmentService, PaymentMethod, User


# Helper function for calculating total with discount
def calculate_total_with_discount(service_price: float, discount_percentage: float) -> float:
    """Calculate the service price with discount applied."""
    discount_factor = 1 - float(discount_percentage) / 100
    return service_price * discount_factor


# Helper function for calculating salary without discount
def calculate_salary_without_discount(service_price: float, discount_percentage: Optional[float] = None) -> float:
    """Calculate the salary amount, ignoring any discount."""
    # Return the full service price without applying discount
    return service_price


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
def salary_report() -> str:
    form = DailySalaryReportForm()

    # Отримання списку майстрів для фільтрації
    master_choices: Any = [(0, "Всі майстри")] + [
        (u.id, u.full_name) for u in User.query.filter_by(is_active_master=True).order_by(User.full_name).all()
    ]
    form.master_id.choices = master_choices

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

        # Get appointment IDs for completed appointments
        appointment_ids = [appointment.id for appointment in appointments]

        # Calculate total service cost based ONLY on AppointmentService.price values
        if appointment_ids:
            # Get the sum of all service prices for these appointments using SQLAlchemy
            service_sum_query = db.session.query(func.sum(AppointmentService.price)).filter(
                AppointmentService.appointment_id.in_(appointment_ids)
            )
            service_sum_result = service_sum_query.scalar()
            total_services_cost = float(service_sum_result or 0)

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
def financial_report() -> str:
    # Create form first so it's available for all template renderings
    form = DailySalaryReportForm()

    # Отримання списку майстрів для фільтрації
    master_choices: Any = [(0, "Всі майстри")] + [
        (u.id, u.full_name) for u in User.query.filter_by(is_active_master=True).order_by(User.full_name).all()
    ]
    form.master_id.choices = master_choices

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

        # Initialize payment method totals
        payment_method_totals: Dict[str, float] = {pm.value: 0.0 for pm in PaymentMethod}
        payment_method_totals["Не вказано"] = 0.0

        # Process each completed appointment
        for appointment in completed_appointments:
            # Use amount_paid if available, otherwise calculate from services with discount
            if appointment.amount_paid is not None and float(appointment.amount_paid) > 0:
                amount = float(appointment.amount_paid)
                total_amount += amount

                # Add to the appropriate payment method
                method_name = "Не вказано" if appointment.payment_method is None else appointment.payment_method.value
                payment_method_totals[method_name] += amount
            else:
                # Calculate amount from services with discount
                services_amount = sum(service.price for service in appointment.services)
                if appointment.discount_percentage:
                    discounted_amount = services_amount * (1 - float(appointment.discount_percentage) / 100)
                else:
                    discounted_amount = services_amount

                total_amount += discounted_amount

                # Add to the appropriate payment method
                method_name = "Не вказано" if appointment.payment_method is None else appointment.payment_method.value
                payment_method_totals[method_name] += discounted_amount

        # Format results for display
        payment_breakdown = [(method, amount) for method, amount in payment_method_totals.items() if amount > 0]

        # Add any missing payment methods with zero values if needed for display
        for method in PaymentMethod:
            if method.value not in [item[0] for item in payment_breakdown]:
                payment_breakdown.append((method.value, 0))

        # Add "Not specified" if not already included
        if "Не вказано" not in [item[0] for item in payment_breakdown]:
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
