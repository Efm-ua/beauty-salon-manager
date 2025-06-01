from datetime import date
from functools import wraps
from typing import Any

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    DecimalField,
    FieldList,
    FloatField,
    FormField,
    HiddenField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError
from wtforms_sqlalchemy.fields import QuerySelectField

from app.models import (
    Brand,
    GoodsReceipt,
    GoodsReceiptItem,
    InventoryAct,
    InventoryActItem,
    Product,
    ProductWriteOff,
    ProductWriteOffItem,
    StockLevel,
    User,
    WriteOffReason,
    db,
)


def admin_required(f):
    """Decorator for routes that require admin access."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash("Доступ заборонено", "danger")
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)

    return decorated_function


# Створення Blueprint
bp = Blueprint("products", __name__, url_prefix="/products")


# Форми
class BrandForm(FlaskForm):
    name = StringField("Назва бренду", validators=[DataRequired(), Length(max=100)])
    submit = SubmitField("Зберегти")

    def __init__(self, original_brand_name: str = "", *args: Any, **kwargs: Any) -> None:
        super(BrandForm, self).__init__(*args, **kwargs)
        self.original_brand_name = original_brand_name

    def validate_name(self, name: StringField) -> None:
        if name.data != self.original_brand_name:
            brand = Brand.query.filter_by(name=name.data).first()
            if brand:
                raise ValidationError("Бренд з такою назвою вже існує.")


class ProductForm(FlaskForm):
    name = StringField("Назва товару", validators=[DataRequired(), Length(max=200)])
    brand_id = SelectField("Бренд", coerce=int, validators=[DataRequired()])
    volume_value = FloatField(
        "Об'єм/Вага",
        validators=[Optional(), NumberRange(min=0)],
        render_kw={"placeholder": "0.0"},
    )
    volume_unit = StringField(
        "Одиниця виміру",
        validators=[Optional(), Length(max=20)],
        render_kw={"placeholder": "мл, г, шт"},
    )
    description = TextAreaField("Опис", validators=[Optional()])
    min_stock_level = IntegerField(
        "Мінімальний рівень запасів",
        validators=[DataRequired(), NumberRange(min=1)],
        default=1,
    )
    current_sale_price = FloatField(
        "Ціна продажу (грн)",
        validators=[Optional(), NumberRange(min=0)],
        render_kw={"placeholder": "0.00"},
    )
    last_cost_price = FloatField(
        "Собівартість (грн)",
        validators=[Optional(), NumberRange(min=0)],
        render_kw={"placeholder": "0.00"},
    )
    submit = SubmitField("Зберегти")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super(ProductForm, self).__init__(*args, **kwargs)
        # Заповнюємо список брендів
        self.brand_id.choices = [(brand.id, brand.name) for brand in Brand.query.order_by(Brand.name).all()]
        self.brand_id.choices.insert(0, (0, "Виберіть бренд..."))


class GoodsReceiptItemForm(FlaskForm):
    product_id = QuerySelectField(
        "Товар",
        query_factory=lambda: Product.query.join(Brand).order_by(Brand.name, Product.name).all(),
        get_label=lambda p: f"{p.brand.name} - {p.name} ({p.sku})",
        validators=[DataRequired()],
    )
    quantity = IntegerField("Кількість", validators=[DataRequired(), NumberRange(min=1)], default=1)
    cost_price = DecimalField(
        "Закупівельна ціна (грн)",
        places=2,
        validators=[DataRequired(), NumberRange(min=0.01)],
        render_kw={"placeholder": "0.00"},
    )


class GoodsReceiptForm(FlaskForm):
    receipt_number = StringField(
        "Номер накладної", validators=[Optional(), Length(max=50)], render_kw={"placeholder": "Необов'язково"}
    )
    receipt_date = DateField("Дата надходження", validators=[DataRequired()], default=date.today)
    items = FieldList(FormField(GoodsReceiptItemForm), min_entries=1, label="Товари")
    submit = SubmitField("Зберегти надходження")


# Маршрути для брендів
@bp.route("/brands")
@login_required
def brands_list() -> Any:
    """Список всіх брендів"""
    if not current_user.is_admin:
        flash("Доступ заборонено", "danger")
        return redirect(url_for("main.index"))

    page = request.args.get("page", 1, type=int)
    per_page = 20

    brands = Brand.query.order_by(Brand.name).paginate(page=page, per_page=per_page, error_out=False)

    return render_template("brands/list_brands.html", brands=brands, title="Бренди")


@bp.route("/brands/create", methods=["GET", "POST"])
@login_required
def brands_create() -> Any:
    """Створення нового бренду"""
    if not current_user.is_admin:
        flash("Доступ заборонено", "danger")
        return redirect(url_for("main.index"))

    form = BrandForm()

    if form.validate_on_submit():
        brand = Brand(name=form.name.data)  # type: ignore[call-arg]
        db.session.add(brand)
        db.session.commit()
        flash(f"Бренд '{brand.name}' успішно створено", "success")
        return redirect(url_for("products.brands_list"))

    return render_template("brands/create_brand.html", form=form, title="Створити бренд")


@bp.route("/brands/<int:id>/edit", methods=["GET", "POST"])
@login_required
def brands_edit(id: int) -> Any:
    """Редагування бренду"""
    if not current_user.is_admin:
        flash("Доступ заборонено", "danger")
        return redirect(url_for("main.index"))

    brand = db.session.get(Brand, id)
    if not brand:
        flash("Бренд не знайдено", "danger")
        return redirect(url_for("products.brands_list"))

    form = BrandForm(original_brand_name=brand.name, obj=brand)

    if form.validate_on_submit():
        brand.name = form.name.data
        db.session.commit()
        flash(f"Бренд '{brand.name}' успішно оновлено", "success")
        return redirect(url_for("products.brands_list"))

    return render_template("brands/edit_brand.html", form=form, brand=brand, title="Редагувати бренд")


@bp.route("/brands/<int:id>/delete", methods=["POST"])
@login_required
def brands_delete(id: int) -> Any:
    """Видалення бренду"""
    if not current_user.is_admin:
        flash("Доступ заборонено", "danger")
        return redirect(url_for("main.index"))

    brand = db.session.get(Brand, id)
    if not brand:
        flash("Бренд не знайдено", "danger")
        return redirect(url_for("products.brands_list"))

    # Перевіряємо чи є товари цього бренду
    if brand.products:
        products_count = Product.query.filter_by(brand_id=brand.id).count()
        flash(
            f"Неможливо видалити бренд '{brand.name}'. "
            f"Цей бренд має {products_count} товар(ів). "
            f"Спочатку видаліть всі товари цього бренду.",
            "danger",
        )
        return redirect(url_for("products.brands_list"))

    brand_name = brand.name
    db.session.delete(brand)
    db.session.commit()
    flash(f"Бренд '{brand_name}' успішно видалено", "success")

    return redirect(url_for("products.brands_list"))


# Маршрути для товарів
@bp.route("/")
@login_required
def index() -> Any:
    """Список всіх товарів"""
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "", type=str)
    brand_filter = request.args.get("brand", 0, type=int)
    per_page = 20

    query = Product.query.join(Brand).join(StockLevel)

    # Пошук
    if search:
        query = query.filter(
            db.or_(Product.name.contains(search), Product.sku.contains(search), Brand.name.contains(search))
        )

    # Фільтр по бренду
    if brand_filter:
        query = query.filter(Product.brand_id == brand_filter)

    products = query.order_by(Product.name).paginate(page=page, per_page=per_page, error_out=False)

    # Для фільтра по брендах
    brands = Brand.query.order_by(Brand.name).all()

    return render_template(
        "products/list_products.html",
        products=products,
        brands=brands,
        search=search,
        brand_filter=brand_filter,
        title="Товари",
    )


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create() -> Any:
    """Створення нового товару"""
    if not current_user.is_admin:
        flash("Доступ заборонено", "danger")
        return redirect(url_for("main.index"))

    form = ProductForm()

    if form.validate_on_submit():
        # Генеруємо SKU
        brand = db.session.get(Brand, form.brand_id.data)
        if not brand:
            flash("Обраний бренд не знайдено", "danger")
            return render_template("products/create_product.html", form=form, title="Створити товар")

        # Ensure form.name.data is not None
        product_name = form.name.data
        if not product_name:
            flash("Назва товару є обов'язковою", "danger")
            return render_template("products/create_product.html", form=form, title="Створити товар")

        sku = Product.generate_sku(brand.name, product_name)

        product = Product(  # type: ignore[call-arg]
            name=product_name,
            sku=sku,
            brand_id=form.brand_id.data,
            volume_value=form.volume_value.data,
            volume_unit=form.volume_unit.data,
            description=form.description.data,
            min_stock_level=form.min_stock_level.data,
            current_sale_price=form.current_sale_price.data,
            last_cost_price=form.last_cost_price.data,
        )

        db.session.add(product)
        db.session.commit()
        flash(f"Товар '{product.name}' (SKU: {product.sku}) успішно створено", "success")
        return redirect(url_for("products.index"))

    return render_template("products/create_product.html", form=form, title="Створити товар")


@bp.route("/<int:id>/view")
@login_required
def view(id: int) -> Any:
    """Перегляд деталей товару"""
    product = db.session.get(Product, id)
    if not product:
        flash("Товар не знайдено", "danger")
        return redirect(url_for("products.index"))

    # Отримуємо поточний рівень запасів
    stock_level = StockLevel.query.filter_by(product_id=product.id).first()

    return render_template(
        "products/view_product.html", product=product, stock_level=stock_level, title=f"Товар: {product.name}"
    )


@bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id: int) -> Any:
    """Редагування товару"""
    if not current_user.is_admin:
        flash("Доступ заборонено", "danger")
        return redirect(url_for("main.index"))

    product = db.session.get(Product, id)
    if not product:
        flash("Товар не знайдено", "danger")
        return redirect(url_for("products.index"))

    form = ProductForm(obj=product)

    if form.validate_on_submit():
        # Перевіряємо чи змінилася назва або бренд для регенерації SKU
        brand = db.session.get(Brand, form.brand_id.data)
        if not brand:
            flash("Обраний бренд не знайдено", "danger")
            return render_template("products/edit_product.html", form=form, product=product, title="Редагувати товар")

        # Ensure form.name.data is not None
        product_name = form.name.data
        if not product_name:
            flash("Назва товару є обов'язковою", "danger")
            return render_template("products/edit_product.html", form=form, product=product, title="Редагувати товар")

        # Якщо змінилась назва або бренд, генеруємо новий SKU
        if product.name != product_name or product.brand_id != form.brand_id.data:
            new_sku = Product.generate_sku(brand.name, product_name)
            product.sku = new_sku

        product.name = product_name
        product.brand_id = form.brand_id.data
        product.volume_value = form.volume_value.data
        product.volume_unit = form.volume_unit.data
        product.description = form.description.data
        product.min_stock_level = form.min_stock_level.data
        product.current_sale_price = form.current_sale_price.data
        product.last_cost_price = form.last_cost_price.data

        db.session.commit()
        flash(f"Товар '{product.name}' успішно оновлено", "success")
        return redirect(url_for("products.view", id=product.id))

    return render_template("products/edit_product.html", form=form, product=product, title="Редагувати товар")


@bp.route("/<int:id>/delete", methods=["POST"])
@login_required
def delete(id: int) -> Any:
    """Видалення товару"""
    if not current_user.is_admin:
        flash("Доступ заборонено", "danger")
        return redirect(url_for("main.index"))

    product = db.session.get(Product, id)
    if not product:
        flash("Товар не знайдено", "danger")
        return redirect(url_for("products.index"))

    product_name = product.name
    db.session.delete(product)
    db.session.commit()
    flash(f"Товар '{product_name}' успішно видалено", "success")

    return redirect(url_for("products.index"))


# Маршрут для перегляду залишків
@bp.route("/stock")
@login_required
def stock_levels() -> Any:
    """Перегляд залишків товарів"""
    page = request.args.get("page", 1, type=int)
    search = request.args.get("search", "", type=str)
    brand_filter = request.args.get("brand", 0, type=int)
    low_stock = request.args.get("low_stock", False, type=bool)
    per_page = 20

    # Start with Product query and join with related tables for filtering
    query = Product.query.join(StockLevel).join(Brand)

    # Пошук
    if search:
        query = query.filter(
            db.or_(Product.name.contains(search), Product.sku.contains(search), Brand.name.contains(search))
        )

    # Фільтр по бренду
    if brand_filter:
        query = query.filter(Product.brand_id == brand_filter)

    # Фільтр низьких залишків
    if low_stock:
        query = query.filter(StockLevel.quantity <= Product.min_stock_level)

    # Paginate the results (this gives us Product objects)
    products_paginated = query.order_by(Product.name).paginate(page=page, per_page=per_page, error_out=False)

    # Create a custom pagination object that returns tuples
    class StockDataPagination:
        def __init__(self, product_pagination: Any) -> None:
            self.page = product_pagination.page
            self.pages = product_pagination.pages
            self.per_page = product_pagination.per_page
            self.total = product_pagination.total
            self.has_prev = product_pagination.has_prev
            self.has_next = product_pagination.has_next
            self.prev_num = product_pagination.prev_num
            self.next_num = product_pagination.next_num

            # Create items as tuples of (product, stock_level, brand)
            self.items = []
            for product in product_pagination.items:
                stock_level = StockLevel.query.filter_by(product_id=product.id).first()
                brand = db.session.get(Brand, product.brand_id)
                self.items.append((product, stock_level, brand))

        def iter_pages(self, *args: Any, **kwargs: Any) -> Any:
            # Delegate to the original pagination object
            return products_paginated.iter_pages(*args, **kwargs)

    stock_data = StockDataPagination(products_paginated)

    # Для фільтра по брендах
    brands = Brand.query.order_by(Brand.name).all()

    return render_template(
        "stock_levels/view_stock.html",
        stock_data=stock_data,
        brands=brands,
        search=search,
        brand_filter=brand_filter,
        low_stock=low_stock,
        title="Залишки товарів",
    )


# Маршрути для надходження товарів
@bp.route("/goods_receipts")
@login_required
@admin_required
def goods_receipts_list() -> Any:
    """Список всіх документів надходження"""
    page = request.args.get("page", 1, type=int)
    per_page = 20

    receipts = GoodsReceipt.query.order_by(GoodsReceipt.receipt_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template("goods_receipts/list_goods_receipts.html", receipts=receipts, title="Надходження товарів")


@bp.route("/goods_receipts/new", methods=["GET", "POST"])
@login_required
@admin_required
def goods_receipts_create() -> Any:
    """Створення нового документа надходження"""
    form = GoodsReceiptForm()

    if form.validate_on_submit():
        receipt = GoodsReceipt(
            receipt_number=form.receipt_number.data, receipt_date=form.receipt_date.data, user_id=current_user.id
        )
        db.session.add(receipt)

        for item_form in form.items:
            product = item_form.product_id.data
            quantity = item_form.quantity.data
            cost_price = item_form.cost_price.data

            # Створюємо запис про надходження товару
            receipt_item = GoodsReceiptItem(
                product_id=product.id,
                quantity_received=quantity,
                quantity_remaining=quantity,
                cost_price_per_unit=cost_price,
                receipt_date=form.receipt_date.data,
            )
            receipt.items.append(receipt_item)

            # Оновлюємо залишок на складі
            stock_level = StockLevel.query.filter_by(product_id=product.id).first()
            if stock_level:
                stock_level.quantity += quantity
            else:
                stock_level = StockLevel(product_id=product.id, quantity=quantity)
                db.session.add(stock_level)

            # Оновлюємо останню закупівельну ціну товару
            product.last_cost_price = cost_price

        db.session.commit()
        flash("Надходження товарів успішно збережено", "success")
        return redirect(url_for("products.goods_receipts_list"))

    return render_template("goods_receipts/create_goods_receipt.html", form=form, title="Нове надходження")


@bp.route("/goods_receipts/<int:id>")
@login_required
@admin_required
def goods_receipts_view(id: int) -> Any:
    """Перегляд деталей документа надходження"""
    receipt = db.session.get(GoodsReceipt, id)
    if not receipt:
        flash("Документ надходження не знайдено", "danger")
        return redirect(url_for("products.goods_receipts_list"))

    return render_template("goods_receipts/view_goods_receipt.html", receipt=receipt, title="Деталі надходження")


# =================== WRITE-OFF FUNCTIONALITY ===================


# Форми для списання
class WriteOffReasonForm(FlaskForm):
    name = StringField("Назва причини", validators=[DataRequired(), Length(max=100)])
    is_active = SelectField("Статус", choices=[(1, "Активна"), (0, "Неактивна")], coerce=int, default=1)
    submit = SubmitField("Зберегти")

    def __init__(self, original_reason_name: str = "", *args: Any, **kwargs: Any) -> None:
        super(WriteOffReasonForm, self).__init__(*args, **kwargs)
        self.original_reason_name = original_reason_name

    def validate_name(self, name: StringField) -> None:
        if name.data != self.original_reason_name:
            reason = WriteOffReason.query.filter_by(name=name.data).first()
            if reason:
                raise ValidationError("Причина списання з такою назвою вже існує.")


class WriteOffItemForm(FlaskForm):
    product_id = QuerySelectField(
        "Товар",
        query_factory=lambda: Product.query.join(Brand).order_by(Brand.name, Product.name).all(),
        get_label=lambda p: f"{p.brand.name} - {p.name} ({p.sku}) - залишок: "
        f"{p.stock_records[0].quantity if p.stock_records else 0} шт.",
        validators=[DataRequired()],
    )
    quantity = IntegerField("Кількість", validators=[DataRequired(), NumberRange(min=1)], default=1)


class ProductWriteOffForm(FlaskForm):
    reason_id = SelectField("Причина списання", coerce=int, validators=[DataRequired()])
    write_off_date = DateField("Дата списання", validators=[DataRequired()], default=date.today)
    notes = TextAreaField("Примітки", validators=[Optional()])
    items = FieldList(FormField(WriteOffItemForm), min_entries=1, label="Товари для списання")
    submit = SubmitField("Списати товари")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super(ProductWriteOffForm, self).__init__(*args, **kwargs)
        from app.services.inventory_service import InventoryService

        # Заповнюємо список причин списання
        reasons = InventoryService.get_active_write_off_reasons()
        self.reason_id.choices = [(reason.id, reason.name) for reason in reasons]
        self.reason_id.choices.insert(0, (0, "Виберіть причину..."))


# Маршрути для причин списання
@bp.route("/write_off_reasons")
@login_required
@admin_required
def write_off_reasons_list() -> Any:
    """Список всіх причин списання"""
    page = request.args.get("page", 1, type=int)
    per_page = 20

    from app.services.inventory_service import InventoryService

    reasons = InventoryService.get_all_write_off_reasons()

    # Manual pagination
    total = len(reasons)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_reasons = reasons[start:end]

    # Create a simple pagination object
    class SimplePagination:
        def __init__(self, page: int, per_page: int, total: int, items: Any):
            self.page = page
            self.per_page = per_page
            self.total = total
            self.items = items
            self.pages = (total - 1) // per_page + 1 if total > 0 else 1
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None

        def iter_pages(self, left_edge: int = 2, left_current: int = 2, right_current: int = 3, right_edge: int = 2):
            last = self.pages
            for num in range(1, last + 1):
                if (
                    num <= left_edge
                    or (num > self.page - left_current - 1 and num < self.page + right_current)
                    or num > last - right_edge
                ):
                    yield num

    pagination = SimplePagination(page, per_page, total, paginated_reasons)

    return render_template("write_offs/list_reasons.html", reasons=pagination, title="Причини списання")


@bp.route("/write_off_reasons/create", methods=["GET", "POST"])
@login_required
@admin_required
def write_off_reasons_create() -> Any:
    """Створення нової причини списання"""
    form = WriteOffReasonForm()

    if form.validate_on_submit():
        from app.services.inventory_service import InventoryService

        try:
            if not form.name.data:
                flash("Назва причини є обов'язковою", "danger")
                return render_template("write_offs/create_reason.html", form=form, title="Створити причину списання")

            is_active = form.is_active.data == 1
            reason = InventoryService.create_write_off_reason(form.name.data, is_active)
            flash(f"Причина списання '{reason.name}' успішно створена", "success")
            return redirect(url_for("products.write_off_reasons_list"))
        except ValueError as e:
            flash(str(e), "danger")

    return render_template("write_offs/create_reason.html", form=form, title="Створити причину списання")


@bp.route("/write_off_reasons/<int:id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def write_off_reasons_edit(id: int) -> Any:
    """Редагування причини списання"""
    reason = db.session.get(WriteOffReason, id)
    if not reason:
        flash("Причину списання не знайдено", "danger")
        return redirect(url_for("products.write_off_reasons_list"))

    # Don't use obj=reason to avoid boolean confusion, create form separately
    form = WriteOffReasonForm(original_reason_name=reason.name)

    # Manually populate form data on GET request
    if request.method == "GET":
        form.name.data = reason.name
        form.is_active.data = 1 if reason.is_active else 0

    if form.validate_on_submit():
        from app.services.inventory_service import InventoryService

        try:
            if not form.name.data:
                flash("Назва причини є обов'язковою", "danger")
                return render_template(
                    "write_offs/edit_reason.html", form=form, reason=reason, title="Редагувати причину списання"
                )

            is_active = form.is_active.data == 1
            InventoryService.update_write_off_reason(reason.id, form.name.data, is_active)
            flash(f"Причина списання '{reason.name}' успішно оновлена", "success")
            return redirect(url_for("products.write_off_reasons_list"))
        except ValueError as e:
            flash(str(e), "danger")

    return render_template("write_offs/edit_reason.html", form=form, reason=reason, title="Редагувати причину списання")


# Маршрути для документів списання
@bp.route("/write_offs")
@login_required
@admin_required
def write_offs_list() -> Any:
    """Список всіх документів списання"""
    page = request.args.get("page", 1, type=int)
    per_page = 20

    from app.models import ProductWriteOff

    write_offs = ProductWriteOff.query.order_by(ProductWriteOff.write_off_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template("write_offs/list_write_offs.html", write_offs=write_offs, title="Списання товарів")


@bp.route("/write_offs/new", methods=["GET", "POST"])
@login_required
@admin_required
def write_offs_create() -> Any:
    """Створення нового документа списання"""
    form = ProductWriteOffForm()

    if form.validate_on_submit():
        from app.services.inventory_service import InventoryService, WriteOffItemData

        try:
            # Перетворюємо дані форми в WriteOffItemData
            write_off_items = []
            for item_form in form.items:
                if item_form.product_id.data and item_form.quantity.data:
                    write_off_items.append(
                        WriteOffItemData(product_id=item_form.product_id.data.id, quantity=item_form.quantity.data)
                    )

            if not write_off_items:
                flash("Додайте хоча б один товар для списання", "warning")
                return render_template("write_offs/create_write_off.html", form=form, title="Нове списання")

            # Створюємо списання
            write_off = InventoryService.create_write_off(
                user_id=current_user.id,
                reason_id=form.reason_id.data,
                write_off_items=write_off_items,
                notes=form.notes.data,
                write_off_date=form.write_off_date.data,
            )

            flash(f"Списання №{write_off.id} успішно створено", "success")
            return redirect(url_for("products.write_offs_view", id=write_off.id))

        except Exception as e:
            flash(f"Помилка при створенні списання: {str(e)}", "danger")

    return render_template("write_offs/create_write_off.html", form=form, title="Нове списання")


@bp.route("/write_offs/<int:id>")
@login_required
@admin_required
def write_offs_view(id: int) -> Any:
    """Переглянути акт списання товарів"""
    write_off = db.session.get(ProductWriteOff, id)
    if not write_off:
        flash("Акт списання не знайдено", "danger")
        return redirect(url_for("products.write_offs_list"))

    return render_template("write_offs/view_write_off.html", write_off=write_off, title="Перегляд акту списання")


# Форми для інвентаризації
class InventoryActItemForm(FlaskForm):
    product_id = HiddenField()
    product_name = StringField("Товар", render_kw={"readonly": True})
    expected_quantity = IntegerField("Планова кількість", render_kw={"readonly": True})
    actual_quantity = IntegerField(
        "Фактична кількість",
        validators=[Optional(), NumberRange(min=0)],
        render_kw={"class": "form-control", "min": "0"},
    )


class InventoryActEditForm(FlaskForm):
    notes = TextAreaField("Примітки", validators=[Optional()], render_kw={"class": "form-control", "rows": "3"})
    items = FieldList(FormField(InventoryActItemForm), min_entries=0)
    save_progress_submit = SubmitField("Зберегти прогрес", render_kw={"class": "btn btn-primary"})
    complete_act_submit = SubmitField("Провести інвентаризацію", render_kw={"class": "btn btn-success"})


# Маршрути інвентаризації
@bp.route("/inventory_acts")
@login_required
@admin_required
def inventory_acts_list() -> Any:
    """Список всіх актів інвентаризації"""
    page = request.args.get("page", 1, type=int)
    per_page = 20

    acts = (
        InventoryAct.query.join(User, InventoryAct.user_id == User.id)
        .order_by(InventoryAct.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return render_template("inventory_acts/list_acts.html", acts=acts, title="Акти інвентаризації")


@bp.route("/inventory_acts/new", methods=["POST"])
@login_required
@admin_required
def inventory_acts_create() -> Any:
    """Створити новий акт інвентаризації"""
    try:
        # Створюємо новий акт
        act = InventoryAct(user_id=current_user.id)
        db.session.add(act)
        db.session.flush()  # Отримуємо ID акту

        # Отримуємо всі активні товари з їх залишками
        products_with_stock = (
            db.session.query(Product, StockLevel)
            .join(StockLevel, Product.id == StockLevel.product_id)
            .join(Brand, Product.brand_id == Brand.id)
            .order_by(Brand.name, Product.name)
            .all()
        )

        # Створюємо позиції акту для всіх товарів
        for product, stock_level in products_with_stock:
            item = InventoryActItem(
                inventory_act_id=act.id, product_id=product.id, expected_quantity=stock_level.quantity
            )
            db.session.add(item)

        db.session.commit()
        flash(f"Акт інвентаризації №{act.id} успішно створено", "success")
        return redirect(url_for("products.inventory_acts_edit", act_id=act.id))

    except Exception as e:
        db.session.rollback()
        flash(f"Помилка при створенні акту інвентаризації: {str(e)}", "danger")
        return redirect(url_for("products.inventory_acts_list"))


@bp.route("/inventory_acts/<int:act_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def inventory_acts_edit(act_id: int) -> Any:
    """Редагувати акт інвентаризації"""
    act = db.session.get(InventoryAct, act_id)
    if not act:
        flash("Акт інвентаризації не знайдено", "danger")
        return redirect(url_for("products.inventory_acts_list"))

    if act.status == "completed":
        flash("Неможливо редагувати завершений акт інвентаризації", "warning")
        return redirect(url_for("products.inventory_acts_view", act_id=act_id))

    form = InventoryActEditForm()

    if request.method == "GET":
        # Заповнюємо форму даними з бази
        form.notes.data = act.notes

        # Очищуємо та заповнюємо список позицій
        while len(form.items) > 0:
            form.items.pop_entry()

        for item in act.items:  # type: ignore[attr-defined]
            item_form = InventoryActItemForm()
            item_form.product_id.data = str(item.product_id)
            item_form.product_name.data = f"{item.product.brand.name} - {item.product.name} ({item.product.sku})"
            item_form.expected_quantity.data = item.expected_quantity
            item_form.actual_quantity.data = item.actual_quantity
            form.items.append_entry(item_form)

    if form.validate_on_submit():
        try:
            # Оновлюємо примітки
            act.notes = form.notes.data

            # Оновлюємо позиції акту
            for form_item in form.items:
                product_id = int(form_item.product_id.data)
                actual_quantity = form_item.actual_quantity.data

                # Знаходимо відповідну позицію в базі
                item = next((item for item in act.items if item.product_id == product_id), None)  # type: ignore[attr-defined]
                if item:
                    item.actual_quantity = actual_quantity
                    item.calculate_discrepancy()

            # Перевіряємо, яка кнопка була натиснута
            if form.complete_act_submit.data:
                # Провести інвентаризацію
                return redirect(url_for("products.inventory_acts_complete", act_id=act_id))
            else:
                # Зберегти прогрес
                act.status = "in_progress" if any(item.actual_quantity is not None for item in act.items) else "new"  # type: ignore[attr-defined]

            db.session.commit()
            flash("Прогрес інвентаризації збережено", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Помилка при збереженні: {str(e)}", "danger")

    return render_template("inventory_acts/edit_act.html", form=form, act=act, title="Редагувати акт інвентаризації")


@bp.route("/inventory_acts/<int:act_id>/complete", methods=["POST"])
@login_required
@admin_required
def inventory_acts_complete(act_id: int) -> Any:
    """Провести акт інвентаризації"""
    act = db.session.get(InventoryAct, act_id)
    if not act:
        flash("Акт інвентаризації не знайдено", "danger")
        return redirect(url_for("products.inventory_acts_list"))

    if act.status == "completed":
        flash("Акт інвентаризації вже було проведено", "warning")
        return redirect(url_for("products.inventory_acts_view", act_id=act_id))

    try:
        items_updated = 0

        for item in act.items:  # type: ignore[attr-defined]
            if item.actual_quantity is not None:
                # Оновлюємо залишки товару
                stock_level = StockLevel.query.filter_by(product_id=item.product_id).first()
                if stock_level:
                    stock_level.quantity = item.actual_quantity
                    items_updated += 1

        # Міняємо статус акту
        act.status = "completed"

        db.session.commit()
        flash(
            f"Акт інвентаризації №{act.id} успішно проведено. " f"Оновлено залишки для {items_updated} товарів.",
            "success",
        )

    except Exception as e:
        db.session.rollback()
        flash(f"Помилка при проведенні інвентаризації: {str(e)}", "danger")

    return redirect(url_for("products.inventory_acts_view", act_id=act_id))


@bp.route("/inventory_acts/<int:act_id>")
@login_required
@admin_required
def inventory_acts_view(act_id: int) -> Any:
    """Переглянути деталі акту інвентаризації"""
    act = db.session.get(InventoryAct, act_id)
    if not act:
        flash("Акт інвентаризації не знайдено", "danger")
        return redirect(url_for("products.inventory_acts_list"))

    return render_template("inventory_acts/view_act.html", act=act, title=f"Акт інвентаризації №{act.id}")
