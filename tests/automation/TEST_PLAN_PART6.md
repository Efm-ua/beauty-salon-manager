# 📋 ПЛАН ТЕСТУВАННЯ ЧАСТИНИ 6: ЗВІТНІСТЬ

## 🎯 Мета тестування
Перевірити коректність формування та відображення даних у звітах по зарплаті майстрів, звіті по зарплаті адміністратора та фінансовому звіті, особливо в частині розрахунків, пов'язаних з послугами та продажами товарів.

## 📊 Об'єкти тестування
- **Звіт по зарплаті майстрів** (`/reports/salary`)
- **Звіт по зарплаті адміністратора** (`/reports/admin_salary`) 
- **Фінансовий звіт** (`/reports/financial`)
- **Моделі та сервісна логіка** для агрегації даних звітів
- **Розрахунки комісій** для майстрів та адміністраторів
- **FIFO логіка** собівартості товарів

## 🔧 Передумови
- Тестувальник увійшов в систему як адміністратор
- У системі є дані за поточний період:
  - Завершені записи на послуги, виконані різними майстрами та адміністратором
  - Продажі товарів, здійснені різними майстрами та адміністратором
  - Деякі продажі пов'язані з записами на послуги
  - Для майстрів та адміністраторів встановлені різні значення `configurable_commission_rate`
  - Товари мають відому собівартість завдяки документам надходження

---

## 🧪 ТЕСТ-КЕЙСИ

### 💰 **Тест 6.1: Звіт по Зарплаті Майстрів** (`/reports/salary`)

**Мета**: Перевірити повний процес формування звіту зарплати для майстрів

**Кроки**:
1. Перейти до розділу "Звіти" → "Звіт по зарплаті майстрів"
2. Обрати конкретного майстра та період (поточний день)
3. Сформувати звіт
4. Перевірити відображення ставок комісії
5. Перевірити таблицю послуг та розрахунки
6. Перевірити загальні підсумки
7. Протестувати опцію "Всі майстри"

**Очікувані результати**:
- ✅ Сторінка звіту доступна
- ✅ Ставка комісії за послуги: відображається правильна `configurable_commission_rate`
- ✅ Ставка комісії за товари: фіксовані 9%
- ✅ Таблиця записів/послуг:
  - Для кожного запису відображається "Total Price" (вартість послуг)
  - "Service Commission" = Вартість послуг × `configurable_commission_rate` / 100
- ✅ Services Summary:
  - "Total Services Cost": загальна вартість усіх послуг майстра
  - "Services Commission": загальна комісія від послуг
- ✅ Products Summary:
  - "Total Products Sold": загальна вартість проданих товарів
  - "Products Commission": `Total Products Sold × 9 / 100`
- ✅ Total Salary Calculation: `Services Commission + Products Commission`

**Тестові дані**:
- Майстер: TestMaster (комісія 15%)
- Послуга: 500.00 грн
- Продажі: 850.00 грн
- Очікувана комісія від послуг: 75.00 грн
- Очікувана комісія від товарів: 76.50 грн
- Загальна зарплата: 151.50 грн

---

### 👔 **Тест 6.2: Звіт по Зарплаті Адміністратора** (`/reports/admin_salary`)

**Мета**: Перевірити розрахунок зарплати адміністратора з трьома компонентами

**Кроки**:
1. Перейти до розділу "Звіти" → "Звіт по зарплаті адміністратора"
2. Обрати період та адміністратора
3. Сформувати звіт
4. Перевірити комісію від особистих послуг
5. Перевірити комісію від особистих продажів товарів
6. Перевірити частку від продажів товарів майстрами
7. Перевірити загальну зарплату

**Очікувані результати**:
- ✅ Сторінка звіту доступна тільки для адміністраторів
- ✅ Комісія від особистих послуг: розрахована за `configurable_commission_rate`
- ✅ Комісія від особистих продажів: `Вартість × (rate + 1%) / 100`
- ✅ Частка від продажів майстрів: `Загальна_вартість_продажів_майстрів × 1%`
- ✅ Загальна зарплата: сума всіх трьох компонентів
- ✅ Всі компоненти чітко відображені в звіті

**Тестові дані**:
- Адміністратор: TestAdminAuto (комісія 12%)
- Особисті послуги: 300.00 грн → комісія 36.00 грн
- Особисті продажі: 450.00 грн → комісія 58.50 грн (13%)
- Продажі майстрів: 850.00 грн → частка 8.50 грн (1%)
- Загальна зарплата: 103.00 грн

---

### 📈 **Тест 6.3: Фінансовий Звіт** (`/reports/financial`)

**Мета**: Перевірити правильність фінансових розрахунків та агрегації

**Кроки**:
1. Перейти до розділу "Звіти" → "Фінансовий звіт"
2. Обрати період (поточний день)
3. Сформувати звіт
4. Перевірити доходи від послуг
5. Перевірити доходи від продажу товарів
6. Перевірити собівартість проданих товарів (COGS)
7. Перевірити валовий прибуток
8. Перевірити розбивку по методах оплати
9. Протестувати сценарій з порожнім періодом

