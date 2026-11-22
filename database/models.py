"""SQLAlchemy models. Money is stored as Numeric and handled as Decimal."""
from datetime import datetime

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Index, Integer,
                        Numeric, String, Text, UniqueConstraint)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), nullable=False, unique=True)
    full_name = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="employee")  # admin / employee
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.now)


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False, unique=True)


class Bike(Base):
    """Bike models, managed by the administrator and used in part descriptions."""
    __tablename__ = "bikes"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    sku = Column(String(60), nullable=False, unique=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    bike_id = Column(Integer, ForeignKey("bikes.id"), nullable=True)
    purchase_price = Column(Numeric(12, 2), nullable=False, default=0)
    selling_price = Column(Numeric(12, 2), nullable=False, default=0)
    gst_percent = Column(Numeric(5, 2), nullable=False, default=0)
    quantity = Column(Integer, nullable=False, default=0)
    min_stock = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.now)
    category = relationship("Category")
    bike = relationship("Bike")

    __table_args__ = (Index("ix_products_name", "name"),
                      Index("ix_products_category", "category_id"),
                      Index("ix_products_bike", "bike_id"))


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(20), nullable=True)
    email = Column(String(120), nullable=True)
    address = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (Index("ix_customers_name", "name"),
                      Index("ix_customers_phone", "phone"))


class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True)
    invoice_number = Column(String(30), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    # Snapshot of customer details so history never changes.
    customer_name = Column(String(120), nullable=False, default="Walk-in Customer")
    customer_phone = Column(String(20), nullable=True)
    customer_address = Column(Text, nullable=True)
    employee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    employee_name = Column(String(100), nullable=True)
    subtotal = Column(Numeric(12, 2), nullable=False, default=0)
    discount_amount = Column(Numeric(12, 2), nullable=False, default=0)
    gst_amount = Column(Numeric(12, 2), nullable=False, default=0)
    grand_total = Column(Numeric(12, 2), nullable=False, default=0)
    payment_method = Column(String(20), nullable=False, default="Cash")
    items = relationship("InvoiceItem", back_populates="invoice",
                         cascade="all, delete-orphan", order_by="InvoiceItem.id")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_invoices_created", "created_at"),
                      Index("ix_invoices_customer", "customer_id"))


class InvoiceItem(Base):
    __tablename__ = "invoice_items"
    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    # Snapshots so later price edits never alter old invoices.
    product_name = Column(String(150), nullable=False)
    sku = Column(String(60), nullable=True)
    bike_name = Column(String(100), nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    discount_amount = Column(Numeric(12, 2), nullable=False, default=0)
    gst_percent = Column(Numeric(5, 2), nullable=False, default=0)
    gst_amount = Column(Numeric(12, 2), nullable=False, default=0)
    line_total = Column(Numeric(12, 2), nullable=False)
    invoice = relationship("Invoice", back_populates="items")

    __table_args__ = (Index("ix_items_invoice", "invoice_id"),
                      Index("ix_items_product", "product_id"))


class StockHistory(Base):
    __tablename__ = "stock_history"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    change = Column(Integer, nullable=False)
    old_quantity = Column(Integer, nullable=False)
    new_quantity = Column(Integer, nullable=False)
    reason = Column(String(200), nullable=True)
    reference = Column(String(50), nullable=True)
    user_name = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    product = relationship("Product")

    __table_args__ = (Index("ix_stock_product", "product_id"),)


class BusinessSetting(Base):
    __tablename__ = "business_settings"
    id = Column(Integer, primary_key=True)
    key = Column(String(60), nullable=False)
    value = Column(Text, nullable=True)
    __table_args__ = (UniqueConstraint("key", name="uq_setting_key"),)


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    method = Column(String(20), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    paid_at = Column(DateTime, default=datetime.now)
    invoice = relationship("Invoice", back_populates="payments")

    __table_args__ = (Index("ix_payments_invoice", "invoice_id"),)
