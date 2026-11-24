"""Table definitions (SQLAlchemy Core). Mirrors sql/schema.sql."""
from sqlalchemy import (CheckConstraint, Column, Date, ForeignKey, Index, Integer,
                        MetaData, Numeric, String, Table)

metadata = MetaData()

customers = Table(
    "customers", metadata,
    Column("customer_id", Integer, primary_key=True),
    Column("first_name", String(50), nullable=False),
    Column("last_name", String(50), nullable=False),
    Column("email", String(100), nullable=False, unique=True),
    Column("phone", String(20)),
    Column("city", String(50), nullable=False),
    Column("signup_date", Date, nullable=False),
)

products = Table(
    "products", metadata,
    Column("product_id", Integer, primary_key=True),
    Column("product_name", String(100), nullable=False),
    Column("category", String(50), nullable=False),
    Column("author", String(100)),
    Column("unit_price", Numeric(10, 2), nullable=False),
    CheckConstraint("unit_price >= 0", name="ck_products_unit_price"),
)

orders = Table(
    "orders", metadata,
    Column("order_id", Integer, primary_key=True),
    Column("order_ref", String(20), nullable=False, unique=True),
    Column("customer_id", Integer, ForeignKey("customers.customer_id"), nullable=False),
    Column("order_date", Date, nullable=False),
    Column("status", String(20), nullable=False),
    Column("payment_method", String(30), nullable=False),
    CheckConstraint("status IN ('Completed','Cancelled','Pending','Returned')",
                    name="ck_orders_status"),
)

order_items = Table(
    "order_items", metadata,
    Column("order_item_id", Integer, primary_key=True),
    Column("order_id", Integer, ForeignKey("orders.order_id"), nullable=False),
    Column("product_id", Integer, ForeignKey("products.product_id"), nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("unit_price", Numeric(10, 2), nullable=False),
    CheckConstraint("quantity > 0", name="ck_order_items_quantity"),
    CheckConstraint("unit_price >= 0", name="ck_order_items_unit_price"),
)

Index("ix_orders_order_date", orders.c.order_date)
Index("ix_orders_customer_id", orders.c.customer_id)
Index("ix_order_items_order_id", order_items.c.order_id)
Index("ix_order_items_product", order_items.c.product_id)
