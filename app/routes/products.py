from typing import Any

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import (
    FloatField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from app.models import Brand, Product, StockLevel, db

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

        def iter_pages(self, *args, **kwargs):  # type: ignore[no-untyped-def]
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
