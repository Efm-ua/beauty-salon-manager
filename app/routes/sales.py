"""
Sales routes for handling sales interface.
"""

from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy import desc
from wtforms import (FieldList, FormField, IntegerField, SelectField,
                     SubmitField, TextAreaField)
from wtforms.validators import DataRequired, NumberRange, Optional
from wtforms_sqlalchemy.fields import QuerySelectField

from app.models import (Appointment, Client, PaymentMethod, Product, Sale,
                        SaleItem, User, db)
from app.services.sales_service import (InsufficientStockError,
                                        ProductNotFoundError, SaleItemData,
                                        SalesService)

# Створюємо blueprint
bp = Blueprint("sales", __name__, url_prefix="/sales")


class SaleItemForm(FlaskForm):
    """Form for individual sale item."""

    product_id = SelectField(
        "Товар",
        choices=[],
        validators=[DataRequired(message="Оберіть товар")],
        coerce=int,
        render_kw={"class": "form-select"},
    )
    quantity = IntegerField(
        "Кількість",
        validators=[
            DataRequired(message="Вкажіть кількість"),
            NumberRange(min=1, message="Кількість повинна бути більше 0"),
        ],
        render_kw={"class": "form-control", "min": "1"},
    )


class SaleForm(FlaskForm):
    """Form for creating a new sale."""

    client_id = SelectField(
        "Клієнт",
        choices=[],
        validators=[Optional()],
        coerce=lambda x: int(x) if x else None,
        render_kw={"class": "form-select"},
    )
    user_id = SelectField(
        "Продавець",
        choices=[],
        validators=[DataRequired(message="Оберіть продавця")],
        coerce=int,
        render_kw={"class": "form-select"},
    )
    appointment_id = QuerySelectField(
        "Пов'язати із записом (опціонально)",
        query_factory=lambda: [],
        get_label=lambda a: (
            f"{a.date.strftime('%d.%m.%Y')} {a.start_time.strftime('%H:%M')} - "
            f"{a.client.name} ({a.master.full_name})"
        ),
        validators=[Optional()],
        allow_blank=True,
        blank_text="Не пов'язувати з записом",
        render_kw={"class": "form-select"},
    )
    payment_method_id = SelectField(
        "Спосіб оплати",
        choices=[],
        validators=[DataRequired(message="Оберіть спосіб оплати")],
        coerce=int,
        render_kw={"class": "form-select"},
    )
    sale_items = FieldList(
        FormField(SaleItemForm),
        min_entries=1,
        label="Товари",
    )
    notes = TextAreaField(
        "Примітки",
        validators=[Optional()],
        render_kw={"class": "form-control", "rows": "3"},
    )
    submit = SubmitField("Створити продаж", render_kw={"class": "btn btn-primary"})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._populate_choices()

    def _populate_choices(self):
        """Populate choices for select fields."""
        # Client choices with anonymous option
        self.client_id.choices = [("", "Анонімний клієнт")]
        clients = Client.query.order_by(Client.name).all()
        self.client_id.choices.extend([(c.id, c.name) for c in clients])

        # User choices (sellers)
        users = (
            User.query.filter((User.is_admin == True) | (User.is_active_master == True))  # noqa: E712
            .order_by(User.full_name)
            .all()
        )
        self.user_id.choices = [(u.id, u.full_name) for u in users]

        # Appointment choices - recent and future appointments
        from datetime import date, timedelta

        today = date.today()
        week_ago = today - timedelta(days=7)

        def appointment_query():
            return (
                Appointment.query.filter(Appointment.date >= week_ago)
                .filter(Appointment.status.in_(["scheduled", "completed"]))
                .order_by(desc(Appointment.date), desc(Appointment.start_time))
                .limit(50)
                .all()
            )

        self.appointment_id.query_factory = appointment_query

        # Payment method choices
        payment_methods = PaymentMethod.query.filter_by(is_active=True).order_by(PaymentMethod.name).all()
        self.payment_method_id.choices = [(pm.id, pm.name) for pm in payment_methods]

        # Product choices for each sale item - only products with set price and stock
        from app.models import StockLevel

        products = (
            Product.query.join(StockLevel)
            .filter(Product.current_sale_price.isnot(None))
            .filter(StockLevel.quantity > 0)
            .order_by(Product.name)
            .all()
        )
        product_choices = [(p.id, f"{p.name} ({p.sku})") for p in products]

        for item_form in self.sale_items:
            item_form.product_id.choices = product_choices


