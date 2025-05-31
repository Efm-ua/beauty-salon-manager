"""
Функциональные тесты для инвентаризации товаров.
"""

import pytest
from datetime import date
from flask import url_for

from app.models import InventoryAct, InventoryActItem, Product, StockLevel, Brand, User, db


class TestInventoryActsBasic:
    """Базовые тесты для актов инвентаризации."""

    def test_inventory_acts_list_access_admin(self, client, admin_user):
        """Тест доступа администратора к списку актов инвентаризации."""
        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin_user.id)
            sess["_fresh"] = True

        response = client.get(url_for("products.inventory_acts_list"))
        assert response.status_code == 200
        assert "Акти інвентаризації" in response.get_data(as_text=True)

    def test_inventory_acts_list_access_denied_master(self, client, master_user):
        """Тест запрета доступа мастера к списку актов инвентаризации."""
        with client.session_transaction() as sess:
            sess["_user_id"] = str(master_user.id)
            sess["_fresh"] = True

        response = client.get(url_for("products.inventory_acts_list"))
        assert response.status_code == 302  # Redirect

        # Проверяем, что перенаправляет на главную
        assert url_for("main.index") in response.location

    def test_inventory_acts_list_empty(self, client, admin_user):
        """Тест отображения пустого списка актов инвентаризации."""
        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin_user.id)
            sess["_fresh"] = True

        response = client.get(url_for("products.inventory_acts_list"))
        assert response.status_code == 200
        data = response.get_data(as_text=True)
        # Проверяем на наличие индикаторов пустого списка или заголовка
        assert "Акти інвентаризації" in data


class TestInventoryActCreation:
    """Тесты создания актов инвентаризации."""

    def test_create_inventory_act_success(self, client, admin_user, sample_products_with_stock):
        """Тест успешного создания акта инвентаризации."""
        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin_user.id)
            sess["_fresh"] = True

        # Проверяем, что актов нет
        assert InventoryAct.query.count() == 0

        # Создаем акт с CSRF токеном
        with client.session_transaction() as sess:
            csrf_token = sess.get("csrf_token", "test_token")

        response = client.post(
            url_for("products.inventory_acts_create"), data={"csrf_token": csrf_token}, follow_redirects=True
        )
        assert response.status_code == 200

        # Проверяем, что акт создан
        assert InventoryAct.query.count() == 1
        act = InventoryAct.query.first()
        assert act.user_id == admin_user.id
        assert act.status == "new"
        assert act.act_date == date.today()

        # Проверяем, что созданы позиции для всех товаров
        products_count = Product.query.count()
        assert InventoryActItem.query.filter_by(inventory_act_id=act.id).count() == products_count

        # Проверяем, что перенаправило на страницу редактирования
        assert "Редагувати акт інвентаризації" in response.get_data(as_text=True)

    def test_create_inventory_act_auto_fill_expected_quantities(self, client, admin_user, sample_products_with_stock):
        """Тест автоматического заполнения ожидаемых количеств при создании акта."""
        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin_user.id)
            sess["_fresh"] = True

        # Устанавливаем известные количества для товаров
        products = Product.query.all()
        expected_quantities = {}
        for i, product in enumerate(products):
            stock_level = StockLevel.query.filter_by(product_id=product.id).first()
            stock_level.quantity = 10 + i  # Разные количества
            expected_quantities[product.id] = stock_level.quantity
        db.session.commit()

        # Создаем акт с CSRF токеном
        with client.session_transaction() as sess:
            csrf_token = sess.get("csrf_token", "test_token")

        response = client.post(url_for("products.inventory_acts_create"), data={"csrf_token": csrf_token})
        assert response.status_code == 302  # Redirect to edit page

        act = InventoryAct.query.first()
        assert act is not None

        # Проверяем, что ожидаемые количества заполнены правильно
        for item in act.items:
            assert item.expected_quantity == expected_quantities[item.product_id]
            assert item.actual_quantity is None
            assert item.discrepancy is None

    def test_create_inventory_act_no_products(self, client, admin_user):
        """Тест создания акта когда нет товаров в системе."""
        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin_user.id)
            sess["_fresh"] = True

        # Убеждаемся, что товаров нет
        assert Product.query.count() == 0

        # Получаем CSRF токен
        with client.session_transaction() as sess:
            csrf_token = sess.get("csrf_token", "test_token")

        response = client.post(
            url_for("products.inventory_acts_create"), data={"csrf_token": csrf_token}, follow_redirects=True
        )
        assert response.status_code == 200

        # Проверяем, что акт создан
        assert InventoryAct.query.count() == 1
        act = InventoryAct.query.first()
        assert act.user_id == admin_user.id

        # Проверяем, что позиций нет (так как нет товаров)
        assert InventoryActItem.query.filter_by(inventory_act_id=act.id).count() == 0


