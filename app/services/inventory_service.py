"""
Inventory service module with FIFO write-off logic.
Handles creation of product write-offs and proper inventory depletion using FIFO methodology.
"""

from datetime import datetime, timezone, date
from decimal import Decimal
from typing import List, Optional, Tuple

from app.models import (
    GoodsReceiptItem,
    Product,
    ProductWriteOff,
    ProductWriteOffItem,
    StockLevel,
    User,
    WriteOffReason,
    db,
)


class InsufficientStockError(Exception):
    """Raised when there's not enough stock to fulfill a write-off."""

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


class WriteOffReasonNotFoundError(Exception):
    """Raised when a write-off reason is not found."""

    pass


class WriteOffItemData:
    """Data structure for write-off item information."""

    def __init__(self, product_id: int, quantity: int):
        self.product_id = product_id
        self.quantity = quantity
        if quantity <= 0:
            raise ValueError("Кількість повинна бути більше 0")


class InventoryService:
    """Service for handling inventory operations including write-offs with FIFO management."""

    @staticmethod
    def create_write_off(
        user_id: int,
        reason_id: int,
        write_off_items: List[WriteOffItemData],
        notes: Optional[str] = None,
        write_off_date: Optional[date] = None,
    ) -> ProductWriteOff:
        """
        Creates a new write-off with FIFO inventory depletion.

        Args:
            user_id: ID of the user who created the write-off
            reason_id: ID of the write-off reason
            write_off_items: List of WriteOffItemData objects
            notes: Optional notes
            write_off_date: Optional write-off date (defaults to today)

        Returns:
            Created ProductWriteOff object

        Raises:
            InsufficientStockError: When there's not enough stock
            ProductNotFoundError: When a product doesn't exist
            WriteOffReasonNotFoundError: When reason doesn't exist
            IntegrityError: When database constraints are violated
        """
        try:
            # Validate input
            if not write_off_items:
                raise ValueError("Список товарів не може бути порожнім")

            # Validate user exists
            user = User.query.get(user_id)
            if not user:
                raise ValueError(f"Користувач з ID {user_id} не знайдений")

            # Validate reason exists
            reason = WriteOffReason.query.get(reason_id)
            if not reason:
                raise WriteOffReasonNotFoundError(f"Причина списання з ID {reason_id} не знайдена")

            if not reason.is_active:
                raise ValueError(f"Причина списання '{reason.name}' неактивна")

            # Create write-off
            write_off = ProductWriteOff()
            write_off.user_id = user_id
            write_off.reason_id = reason_id
            write_off.notes = notes
            write_off.write_off_date = write_off_date or datetime.now(timezone.utc).date()

            db.session.add(write_off)
            db.session.flush()  # Get write-off ID

            # Process each write-off item with FIFO logic
            for item_data in write_off_items:
                InventoryService._create_write_off_item_with_fifo(write_off, item_data)

            db.session.commit()
            return write_off

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def _create_write_off_item_with_fifo(
        write_off: ProductWriteOff, item_data: WriteOffItemData
    ) -> ProductWriteOffItem:
        """
        Creates a write-off item and depletes inventory using FIFO logic.

        Args:
            write_off: ProductWriteOff object
            item_data: WriteOffItemData object

        Returns:
            Created ProductWriteOffItem

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

        # Calculate FIFO cost price
        cost_price = InventoryService._calculate_fifo_cost_and_deplete_inventory(product, item_data.quantity)

        # Create write-off item
        write_off_item = ProductWriteOffItem()
        write_off_item.product_write_off_id = write_off.id
        write_off_item.product_id = product.id
        write_off_item.quantity = item_data.quantity
        write_off_item.cost_price_per_unit = cost_price

        db.session.add(write_off_item)

        # Update stock level
        stock_level.quantity -= item_data.quantity
        stock_level.last_updated = datetime.now(timezone.utc)

        return write_off_item

    @staticmethod
    def _calculate_fifo_cost_and_deplete_inventory(product: Product, quantity_needed: int) -> Decimal:
        """
        Calculates weighted average cost price using FIFO and depletes inventory batches.

        Args:
            product: Product object
            quantity_needed: Quantity to write off

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
    def get_write_off_by_id(write_off_id: int) -> Optional[ProductWriteOff]:
        """Get write-off by ID with all related data."""
        return db.session.get(ProductWriteOff, write_off_id)

    @staticmethod
    def get_write_offs_by_date_range(
        start_date: date, end_date: date, reason_id: Optional[int] = None, user_id: Optional[int] = None
    ) -> List[ProductWriteOff]:
        """Get write-offs within date range with optional filters."""
        query = ProductWriteOff.query.filter(
            ProductWriteOff.write_off_date >= start_date, ProductWriteOff.write_off_date <= end_date
        )

        if reason_id:
            query = query.filter(ProductWriteOff.reason_id == reason_id)

        if user_id:
            query = query.filter(ProductWriteOff.user_id == user_id)

        write_offs: List[ProductWriteOff] = (
            query.options(
                db.joinedload(ProductWriteOff.items),
                db.joinedload(ProductWriteOff.reason),
                db.joinedload(ProductWriteOff.user),
            )
            .order_by(ProductWriteOff.write_off_date.desc())
            .all()
        )

        return write_offs

    @staticmethod
    def get_active_write_off_reasons() -> List[WriteOffReason]:
        """Get all active write-off reasons."""
        return WriteOffReason.query.filter_by(is_active=True).order_by(WriteOffReason.name).all()

    @staticmethod
    def create_write_off_reason(name: str, is_active: bool = True) -> WriteOffReason:
        """Create a new write-off reason."""
        # Check if reason with this name already exists
        existing = WriteOffReason.query.filter_by(name=name).first()
        if existing:
            raise ValueError(f"Причина списання з назвою '{name}' вже існує")

        reason = WriteOffReason(name=name, is_active=is_active)
        db.session.add(reason)
        db.session.commit()
        return reason

    @staticmethod
    def update_write_off_reason(reason_id: int, name: str, is_active: bool) -> WriteOffReason:
        """Update a write-off reason."""
        reason = db.session.get(WriteOffReason, reason_id)
        if not reason:
            raise WriteOffReasonNotFoundError(f"Причина списання з ID {reason_id} не знайдена")

        # Check if name is changed and new name already exists
        if reason.name != name:
            existing = WriteOffReason.query.filter_by(name=name).first()
            if existing:
                raise ValueError(f"Причина списання з назвою '{name}' вже існує")

        reason.name = name
        reason.is_active = is_active
        db.session.commit()
        return reason

    @staticmethod
    def get_all_write_off_reasons() -> List[WriteOffReason]:
        """Get all write-off reasons (both active and inactive)."""
        return WriteOffReason.query.order_by(WriteOffReason.name).all()
