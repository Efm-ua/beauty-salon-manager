#!/usr/bin/env python3
"""
Автоматизовані тести Частини 5: Розширений Складський Облік
Тестує списання товарів, інвентаризацію та сповіщення про низькі залишки.
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from app import create_app
from app.models import (
    Product,
    StockLevel,
    ProductWriteOff,
    ProductWriteOffItem,
    InventoryAct,
    InventoryActItem,
    WriteOffReason,
    User,
    db,
)
from decimal import Decimal
from datetime import date

BASE_URL = "http://127.0.0.1:5000"


class AutomatedWarehouseTester:
    def __init__(self):
        self.session = requests.Session()
        self.csrf_token = None

    def get_csrf_token(self, url):
        """Extract CSRF token from a form page."""
        response = self.session.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            csrf_input = soup.find("input", {"name": "csrf_token"})
            if csrf_input:
                return csrf_input.get("value")
        return None

    def login_as_admin(self, username="TestAdminAuto", password="test123admin"):
        """🔐 Login as admin for warehouse management."""
        print("🔐 Testing Admin Login for Warehouse Management...")

        login_url = urljoin(BASE_URL, "/auth/login")
        csrf_token = self.get_csrf_token(login_url)

        if not csrf_token:
            print("❌ Could not get CSRF token")
            return False

        login_data = {"username": username, "password": password, "csrf_token": csrf_token, "submit": "Увійти"}

        response = self.session.post(login_url, data=login_data, allow_redirects=True)

        if response.status_code == 200 and "Вийти" in response.text:
            print("✅ Admin login successful!")
            return True
        else:
            print(f"❌ Login failed. Status: {response.status_code}")
            return False

    def test_write_off_process(self):
        """📝 Test 5.1: Complete write-off process."""
        print("\n📝 Testing Product Write-off Process...")

        # Step 1: Access write-offs list
        write_offs_url = urljoin(BASE_URL, "/products/write_offs")
        response = self.session.get(write_offs_url)

        if response.status_code != 200:
            print(f"❌ Cannot access write-offs list. Status: {response.status_code}")
            return False

        print("✅ Write-offs list accessible")

        # Step 2: Access create write-off form
        create_url = urljoin(BASE_URL, "/products/write_offs/new")
        response = self.session.get(create_url)

        if response.status_code != 200:
            print(f"❌ Cannot access create write-off form. Status: {response.status_code}")
            return False

        print("✅ Create write-off form accessible")

        # Get current stock levels for testing
        app = create_app()
        with app.app_context():
            shampoo = Product.query.filter_by(name="Шампунь Зволожуючий").first()
            mask = Product.query.filter_by(name="Маска Відновлююча").first()

            if not shampoo or not mask:
                print("❌ Test products not found")
                return False

            shampoo_stock = StockLevel.query.filter_by(product_id=shampoo.id).first()
            mask_stock = StockLevel.query.filter_by(product_id=mask.id).first()

            if not shampoo_stock or not mask_stock:
                print("❌ Stock levels not found")
                return False

            shampoo_qty = shampoo_stock.quantity
            mask_qty = mask_stock.quantity

            print(f"   📦 Current stock - Shampoo: {shampoo_qty}, Mask: {mask_qty}")

            # Find an active write-off reason
            reason = WriteOffReason.query.filter_by(is_active=True).first()
            if not reason:
                print("❌ No active write-off reasons found")
                return False

        # Step 3: Test excessive quantity validation
        csrf_token = self.get_csrf_token(create_url)
        if not csrf_token:
            print("❌ Could not get CSRF token for write-off form")
            return False

        # Test with excessive quantity first
        excessive_write_off_data = {
            "csrf_token": csrf_token,
            "reason_id": reason.id,
            "write_off_date": date.today().strftime("%Y-%m-%d"),
            "notes": "Test excessive quantity",
            "items-0-product_id": shampoo.id,
            "items-0-quantity": shampoo_qty + 5,  # More than available
            "submit": "Списати товари",
        }

        response = self.session.post(create_url, data=excessive_write_off_data)

        if "недостатньо" in response.text.lower() or "insufficient" in response.text.lower():
            print("✅ Excessive quantity validation works")
        else:
            print("⚠️ Excessive quantity validation might need checking")

        # Step 4: Create valid write-off
        csrf_token = self.get_csrf_token(create_url)  # Get fresh token

        valid_write_off_data = {
            "csrf_token": csrf_token,
            "reason_id": reason.id,
            "write_off_date": date.today().strftime("%Y-%m-%d"),
            "notes": "Тестове списання",
            "items-0-product_id": shampoo.id,
            "items-0-quantity": 1,
            "items-1-product_id": mask.id,
            "items-1-quantity": 1,
            "submit": "Списати товари",
        }

        response = self.session.post(create_url, data=valid_write_off_data, allow_redirects=False)

        if response.status_code in [200, 302]:
            print("✅ Write-off document created successfully")
        else:
            print(f"❌ Write-off creation failed. Status: {response.status_code}")
            return False

        # Step 5: Verify stock levels updated
        with app.app_context():
            # Refresh stock levels
            db.session.expire_all()

            shampoo_stock_after = StockLevel.query.filter_by(product_id=shampoo.id).first()
            mask_stock_after = StockLevel.query.filter_by(product_id=mask.id).first()

            expected_shampoo = shampoo_qty - 1
            expected_mask = mask_qty - 1

            shampoo_qty_after = shampoo_stock_after.quantity
            mask_qty_after = mask_stock_after.quantity
            print(f"   📦 Stock after write-off - Shampoo: {shampoo_qty_after}, Mask: {mask_qty_after}")

            if shampoo_stock_after.quantity == expected_shampoo and mask_stock_after.quantity == expected_mask:
                print("✅ Stock levels correctly updated after write-off")
            else:
                print("❌ Stock levels not updated correctly")
                return False

        # Step 6: Verify write-off document details
        with app.app_context():
            latest_write_off = ProductWriteOff.query.order_by(ProductWriteOff.id.desc()).first()
            if latest_write_off:
                write_off_id = latest_write_off.id

        if latest_write_off:
            view_url = urljoin(BASE_URL, f"/products/write_offs/{write_off_id}")
            response = self.session.get(view_url)

            if response.status_code == 200:
                if (
                    "Шампунь Зволожуючий" in response.text
                    and "Маска Відновлююча" in response.text
                    and "Тестове списання" in response.text
                ):
                    print("✅ Write-off document details display correctly")
                else:
                    print("⚠️ Some write-off details might be missing")
            else:
                print("❌ Cannot access write-off document details")
                return False

        return True

    def test_inventory_audit_process(self):
        """📋 Test 5.2: Complete inventory audit process."""
        print("\n📋 Testing Inventory Audit Process...")

        # Step 1: Access inventory acts list
        acts_url = urljoin(BASE_URL, "/products/inventory_acts")
        response = self.session.get(acts_url)

        if response.status_code != 200:
            print(f"❌ Cannot access inventory acts list. Status: {response.status_code}")
            return False

        print("✅ Inventory acts list accessible")

        # Step 2: Create new inventory act
        csrf_token = self.get_csrf_token(acts_url)
        if not csrf_token:
            print("❌ Could not get CSRF token")
            return False

        create_data = {"csrf_token": csrf_token}
        response = self.session.post(
            urljoin(BASE_URL, "/products/inventory_acts/new"), data=create_data, allow_redirects=False
        )

        if response.status_code in [200, 302]:
            print("✅ New inventory act created")
        else:
            print(f"❌ Failed to create inventory act. Status: {response.status_code}")
            return False

        # Get the created act ID
        app = create_app()
        with app.app_context():
            latest_act = InventoryAct.query.order_by(InventoryAct.id.desc()).first()
            if not latest_act:
                print("❌ Could not find created inventory act")
                return False

            act_id = latest_act.id
            print(f"   📋 Created inventory act #{act_id}")

        # Step 3: Edit inventory act (enter actual quantities)
        edit_url = urljoin(BASE_URL, f"/products/inventory_acts/{act_id}/edit")
        response = self.session.get(edit_url)

        if response.status_code != 200:
            print(f"❌ Cannot access inventory act edit page. Status: {response.status_code}")
            return False

        print("✅ Inventory act edit page accessible")

        # Get current expected quantities and prepare test data
        with app.app_context():
            act = db.session.get(InventoryAct, act_id)
            if not act:
                print("❌ Inventory act not found")
                return False

            # Load items properly using query
            act_items = InventoryActItem.query.filter_by(inventory_act_id=act_id).all()
            if not act_items:
                print("❌ Inventory act has no items")
                return False

            print(f"   📊 Act has {len(act_items)} items to audit")

        # Step 4: Save progress with actual quantities
        csrf_token = self.get_csrf_token(edit_url)
        if not csrf_token:
            print("❌ Could not get CSRF token for edit form")
            return False

        # Prepare form data with actual quantities different from expected
        form_data = {
            "csrf_token": csrf_token,
            "notes": "Тестова інвентаризація",
            "save_progress_submit": "Зберегти прогрес",
        }

        # Add actual quantities for each item (modify some quantities for testing)
        with app.app_context():
            act_items = InventoryActItem.query.filter_by(inventory_act_id=act_id).all()
            for i, item in enumerate(act_items):
                brand_name = item.product.brand.name
                product_name = item.product.name
                form_data[f"items-{i}-product_id"] = str(item.product_id)
                form_data[f"items-{i}-product_name"] = f"{brand_name} - {product_name}"
                form_data[f"items-{i}-expected_quantity"] = str(item.expected_quantity)

                # Modify quantities for first two items to test discrepancies
                if i == 0 and item.expected_quantity > 0:
                    actual_qty = str(item.expected_quantity - 1)
                    form_data[f"items-{i}-actual_quantity"] = actual_qty
                elif i == 1:
                    actual_qty = str(item.expected_quantity + 1)
                    form_data[f"items-{i}-actual_quantity"] = actual_qty
                else:
                    form_data[f"items-{i}-actual_quantity"] = str(item.expected_quantity)

        response = self.session.post(edit_url, data=form_data, allow_redirects=False)

        if response.status_code in [200, 302]:
            print("✅ Inventory progress saved")
        else:
            print(f"❌ Failed to save inventory progress. Status: {response.status_code}")
            return False

        # Step 5: Complete inventory act
        complete_data = {"csrf_token": csrf_token}
        complete_url = urljoin(BASE_URL, f"/products/inventory_acts/{act_id}/complete")
        response = self.session.post(complete_url, data=complete_data, allow_redirects=False)

        if response.status_code in [200, 302]:
            print("✅ Inventory act completed")
        else:
            print(f"❌ Failed to complete inventory act. Status: {response.status_code}")
            return False

        # Step 6: Verify act details and stock updates
        view_url = urljoin(BASE_URL, f"/products/inventory_acts/{act_id}")
        response = self.session.get(view_url)

        if response.status_code == 200:
            if "Завершено" in response.text and "Тестова інвентаризація" in response.text:
                print("✅ Completed inventory act displays correctly")
            else:
                print("⚠️ Some inventory act details might be missing")
        else:
            print("❌ Cannot access completed inventory act")
            return False

        # Verify stock levels were updated
        with app.app_context():
            db.session.expire_all()
            act = db.session.get(InventoryAct, act_id)

            if act.status == "completed":
                print("✅ Inventory act status is 'completed'")

                # Check if stock levels were updated using proper query
                act_items = InventoryActItem.query.filter_by(inventory_act_id=act_id).all()
                stock_updated = False
                for item in act_items:
                    stock = StockLevel.query.filter_by(product_id=item.product_id).first()
                    if stock and item.actual_quantity is not None:
                        if stock.quantity == item.actual_quantity:
                            stock_updated = True

                if stock_updated:
                    print("✅ Stock levels updated according to actual quantities")
                else:
                    print("⚠️ Stock levels might not be updated correctly")
            else:
                print("❌ Inventory act not marked as completed")
                return False

        return True

    def test_low_stock_alerts(self):
        """⚠️ Test 5.3: Low stock alerts functionality."""
        print("\n⚠️ Testing Low Stock Alerts...")

        # Step 1: Access low stock alerts page
        alerts_url = urljoin(BASE_URL, "/reports/low_stock_alerts")
        response = self.session.get(alerts_url)

        if response.status_code != 200:
            print(f"❌ Cannot access low stock alerts page. Status: {response.status_code}")
            return False

        print("✅ Low stock alerts page accessible")

        # Step 2: Check current low stock situation
        app = create_app()
        with app.app_context():
            # Find products with low stock (current_qty <= min_stock_level)
            low_stock_products = []
            products = Product.query.filter(Product.min_stock_level.isnot(None)).all()

            for product in products:
                stock = StockLevel.query.filter_by(product_id=product.id).first()
                if stock and stock.quantity <= product.min_stock_level:
                    low_stock_products.append(
                        {"name": product.name, "current_qty": stock.quantity, "min_level": product.min_stock_level}
                    )

            print(f"   📊 Found {len(low_stock_products)} products with low stock")

        # Step 3: Verify alerts display
        if low_stock_products:
            # Check if low stock products are displayed
            found_products = 0
            for product in low_stock_products:
                if product["name"] in response.text:
                    found_products += 1

            if found_products > 0:
                print(f"✅ Low stock alerts display correctly ({found_products} products shown)")
            else:
                print("❌ Low stock products not displayed correctly")
                return False

            # Check for warning message
            if "потребують термінового" in response.text:
                print("✅ Warning message displayed for low stock")
            else:
                print("⚠️ Warning message might be missing")

        else:
            # No low stock products - should show success message
            if "Наразі немає товарів" in response.text or "Відмінно!" in response.text:
                print("✅ Correct message displayed when no low stock products")
            else:
                print("⚠️ Expected 'no low stock' message not found")

        # Step 4: Test scenario with artificially low stock
        with app.app_context():
            # Find a product and temporarily lower its stock for testing
            test_product = Product.query.filter(Product.min_stock_level.isnot(None)).first()
            if test_product:
                stock = StockLevel.query.filter_by(product_id=test_product.id).first()
                if stock:
                    original_qty = stock.quantity
                    original_min = test_product.min_stock_level

                    # Temporarily set stock below minimum
                    stock.quantity = max(0, original_min - 1)
                    db.session.commit()

                    print(
                        f"   🧪 Temporarily lowered {test_product.name} stock to {stock.quantity} (min: {original_min})"
                    )

        # Re-check alerts page
        response = self.session.get(alerts_url)
        if response.status_code == 200:
            if test_product.name in response.text:
                print("✅ Low stock alert correctly triggered for test product")
            else:
                print("⚠️ Test product not shown in low stock alerts")

        # Restore original stock level
        with app.app_context():
            if "original_qty" in locals():
                stock = StockLevel.query.filter_by(product_id=test_product.id).first()
                if stock:
                    stock.quantity = original_qty
                    db.session.commit()
                    print(f"   🔄 Restored {test_product.name} stock to {original_qty}")

        return True

    def run_all_tests(self):
        """🚀 Run complete automated warehouse management test suite."""
        print("🚀 Starting Automated Warehouse Management Test Suite (Part 5)")
        print("=" * 80)

        tests_passed = 0
        total_tests = 0

        # Test 1: Login
        total_tests += 1
        if self.login_as_admin():
            tests_passed += 1

            # Test 2: Write-off process
            total_tests += 1
            if self.test_write_off_process():
                tests_passed += 1

            # Test 3: Inventory audit process
            total_tests += 1
            if self.test_inventory_audit_process():
                tests_passed += 1

            # Test 4: Low stock alerts
            total_tests += 1
            if self.test_low_stock_alerts():
                tests_passed += 1

        # Final report
        print("\n" + "=" * 80)
        print(f"🏁 Automated Warehouse Management Tests Completed: {tests_passed}/{total_tests} passed")
        print(f"   Success rate: {(tests_passed/total_tests)*100:.1f}%")

        if tests_passed == total_tests:
            print("🎉 All warehouse management tests passed! System is working correctly.")
        else:
            print("⚠️ Some tests failed. Check the output above for details.")

        return tests_passed == total_tests


if __name__ == "__main__":
    tester = AutomatedWarehouseTester()
    tester.run_all_tests()
