from datetime import datetime
from typing import Any, List, Optional as OptionalType

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional, ValidationError

from app.models import Appointment, Client, db

# Створення Blueprint
bp = Blueprint("clients", __name__, url_prefix="/clients")


# Функція для перевірки чи містить рядок всі слова пошуку
def contains_all_words(text: OptionalType[str], search_words: List[str]) -> bool:
    if not text:
        return False

    text_lower = text.lower()
    return all(word in text_lower for word in search_words)


# Форма для клієнта
class ClientForm(FlaskForm):
    name = StringField("Ім'я", validators=[DataRequired(), Length(max=100)])
    phone = StringField("Телефон", validators=[DataRequired(), Length(max=20)])
    email = StringField("Email", validators=[Optional(), Email(), Length(max=120)])
    notes = TextAreaField("Примітки", validators=[Optional()])
    submit = SubmitField("Зберегти")

    def validate_phone(self, phone: StringField) -> None:
        client = Client.query.filter_by(phone=phone.data).first()
        if client and (not hasattr(self, "client_id") or client.id != getattr(self, "client_id", None)):
            raise ValidationError("Клієнт з таким номером телефону вже існує.")

    def validate_email(self, email: StringField) -> None:
        if email.data:
            client = Client.query.filter_by(email=email.data).first()
            if client and (not hasattr(self, "client_id") or client.id != getattr(self, "client_id", None)):
                raise ValidationError("Клієнт з таким email вже існує.")


# Список всіх клієнтів
@bp.route("/")
@login_required
def index() -> str:
    # Отримання параметра пошуку
    search = request.args.get("search", "")

    # Базовий запит клієнтів
    if current_user.is_admin:
        # Адміністратор може бачити всіх клієнтів
        query = Client.query
    else:
        # Майстер може бачити тільки клієнтів з якими мав записи
        client_ids = db.session.query(Appointment.client_id).filter(Appointment.master_id == current_user.id).distinct()
        query = Client.query.filter(Client.id.in_(client_ids))

    # Фільтрація за пошуковим запитом
    if search and search.strip():
        # Get all clients from the already filtered query and filter further in Python
        # This is a workaround for SQLite's case-sensitivity issues with Cyrillic
        all_clients = query.all()

        # Split search string into words and convert to lowercase for case-insensitive comparison
        search_words = [word.lower() for word in search.split()]

        # Filter clients in Python (case-insensitive)
        clients = []
        for client in all_clients:
            # Check if all search words are in the client name (in any order)
            if contains_all_words(client.name, search_words):
                clients.append(client)
                continue

            # Check phone (exact match for phone numbers)
            if client.phone and search in client.phone:
                clients.append(client)
                continue

            # Check email
            if contains_all_words(client.email, search_words):
                clients.append(client)
                continue

            # Check notes
            if contains_all_words(client.notes, search_words):
                clients.append(client)
                continue

    else:
        # Без пошуку просто повертаємо відфільтрованих клієнтів
        clients = query.order_by(Client.name).all()

    return render_template(
        "clients/index.html",
        title="Клієнти",
        clients=clients,
        search=search,
        is_admin=current_user.is_admin,
    )


# Створення нового клієнта
@bp.route("/create", methods=["GET", "POST"])
@login_required
def create() -> Any:
    # Перевірка прав доступу: тільки адміністратори можуть створювати клієнтів
    if not current_user.is_admin:
        flash("У вас немає прав для створення нових клієнтів", "danger")
        return redirect(url_for("clients.index"))

    form = ClientForm()

    if form.validate_on_submit():
        # Якщо email пустий, встановлюємо його як None
        email = form.email.data if form.email.data else None

        client = Client()
        client.name = form.name.data
        client.phone = form.phone.data
        client.email = email
        client.notes = form.notes.data

        db.session.add(client)
        db.session.commit()

        flash("Клієнт успішно доданий!", "success")
        return redirect(url_for("clients.view", id=client.id))

    return render_template("clients/create.html", title="Новий клієнт", form=form)


