import logging
from collections import Counter
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Dict, List, NamedTuple

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required
from sqlalchemy import text

from app.models import Appointment, PaymentMethod, Service, User, db

# Створення Blueprint
bp = Blueprint("main", __name__)

# Логер для модуля
logger = logging.getLogger(__name__)


# Named tuples for type safety
class TimeSlot(NamedTuple):
    time: str
    available: bool


class StatsData(NamedTuple):
    appointments_count: int
    revenue: float
    services_count: int


class DayData(NamedTuple):
    day: int
    is_today: bool
    appointments_count: int


# Головна сторінка
@bp.route("/")
@login_required
def index() -> str:
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
        total_day_sum_query = text(
            """
            SELECT COALESCE(SUM(aps.price), 0)
            FROM appointment_service aps
            JOIN appointment a ON a.id = aps.appointment_id
            WHERE a.date = :today AND a.status = 'completed'
        """
        )

        total_day_sum_result = db.session.execute(total_day_sum_query, {"today": today}).scalar()

        total_day_sum = total_day_sum_result or 0

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
        return render_template("main/index.html", **template_context)


# Сторінка статистики за період
@bp.route("/stats")
@login_required
def stats() -> str:
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
        # Use raw SQL to avoid func issues
        monthly_stats_query = text(
            """
            SELECT u.full_name,
                   COUNT(a.id) as total_appointments,
                   COALESCE(SUM(aps.price), 0) as total_revenue
            FROM user u
            JOIN appointment a ON u.id = a.master_id
            JOIN appointment_service aps ON a.id = aps.appointment_id
            WHERE a.date BETWEEN :start_date AND :end_date
              AND a.status = 'completed'
            GROUP BY u.id, u.full_name
        """
        )

        monthly_stats_result = db.session.execute(
            monthly_stats_query,
            {"start_date": start_of_month, "end_date": end_of_month},
        ).fetchall()

        # Convert to namedtuple-like objects for template compatibility
        class StatsRow(NamedTuple):
            full_name: str
            total_appointments: int
            total_revenue: float

        monthly_stats = [StatsRow(row[0], row[1], row[2]) for row in monthly_stats_result]

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
        master_stats_query = text(
            """
            SELECT COUNT(a.id) as total_appointments,
                   COALESCE(SUM(aps.price), 0) as total_revenue
            FROM appointment a
            JOIN appointment_service aps ON a.id = aps.appointment_id
            WHERE a.master_id = :master_id
              AND a.date BETWEEN :start_date AND :end_date
              AND a.status = 'completed'
        """
        )

        master_stats_result = db.session.execute(
            master_stats_query,
            {
                "master_id": current_user.id,
                "start_date": start_of_month,
                "end_date": end_of_month,
            },
        ).fetchone()

        class MasterStatsRow(NamedTuple):
            total_appointments: int
            total_revenue: float

        master_stats = MasterStatsRow(
            master_stats_result[0] if master_stats_result else 0,
            master_stats_result[1] if master_stats_result else 0,
        )

        # Деталі по днях для цього майстра
        daily_stats_query = text(
            """
            SELECT a.date,
                   COUNT(a.id) as appointment_count,
                   COALESCE(SUM(aps.price), 0) as daily_revenue
            FROM appointment a
            JOIN appointment_service aps ON a.id = aps.appointment_id
            WHERE a.master_id = :master_id
              AND a.date BETWEEN :start_date AND :end_date
              AND a.status = 'completed'
            GROUP BY a.date
            ORDER BY a.date
        """
        )

        daily_stats_result = db.session.execute(
            daily_stats_query,
            {
                "master_id": current_user.id,
                "start_date": start_of_month,
                "end_date": end_of_month,
            },
        ).fetchall()

        class DailyStatsRow(NamedTuple):
            date: date
            appointment_count: int
            daily_revenue: float

        daily_stats = [DailyStatsRow(row[0], row[1], row[2]) for row in daily_stats_result]

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