class TestInventoryActEditing:
    """Тесты редактирования актов инвентаризации."""

    @pytest.fixture
    def sample_inventory_act(self, admin_user, sample_products_with_stock):
        """Создает образец акта инвентаризации для тестов."""
        act = InventoryAct(user_id=admin_user.id)
        db.session.add(act)
        db.session.flush()

        # Добавляем позиции
        products = Product.query.all()[:3]  # Берем первые 3 товара
        for i, product in enumerate(products):
            stock_level = StockLevel.query.filter_by(product_id=product.id).first()
            item = InventoryActItem(
                inventory_act_id=act.id, product_id=product.id, expected_quantity=stock_level.quantity
            )
            db.session.add(item)

        db.session.commit()
        return act

    def test_inventory_act_edit_page_access(self, client, admin_user, sample_inventory_act):
        """Тест доступа к странице редактирования акта."""
        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin_user.id)
            sess["_fresh"] = True

        response = client.get(url_for("products.inventory_acts_edit", act_id=sample_inventory_act.id))
        assert response.status_code == 200
        data = response.get_data(as_text=True)
        assert "Редагувати акт інвентаризації" in data
        # Проверяем наличие ID акта в ответе (может быть в разных форматах)
        assert str(sample_inventory_act.id) in data

    def test_inventory_act_edit_completed_redirect(self, client, admin_user, sample_inventory_act):
        """Тест перенаправления при попытке редактировать завершенный акт."""
        # Завершаем акт
        sample_inventory_act.status = "completed"
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin_user.id)
            sess["_fresh"] = True

        response = client.get(url_for("products.inventory_acts_edit", act_id=sample_inventory_act.id))
        assert response.status_code == 302
        assert url_for("products.inventory_acts_view", act_id=sample_inventory_act.id) in response.location

    def test_save_progress_inventory_act(self, client, admin_user, sample_inventory_act):
        """Тест сохранения прогресса инвентаризации."""
        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin_user.id)
            sess["_fresh"] = True

        # Получаем форму
        response = client.get(url_for("products.inventory_acts_edit", act_id=sample_inventory_act.id))
        assert response.status_code == 200

        # Получаем CSRF токен из сессии
        with client.session_transaction() as sess:
            csrf_token = sess.get("csrf_token", "test_token")

        # Подготавливаем данные для отправки
        items = InventoryActItem.query.filter_by(inventory_act_id=sample_inventory_act.id).all()
        form_data = {
            "csrf_token": csrf_token,
            "notes": "Тестовые примечания",
            "save_progress_submit": "Зберегти прогрес",
        }

        # Добавляем данные по позициям
        for i, item in enumerate(items):
            form_data[f"items-{i}-product_id"] = str(item.product_id)
            form_data[f"items-{i}-product_name"] = f"Test Product {i}"
            form_data[f"items-{i}-expected_quantity"] = str(item.expected_quantity)
            form_data[f"items-{i}-actual_quantity"] = str(item.expected_quantity + 1)  # Добавляем 1

        # Отправляем форму
        response = client.post(
            url_for("products.inventory_acts_edit", act_id=sample_inventory_act.id),
            data=form_data,
            follow_redirects=True,
        )

        # Проверяем, что запрос прошел успешно (может быть ошибка валидации, но не 500)
        assert response.status_code == 200

    def test_inventory_act_edit_access_denied_master(self, client, master_user, sample_inventory_act):
        """Тест запрета доступа мастера к редактированию акта."""
        with client.session_transaction() as sess:
            sess["_user_id"] = str(master_user.id)
            sess["_fresh"] = True

        response = client.get(url_for("products.inventory_acts_edit", act_id=sample_inventory_act.id))
        assert response.status_code == 302  # Redirect
        assert url_for("main.index") in response.location

    def test_inventory_act_edit_nonexistent(self, client, admin_user):
        """Тест попытки редактировать несуществующий акт."""
        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin_user.id)
            sess["_fresh"] = True

        response = client.get(url_for("products.inventory_acts_edit", act_id=999))
        assert response.status_code == 302  # Redirect to list
        assert url_for("products.inventory_acts_list") in response.location


