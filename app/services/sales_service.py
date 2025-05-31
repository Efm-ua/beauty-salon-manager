"""
Sales service module with FIFO inventory logic.
Handles creation of sales and proper inventory depletion using FIFO methodology.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

from app.models import (Appointment, Client, GoodsReceiptItem, PaymentMethod,
                        Product, Sale, SaleItem, StockLevel, User, db)


class InsufficientStockError(Exception):
    """Raised when there's not enough stock to fulfill a sale."""

    def __init__(self, product_name: str, requested_qty: int, available_qty: int):
        self.product_name = product_name
        self.requested_qty = requested_qty
        self.available_qty = available_qty
        super().__init__(
            f"Недостатньо товару '{product_name}': запрошено {requested_qty}, " f"доступно {available_qty}"
        )


class ProductNotFoundError(Exception):
    """Raised when a product is not found."""

    pass


class SaleItemData:
    """Data structure for sale item information."""

    def __init__(self, product_id: int, quantity: int):
        self.product_id = product_id
        self.quantity = quantity
        if quantity <= 0:
            raise ValueError("Кількість повинна бути більше 0")


class SalesService:
    """Service for handling sales operations with FIFO inventory management."""

    @staticmethod
    def create_sale(
        user_id: int,
        created_by_user_id: int,
        sale_items: List[SaleItemData],
        client_id: Optional[int] = None,
        appointment_id: Optional[int] = None,
        payment_method_id: Optional[int] = None,
        notes: Optional[str] = None,
        sale_date: Optional[datetime] = None,
    ) -> Sale:
        """
        Creates a new sale with FIFO inventory depletion.

        Args:
            user_id: ID of the user who made the sale (seller)
            created_by_user_id: ID of the user who created the record
            sale_items: List of SaleItemData objects
            client_id: Optional client ID
            appointment_id: Optional appointment ID
            payment_method_id: Optional payment method ID
            notes: Optional notes
            sale_date: Optional sale date (defaults to now)

        Returns:
            Created Sale object

        Raises:
            InsufficientStockError: When there's not enough stock
            ProductNotFoundError: When a product doesn't exist
            IntegrityError: When database constraints are violated
        """
        try:
            # Validate input
            if not sale_items:
                raise ValueError("Список товарів не може бути порожнім")

            # Validate users exist
            seller = User.query.get(user_id)
            if not seller:
                raise ValueError(f"Користувач з ID {user_id} не знайдений")

            creator = User.query.get(created_by_user_id)
            if not creator:
                raise ValueError(f"Користувач з ID {created_by_user_id} не знайдений")

            # Validate optional references
            if client_id:
                client = Client.query.get(client_id)
                if not client:
                    raise ValueError(f"Клієнт з ID {client_id} не знайдений")

            if appointment_id:
                appointment = Appointment.query.get(appointment_id)
                if not appointment:
                    raise ValueError(f"Запис з ID {appointment_id} не знайдений")

            if payment_method_id:
                payment_method = PaymentMethod.query.get(payment_method_id)
                if not payment_method:
                    raise ValueError(f"Спосіб оплати з ID {payment_method_id} не знайдений")

            # Create sale
            sale = Sale()
            sale.user_id = user_id
            sale.created_by_user_id = created_by_user_id
            sale.client_id = client_id
            sale.appointment_id = appointment_id
            sale.payment_method_id = payment_method_id
            sale.notes = notes
            sale.sale_date = sale_date or datetime.now(timezone.utc)
            sale.total_amount = Decimal("0.00")

            db.session.add(sale)
            db.session.flush()  # Get sale ID

            total_amount = Decimal("0.00")

            # Process each sale item with FIFO logic
            for item_data in sale_items:
                _, item_total = SalesService._create_sale_item_with_fifo(sale, item_data)
                total_amount += item_total

            # Update sale total
            sale.total_amount = total_amount

            db.session.commit()
            return sale

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def _create_sale_item_with_fifo(sale: Sale, item_data: SaleItemData) -> Tuple[SaleItem, Decimal]:
        """
        Creates a sale item and depletes inventory using FIFO logic.

        Args:
            sale: Sale object
            item_data: SaleItemData object

        Returns:
            Tuple of (SaleItem, total_price)

        Raises:
            InsufficientStockError: When there's not enough stock
            ProductNotFoundError: When product doesn't exist
        """
        # Get product
        product = Product.query.get(item_data.product_id)
        if not product:
            raise ProductNotFoundError(f"Товар з ID {item_data.product_id} не знайдений")

        # Check current stock
        stock_level = StockLevel.query.filter_by(product_id=product.id).first()
        if not stock_level or stock_level.quantity < item_data.quantity:
            available_qty = stock_level.quantity if stock_level else 0
            raise InsufficientStockError(product.name, item_data.quantity, available_qty)

        # Get sale price
        if not product.current_sale_price:
            raise ValueError(f"Товар '{product.name}' не має встановленої ціни продажу")

        # Calculate FIFO cost price
        cost_price = SalesService._calculate_fifo_cost_and_deplete_inventory(product, item_data.quantity)

        # Create sale item
        sale_item = SaleItem()
        sale_item.sale_id = sale.id
        sale_item.product_id = product.id
        sale_item.quantity = item_data.quantity
        sale_item.price_per_unit = product.current_sale_price
        sale_item.cost_price_per_unit = cost_price

        db.session.add(sale_item)

        # Update stock level
        stock_level.quantity -= item_data.quantity
        stock_level.last_updated = datetime.now(timezone.utc)

        total_price = sale_item.price_per_unit * sale_item.quantity
        return sale_item, total_price

    @staticmethod
    def _calculate_fifo_cost_and_deplete_inventory(product: Product, quantity_needed: int) -> Decimal:
        """
        Calculates weighted average cost price using FIFO and depletes inventory batches.

        Args:
            product: Product object
            quantity_needed: Quantity to sell

        Returns:
            Weighted average cost price per unit

        Raises:
            InsufficientStockError: When there's not enough stock in receipt items
        """
        # Get all receipt items for this product, ordered by receipt date (FIFO)
        receipt_items = (
            GoodsReceiptItem.query.filter_by(product_id=product.id)
            .filter(GoodsReceiptItem.quantity_remaining > 0)
            .order_by(GoodsReceiptItem.receipt_date)
            .all()
        )

        if not receipt_items:
            raise InsufficientStockError(product.name, quantity_needed, 0)

        # Check if we have enough total quantity
        total_available = sum(item.quantity_remaining for item in receipt_items)
        if total_available < quantity_needed:
            raise InsufficientStockError(product.name, quantity_needed, total_available)

        # Calculate weighted average cost using FIFO
        remaining_needed = quantity_needed
        total_cost = Decimal("0.00")

        for receipt_item in receipt_items:
            if remaining_needed <= 0:
                break

            # Calculate how much to take from this batch
            quantity_from_batch = min(remaining_needed, receipt_item.quantity_remaining)

            # Add to total cost
            batch_cost = quantity_from_batch * receipt_item.cost_price_per_unit
            total_cost += batch_cost

            # Update remaining quantities
            receipt_item.quantity_remaining -= quantity_from_batch
            remaining_needed -= quantity_from_batch

        # Calculate weighted average cost per unit
        average_cost_per_unit = total_cost / quantity_needed
        return average_cost_per_unit

    @staticmethod
    def get_sale_by_id(sale_id: int) -> Optional[Sale]:
        """Get sale by ID with all related data."""
        return db.session.get(Sale, sale_id)

    @staticmethod
    def get_sales_by_date_range(
        start_date: datetime, end_date: datetime, client_id: Optional[int] = None, user_id: Optional[int] = None
    ) -> List[Sale]:
        """Get sales within date range with optional filters."""
        query = Sale.query.filter(Sale.sale_date >= start_date, Sale.sale_date <= end_date)

        if client_id:
            query = query.filter(Sale.client_id == client_id)

        if user_id:
            query = query.filter(Sale.user_id == user_id)

        sales: List[Sale] = (
            query.options(
                db.joinedload(Sale.items),
                db.joinedload(Sale.client),  # type: ignore[attr-defined]
                db.joinedload(Sale.seller),  # type: ignore[attr-defined]
            )
            .order_by(Sale.sale_date.desc())
            .all()
        )

        return sales

    @staticmethod
    def calculate_total_sales_amount(sales: List[Sale]) -> Decimal:
        """Calculate total amount from list of sales."""
        if not sales:
            return Decimal("0.00")
        return sum((sale.total_amount for sale in sales), Decimal("0.00"))

    @staticmethod
    def calculate_total_profit(sales: List[Sale]) -> Decimal:
        """Calculate total profit from list of sales."""
        total_profit = Decimal("0.00")
        for sale in sales:
            sale_items = SaleItem.query.filter_by(sale_id=sale.id).all()
            for item in sale_items:
                total_profit += item.profit
        return total_profit
