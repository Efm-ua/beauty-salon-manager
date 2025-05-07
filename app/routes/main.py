from collections import Counter
from datetime import datetime, time, timedelta

from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, url_for)
from flask_login import current_user, login_required
from sqlalchemy import func

from app.models import Appointment, AppointmentService, User, db

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

    # Загальна сума за місяць це комент для апдейта
    total_month_revenue = sum(stats.total_revenue or 0 for stats in monthly_stats)

    return render_template(
        "main/stats.html",
        title="Статистика",
        start_of_month=start_of_month,
        end_of_month=end_of_month,
        monthly_stats=monthly_stats,
        total_month_revenue=total_month_revenue,
    )


# Сторінка розкладу (для адміністратора)
@bp.route("/schedule")
@login_required
def schedule():
    try:
        # Перевірка, чи є користувач адміністратором
        if not current_user.is_admin:
            flash("Тільки адміністратори мають доступ до цієї сторінки", "danger")
            return redirect(url_for("main.index"))

        # Отримання дати з параметрів запиту або використання поточної дати
        date_str = request.args.get("date")
        if date_str:
            try:
                selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                selected_date = datetime.now().date()
        else:
            selected_date = datetime.now().date()

        # Отримання всіх майстрів
        masters = User.query.order_by(User.full_name).all()

        # Отримання записів на вибрану дату
        appointments = Appointment.query.filter(
            Appointment.date == selected_date, Appointment.status != "cancelled"
        ).all()

        # Підрахунок записів для кожного клієнта на вибрану дату
        client_appointments_count = Counter(
            appointment.client_id for appointment in appointments
        )

        # Створення множини client_id, у яких більше одного запису
        multi_booking_client_ids = {
            client_id
            for client_id, count in client_appointments_count.items()
            if count > 1
        }

        # Створення структури 30-хвилинних слотів з 15-хвилинними підслотами
        time_intervals = []
        for hour in range(8, 21):
            for minute in [0, 30]:
                main_time = time(hour, minute)
                sub_slots = [time(hour, minute), time(hour, minute + 15)]
                time_intervals.append(
                    {"main_time": main_time, "sub_slots": sub_slots, "expanded": False}
                )

        # Додавання останнього слоту 20:30
        if time_intervals[-1]["main_time"] != time(20, 30):
            time_intervals.append(
                {
                    "main_time": time(20, 30),
                    "sub_slots": [time(20, 30), time(20, 45)],
                    "expanded": False,
                }
            )

        # Створення структури даних для розкладу
        all_15min_slots = []
        for interval in time_intervals:
            all_15min_slots.extend(interval["sub_slots"])

        schedule_data = {
            master.id: {slot: [] for slot in all_15min_slots} for master in masters
        }

        # Заповнення розкладу записами та встановлення expanded
        for appointment in appointments:
            # Визначення, чи запис починається або закінчується в :15 або :45 хвилин
            starts_at_15_or_45 = appointment.start_time.minute in [15, 45]
            ends_at_15_or_45 = appointment.end_time.minute in [15, 45]

            # Визначення всіх 15-хвилинних слотів, які займає запис
            current_time = datetime.combine(selected_date, appointment.start_time)
            end_datetime = datetime.combine(selected_date, appointment.end_time)

            while current_time < end_datetime:
                current_slot_time = current_time.time()

                # Додавання запису до відповідного слоту
                if (
                    appointment.master_id in schedule_data
                    and current_slot_time in schedule_data[appointment.master_id]
                ):
                    schedule_data[appointment.master_id][current_slot_time].append(
                        appointment
                    )

                # Пошук відповідного 30-хвилинного інтервалу для встановлення expanded
                if starts_at_15_or_45 or ends_at_15_or_45:
                    for interval in time_intervals:
                        if current_slot_time in interval["sub_slots"]:
                            interval["expanded"] = True
                            break

                # Перехід до наступного 15-хвилинного слоту
                current_time += timedelta(minutes=15)

        return render_template(
            "main/schedule.html",
            title="Розклад майстрів",
            masters=masters,
            time_intervals=time_intervals,
            schedule_data=schedule_data,
            selected_date=selected_date,
            multi_booking_client_ids=multi_booking_client_ids,
        )
    except Exception as e:
        current_app.logger.exception(f"!!! EXCEPTION in /schedule route: {e}")
        abort(500)
