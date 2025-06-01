from datetime import date
from decimal import Decimal
from typing import Any, Dict, Optional

from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy import and_, extract, func
from wtforms import DateField, SelectField, SubmitField
from wtforms.validators import DataRequired
from wtforms.validators import Optional as OptionalValidator
from wtforms.validators import ValidationError

from app import db
from app.models import Appointment, AppointmentService, Brand, PaymentMethod, Product, Sale, SaleItem, StockLevel, User


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


# Admin salary report form
class AdminSalaryReportForm(FlaskForm):
    start_date = DateField(
        "From Date",
        validators=[OptionalValidator()],
        default=date.today,
    )
    end_date = DateField(
        "To Date",
        validators=[OptionalValidator()],
        default=date.today,
    )
    admin_id = SelectField(
        "Administrator",
        coerce=int,
        validators=[DataRequired()],
    )
    submit = SubmitField("Generate Report")

    def validate_end_date(self, field):
        if self.start_date.data and field.data:
            if field.data < self.start_date.data:
                raise ValidationError("End date must be after or equal to start date.")


# Financial report form with date range
class FinancialReportForm(FlaskForm):
    start_date = DateField(
        "Дата з",
        validators=[OptionalValidator()],
        default=date.today,
    )
    end_date = DateField(
        "Дата по",
        validators=[OptionalValidator()],
        default=date.today,
    )
    submit = SubmitField("Сформувати звіт")

    def validate_end_date(self, field):
        if self.start_date.data and field.data:
            if field.data < self.start_date.data:
                raise ValidationError("Кінцева дата має бути пізніше або дорівнювати початковій даті.")


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
    appointments_with_totals = []  # Додаємо список записів з розрахованими сумами
    total_services_cost = 0.0
    services_commission = 0.0
    products_commission = 0.0
    total_salary = 0.0
    total_products_cost = 0.0
    commission_rate = 0.0
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

        # Get master for name display and commission rate
        selected_master = db.session.get(User, master_id)
        if selected_master and selected_master.configurable_commission_rate:
            commission_rate = float(selected_master.configurable_commission_rate)

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

        # Calculate individual totals for each appointment and prepare data for template
        for appointment in appointments:
            # Calculate total price of services for this specific appointment
            appointment_services_total = sum(service.price for service in appointment.services)

            # Calculate commission for this specific appointment
            appointment_commission = (
                appointment_services_total * (commission_rate / 100) if commission_rate > 0 else 0.0
            )

            # Create a dictionary with appointment data and calculated totals
            appointment_data = {
                "appointment": appointment,
                "services_total": appointment_services_total,
                "commission": appointment_commission,
            }
            appointments_with_totals.append(appointment_data)

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

        # Calculate services commission
        if total_services_cost > 0 and commission_rate > 0:
            services_commission = total_services_cost * (commission_rate / 100)

        # Calculate products sales commission (9% fixed rate)
        products_sales_query = Sale.query.filter(Sale.user_id == master_id, func.date(Sale.sale_date) == selected_date)

        total_products_amount = (
            db.session.query(func.sum(Sale.total_amount))
            .filter(Sale.user_id == master_id, func.date(Sale.sale_date) == selected_date)
            .scalar()
        )

        total_products_cost = float(total_products_amount or 0)

        if total_products_cost > 0:
            products_commission = total_products_cost * 0.09  # Fixed 9% commission

        # Calculate total salary
        total_salary = services_commission + products_commission

    return render_template(
        "reports/salary_report.html",
        title="Master Salary Report",
        form=form,
        appointments=appointments,
        appointments_with_totals=appointments_with_totals,  # Передаємо додаткові дані
        total_services_cost=total_services_cost,
        services_commission=services_commission,
        products_commission=products_commission,
        total_products_cost=total_products_cost,
        total_salary=total_salary,
        commission_rate=commission_rate,
        selected_date=selected_date,
        selected_master=selected_master,
    )


