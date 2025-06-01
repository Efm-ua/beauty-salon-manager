#!/usr/bin/env python3
"""
Швидка перевірка стану бази даних після тестів
Показує кількість та основну інформацію про всі сутності в системі.
"""

from app import create_app
from app.models import (
    User,
    WriteOffReason,
    PaymentMethod,
    Brand,
    Product,
    StockLevel,
    GoodsReceipt,
    Sale,
    SaleItem,
    Client,
    Appointment,
    ProductWriteOff,
    InventoryAct,
)


def check_database_state():
    """Перевіряє поточний стан бази даних."""
    app = create_app()

    with app.app_context():
        print("🔍 Перевірка стану бази даних...")
        print("=" * 50)

        # Користувачі
        users = User.query.all()
        admins = [u for u in users if u.is_admin]
        masters = [u for u in users if not u.is_admin]

        print(f"👥 Користувачі: {len(users)} загалом")
        print(f"   🔑 Адміністратори: {len(admins)}")
        print(f"   ✂️  Майстри: {len(masters)}")

        if admins:
            print("   Адміністратори:")
            for admin in admins:
                print(f"     - {admin.username} ({admin.full_name})")

        # Клієнти
        clients = Client.query.all()
        print(f"\n👤 Клієнти: {len(clients)}")

        if clients:
            for client in clients:
                print(f"   - {client.name} ({client.phone or 'без телефону'})")

        # Причини списання
        reasons = WriteOffReason.query.all()
        active_reasons = [r for r in reasons if r.is_active]
        print(f"\n📝 Причини списання: {len(reasons)} загалом")
        print(f"   ✅ Активні: {len(active_reasons)}")

        if active_reasons:
            print("   Активні причини:")
            for reason in active_reasons:
                print(f"     - {reason.name}")

        # Методи оплати
        payment_methods = PaymentMethod.query.all()
        print(f"\n💳 Методи оплати: {len(payment_methods)}")

        if payment_methods:
            for method in payment_methods:
                print(f"   - {method.name}")

        # Бренди
        brands = Brand.query.all()
        print(f"\n🏷️  Бренди: {len(brands)}")

        if brands:
            for brand in brands:
                product_count = Product.query.filter_by(brand_id=brand.id).count()
                print(f"   - {brand.name} ({product_count} товарів)")

        # Товари
        products = Product.query.all()
        print(f"\n📦 Товари: {len(products)}")

        if products:
            print("   Товари та залишки:")
            for product in products:
                stock = StockLevel.query.filter_by(product_id=product.id).first()
                stock_qty = stock.quantity if stock else 0
                cost_price = product.last_cost_price or 0
                print(f"     - {product.name} (SKU: {product.sku})")
                print(f"       Залишок: {stock_qty} шт., Собівартість: {cost_price} грн")

        # Надходження товарів
        receipts = GoodsReceipt.query.all()
        print(f"\n📋 Надходження товарів: {len(receipts)}")

        if receipts:
            for receipt in receipts:
                receipt_number = receipt.receipt_number or f"№{receipt.id}"
                items_count = len(receipt.items)
                print(f"   - {receipt_number} від {receipt.receipt_date} ({items_count} позицій)")

        # Продажі
        sales = Sale.query.all()
        total_sales_amount = sum(sale.total_amount for sale in sales)
        anonymous_sales = Sale.query.filter(Sale.client_id.is_(None)).count()
        client_sales = Sale.query.filter(Sale.client_id.isnot(None)).count()
        linked_sales = Sale.query.filter(Sale.appointment_id.isnot(None)).count()

        print(f"\n🛒 Продажі: {len(sales)}")
        print(f"   💰 Загальна сума продажів: {total_sales_amount:.2f} грн")
        print(f"   📊 Анонімні продажі: {anonymous_sales}")
        print(f"   👤 Продажі клієнтам: {client_sales}")
        print(f"   🔗 Продажі з прив'язкою до записів: {linked_sales}")

        # Show recent sales with appointment links
        if sales:
            print("   Останні продажі:")
            recent_sales = Sale.query.order_by(Sale.id.desc()).limit(5).all()
            for sale in recent_sales:
                client_name = sale.client.name if sale.client else "Анонімний"
                appointment_info = f" → Запис #{sale.appointment_id}" if sale.appointment_id else ""
                item_count = SaleItem.query.filter_by(sale_id=sale.id).count()
                print(
                    f"     - #{sale.id}: {client_name}, {sale.total_amount:.2f} грн ({item_count} поз.) {sale.sale_date.strftime('%d.%m.%Y %H:%M')}{appointment_info}"
                )

        # Appointments statistics
        appointments = Appointment.query.all()
        appointments_with_sales = len([a for a in appointments if Sale.query.filter_by(appointment_id=a.id).first()])

        print(f"\n📅 Записи на послуги: {len(appointments)}")
        print(f"   🔗 Записи з пов'язаними продажами: {appointments_with_sales}")

        if appointments_with_sales > 0:
            print("   Записи з продажами:")
            for appointment in appointments:
                linked_sales_count = Sale.query.filter_by(appointment_id=appointment.id).count()
                if linked_sales_count > 0:
                    print(
                        f"     - Запис #{appointment.id}: {appointment.client.name} " f"({linked_sales_count} продажів)"
                    )

        # Calculate profit
        profit_info = []
        for sale in sales:
            sale_items = SaleItem.query.filter_by(sale_id=sale.id).all()
            sale_cost = sum(item.total_cost for item in sale_items)
            sale_profit = sale.total_amount - sale_cost
            profit_info.append(sale_profit)

        # Позиції продажів
        sale_items = SaleItem.query.all()
        if sale_items:
            total_items_sold = sum(item.quantity for item in sale_items)
            total_profit = sum(item.profit for item in sale_items)
            print("\n📈 Статистика продажів:")
            print(f"   🔢 Всього позицій: {len(sale_items)}")
            print(f"   📦 Всього одиниць продано: {total_items_sold}")
            print(f"   💵 Загальний прибуток: {total_profit:.2f} грн")

        # Warehouse operations statistics
        write_offs = ProductWriteOff.query.all()
        inventory_acts = InventoryAct.query.all()

        print("\n🏭 Складські операції:")
        print(f"   📝 Документи списання: {len(write_offs)}")
        print(f"   📋 Акти інвентаризації: {len(inventory_acts)}")

        if write_offs:
            total_writeoff_cost = sum(write_off.total_cost for write_off in write_offs)
            print(f"   💸 Загальна собівартість списань: {total_writeoff_cost:.2f} грн")

            print("   Останні списання:")
            recent_writeoffs = ProductWriteOff.query.order_by(ProductWriteOff.id.desc()).limit(3).all()
            for wo in recent_writeoffs:
                reason_name = wo.reason.name if wo.reason else "Без причини"
                date_str = wo.write_off_date.strftime("%d.%m.%Y")
                wo_details = f"#{wo.id}: {reason_name}, {wo.total_cost:.2f} грн ({date_str})"
                print(f"     - {wo_details}")

        if inventory_acts:
            completed_acts = [act for act in inventory_acts if act.status == "completed"]
            print(f"   ✅ Завершені інвентаризації: {len(completed_acts)}")

            if completed_acts:
                print("   Останні інвентаризації:")
                recent_acts = sorted(completed_acts, key=lambda x: x.id, reverse=True)[:3]
                for act in recent_acts:
                    date_str = act.act_date.strftime("%d.%m.%Y")
                    print(f"     - #{act.id}: {act.status}, {date_str}")

        # Загальна статистика
        print("\n📊 Загальна статистика:")
        stats_text = (
            f"Users: {len(users)}, Clients: {len(clients)}, Brands: {len(brands)}, " f"Products: {len(products)}"
        )
        print(f"   {stats_text}")
        print(f"   PaymentMethods: {len(payment_methods)}, WriteOffReasons: {len(reasons)}")
        warehouse_stats = f"GoodsReceipts: {len(receipts)}, Sales: {len(sales)}"
        print(f"   {warehouse_stats}")
        warehouse_ops = f"WriteOffs: {len(write_offs)}, InventoryActs: {len(inventory_acts)}"
        print(f"   {warehouse_ops}")

        # Статистика для звітів (Частина 6)
        print("\n📈 Статистика для звітів:")

        # Підрахунок зарплат майстрів
        active_masters = [u for u in users if u.is_active_master and not u.is_admin]
        print(f"   👨‍💼 Активні майстри: {len(active_masters)}")

        if active_masters:
            print("   Майстри з комісійними ставками:")
            for master in active_masters:
                commission_rate = master.configurable_commission_rate or 0
                master_appointments = Appointment.query.filter_by(master_id=master.id, status="completed").count()
                master_sales_count = Sale.query.filter_by(user_id=master.id).count()
                master_info = (
                    f"     - {master.full_name}: {commission_rate}% комісії, "
                    f"{master_appointments} записів, {master_sales_count} продажів"
                )
                print(master_info)

        # Підрахунок зарплат адміністраторів
        print(f"   👔 Адміністратори: {len(admins)}")

        if admins:
            print("   Адміністратори з комісійними ставками:")
            for admin in admins:
                commission_rate = admin.configurable_commission_rate or 0
                admin_appointments = Appointment.query.filter_by(master_id=admin.id, status="completed").count()
                admin_sales_count = Sale.query.filter_by(user_id=admin.id).count()
                admin_info = (
                    f"     - {admin.full_name}: {commission_rate}% комісії, "
                    f"{admin_appointments} записів, {admin_sales_count} продажів"
                )
                print(admin_info)

        # Фінансова статистика
        total_appointments_revenue = sum(
            appointment.amount_paid or 0 for appointment in Appointment.query.filter_by(status="completed").all()
        )
        total_sales_revenue = sum(sale.total_amount for sale in sales)

        print(f"   💰 Загальний дохід від послуг: {total_appointments_revenue:.2f} грн")
        print(f"   💰 Загальний дохід від продажів: {total_sales_revenue:.2f} грн")
        total_revenue = total_appointments_revenue + total_sales_revenue
        print(f"   💰 Загальний дохід: {total_revenue:.2f} грн")

        print("\n✅ Перевірка завершена!")


if __name__ == "__main__":
    check_database_state()
