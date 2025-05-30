from typing import Any

from flask import Blueprint, flash, jsonify, redirect, render_template, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import FloatField, IntegerField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.models import AppointmentService, Service, db

# Створення Blueprint
bp = Blueprint("services", __name__, url_prefix="/services")


# Форма для послуги
class ServiceForm(FlaskForm):
    name = StringField("Назва", validators=[DataRequired(), Length(max=100)])
    description = TextAreaField("Опис", validators=[Optional()])
    duration = IntegerField("Тривалість (хв)", validators=[DataRequired(), NumberRange(min=5, max=480)])
    base_price = FloatField(
        "Базова ціна (грн)",
        validators=[Optional(), NumberRange(min=0)],
        render_kw={"placeholder": "0.00"},
    )
    submit = SubmitField("Зберегти")


# Список всіх послуг (доступно для всіх користувачів)
@bp.route("/")
@login_required
def index() -> str:
    services = Service.query.order_by(Service.name).all()

    return render_template(
        "services/index.html",
        title="Послуги",
        services=services,
        is_admin=current_user.is_admin,
    )


# Створення нової послуги (тільки для адміністраторів)
@bp.route("/create", methods=["GET", "POST"])
@login_required
def create() -> Any:
    # Перевірка прав доступу
    if not current_user.is_admin:
        flash("У вас немає прав для створення нових послуг", "danger")
        return redirect(url_for("services.index"))

    form = ServiceForm()

    if form.validate_on_submit():
        service = Service()
        service.name = form.name.data
        service.description = form.description.data
        service.duration = form.duration.data
        service.base_price = form.base_price.data

        db.session.add(service)
        db.session.commit()

        flash("Послугу успішно додано!", "success")
        return redirect(url_for("services.index"))

    return render_template("services/create.html", title="Нова послуга", form=form)


# Редагування послуги (тільки для адміністраторів)
@bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id: int) -> Any:
    # Перевірка прав доступу
    if not current_user.is_admin:
        flash("У вас немає прав для редагування послуг", "danger")
        return redirect(url_for("services.index"))

    service = Service.query.get_or_404(id)
    form = ServiceForm(obj=service)

    if form.validate_on_submit():
        form.populate_obj(service)
        db.session.commit()

        flash("Послугу успішно оновлено!", "success")
        return redirect(url_for("services.index"))

    return render_template(
        "services/edit.html",
        title=f"Редагування послуги: {service.name}",
        form=form,
        service=service,
    )


# Видалення послуги (тільки для адміністраторів)
@bp.route("/<int:id>/delete", methods=["POST"])
@login_required
def delete(id: int) -> Any:
    # Перевірка прав доступу
    if not current_user.is_admin:
        flash("У вас немає прав для видалення послуг", "danger")
        return redirect(url_for("services.index"))

    service = Service.query.get_or_404(id)

    # Перевірка, чи використовується послуга
    usage_count = AppointmentService.query.filter_by(service_id=service.id).count()

    if usage_count > 0:
        flash(
            f"Не можна видалити послугу, оскільки вона використовується в {usage_count} записах!",
            "danger",
        )
        return redirect(url_for("services.index"))

    # Видалення послуги
    db.session.delete(service)
    db.session.commit()

    flash("Послугу успішно видалено!", "success")
    return redirect(url_for("services.index"))


# API для отримання інформації про послугу
@bp.route("/api/<int:id>")
@login_required
def api_service(id: int) -> Any:
    service = Service.query.get_or_404(id)

    return jsonify(
        {
            "id": service.id,
            "name": service.name,
            "description": service.description,
            "duration": service.duration,
            "base_price": service.base_price,
        }
    )


# API для отримання списку послуг
@bp.route("/api/list")
@login_required
def api_list() -> Any:
    services = Service.query.order_by(Service.name).all()

    result = []
    for service in services:
        result.append(
            {
                "id": service.id,
                "name": service.name,
                "duration": service.duration,
                "base_price": service.base_price,
            }
        )

    return jsonify(result)
