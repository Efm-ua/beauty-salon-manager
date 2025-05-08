from collections import Counter
from datetime import datetime, time, timedelta
from decimal import Decimal

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
)
from flask_login import current_user, login_required
from sqlalchemy import func

from app.models import Appointment, AppointmentService, PaymentMethod, User, db

# Створення Blueprint
bp = Blueprint("main", __name__)


# Головна сторінка
@bp.route("/")
@login_required
def index():
    print(f"DEBUG index(): current_user.id = {current_user.id}")
    print(f"DEBUG index(): current_user.username = {current_user.username}")
    print(
        f"DEBUG index(): current_user.is_authenticated = {current_user.is_authenticated}"
    )
    print(f"DEBUG index(): current_user.is_admin = {current_user.is_admin}")
    print(f"DEBUG index(): type of current_user = {type(current_user)}")

    today = datetime.now().date()

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

    # Різні дані для адміністраторів і майстрів
    if current_user.is_admin:
        # Для адміністраторів - загальна статистика

        # Отримання загальної кількості записів на сьогодні
        today_appointments_count = Appointment.query.filter(
            Appointment.date == today, Appointment.status != "cancelled"
        ).count()

        # Отримання загальної кількості майстрів
        masters_count = User.query.filter_by(is_active_master=True).count()

        # Розрахунок загальної суми за день для всіх майстрів
        total_day_sum = (
            db.session.query(func.sum(AppointmentService.price))
            .join(Appointment, Appointment.id == AppointmentService.appointment_id)
            .filter(Appointment.date == today, Appointment.status == "completed")
            .scalar()
            or 0
        )

        template_context = {
            "title": "Головна",
            "today": today,
            "today_appointments_count": today_appointments_count,
            "masters_count": masters_count,
            "user_appointments": user_appointments,
            "user_total": user_total,
            "total_day_sum": total_day_sum,
            "is_admin": True,
        }
        print(f"DEBUG index(): admin template context = {template_context}")
        return render_template("main/index.html", **template_context)
    else:
        # Для майстрів - тільки їх персональна статистика
        # Отримання кількості записів поточного майстра на сьогодні (для зручності)
        today_appointments_count = len(user_appointments)

        template_context = {
            "title": "Головна",
            "today": today,
            "today_appointments_count": today_appointments_count,
            "user_appointments": user_appointments,
            "user_total": user_total,
            "is_admin": False,  # Переконуємося, що встановлюємо is_admin=False
        }
        print(f"DEBUG index(): master template context = {template_context}")
        return render_template("main/index.html", **template_context)


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

    if current_user.is_admin:
        # Статистика за місяць для всіх майстрів (адміністратор)
        monthly_stats = (
            db.session.query(
                User.full_name,
                func.count(Appointment.id).label("total_appointments"),
                func.sum(AppointmentService.price).label("total_revenue"),
            )
            .join(Appointment, User.id == Appointment.master_id)
            .join(
                AppointmentService, Appointment.id == AppointmentService.appointment_id
            )
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
            is_admin=True,
        )
    else:
        # Статистика за місяць тільки для поточного майстра
        master_stats = (
            db.session.query(
                func.count(Appointment.id).label("total_appointments"),
                func.sum(AppointmentService.price).label("total_revenue"),
            )
            .join(Appointment, AppointmentService.appointment_id == Appointment.id)
            .filter(
                Appointment.master_id == current_user.id,
                Appointment.date.between(start_of_month, end_of_month),
                Appointment.status == "completed",
            )
            .first()
        )

        # Деталі по днях для цього майстра
        daily_stats = (
            db.session.query(
                Appointment.date,
                func.count(Appointment.id).label("appointment_count"),
                func.sum(AppointmentService.price).label("daily_revenue"),
            )
            .join(
                AppointmentService, Appointment.id == AppointmentService.appointment_id
            )
            .filter(
                Appointment.master_id == current_user.id,
                Appointment.date.between(start_of_month, end_of_month),
                Appointment.status == "completed",
            )
            .group_by(Appointment.date)
            .order_by(Appointment.date)
            .all()
        )

        return render_template(
            "main/stats.html",
            title="Ваша статистика",
            start_of_month=start_of_month,
            end_of_month=end_of_month,
            master_stats=master_stats,
            daily_stats=daily_stats,
            is_admin=False,
            user_name=current_user.full_name,
        )


