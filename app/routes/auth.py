from typing import Any

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import StringField  # type: ignore
from wtforms import BooleanField, IntegerField, PasswordField, SubmitField
from wtforms.fields import DecimalField
from wtforms.validators import NumberRange  # type: ignore
from wtforms.validators import (DataRequired, EqualTo, Length, Optional,
                                ValidationError)

from app.models import User, db

# Створення Blueprint
bp = Blueprint("auth", __name__, url_prefix="/auth")


# Форма для входу
class LoginForm(FlaskForm):
    username = StringField("Логін", validators=[DataRequired()])
    password = PasswordField("Пароль", validators=[DataRequired()])
    remember_me = BooleanField("Запам'ятати мене")
    submit = SubmitField("Увійти")


# Форма для реєстрації
class RegistrationForm(FlaskForm):
    username = StringField("Логін", validators=[DataRequired(), Length(min=3, max=20)])
    full_name = StringField("Повне ім'я", validators=[DataRequired(), Length(max=100)])
    password = PasswordField("Пароль", validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField("Повторіть пароль", validators=[DataRequired(), EqualTo("password")])
    is_admin = BooleanField("Адміністратор")
    is_active_master = BooleanField("Активний майстер")
    schedule_display_order = IntegerField(
        "Порядок відображення у розкладі",
        validators=[
            Optional(),
            NumberRange(min=1, message="Порядок відображення повинен бути позитивним числом"),
        ],
    )
    submit = SubmitField("Зареєструватися")

    def validate_username(self, username: StringField) -> None:
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError("Цей логін вже використовується. Виберіть інший.")

    def validate_schedule_display_order(self, field: IntegerField) -> None:
        if self.is_active_master.data:
            # Порядок відображення обов'язковий для активного майстра
            if field.data is None:
                raise ValidationError("Порядок відображення обов'язковий для активного майстра")

            # Перевірка на унікальність порядку відображення серед активних майстрів
            exists = (
                User.query.filter(User.schedule_display_order == field.data).filter_by(is_active_master=True).first()
            )
            if exists:
                raise ValidationError(f"Порядок відображення {field.data} вже використовується іншим активним майстром")


# Форма для редагування користувача
class UserEditForm(FlaskForm):
    full_name = StringField("Повне ім'я", validators=[DataRequired(), Length(max=100)])
    is_admin = BooleanField("Адміністратор")
    is_active_master = BooleanField("Активний майстер")
    schedule_display_order = IntegerField(
        "Порядок відображення у розкладі",
        validators=[
            Optional(),
            NumberRange(min=1, message="Порядок відображення повинен бути позитивним числом"),
        ],
    )
    configurable_commission_rate = DecimalField(
        "Комісійна ставка (%)",
        validators=[
            Optional(),
            NumberRange(min=0, max=100, message="Комісійна ставка повинна бути від 0 до 100 відсотків"),
        ],
    )
    submit = SubmitField("Зберегти")

    def validate_schedule_display_order(self, field: IntegerField) -> None:
        if self.is_active_master.data:
            # Порядок відображення обов'язковий для активного майстра
            if field.data is None:
                raise ValidationError("Порядок відображення обов'язковий для активного майстра")

            # Перевірка на унікальність порядку відображення серед активних майстрів
            user_id = request.view_args.get("id")  # ID поточного користувача
            exists = (
                User.query.filter(
                    User.schedule_display_order == field.data,
                    User.id != user_id,
                )
                .filter_by(is_active_master=True)
                .first()
            )
            if exists:
                raise ValidationError(f"Порядок відображення {field.data} вже використовується іншим активним майстром")


# Форма для зміни пароля
class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Поточний пароль", validators=[DataRequired()])
    new_password = PasswordField("Новий пароль", validators=[DataRequired(), Length(min=6)])
    new_password2 = PasswordField("Повторіть новий пароль", validators=[DataRequired(), EqualTo("new_password")])
    submit = SubmitField("Змінити пароль")


# Маршрут для входу
@bp.route("/login", methods=["GET", "POST"])
def login() -> Any:
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if user is None or not check_password_hash(user.password, form.password.data):
            flash("Невірний логін або пароль", "danger")
            return redirect(url_for("auth.login"))

        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get("next")
        if not next_page or not next_page.startswith("/"):
            next_page = url_for("main.index")

        flash(f"Ласкаво просимо, {user.full_name}!", "success")
        return redirect(next_page)

    return render_template("auth/login.html", title="Вхід", form=form)


# Маршрут для виходу
@bp.route("/logout")
@login_required
def logout() -> Any:
    logout_user()
    flash("Ви вийшли з системи", "info")
    return redirect(url_for("main.index"))


# Маршрут для реєстрації (доступний тільки для адміністраторів)
@bp.route("/register", methods=["GET", "POST"])
@login_required
def register() -> Any:
    if not current_user.is_admin:
        flash("Тільки адміністратори можуть додавати нових користувачів", "danger")
        return redirect(url_for("main.index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        # Визначаємо значення is_active_master
        is_admin = form.is_admin.data
        # Якщо is_active_master не передано в формі явно
        # Визначаємо значення за замовчуванням на основі ролі
        is_active_master = form.is_active_master.data
        if "is_active_master" not in request.form:
            # За замовчуванням: якщо користувач є майстром (не адмін), то він є активним майстром
            # якщо користувач є адміном, то він не є активним майстром
            is_active_master = not is_admin

        # Визначаємо значення schedule_display_order
        schedule_display_order = None
        if is_active_master and form.schedule_display_order.data:
            schedule_display_order = form.schedule_display_order.data
        else:
            # Для неактивних майстрів та адмінів явно встановлюємо None
            schedule_display_order = None

        user = User(
            username=form.username.data,
            full_name=form.full_name.data,
            password=generate_password_hash(form.password.data),
            is_admin=is_admin,
            is_active_master=is_active_master,
            schedule_display_order=schedule_display_order,
        )
        db.session.add(user)
        db.session.commit()
        flash(f"Користувач {form.full_name.data} успішно зареєстрований!", "success")
        return redirect(url_for("auth.users"))

    return render_template("auth/register.html", title="Реєстрація нового користувача", form=form)


# Маршрут для створення першого адміністратора (використовується при першому запуску)
@bp.route("/initialize", methods=["GET", "POST"])
def initialize() -> Any:
    # Перевірка, чи є вже користувачі в системі
    if User.query.count() > 0:
        flash("Система вже ініціалізована", "info")
        return redirect(url_for("main.index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        admin = User(
            username=form.username.data,
            full_name=form.full_name.data,
            password=generate_password_hash(form.password.data),
            is_admin=True,
            is_active_master=False,  # Адміністратор за замовчуванням не є активним майстром
        )
        db.session.add(admin)
        db.session.commit()
        flash("Адміністратор успішно створений! Тепер ви можете увійти.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/initialize.html", title="Створення адміністратора", form=form)


# Новий маршрут для списку користувачів (тільки для адміністраторів)
@bp.route("/users")
@login_required
def users() -> Any:
    if not current_user.is_admin:
        flash("Тільки адміністратори мають доступ до цієї сторінки", "danger")
        return redirect(url_for("main.index"))

    users = User.query.order_by(User.full_name).all()
    return render_template("auth/users.html", title="Користувачі", users=users)


# Новий маршрут для редагування користувача (тільки для адміністраторів)
@bp.route("/users/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_user(id: int) -> Any:
    if not current_user.is_admin:
        flash("Тільки адміністратори можуть редагувати користувачів", "danger")
        return redirect(url_for("main.index"))

    user = User.query.get_or_404(id)
    form = UserEditForm(obj=user)

    if form.validate_on_submit():
        user.full_name = form.full_name.data
        user.is_admin = form.is_admin.data
        user.is_active_master = form.is_active_master.data

        # Встановлюємо schedule_display_order
        if form.is_active_master.data:
            user.schedule_display_order = form.schedule_display_order.data
        else:
            # Якщо користувач не є активним майстром, встановлюємо None
            user.schedule_display_order = None

        # Встановлюємо configurable_commission_rate
        user.configurable_commission_rate = form.configurable_commission_rate.data

        db.session.commit()
        flash(f"Користувач {user.full_name} успішно оновлений!", "success")
        return redirect(url_for("auth.users"))

    return render_template(
        "auth/edit_user.html",
        title=f"Редагування користувача: {user.full_name}",
        form=form,
        user=user,
    )


# Маршрут для зміни статусу адміністратора (тільки для адміністраторів)
@bp.route("/users/<int:id>/toggle_admin", methods=["POST"])
@login_required
def toggle_admin(id: int) -> Any:
    if not current_user.is_admin:
        flash("Тільки адміністратори можуть змінювати статус користувачів", "danger")
        return redirect(url_for("main.index"))

    # Перевірка, щоб користувач не зміг понизити сам себе
    if id == current_user.id:
        flash("Ви не можете змінити свій власний статус адміністратора", "danger")
        return redirect(url_for("auth.users"))

    user = User.query.get_or_404(id)
    user.is_admin = not user.is_admin

    # Автоматично встановлюємо is_active_master на основі is_admin
    if user.is_admin:
        # Якщо користувач став адміном, він не є активним майстром
        user.is_active_master = False
        # Скидаємо порядок відображення
        user.schedule_display_order = None
    else:
        # Якщо користувач став майстром (не адміном), робимо його активним майстром
        user.is_active_master = True

    db.session.commit()

    if user.is_admin:
        flash(f"Користувач {user.full_name} тепер має права адміністратора", "success")
    else:
        flash(f"Користувач {user.full_name} тепер має права майстра", "success")

    return redirect(url_for("auth.users"))


# Маршрут для зміни пароля (доступний для всіх користувачів)
@bp.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password() -> Any:
    form = ChangePasswordForm()

    if form.validate_on_submit():
        if not check_password_hash(current_user.password, form.current_password.data):
            flash("Невірний поточний пароль", "danger")
            return redirect(url_for("auth.change_password"))

        current_user.password = generate_password_hash(form.new_password.data)
        db.session.commit()
        flash("Ваш пароль успішно змінено!", "success")
        return redirect(url_for("main.index"))

    return render_template("auth/change_password.html", title="Зміна пароля", form=form)
