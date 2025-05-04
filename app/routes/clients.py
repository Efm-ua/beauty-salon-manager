from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional, ValidationError
from sqlalchemy import and_, or_

from app.models import Appointment, Client, db

# Створення Blueprint
bp = Blueprint("clients", __name__, url_prefix="/clients")


# Форма для клієнта
class ClientForm(FlaskForm):
    name = StringField("Ім'я", validators=[DataRequired(), Length(max=100)])
    phone = StringField("Телефон", validators=[DataRequired(), Length(max=20)])
    email = StringField("Email", validators=[Optional(), Email(), Length(max=120)])
    notes = TextAreaField("Примітки", validators=[Optional()])
    submit = SubmitField("Зберегти")

    def validate_phone(self, phone):
        client = Client.query.filter_by(phone=phone.data).first()
        if client and (not hasattr(self, "client_id") or client.id != self.client_id):
            raise ValidationError("Клієнт з таким номером телефону вже існує.")

    def validate_email(self, email):
        if email.data:
            client = Client.query.filter_by(email=email.data).first()
            if client and (
                not hasattr(self, "client_id") or client.id != self.client_id
            ):
                raise ValidationError("Клієнт з таким email вже існує.")


# Список всіх клієнтів
@bp.route("/")
@login_required
def index():
    # Отримання параметра пошуку
    search = request.args.get("search", "")

    # Базовий запит
    query = Client.query

    # Додавання фільтрації за пошуком
    if search:
        # Розбиваємо пошуковий запит на слова
        search_words = search.split()

        if search_words:
            # Створюємо умову для пошуку за іменем, де кожне слово має бути в імені
            name_conditions = []
            for word in search_words:
                name_conditions.append(Client.name.ilike(f"%{word}%"))

            # Об'єднуємо умови для імені з AND (всі слова повинні бути присутні)
            name_condition = and_(*name_conditions)

            # Додаємо умови для телефону та email (для повного пошукового запиту)
            phone_condition = Client.phone.ilike(f"%{search}%")
            email_condition = Client.email.ilike(f"%{search}%")
            notes_condition = Client.notes.ilike(f"%{search}%")

            # Об'єднуємо всі умови з OR
            query = query.filter(
                or_(name_condition, phone_condition, email_condition, notes_condition)
            )
        else:
            # Порожній пошуковий запит після розбиття - просто повертаємо всіх клієнтів
            pass

    # Отримання клієнтів
    clients = query.order_by(Client.name).all()

    return render_template(
        "clients/index.html", title="Клієнти", clients=clients, search=search
    )


# Створення нового клієнта
@bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    form = ClientForm()

    if form.validate_on_submit():
        # Якщо email пустий, встановлюємо його як None
        email = form.email.data if form.email.data else None

        client = Client(
            name=form.name.data,
            phone=form.phone.data,
            email=email,  # Використовуємо None замість порожнього рядка
            notes=form.notes.data,
        )
        db.session.add(client)
        db.session.commit()

        flash("Клієнт успішно доданий!", "success")
        return redirect(url_for("clients.view", id=client.id))

    return render_template("clients/create.html", title="Новий клієнт", form=form)


# Перегляд клієнта
@bp.route("/<int:id>")
@login_required
def view(id):
    client = Client.query.get_or_404(id)

    # Отримання останніх записів клієнта
    appointments = (
        Appointment.query.filter_by(client_id=client.id)
        .order_by(Appointment.date.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "clients/view.html",
        title=f"Клієнт: {client.name}",
        client=client,
        appointments=appointments,
    )


# Редагування клієнта
@bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id):
    client = Client.query.get_or_404(id)
    form = ClientForm(obj=client)
    form.client_id = client.id

    if form.validate_on_submit():
        # Зберігаємо всі поля, крім email
        client.name = form.name.data
        client.phone = form.phone.data
        client.notes = form.notes.data

        # Якщо email порожній, зберігаємо як None
        client.email = form.email.data if form.email.data else None

        db.session.commit()

        flash("Інформацію про клієнта успішно оновлено!", "success")
        return redirect(url_for("clients.view", id=client.id))

    return render_template(
        "clients/edit.html",
        title=f"Редагування клієнта: {client.name}",
        form=form,
        client=client,
    )


# Видалення клієнта
@bp.route("/<int:id>/delete", methods=["POST"])
@login_required
def delete(id):
    client = Client.query.get_or_404(id)

    # Перевірка, чи є запланові записи для цього клієнта
    future_appointments = Appointment.query.filter(
        Appointment.client_id == client.id,
        Appointment.date >= datetime.now().date(),
        Appointment.status != "cancelled",
    ).count()

    if future_appointments > 0:
        flash(
            f"Не можна видалити клієнта, оскільки у нього є {future_appointments} запланованих записів!",
            "danger",
        )
        return redirect(url_for("clients.view", id=client.id))

    # Видалення клієнта
    db.session.delete(client)
    db.session.commit()

    flash("Клієнт успішно видалений!", "success")
    return redirect(url_for("clients.index"))


# API для пошуку клієнтів
@bp.route("/api/search")
@login_required
def api_search():
    query = request.args.get("q", "")
    if not query or len(query) < 2:
        return jsonify([])

    # Розбиваємо пошуковий запит на слова
    search_words = query.split()

    if search_words:
        # Створюємо умову для пошуку за іменем, де кожне слово має бути в імені
        name_conditions = []
        for word in search_words:
            name_conditions.append(Client.name.ilike(f"%{word}%"))

        # Об'єднуємо умови для імені з AND
        name_condition = and_(*name_conditions)

        # Додаємо умову для телефону (для повного пошукового запиту)
        phone_condition = Client.phone.ilike(f"%{query}%")

        # Об'єднуємо всі умови з OR
        clients = (
            Client.query.filter(or_(name_condition, phone_condition)).limit(10).all()
        )
    else:
        clients = []

    result = []
    for client in clients:
        result.append(
            {
                "id": client.id,
                "name": client.name,
                "phone": client.phone,
                "email": client.email,
            }
        )

    return jsonify(result)


from datetime import datetime  # Додайте цей імпорт на початку файлу