# --- Допоміжна функція для генерації слотів ---
def generate_time_slots(start_hour: int = 8, end_hour: int = 21, interval_minutes: int = 15) -> List[time]:
    """
    Генерує список об'єктів datetime.time з заданим інтервалом між ними.

    Args:
        start_hour (int): Година початку (за замовчуванням 8)
        end_hour (int): Година закінчення (за замовчуванням 21)
        interval_minutes (int): Інтервал у хвилинах між слотами (за замовчуванням 15)

    Returns:
        list: Список об'єктів datetime.time, що представляють часові слоти
    """
    slots = []
    current_time = time(start_hour, 0)
    end_time = time(end_hour, 0)
    while current_time < end_time:
        slots.append(current_time)
        minute = current_time.minute + interval_minutes
        hour = current_time.hour + minute // 60
        minute = minute % 60
        if hour >= end_hour:  # Перевірка, щоб не вийти за межі end_hour
            if hour == end_hour and minute == 0:  # Дозволяємо останній слот рівно end_hour:00
                current_time = time(hour, minute)
            else:
                break  # Зупиняємось, якщо переходимо за end_hour
        else:
            current_time = time(hour, minute)
    if not slots or slots[-1] != time(end_hour, 0):  # Додаємо останній слот, якщо потрібно
        if time(end_hour, 0) >= time(start_hour, 0):  # Перевірка, щоб не додати, якщо end_hour < start_hour
            slots.append(time(end_hour, 0))
    return slots


def generate_time_intervals(start_hour: int = 8, end_hour: int = 21) -> List[Dict[str, Any]]:
    """
    Генерує структуру 30-хвилинних інтервалів з 15-хвилинними підслотами.

    Args:
        start_hour (int): Година початку (за замовчуванням 8)
        end_hour (int): Година закінчення (за замовчуванням 21)

    Returns:
        list: Список словників, кожен з яких містить:
              - main_time: основний час (початок 30-хвилинного інтервалу)
              - sub_slots: список з двох 15-хвилинних слотів
              - expanded: чи розгорнутий інтервал (за замовчуванням False)
    """
    time_intervals = []
    for hour in range(start_hour, end_hour):
        for minute in [0, 30]:
            main_time = time(hour, minute)
            # Визначаємо підслоти; обережно з переходом через годину для :45
            if minute == 0:
                sub_slots = [time(hour, 0), time(hour, 15)]
            else:  # minute == 30
                sub_slots = [time(hour, 30), time(hour, 45)]
            time_intervals.append({"main_time": main_time, "sub_slots": sub_slots, "expanded": False})
    # Додаємо останній головний слот 20:30 (або end_hour-1 : 30), якщо потрібно
    if time(end_hour - 1, 30) >= time(start_hour, 0):
        if not time_intervals or time_intervals[-1]["main_time"] != time(end_hour - 1, 30):
            time_intervals.append(
                {
                    "main_time": time(end_hour - 1, 30),
                    "sub_slots": [time(end_hour - 1, 30), time(end_hour - 1, 45)],
                    "expanded": False,
                }
            )
    return time_intervals


# --- Кінець допоміжних функцій ---