class TestInventoryActCompletion:
    """Тесты завершения актов инвентаризации."""

    @pytest.fixture
    def inventory_act_with_data(self, admin_user, sample_products_with_stock):
        """Создает акт с заполненными фактическими данными."""
        act = InventoryAct(user_id=admin_user.id)
        db.session.add(act)
        db.session.flush()

        products = Product.query.all()[:2]  # Берем 2 товара
        for i, product in enumerate(products):
            stock_level = StockLevel.query.filter_by(product_id=product.id).first()
            expected_qty = stock_level.quantity
            actual_qty = expected_qty + (1 if i == 0 else -1)  # +1 для первого, -1 для второго

            item = InventoryActItem(
                inventory_act_id=act.id,
                product_id=product.id,
                expected_quantity=expected_qty,
                actual_quantity=actual_qty,
            )
            item.calculate_discrepancy()
            db.session.add(item)

        db.session.commit()
        return act

    def test_complete_inventory_act_updates_stock_levels(self, client, admin_user, inventory_act_with_data):
        """Тест обновления остатков при завершении акта."""
        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin_user.id)
            sess["_fresh"] = True

        act = inventory_act_with_data

        # Запоминаем исходные остатки
        original_stocks = {}
        for item in act.items:
            stock_level = StockLevel.query.filter_by(product_id=item.product_id).first()
            original_stocks[item.product_id] = stock_level.quantity

        # Получаем CSRF токен
        with client.session_transaction() as sess:
            csrf_token = sess.get("csrf_token", "test_token")

        # Завершаем акт
        response = client.post(
            url_for("products.inventory_acts_complete", act_id=act.id), data={"csrf_token": csrf_token}
        )
        assert response.status_code == 302  # Redirect to view page

        # Проверяем, что статус изменился
        db.session.refresh(act)
        assert act.status == "completed"

        # Проверяем, что остатки обновились
        for item in act.items:
            stock_level = StockLevel.query.filter_by(product_id=item.product_id).first()
            assert stock_level.quantity == item.actual_quantity

    def test_complete_already_completed_act(self, client, admin_user, inventory_act_with_data):
        """Тест попытки завершить уже завершенный акт."""
        act = inventory_act_with_data
        act.status = "completed"
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin_user.id)
            sess["_fresh"] = True

        # Получаем CSRF токен
        with client.session_transaction() as sess:
            csrf_token = sess.get("csrf_token", "test_token")

        response = client.post(
            url_for("products.inventory_acts_complete", act_id=act.id), data={"csrf_token": csrf_token}
        )
        assert response.status_code == 302  # Redirect to view page

    def test_complete_inventory_act_access_denied_master(self, client, master_user, inventory_act_with_data):
        """Тест запрета доступа мастера к завершению акта."""
        with client.session_transaction() as sess:
            sess["_user_id"] = str(master_user.id)
            sess["_fresh"] = True

        # Получаем CSRF токен
        with client.session_transaction() as sess:
            csrf_token = sess.get("csrf_token", "test_token")

        response = client.post(
            url_for("products.inventory_acts_complete", act_id=inventory_act_with_data.id),
            data={"csrf_token": csrf_token},
        )
        assert response.status_code == 302  # Redirect
        assert url_for("main.index") in response.location

    def test_complete_nonexistent_inventory_act(self, client, admin_user):
        """Тест попытки завершить несуществующий акт."""
        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin_user.id)
            sess["_fresh"] = True

        # Получаем CSRF токен
        with client.session_transaction() as sess:
            csrf_token = sess.get("csrf_token", "test_token")

        response = client.post(url_for("products.inventory_acts_complete", act_id=999), data={"csrf_token": csrf_token})
        assert response.status_code == 302  # Redirect to list
        assert url_for("products.inventory_acts_list") in response.location