# Admin salary report route
@bp.route("/admin_salary", methods=["GET", "POST"])
@login_required
def admin_salary_report() -> str:
    form = AdminSalaryReportForm()

    # Only admins can access this report
    if not current_user.is_admin:
        return render_template(
            "reports/admin_salary_report.html",
            title="Administrator Salary Report",
            form=form,
            error="Only administrators can access this report",
        )

    # Get list of administrators for filtering
    admin_choices: Any = [(0, "Всі адміністратори")] + [
        (u.id, u.full_name) for u in User.query.filter_by(is_admin=True).order_by(User.full_name).all()
    ]
    form.admin_id.choices = admin_choices

    appointments = []
    appointments_with_totals = []
    admin_sales = []
    total_services_cost = 0.0
    services_commission = 0.0
    personal_products_commission = 0.0
    masters_products_share = 0.0
    total_salary = 0.0
    total_personal_products_cost = 0.0
    total_masters_products_cost = 0.0
    commission_rate = 0.0
    selected_date = None
    end_date = None
    selected_admin = None

    if form.validate_on_submit():
        selected_date = form.start_date.data
        end_date = form.end_date.data
        admin_id = form.admin_id.data

        # If "All administrators" is selected, we'll process all admins
        # For now, let's handle single admin selection
        if admin_id != 0:
            # Get admin for name display and commission rate
            selected_admin = db.session.get(User, admin_id)
            if selected_admin and selected_admin.configurable_commission_rate:
                commission_rate = float(selected_admin.configurable_commission_rate)

            # 1. Calculate commission from personal services
            appointments = (
                Appointment.query.filter(
                    Appointment.date >= selected_date,
                    Appointment.date <= end_date,
                    Appointment.master_id == admin_id,
                    Appointment.status == "completed",
                )
                .order_by(Appointment.start_time)
                .all()
            )

            # Calculate individual totals for each appointment
            for appointment in appointments:
                appointment_services_total = sum(service.price for service in appointment.services)
                appointment_commission = (
                    appointment_services_total * (commission_rate / 100) if commission_rate > 0 else 0.0
                )

                appointment_data = {
                    "appointment": appointment,
                    "services_total": appointment_services_total,
                    "commission": appointment_commission,
                }
                appointments_with_totals.append(appointment_data)

            # Calculate total service cost
            appointment_ids = [appointment.id for appointment in appointments]
            if appointment_ids:
                service_sum_query = db.session.query(func.sum(AppointmentService.price)).filter(
                    AppointmentService.appointment_id.in_(appointment_ids)
                )
                service_sum_result = service_sum_query.scalar()
                total_services_cost = float(service_sum_result or 0)

            # Calculate services commission
            if total_services_cost > 0 and commission_rate > 0:
                services_commission = total_services_cost * (commission_rate / 100)

            # 2. Calculate commission from personal product sales (rate + 1%)
            admin_sales = Sale.query.filter(
                Sale.user_id == admin_id,
                func.date(Sale.sale_date) >= selected_date,
                func.date(Sale.sale_date) <= end_date,
            ).all()

            total_personal_products_amount = (
                db.session.query(func.sum(Sale.total_amount))
                .filter(
                    Sale.user_id == admin_id,
                    func.date(Sale.sale_date) >= selected_date,
                    func.date(Sale.sale_date) <= end_date,
                )
                .scalar()
            )

            total_personal_products_cost = float(total_personal_products_amount or 0)

            if total_personal_products_cost > 0 and commission_rate > 0:
                # Admin commission rate + 1%
                personal_products_commission = total_personal_products_cost * ((commission_rate + 1) / 100)

            # 3. Calculate 1% share from all masters' product sales
            # Get all masters (non-admin active users)
            masters = User.query.filter_by(is_active_master=True, is_admin=False).all()
            master_ids = [master.id for master in masters]

            if master_ids:
                total_masters_products_amount = (
                    db.session.query(func.sum(Sale.total_amount))
                    .filter(
                        Sale.user_id.in_(master_ids),
                        func.date(Sale.sale_date) >= selected_date,
                        func.date(Sale.sale_date) <= end_date,
                    )
                    .scalar()
                )

                total_masters_products_cost = float(total_masters_products_amount or 0)

                if total_masters_products_cost > 0:
                    masters_products_share = total_masters_products_cost * 0.01  # 1% share

            # Calculate total salary
            total_salary = services_commission + personal_products_commission + masters_products_share

        else:
            # Handle "All administrators" case - for now, show error or redirect to individual selection
            pass

    return render_template(
        "reports/admin_salary_report.html",
        title="Administrator Salary Report",
        form=form,
        appointments=appointments,
        appointments_with_totals=appointments_with_totals,
        admin_sales=admin_sales,
        total_services_cost=total_services_cost,
        services_commission=services_commission,
        personal_products_commission=personal_products_commission,
        masters_products_share=masters_products_share,
        total_personal_products_cost=total_personal_products_cost,
        total_masters_products_cost=total_masters_products_cost,
        total_salary=total_salary,
        commission_rate=commission_rate,
        selected_date=selected_date,
        end_date=end_date,
        selected_admin=selected_admin,
    )