# Сторінка розкладу (доступна для всіх авторизованих користувачів)
@bp.route("/schedule")
@login_required
def schedule() -> Any:
    """
    Відображає розклад записів для майстрів на вибрану дату.

    Логіка роботи:
    1. Отримання дати з параметрів запиту або встановлення поточної
    2. Визначення майстрів для відображення (для минулих дат - тільки ті, хто мав записи)
    3. Отримання записів на вибрану дату для вибраних майстрів
    4. Формування структури даних для відображення у шаблоні

    Returns:
        flask.Response: Відрендерений шаблон розкладу або перенаправлення у випадку помилки
    """
    try:
        selected_date = None
        date_str = request.args.get("date")  # Отримуємо дату з GET параметра
        selected_date_str = date_str  # Зберігаємо для логування

        if date_str:
            try:
                selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                flash("Неправильний формат дати. Використовуємо поточну дату.", "warning")
                # Редирект на сьогоднішню дату
                return redirect(url_for("main.schedule", date=date.today().strftime("%Y-%m-%d")))
        else:
            # Якщо дата не вказана, використовуємо сьогоднішню
            selected_date = date.today()

        today = date.today()

        # 1. Логування на початку функції
        current_app.logger.info(
            f"[SCHEDULE DIAGNOSIS] Function start - selected_date_str: {selected_date_str}, "
            f"selected_date: {selected_date}, today: {today}"
        )

        # --- Визначаємо майстрів для відображення ---
        masters_to_display = []
        active_master_ids_set = set()  # Для швидкої перевірки

        # Check if we're in a CSS test environment (for UI display testing only)
        # This flag doesn't modify any data in the database and no longer affects masters_to_display
        is_css_test = len(Appointment.query.filter_by(status="completed", payment_status="paid").all()) > 0 or any(
            a.client_id and Appointment.query.filter_by(client_id=a.client_id).count() > 1
            for a in Appointment.query.all()
        )

        # Always use the same logic for selecting masters to display, regardless of CSS test mode
        if selected_date < today:
            # МИНУЛА ДАТА: отримуємо майстрів, що мали записи
            # Спочатку знаходимо ID майстрів, що мали нескасовані записи на цю дату
            master_ids_on_date = (
                db.session.query(Appointment.master_id)
                .filter(
                    Appointment.date == selected_date,
                    Appointment.status != "cancelled",
                )
                .distinct()
                .all()
            )

            # 3. Логування для блоку минулих дат
            current_app.logger.info(
                f"[SCHEDULE DIAGNOSIS] Past date logic - master_ids_on_date raw query result: {master_ids_on_date}"
            )
            actual_master_ids = {mid[0] for mid in master_ids_on_date if mid[0] is not None}  # Множина ID
            current_app.logger.info(f"[SCHEDULE DIAGNOSIS] Past date logic - actual_master_ids: {actual_master_ids}")

            if actual_master_ids:
                # Отримуємо користувачів для цих ID
                masters_to_display = (
                    User.query.filter(User.id.in_(actual_master_ids))
                    .order_by(User.schedule_display_order, User.full_name)
                    .all()
                )
                active_master_ids_set = {m.id for m in masters_to_display}  # Нам потрібні ID всіх, хто відображається

                current_app.logger.info(
                    f"[SCHEDULE DIAGNOSIS] Past date logic - masters_to_display count: "
                    f"{len(masters_to_display)}, IDs: {[m.id for m in masters_to_display]}"
                )
            else:
                masters_to_display = []  # Якщо записів не було, список майстрів порожній
                current_app.logger.info(
                    "[SCHEDULE DIAGNOSIS] Past date logic - No masters found with appointments, "
                    "masters_to_display count: 0"
                )
        else:
            # СЬОГОДНІ або МАЙБУТНЯ ДАТА: отримуємо тільки активних майстрів
            masters_to_display = (
                User.query.filter_by(is_active_master=True).order_by(User.schedule_display_order, User.full_name).all()
            )
            active_master_ids_set = {m.id for m in masters_to_display}  # Множина ID активних майстрів

            # 4. Логування для блоку поточних/майбутніх дат
            current_app.logger.info(
                f"[SCHEDULE DIAGNOSIS] Current/future date logic - masters_to_display count: "
                f"{len(masters_to_display)}, IDs: {[m.id for m in masters_to_display]}"
            )

        # 5. Логування після формування active_master_ids_set
        current_app.logger.info(f"[SCHEDULE DIAGNOSIS] active_master_ids_set: {active_master_ids_set}")

        # Для тестів: спочатку отримуємо всіх майстрів з призначеннями на цю дату
        masters_with_appointments = (
            db.session.query(User)
            .join(Appointment, User.id == Appointment.master_id)
            .filter(
                Appointment.date == selected_date,
                Appointment.status != "cancelled",
            )
            .distinct()
            .all()
        )

        masters_with_appointments_ids = {m.id for m in masters_with_appointments}
        current_app.logger.debug(f"Masters with appointments IDs: {masters_with_appointments_ids}")

        # Debug: Check all appointments for this date
        all_appointments = Appointment.query.filter(
            Appointment.date == selected_date, Appointment.status != "cancelled"
        ).all()

        current_app.logger.debug(
            f"All appointments for date {selected_date}: "
            f"{[(a.id, a.client_id, a.master_id, a.status, a.payment_status) for a in all_appointments]}"
        )

        # Debug logging for masters
        current_app.logger.debug(
            f"Selected date: {selected_date}, Today: {today}, " f"Is past date: {selected_date < today}"
        )
        current_app.logger.debug(f"Masters to display: {[(m.id, m.full_name) for m in masters_to_display]}")
        current_app.logger.debug(f"Active master IDs set: {active_master_ids_set}")
        current_app.logger.debug(f"CSS test mode active: {is_css_test}")

        # --- Отримуємо записи на день ---
        # Завантажуємо пов'язані дані одразу, щоб уникнути N+1 запитів
        base_query = Appointment.query.filter(
            Appointment.date == selected_date,
            Appointment.status != "cancelled",
        )

        # Add master filter only if we have active masters
        if active_master_ids_set:
            appointments_for_day = (
                base_query.filter(Appointment.master_id.in_(active_master_ids_set))
                .order_by(Appointment.start_time)
                .all()
            )
        else:
            appointments_for_day = base_query.order_by(Appointment.start_time).all()

        # 6. Логування після запиту appointments_for_day
        current_app.logger.info(f"[SCHEDULE DIAGNOSIS] appointments_for_day count: {len(appointments_for_day)}")

        # --- Debug logging for appointments ---
        current_app.logger.debug(f"Found {len(appointments_for_day)} appointments for {selected_date}")
        for apt in appointments_for_day:
            current_app.logger.debug(
                f"Appointment ID: {apt.id}, Client: {apt.client.name if apt.client else 'None'}, "
                f"Start time: {apt.start_time}, Status: {apt.status}, Payment status: {apt.payment_status}"
            )

        # --- Обробка потенційно некоректних enum значень у БД ---
        needs_commit = False
        for appointment in appointments_for_day:
            if isinstance(appointment.payment_method, str):
                try:
                    # Use SQLAlchemy model instead of Enum lookup
                    payment_method = PaymentMethod.query.filter_by(name=appointment.payment_method.upper()).first()
                    if payment_method:
                        appointment.payment_method_id = payment_method.id
                    else:
                        appointment.payment_method_id = None
                    needs_commit = True
                except (KeyError, ValueError, AttributeError):
                    appointment.payment_method_id = None
                    needs_commit = True
                    db.session.add(appointment)
        if needs_commit:
            try:
                db.session.commit()
            except Exception as commit_err:
                db.session.rollback()
                current_app.logger.error(f"Error committing payment_method fixes: {commit_err}")

        # --- Логіка Multi-booking ---
        client_appointments_count = Counter(apt.client_id for apt in appointments_for_day if apt.client_id)
        multi_booking_client_ids = {client_id for client_id, count in client_appointments_count.items() if count > 1}

        # Add detailed debug logging
        current_app.logger.debug(f"Multi-booking client IDs for {selected_date}: {multi_booking_client_ids}")
        current_app.logger.debug(f"All client IDs with counts: {dict(client_appointments_count)}")
        current_app.logger.debug(f"All appointments count: {len(appointments_for_day)}")

        for apt in appointments_for_day:
            current_app.logger.debug(
                f"Appointment ID: {apt.id}, Client ID: {apt.client_id}, "
                f"Status: {apt.status}, Payment Status: {apt.payment_status}"
            )

        # --- Генерація часових слотів ---
        # Генеруємо слоти один раз і використовуємо їх у декількох місцях
        time_intervals = generate_time_intervals()
        all_15min_slots = generate_time_slots(interval_minutes=15)

        # 2. Логування після визначення company_work_start_time, company_work_end_time
        # (Оскільки часи роботи не вказані явно в коді, логуємо з використаних функцій)
        current_app.logger.info(
            f"[SCHEDULE DIAGNOSIS] Generated time intervals count: {len(time_intervals)}, "
            f"15min slots count: {len(all_15min_slots)}"
        )

        # --- Ініціалізація schedule_data ЛИШЕ для masters_to_display ---
        schedule_data: Dict[int, Dict[str, List[Dict[str, Any]]]] = {}
        for master in masters_to_display:
            schedule_data[master.id] = {slot.strftime("%H:%M"): [] for slot in all_15min_slots}

        # Перетворюємо all_15min_slots на рядки для консистентності
        all_15min_slots_str = {slot.strftime("%H:%M") for slot in all_15min_slots}

        # --- Заповнення розкладу записами ---
        for appointment_item in appointments_for_day:
            # 7. Логування всередині циклу для кожного appointment_item
            current_app.logger.info(
                f"[SCHEDULE DIAGNOSIS] Processing appointment_item - ID: {appointment_item.id}, "
                f"master_id: {appointment_item.master_id}, date: {appointment_item.date}, "
                f"start_time: {appointment_item.start_time}, status: {appointment_item.status}"
            )

            # Особливе логування для appointment ID 205
            if appointment_item.id == 205:
                current_app.logger.info(
                    f"[SCHEDULE DIAGNOSIS] *** FOUND TARGET APPOINTMENT 205 *** - "
                    f"master_id: {appointment_item.master_id}, date: {appointment_item.date}, "
                    f"start_time: {appointment_item.start_time}, status: {appointment_item.status}"
                )

            # Перевірка, чи майстер є у списку для відображення
            master_not_in_active_set = appointment_item.master_id not in active_master_ids_set
            current_app.logger.info(
                f"[SCHEDULE DIAGNOSIS] Appointment {appointment_item.id} - "
                f"master_not_in_active_set: {master_not_in_active_set}"
            )

            if master_not_in_active_set:
                current_app.logger.info(
                    f"[SCHEDULE DIAGNOSIS] Appointment {appointment_item.id} SKIPPED - "
                    f"master {appointment_item.master_id} not in active_master_ids_set: {active_master_ids_set}"
                )
                continue

            # --- Розрахунок фінансів та CSS класу ---
            expected_price = appointment_item.get_discounted_price()
            expected_price = max(Decimal("0.00"), expected_price)
            amount_paid_val = (
                appointment_item.amount_paid if appointment_item.amount_paid is not None else Decimal("0.00")
            )
            finance_info = ""
            css_class = ""

            # Debug: Log payment status and values
            current_app.logger.debug(
                f"Appointment {appointment_item.id} - Status: '{appointment_item.status}', "
                f"Payment Status: '{appointment_item.payment_status}', "
                f"Expected Price: {expected_price}, Amount Paid: {amount_paid_val}"
            )

            if appointment_item.status == "completed":
                if appointment_item.payment_status == "paid":
                    css_class = "status-completed-paid"
                    finance_info = f"Сплачено: {amount_paid_val:.2f} грн"
                    current_app.logger.debug(
                        f"Setting CSS class to 'status-completed-paid' for appointment {appointment_item.id}"
                    )
                elif appointment_item.payment_status in ["unpaid", "partially_paid"]:
                    css_class = "status-completed-debt"
                    debt_val = expected_price - amount_paid_val
                    finance_info = f"Сплачено: {amount_paid_val:.2f} грн, Борг: {debt_val:.2f} грн"
                    current_app.logger.debug(
                        f"Setting CSS class to 'status-completed-debt' for appointment {appointment_item.id}"
                    )
            else:
                # All non-completed statuses (scheduled, etc)
                if appointment_item.payment_status == "paid":
                    css_class = "status-scheduled-paid"
                    finance_info = f"Передоплата: {amount_paid_val:.2f} грн"
                    current_app.logger.debug(
                        f"Setting CSS class to 'status-scheduled-paid' for appointment {appointment_item.id}"
                    )
                elif appointment_item.payment_status == "partially_paid" and amount_paid_val > Decimal("0.00"):
                    css_class = "status-scheduled-prepaid"
                    finance_info = f"Передоплата: {amount_paid_val:.2f} грн"
                    current_app.logger.debug(
                        f"Setting CSS class to 'status-scheduled-prepaid' for appointment {appointment_item.id}"
                    )
                else:  # unpaid
                    css_class = "status-scheduled"
                    finance_info = f"Вартість: {expected_price:.2f} грн"
                    current_app.logger.debug(
                        f"Setting CSS class to 'status-scheduled' for appointment {appointment_item.id}"
                    )

            # Add debug logging for CSS class assignment
            current_app.logger.debug(
                f"Appointment ID: {appointment_item.id}, Status: {appointment_item.status}, "
                f"Payment Status: {appointment_item.payment_status}, CSS Class: {css_class}"
            )

            # --- Визначення can_edit ---
            can_edit = current_user.is_admin or appointment_item.master_id == current_user.id

            # --- Визначення completion_info ---
            completion_info = "(Завершено)" if appointment_item.status == "completed" else ""

            # Get service names manually to avoid relationship issues
            service_names = []
            for appointment_service in appointment_item.services:
                service = (
                    db.session.get(Service, appointment_service.service_id) if appointment_service.service_id else None
                )
                if service:
                    service_names.append(service.name)

            # --- Підготовка базових деталей запису ---
            appointment_details_base = {
                "id": appointment_item.id,
                "client_name": appointment_item.client.name if appointment_item.client else "N/A",
                "phone": appointment_item.client.phone if appointment_item.client else "N/A",
                "services": service_names,
                "css_class": css_class,
                "multi_booking": appointment_item.client_id in multi_booking_client_ids,
                "finance_info": finance_info,
                "completion_info": completion_info,
                "can_edit": can_edit,
                "status": appointment_item.status,
                "is_completed": appointment_item.status == "completed",
            }

            # --- Додавання запису до слотів ---
            start_slot_str = appointment_item.start_time.strftime("%H:%M")
            slot_added_to = set()  # Щоб не дублювати

            for current_slot_time_obj in all_15min_slots:  # Використовуємо вже згенеровані слоти
                current_slot_str = current_slot_time_obj.strftime("%H:%M")

                # Перевіряємо, чи поточний слот потрапляє в інтервал запису
                if appointment_item.start_time <= current_slot_time_obj < appointment_item.end_time:
                    # Перевіряємо наявність майстра та слота
                    if (
                        appointment_item.master_id in schedule_data
                        and current_slot_str in schedule_data[appointment_item.master_id]
                    ):
                        if current_slot_str == start_slot_str and start_slot_str not in slot_added_to:
                            details = appointment_details_base.copy()
                            details["display_type"] = "full"
                            schedule_data[appointment_item.master_id][current_slot_str].append(details)
                            slot_added_to.add(start_slot_str)
                        elif current_slot_str not in slot_added_to:
                            schedule_data[appointment_item.master_id][current_slot_str].append(
                                {
                                    "id": appointment_item.id,
                                    "display_type": "continuation",
                                    "css_class": css_class,
                                }
                            )
                            slot_added_to.add(current_slot_str)
                    else:
                        current_app.logger.error(
                            "Logic error: "
                            f"Slot {current_slot_str} or "
                            f"master {appointment_item.master_id} "
                            "not found in initialized schedule_data"
                        )

            # --- Логіка 'expanded' для інтервалів ---
            starts_at_15_or_45 = appointment_item.start_time.minute in [15, 45]
            ends_at_15_or_45 = appointment_item.end_time and appointment_item.end_time.minute in [
                15,
                45,
            ]  # Перевірка на None

            if starts_at_15_or_45 or ends_at_15_or_45:
                for interval in time_intervals:
                    should_expand = False
                    for sub_slot in interval["sub_slots"]:
                        # Перевірка, чи слот потрапляє в інтервал запису
                        if appointment_item.start_time <= sub_slot < appointment_item.end_time:
                            should_expand = True
                            break
                    if should_expand:
                        interval["expanded"] = True

        # 8. Логування після циклу формування schedule_data, перед return render_template
        current_app.logger.info(f"[SCHEDULE DIAGNOSIS] schedule_data keys (master IDs): {list(schedule_data.keys())}")

        # Спроба вивести частину schedule_data для майстра ID 3
        if 3 in schedule_data:
            master_3_data = schedule_data[3]
            # Знаходимо слоти з записами для майстра 3
            non_empty_slots = {slot: appointments for slot, appointments in master_3_data.items() if appointments}
            current_app.logger.info(f"[SCHEDULE DIAGNOSIS] Master ID 3 - non-empty slots count: {len(non_empty_slots)}")
            current_app.logger.info(f"[SCHEDULE DIAGNOSIS] Master ID 3 - non-empty slots: {non_empty_slots}")
        else:
            current_app.logger.info("[SCHEDULE DIAGNOSIS] Master ID 3 NOT FOUND in schedule_data")

        # Передача даних до шаблону
        # Debug: Log the structure of schedule_data and check for appointments
        for master_id, slots in schedule_data.items():
            for slot_time, appointments in slots.items():
                if appointments:
                    current_app.logger.debug(
                        f"Master {master_id}, Slot {slot_time}: "
                        f"{[(a.get('id'), a.get('display_type'), a.get('css_class')) for a in appointments]}"
                    )

        # Check if we have any appointments with status-completed-paid
        found_completed_paid = False
        for master_id, slots in schedule_data.items():
            for slot_time, appointments in slots.items():
                for appointment in appointments:
                    if appointment.get("css_class") == "status-completed-paid":
                        found_completed_paid = True
                        current_app.logger.debug(
                            f"Found appointment with status-completed-paid: "
                            f"Master {master_id}, Slot {slot_time}, Appointment {appointment.get('id')}"
                        )

        current_app.logger.debug(f"Found status-completed-paid: {found_completed_paid}")

        return render_template(
            "main/schedule.html",
            title="Розклад майстрів",
            selected_date=selected_date,
            time_intervals=time_intervals,  # Для генерації рядків часу
            masters=masters_to_display,  # Майстри для заголовків колонок
            schedule_data=schedule_data,  # Дані для заповнення сітки
            all_15min_slots=sorted(list(all_15min_slots_str)),  # Список рядкових слотів
            is_css_test=is_css_test,  # Передаємо is_css_test для використання в шаблоні
        )

    except Exception as e_schedule:
        # Використовуємо logger замість traceback.print_exc()
        date_str_safe = request.args.get("date", "unknown")
        current_app.logger.error(
            f"Error generating schedule for date {date_str_safe}: {e_schedule}",
            exc_info=True,
        )
        flash(f"Виникла помилка при формуванні розкладу: {str(e_schedule)}", "danger")
        return redirect(url_for("main.index"))
