from flask import Blueprint, render_template
from flask_login import login_required, current_user
from datetime import datetime, timedelta

from app.models import Appointment, AppointmentService, User
from sqlalchemy import func

# Створення Blueprint
bp = Blueprint("main", __name__)


# Головна сторінка
@bp.route("/")
@login_required
def index():
    today = datetime.now().date()

    # Отримання загальної кількості записів на сьогодні
    today_appointments_count = Appointment.query.filter(
        Appointment.date == today, Appointment.status != "cancelled"
    ).count()

    # Отримання загальної кількості майстрів
    masters_count = User.query.count()

    # Отримання записів поточного користувача на сьогодні
    user_appointments = (
        Appointment.query.filter(
            Appointment.date == today,
            Appointment.master_id == current_user.id,
            Appointment.status != "cancelled",
        )
        .order_by(Appointment.start_time)
        .all()
    )

    # Розрахунок загальної суми за день для поточного користувача
    user_total = 0
    for appointment in user_appointments:
        for service in appointment.services:
            user_total += service.price

    # Розрахунок загальної суми за день для всіх майстрів
    total_day_sum = (
        db.session.query(func.sum(AppointmentService.price))
        .join(Appointment, Appointment.id == AppointmentService.appointment_id)
        .filter(Appointment.date == today, Appointment.status == "completed")
        .scalar()
        or 0
    )

    return render_template(
        "main/index.html",
        title="Головна",
        today=today,
        today_appointments_count=today_appointments_count,
        masters_count=masters_count,
        user_appointments=user_appointments,
        user_total=user_total,
        total_day_sum=total_day_sum,
    )


# Сторінка статистики за період
@bp.route("/stats")
@login_required
def stats():
    # Поточний місяць
    today = datetime.now().date()
    start_of_month = today.replace(day=1)

    # Кінець місяця (перший день наступного місяця мінус один день)
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)

    end_of_month = next_month - timedelta(days=1)

    # Статистика за місяць
    monthly_stats = (
        db.session.query(
            User.full_name,
            func.count(Appointment.id).label("total_appointments"),
            func.sum(AppointmentService.price).label("total_revenue"),
        )
        .join(Appointment, User.id == Appointment.master_id)
        .join(AppointmentService, Appointment.id == AppointmentService.appointment_id)
        .filter(
            Appointment.date.between(start_of_month, end_of_month),
            Appointment.status == "completed",
        )
        .group_by(User.id)
        .all()
    )

    # Загальна сума за місяць
    total_month_revenue = sum(stats.total_revenue or 0 for stats in monthly_stats)

    return render_template(
        "main/stats.html",
        title="Статистика",
        start_of_month=start_of_month,
        end_of_month=end_of_month,
        monthly_stats=monthly_stats,
        total_month_revenue=total_month_revenue,
    )


from app.models import db  # Додайте цей імпорт на початку файлу