# Перегляд клієнта
@bp.route("/<int:id>")
@login_required
def view(id: int) -> Any:
    client = Client.query.get_or_404(id)

    # Перевірка прав доступу: Майстер може переглядати тільки клієнтів з якими мав записи
    if not current_user.is_admin:
        appointment_count = Appointment.query.filter(
            Appointment.client_id == client.id, Appointment.master_id == current_user.id
        ).count()

        if appointment_count == 0:
            flash("У вас немає прав для перегляду цього клієнта", "danger")
            return redirect(url_for("clients.index"))

    # Отримання останніх записів клієнта
    if current_user.is_admin:
        # Адміністратор бачить всі записи клієнта
        appointments = (
            Appointment.query.filter_by(client_id=client.id).order_by(Appointment.date.desc()).limit(10).all()
        )
    else:
        # Майстер бачить тільки свої записи з цим клієнтом
        appointments = (
            Appointment.query.filter_by(client_id=client.id, master_id=current_user.id)
            .order_by(Appointment.date.desc())
            .limit(10)
            .all()
        )

    return render_template(
        "clients/view.html",
        title=f"Клієнт: {client.name}",
        client=client,
        appointments=appointments,
        is_admin=current_user.is_admin,
    )


# Редагування клієнта
@bp.route("/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit(id: int) -> Any:
    # Перевірка прав доступу: тільки адміністратори можуть редагувати клієнтів
    if not current_user.is_admin:
        flash("У вас немає прав для редагування клієнтів", "danger")
        return redirect(url_for("clients.index"))

    client = Client.query.get_or_404(id)
    form = ClientForm(obj=client)
    setattr(form, "client_id", client.id)

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
def delete(id: int) -> Any:
    # Перевірка прав доступу: тільки адміністратори можуть видаляти клієнтів
    if not current_user.is_admin:
        flash("У вас немає прав для видалення клієнтів", "danger")
        return redirect(url_for("clients.index"))

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
def api_search() -> Any:
    query_string = request.args.get("q", "")
    if not query_string or len(query_string) < 2:
        return jsonify([])

    # Базовий запит для отримання клієнтів
    if current_user.is_admin:
        # Адміністратор може бачити всіх клієнтів
        all_clients = Client.query.all()
    else:
        # Майстер може бачити тільки клієнтів з якими мав записи
        client_ids = (
            db.session.query(Appointment.client_id).filter(Appointment.master_id == current_user.id).distinct().all()
        )
        client_ids = [client_id[0] for client_id in client_ids]
        all_clients = Client.query.filter(Client.id.in_(client_ids)).all() if client_ids else []

    # Split query string into words and convert to lowercase for case-insensitive comparison
    query_words = [word.lower() for word in query_string.split()]

    # Filter clients in Python (case-insensitive)
    clients = []
    for client in all_clients:
        # Check if all query words are in the client name (in any order)
        if contains_all_words(client.name, query_words):
            clients.append(
                {
                    "id": client.id,
                    "name": client.name,
                    "phone": client.phone,
                    "email": client.email,
                }
            )
            continue

        # Check phone (exact match for phone numbers)
        if client.phone and query_string in client.phone:
            clients.append(
                {
                    "id": client.id,
                    "name": client.name,
                    "phone": client.phone,
                    "email": client.email,
                }
            )
            continue

        # Check email
        if contains_all_words(client.email, query_words):
            clients.append(
                {
                    "id": client.id,
                    "name": client.name,
                    "phone": client.phone,
                    "email": client.email,
                }
            )
            continue

        # Check notes
        if contains_all_words(client.notes, query_words):
            clients.append(
                {
                    "id": client.id,
                    "name": client.name,
                    "phone": client.phone,
                    "email": client.email,
                }
            )

    return jsonify(clients[:10])