# Financial report route
@bp.route("/financial", methods=["GET", "POST"])
@login_required
def financial_report() -> str:
    # Create form for date range filtering
    form = FinancialReportForm()

    # Only admins should see financial data
    error_message = None
    if not current_user.is_admin:
        error_message = "Тільки адміністратори мають доступ до цього звіту"

    # Initialize all variables
    selected_start_date = None
    selected_end_date = None

    # Service revenue data
    service_revenue = Decimal("0.00")

    # Product sales data
    product_revenue = Decimal("0.00")
    total_cogs = Decimal("0.00")
    product_gross_profit = Decimal("0.00")

    # Totals
    total_revenue = Decimal("0.00")
    total_gross_profit = Decimal("0.00")

    # Payment breakdown
    payment_breakdown = []

    # Only process form if user is admin
    if current_user.is_admin and form.validate_on_submit():
        selected_start_date = form.start_date.data
        selected_end_date = form.end_date.data

        # 1. Calculate service revenue from completed appointments
        completed_appointments = Appointment.query.filter(
            Appointment.date >= selected_start_date,
            Appointment.date <= selected_end_date,
            Appointment.status == "completed",
        ).all()

        # Initialize payment method totals
        payment_methods_from_db = PaymentMethod.query.filter_by(is_active=True).all()
        payment_method_totals: Dict[str, Decimal] = {pm.name: Decimal("0.00") for pm in payment_methods_from_db}
        payment_method_totals["Не вказано"] = Decimal("0.00")

        # Process each completed appointment for service revenue
        for appointment in completed_appointments:
            # Use amount_paid if available, otherwise calculate from services with discount
            if appointment.amount_paid is not None and appointment.amount_paid > 0:
                amount = Decimal(str(appointment.amount_paid))
                service_revenue += amount

                # Add to the appropriate payment method
                if appointment.payment_method_id is None:
                    method_name = "Не вказано"
                else:
                    payment_method_obj = appointment.payment_method
                    method_name = payment_method_obj.name if payment_method_obj else "Не вказано"
                payment_method_totals[method_name] += amount
            else:
                # Calculate amount from services with discount
                services_amount = sum(Decimal(str(service.price)) for service in appointment.services)
                if appointment.discount_percentage:
                    discounted_amount = services_amount * (
                        Decimal("1.0") - Decimal(str(appointment.discount_percentage)) / Decimal("100.0")
                    )
                else:
                    discounted_amount = services_amount

                service_revenue += discounted_amount

                # Add to the appropriate payment method
                if appointment.payment_method_id is None:
                    method_name = "Не вказано"
                else:
                    payment_method_obj = appointment.payment_method
                    method_name = payment_method_obj.name if payment_method_obj else "Не вказано"
                payment_method_totals[method_name] += discounted_amount

        # 2. Calculate product sales data
        product_sales = Sale.query.filter(
            func.date(Sale.sale_date) >= selected_start_date, func.date(Sale.sale_date) <= selected_end_date
        ).all()

        for sale in product_sales:
            # Add sale total to payment method breakdown
            sale_amount = Decimal(str(sale.total_amount))

            if sale.payment_method_id is None:
                method_name = "Не вказано"
            else:
                payment_method_obj = PaymentMethod.query.get(sale.payment_method_id)
                method_name = payment_method_obj.name if payment_method_obj else "Не вказано"
            payment_method_totals[method_name] += sale_amount

            # Calculate product revenue and COGS from sale items
            for item in sale.items:
                item_revenue = Decimal(str(item.price_per_unit)) * Decimal(str(item.quantity))
                item_cogs = Decimal(str(item.cost_price_per_unit)) * Decimal(str(item.quantity))

                product_revenue += item_revenue
                total_cogs += item_cogs

        # 3. Calculate derived values
        product_gross_profit = product_revenue - total_cogs
        total_revenue = service_revenue + product_revenue
        total_gross_profit = service_revenue + product_gross_profit  # Services have no COGS tracked

        # Format payment breakdown for display
        payment_breakdown = [(method, amount) for method, amount in payment_method_totals.items() if amount > 0]

        # Add missing payment methods with zero values if needed for display
        for method in payment_methods_from_db:
            if method.name not in [item[0] for item in payment_breakdown]:
                payment_breakdown.append((method.name, Decimal("0.00")))

        # Add "Not specified" if not already included
        if "Не вказано" not in [item[0] for item in payment_breakdown]:
            payment_breakdown.append(("Не вказано", Decimal("0.00")))

        # Sort by payment method name
        payment_breakdown.sort(key=lambda x: x[0])

    return render_template(
        "reports/financial_report.html",
        title="Фінансовий звіт",
        form=form,
        selected_start_date=selected_start_date,
        selected_end_date=selected_end_date,
        service_revenue=service_revenue,
        product_revenue=product_revenue,
        total_cogs=total_cogs,
        product_gross_profit=product_gross_profit,
        total_revenue=total_revenue,
        total_gross_profit=total_gross_profit,
        payment_breakdown=payment_breakdown,
        error=error_message,
    )


