from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, ValidationError

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
    password2 = PasswordField(
        "Повторіть пароль", validators=[DataRequired(), EqualTo("password")]
    )
    submit = SubmitField("Зареєструватися")

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError("Цей логін вже використовується. Виберіть інший.")


# Маршрут для входу
@bp.route("/login", methods=["GET", "POST"])
def login():
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
def logout():
    logout_user()
    flash("Ви вийшли з системи", "info")
    return redirect(url_for("main.index"))


# Маршрут для реєстрації (доступний тільки для адміністраторів)
@bp.route("/register", methods=["GET", "POST"])
@login_required
def register():
    if not current_user.is_admin:
        flash("Тільки адміністратори можуть додавати нових користувачів", "danger")
        return redirect(url_for("main.index"))

    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            full_name=form.full_name.data,
            password=generate_password_hash(form.password.data),
        )
        db.session.add(user)
        db.session.commit()
        flash(f"Користувач {form.full_name.data} успішно зареєстрований!", "success")
        return redirect(url_for("auth.login"))

    return render_template(
        "auth/register.html", title="Реєстрація нового майстра", form=form
    )


# Створення першого адміністратора (використовується при першому запуску)
@bp.route("/initialize", methods=["GET", "POST"])
def initialize():
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
        )
        db.session.add(admin)
        db.session.commit()
        flash("Адміністратор успішно створений! Тепер ви можете увійти.", "success")
        return redirect(url_for("auth.login"))

    return render_template(
        "auth/initialize.html", title="Створення адміністратора", form=form
    )
