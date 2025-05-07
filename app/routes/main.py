from collections import Counter
from datetime import datetime, time, timedelta
from decimal import Decimal

from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, url_for)
from flask_login import current_user, login_required
from sqlalchemy import func

from app.models import Appointment, AppointmentService, PaymentMethod, User, db

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
        print(f"DEBUG: current_user.is_admin = {current_user.is_admin}")
        print(f"DEBUG: type of current_user = {type(current_user)}")
        print(f"DEBUG: current_user.username = {current_user.username}")

        if not current_user.is_admin:
            flash("Тільки адміністратори мають доступ до цієї сторінки", "danger")
            return redirect(url_for("main.index"))

        # Отримання дати з параметрів запиту або використання поточної дати
        date_str = request.args.get("date")
        if date_str:
            try:
                selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                flash(
                    "Неправильний формат дати. Використовуємо поточну дату.", "warning"
                )
                return redirect(url_for("main.schedule"))
        else:
            selected_date = datetime.now().date()

        # Отримання всіх майстрів
        masters = User.query.order_by(User.full_name).all()

        # Use explicit query with joins to avoid lazy loading issues
        # First fetch the IDs to avoid enum string conversion issues
        appointment_ids = (
            db.session.query(Appointment.id)
            .filter(
                Appointment.date == selected_date, Appointment.status != "cancelled"
            )
            .all()
        )

        # Then fetch the full appointments by ID to avoid enum conversion issues
        appointment_ids = [id[0] for id in appointment_ids]
        appointments = Appointment.query.filter(
            Appointment.id.in_(appointment_ids) if appointment_ids else False
        ).all()

        # For any appointments with payment_method that might cause enum errors, set it to None
        for appointment in appointments:
            if isinstance(appointment.payment_method, str):
                # Set the payment_method to a valid enum value or None if not valid
                try:
                    appointment.payment_method = PaymentMethod[
                        appointment.payment_method
                    ]
                except (KeyError, ValueError):
                    appointment.payment_method = None
                    db.session.add(appointment)

        # Commit any changes to payment_method
        db.session.commit()

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

        current_app.logger.debug(
            f"Multi-booking client IDs: {multi_booking_client_ids}"
        )

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

            # Розрахунок фінансової інформації та CSS класу
            expected_price = appointment.get_discounted_price()
            # Ensure expected_price is non-negative
            expected_price = max(Decimal("0.00"), expected_price)

            amount_paid_val = (
                appointment.amount_paid
                if appointment.amount_paid is not None
                else Decimal("0.00")
            )
            finance_info = ""
            css_class = ""

            if appointment.status == "completed":
                if appointment.payment_status == "paid":
                    css_class = "status-completed-paid"
                    finance_info = f"Сплачено: {amount_paid_val:.2f} грн"
                elif appointment.payment_status in ["unpaid", "partially_paid"]:
                    css_class = "status-completed-debt"
                    debt_val = expected_price - amount_paid_val
                    finance_info = (
                        f"Сплачено: {amount_paid_val:.2f} грн, Борг: {debt_val:.2f} грн"
                    )
            else:
                # All non-completed statuses (scheduled, etc)
                if appointment.payment_status == "unpaid":
                    css_class = "status-unpaid"
                elif appointment.payment_status == "partially_paid":
                    css_class = "status-scheduled-custom"
                elif appointment.payment_status == "paid":
                    css_class = "status-paid"
                else:
                    css_class = "status-scheduled-custom"

                if amount_paid_val > Decimal("0.00"):
                    finance_info = f"Передоплата: {amount_paid_val:.2f} грн"

            # Додаємо extra_class для multi-booking
            if appointment.client_id in multi_booking_client_ids:
                css_class += " multi-booking"
                current_app.logger.debug(
                    f"Adding multi-booking class to appointment {appointment.id} "
                    f"for client {appointment.client_id}"
                )

            appointment_display_data = {
                "appointment": appointment,
                "finance_info": finance_info,
                "css_class": css_class.strip(),  # remove leading/trailing spaces if multi-booking not added
            }

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
                        appointment_display_data  # Pass the prepared dictionary
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