# Low stock alerts route
@bp.route("/low_stock_alerts", methods=["GET"])
@login_required
def low_stock_alerts() -> str:
    """
    Display products with low stock levels.
    Only accessible to administrators.
    """
    # Check if user is admin
    if not current_user.is_admin:
        abort(403)

    # Query products with low stock levels
    # Join Product with StockLevel and Brand
    # Filter where quantity <= min_stock_level and min_stock_level is not null
    low_stock_products = (
        db.session.query(Product, StockLevel, Brand)
        .join(StockLevel, Product.id == StockLevel.product_id)
        .join(Brand, Product.brand_id == Brand.id)
        .filter(and_(StockLevel.quantity <= Product.min_stock_level, Product.min_stock_level.isnot(None)))
        .order_by(Product.name)
        .all()
    )

    # Prepare data for template
    products_data = []
    for product, stock_level, brand in low_stock_products:
        # Calculate how much needs to be ordered (difference)
        # Ensure min_stock_level is not None (it should not be due to filter, but for type safety)
        min_stock_level = product.min_stock_level or 0
        difference = min_stock_level - stock_level.quantity

        product_info = {
            "name": product.name,
            "sku": product.sku,
            "brand_name": brand.name,
            "current_quantity": stock_level.quantity,
            "min_stock_level": min_stock_level,
            "difference": difference,
        }
        products_data.append(product_info)

    return render_template(
        "reports/low_stock_alerts.html", title="Сповіщення про низькі залишки товарів", products=products_data
    )