# Сторінка розкладу (доступна для всіх авторизованих користувачів)
@bp.route("/schedule")
@login_required
def schedule():
    try:
        # Debugging інформація про користувача
        print(f"DEBUG: current_user.is_admin = {current_user.is_admin}")
        print(f"DEBUG: type of current_user = {type(current_user)}")
        print(f"DEBUG: current_user.username = {current_user.username}")

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

        # Отримання списку всіх майстрів
        masters = (
            User.query.filter_by(is_active_master=True).order_by(User.full_name).all()
        )

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
                if appointment.payment_status == "paid":
                    css_class = "status-scheduled-paid"
                    finance_info = f"Передоплата: {amount_paid_val:.2f} грн"
                elif (
                    appointment.payment_status == "partially_paid"
                    and amount_paid_val > Decimal("0.00")
                ):
                    css_class = "status-scheduled-prepaid"
                    finance_info = f"Передоплата: {amount_paid_val:.2f} грн"
                else:  # unpaid
                    css_class = "status-scheduled"
                    finance_info = f"Вартість: {expected_price:.2f} грн"

            # Якщо запис починається або закінчується в :15 або :45, необхідно розгорнути відповідні слоти
            if starts_at_15_or_45 or ends_at_15_or_45:
                # Знаходимо всі time_intervals, що включають ці слоти
                for interval in time_intervals:
                    for sub_slot in interval["sub_slots"]:
                        if (
                            appointment.start_time <= sub_slot < appointment.end_time
                            or sub_slot == appointment.start_time
                        ):
                            interval["expanded"] = True
                            break

            # Ця змінна визначає, чи користувач може редагувати/видаляти запис
            can_edit = current_user.is_admin or appointment.master_id == current_user.id

            # Додаємо інформацію про завершений статус, якщо запис вже завершено
            if appointment.status == "completed":
                completion_info = "(Завершено)"
            else:
                completion_info = ""

            # Додавання запису в усі слоти, які він займає
            for slot in all_15min_slots:
                if (
                    appointment.start_time <= slot < appointment.end_time
                    or slot == appointment.start_time
                ):
                    if slot == appointment.start_time:
                        # Основна інформація про запис відображається в першому слоті
                        schedule_data[appointment.master_id][slot].append(
                            {
                                "id": appointment.id,
                                "client_name": appointment.client.name,
                                "phone": appointment.client.phone,
                                "services": [
                                    s.service.name for s in appointment.services
                                ],
                                "display_type": "full",
                                "css_class": css_class,
                                "multi_booking": appointment.client_id
                                in multi_booking_client_ids,
                                "finance_info": finance_info,
                                "completion_info": completion_info,
                                "can_edit": can_edit,
                                "status": appointment.status,
                                "is_completed": appointment.status == "completed",
                            }
                        )
                    else:
                        # У наступних слотах - тільки продовження запису
                        schedule_data[appointment.master_id][slot].append(
                            {
                                "id": appointment.id,
                                "display_type": "continuation",
                                "css_class": css_class,
                            }
                        )

        # Передача даних до шаблону
        return render_template(
            "main/schedule.html",
            title="Розклад майстрів",
            selected_date=selected_date,
            time_intervals=time_intervals,
            masters=masters,
            schedule_data=schedule_data,
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        flash(f"Помилка при формуванні розкладу: {str(e)}", "danger")
        return redirect(url_for("main.index"))
