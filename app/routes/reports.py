from datetime import date

from flask import Blueprint, render_template
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, SubmitField
from wtforms.validators import DataRequired

from app import db
from app.models import Appointment, User

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