def admin_required(f):
    """Decorator to require admin access."""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash("Доступ заборонено. Потрібні права адміністратора.", "danger")
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)

    return decorated_function


@bp.route("/")
@login_required
@admin_required
def index():
    """Display list of all sales."""
    page = request.args.get("page", 1, type=int)
    per_page = 20  # Number of sales per page

    sales = (
        Sale.query.options(
            db.selectinload(Sale.client),
            db.selectinload(Sale.seller),
            db.selectinload(Sale.payment_method_ref),
        )
        .order_by(desc(Sale.sale_date))
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return render_template("sales/list_sales.html", title="Продажі", sales=sales)


@bp.route("/new", methods=["GET", "POST"])
@login_required
@admin_required
def create_sale():
    """Create a new sale."""
    form = SaleForm()

    if form.validate_on_submit():
        try:
            # Prepare sale items data
            sale_items_data = []
            for item_form in form.sale_items:
                if item_form.product_id.data and item_form.quantity.data:
                    sale_items_data.append(
                        SaleItemData(
                            product_id=item_form.product_id.data,
                            quantity=item_form.quantity.data,
                        )
                    )

            if not sale_items_data:
                flash("Додайте хоча б один товар до продажу.", "warning")
                # Get product data for template
                from app.models import StockLevel

                products = (
                    Product.query.join(StockLevel)
                    .filter(Product.current_sale_price.isnot(None))
                    .filter(StockLevel.quantity > 0)
                    .order_by(Product.name)
                    .all()
                )
                product_prices = {p.id: float(p.current_sale_price) for p in products}
                return render_template(
                    "sales/create_sale.html", title="Новий продаж", form=form, product_prices=product_prices
                )

            # Create sale using service
            sale = SalesService.create_sale(
                user_id=form.user_id.data,
                created_by_user_id=current_user.id,
                sale_items=sale_items_data,
                client_id=form.client_id.data if form.client_id.data else None,
                appointment_id=form.appointment_id.data.id if form.appointment_id.data else None,
                payment_method_id=form.payment_method_id.data,
                notes=form.notes.data,
            )

            flash(f"Продаж №{sale.id} успішно створено на суму {sale.total_amount:.2f} грн.", "success")
            return redirect(url_for("sales.view_sale", id=sale.id))

        except InsufficientStockError as e:
            flash(str(e), "danger")
        except ProductNotFoundError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash(f"Помилка при створенні продажу: {str(e)}", "danger")

    # Get product data for template (for GET request or when form has errors)
    from app.models import StockLevel

    products = (
        Product.query.join(StockLevel)
        .filter(Product.current_sale_price.isnot(None))
        .filter(StockLevel.quantity > 0)
        .order_by(Product.name)
        .all()
    )
    product_prices = {p.id: float(p.current_sale_price) for p in products}

    return render_template("sales/create_sale.html", title="Новий продаж", form=form, product_prices=product_prices)


@bp.route("/<int:id>")
@login_required
@admin_required
def view_sale(id):
    """View details of a specific sale."""
    sale = Sale.query.options(
        db.selectinload(Sale.client),
        db.selectinload(Sale.seller),
        db.selectinload(Sale.creator),
        db.selectinload(Sale.payment_method_ref),
        db.selectinload(Sale.items).selectinload(SaleItem.product),
    ).get_or_404(id)

    return render_template("sales/view_sale.html", title=f"Продаж №{sale.id}", sale=sale)