**Очікувані результати**:
- ✅ Сторінка доступна тільки для адміністраторів
- ✅ Доходи від послуг: загальна сума завершених послуг
- ✅ Доходи від продажу товарів: загальна сума виручки від товарів
- ✅ COGS: собівартість проданих товарів (з FIFO розрахунком)
- ✅ Валовий прибуток від товарів: `Доходи - COGS`
- ✅ Загальний дохід: `Послуги + Товари`
- ✅ Загальний валовий прибуток: `Послуги + Валовий_прибуток_товарів`
- ✅ Розбивка по методах оплати відображається
- ✅ Порожній період показує нульові значення

**Тестові дані**:
- Доходи від послуг: 800.00 грн (500 + 300)
- Доходи від товарів: 1300.00 грн (850 + 450)
- COGS: 720.00 грн (собівартість)
- Валовий прибуток від товарів: 580.00 грн
- Загальний дохід: 2100.00 грн
- Загальний валовий прибуток: 1380.00 грн

---

## 🔧 Технічна реалізація

### Структура тестувальника
```python
class AutomatedReportsTester:
    def __init__(self):
        self.session = requests.Session()
        self.csrf_token = None
```

### Основні методи
- `setup_test_data_for_reports()` - створення тестових даних
- `test_master_salary_report()` - тестування звіту майстрів
- `test_admin_salary_report()` - тестування звіту адміністратора
- `test_financial_report()` - тестування фінансового звіту
- `verify_calculation_accuracy()` - додаткова перевірка розрахунків

### Тестові дані
```python
# Майстер
master = User(commission_rate=15.0%)
appointment = Appointment(amount_paid=500.00)
sale = Sale(total_amount=850.00)

# Адміністратор  
admin = User(commission_rate=12.0%)
admin_appointment = Appointment(amount_paid=300.00)
admin_sale = Sale(total_amount=450.00)
```

### Розрахунки комісій

**Майстер**:
- Комісія від послуг: `500.00 × 15% = 75.00`
- Комісія від товарів: `850.00 × 9% = 76.50`
- Загальна зарплата: `75.00 + 76.50 = 151.50`

**Адміністратор**:
- Комісія від послуг: `300.00 × 12% = 36.00`
- Комісія від особистих товарів: `450.00 × 13% = 58.50`
- Частка від товарів майстрів: `850.00 × 1% = 8.50`
- Загальна зарплата: `36.00 + 58.50 + 8.50 = 103.00`

**Фінансовий звіт**:
- Доходи від послуг: `500.00 + 300.00 = 800.00`
- Доходи від товарів: `850.00 + 450.00 = 1300.00`
- COGS: `470.00 + 250.00 = 720.00`
- Валовий прибуток: `1300.00 - 720.00 = 580.00`

## 📋 Результати тестування

### ✅ Успішні тести (6/6)
1. **Логін адміністратора** - ✅ Пройдено
2. **Створення тестових даних** - ✅ Пройдено
3. **Звіт зарплати майстрів** - ✅ Пройдено
4. **Звіт зарплати адміністратора** - ✅ Пройдено
5. **Фінансовий звіт** - ✅ Пройдено
6. **Перевірка розрахунків** - ✅ Пройдено

### 🎯 Покриття функціональності
- **Звіт майстрів**: фільтрація, розрахунки комісій, загальні підсумки
- **Звіт адміністратора**: три компоненти зарплати, складні розрахунки
- **Фінансовий звіт**: FIFO собівартість, валові прибутки, розбивка платежів
- **Розрахунки**: всі формули комісій та прибутків перевірені

## 📊 Виявлені функціональності

### ✅ Працюючі функції
1. **Система комісій**: Правильно розраховує за різними ставками
2. **FIFO собівартість**: Коректно обчислює собівартість товарів
3. **Агрегація даних**: Правильно підсумовує дані за періоди
4. **Фільтрація**: Працює по майстрах, періодах, адміністраторах
5. **Безпека**: Адміністративні звіти доступні тільки адмінам
6. **Валідація**: Перевіряє дати та права доступу

### 🔍 Перевірені сценарії
- Розрахунки зарплат з різними комісійними ставками
- Комбіновані доходи від послуг та товарів
- FIFO логіка при розрахунку собівартості
- Розбивка по методах оплати
- Сценарії з порожніми періодами
- Фільтрація за майстрами та адміністраторами

## 🚀 Команди запуску

### Окремий запуск Частини 6
```bash
python tests/automation/automated_part6_reports.py
```

### У складі всіх тестів
```bash
python tests/automation/run_all_tests.py
```

### Перевірка результатів
```bash
python tests/automation/check_db.py
```

## 📈 Статистика тестування

- **Всього тестів**: 6
- **Пройдено**: 6 ✅
- **Не пройдено**: 0 ❌
- **Успішність**: 100.0%
- **Час виконання**: ~8-10 секунд

---

## 🎉 Висновки

**Частина 6** повністю автоматизована та демонструє відмінну роботу системи звітності. Система коректно:

1. **Розраховує зарплати майстрів** з індивідуальними комісіями
2. **Обчислює зарплати адміністраторів** з трьома компонентами
3. **Формує фінансові звіти** з FIFO собівартістю
4. **Агрегує дані** за різними періодами та фільтрами
5. **Забезпечує безпеку** доступу до конфіденційних даних
6. **Надає точні розрахунки** для бізнес-аналітики

Система звітності працює стабільно та готова для продакшену! 📊 