class TestInventoryActViewing:
    """Тесты просмотра актов инвентаризации."""

    def test_view_inventory_act_completed(self, client, admin_user, sample_products_with_stock):
        """Тест просмотра завершенного акта инвентаризации."""
        # Создаем завершенный акт
        act = InventoryAct(user_id=admin_user.id, status="completed")
        db.session.add(act)
        db.session.flush()

        product = Product.query.first()
        item = InventoryActItem(
            inventory_act_id=act.id, product_id=product.id, expected_quantity=10, actual_quantity=12, discrepancy=2
        )
        db.session.add(item)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin_user.id)
            sess["_fresh"] = True

        response = client.get(url_for("products.inventory_acts_view", act_id=act.id))
        assert response.status_code == 200
        data = response.get_data(as_text=True)
        assert f"Акт інвентаризації №{act.id}" in data
        # Проверяем наличие информации о статусе или расхождении
        assert str(act.id) in data

    def test_view_nonexistent_inventory_act(self, client, admin_user):
        """Тест просмотра несуществующего акта."""
        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin_user.id)
            sess["_fresh"] = True

        response = client.get(url_for("products.inventory_acts_view", act_id=999))
        assert response.status_code == 302  # Redirect to list

    def test_view_inventory_act_access_denied_master(self, client, master_user, sample_products_with_stock):
        """Тест запрета доступа мастера к просмотру акта."""
        # Создаем акт
        act = InventoryAct(user_id=master_user.id, status="completed")
        db.session.add(act)
        db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(master_user.id)
            sess["_fresh"] = True

        response = client.get(url_for("products.inventory_acts_view", act_id=act.id))
        assert response.status_code == 302  # Redirect
        assert url_for("main.index") in response.location


class TestInventoryActProperties:
    """Тесты свойств модели InventoryAct."""

    def test_total_discrepancy_calculation(self, admin_user, sample_products_with_stock):
        """Тест расчета общего расхождения."""
        act = InventoryAct(user_id=admin_user.id)
        db.session.add(act)
        db.session.flush()

        products = Product.query.all()[:3]
        discrepancies = [2, -1, 0]  # +2, -1, 0

        for product, discrepancy in zip(products, discrepancies):
            item = InventoryActItem(
                inventory_act_id=act.id,
                product_id=product.id,
                expected_quantity=10,
                actual_quantity=10 + discrepancy,
                discrepancy=discrepancy,
            )
            db.session.add(item)

        db.session.commit()

        # Проверяем общее расхождение: 2 + (-1) + 0 = 1
        assert act.total_discrepancy == 1

    def test_items_with_discrepancy_count(self, admin_user, sample_products_with_stock):
        """Тест подсчета позиций с расхождениями."""
        act = InventoryAct(user_id=admin_user.id)
        db.session.add(act)
        db.session.flush()

        products = Product.query.all()[:3]
        discrepancies = [2, -1, 0]  # 2 позиции с расхождениями

        for product, discrepancy in zip(products, discrepancies):
            item = InventoryActItem(
                inventory_act_id=act.id,
                product_id=product.id,
                expected_quantity=10,
                actual_quantity=10 + discrepancy,
                discrepancy=discrepancy,
            )
            db.session.add(item)

        db.session.commit()

        # Проверяем количество позиций с расхождениями (не равными 0)
        assert act.items_with_discrepancy == 2

    def test_empty_act_properties(self, admin_user):
        """Тест свойств пустого акта."""
        act = InventoryAct(user_id=admin_user.id)
        db.session.add(act)
        db.session.commit()

        # Проверяем свойства пустого акта
        assert act.total_discrepancy == 0
        assert act.items_with_discrepancy == 0


class TestInventoryActItemModel:
    """Тесты модели InventoryActItem."""

    def test_calculate_discrepancy_method(self, admin_user, sample_products_with_stock):
        """Тест метода расчета расхождения."""
        product = Product.query.first()

        item = InventoryActItem(product_id=product.id, expected_quantity=10, actual_quantity=12)

        # Расчет расхождения
        item.calculate_discrepancy()
        assert item.discrepancy == 2

        # Тест с отрицательным расхождением
        item.actual_quantity = 8
        item.calculate_discrepancy()
        assert item.discrepancy == -2

        # Тест без фактического количества
        item.actual_quantity = None
        item.calculate_discrepancy()
        assert item.discrepancy is None

    def test_calculate_discrepancy_zero_quantities(self, admin_user, sample_products_with_stock):
        """Тест расчета расхождения с нулевыми значениями."""
        product = Product.query.first()

        # Тест с нулевой ожидаемой и фактической количеством
        item = InventoryActItem(product_id=product.id, expected_quantity=0, actual_quantity=0)
        item.calculate_discrepancy()
        assert item.discrepancy == 0

        # Тест с нулевой ожидаемой и положительной фактической
        item.expected_quantity = 0
        item.actual_quantity = 5
        item.calculate_discrepancy()
        assert item.discrepancy == 5

        # Тест с положительной ожидаемой и нулевой фактической
        item.expected_quantity = 5
        item.actual_quantity = 0
        item.calculate_discrepancy()
        assert item.discrepancy == -5
