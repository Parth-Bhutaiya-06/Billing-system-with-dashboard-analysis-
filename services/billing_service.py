"""Customer management and invoice creation (atomic bill + stock update)."""
from datetime import datetime

from sqlalchemy import or_

import config
from database.connection import get_session
from database.models import Customer, Invoice, InvoiceItem, Payment, Product
from services.inventory_service import ServiceError, apply_stock_change
from utils.calculations import calculate_invoice, money


# --------------------------------------------------------------- customers
def _cust(c: Customer) -> dict:
    return {"id": c.id, "name": c.name, "phone": c.phone or "", "email": c.email or "",
            "address": c.address or "", "is_active": c.is_active}


def add_customer(name, phone="", email="", address="") -> int:
    if not (name or "").strip():
        raise ServiceError("Customer name is required.")
    with get_session() as s:
        c = Customer(name=name.strip(), phone=(phone or "").strip(),
                     email=(email or "").strip(), address=(address or "").strip())
        s.add(c)
        s.flush()
        return c.id


def update_customer(customer_id, name, phone="", email="", address="", is_active=True):
    if not (name or "").strip():
        raise ServiceError("Customer name is required.")
    with get_session() as s:
        c = s.get(Customer, customer_id)
        if not c:
            raise ServiceError("Customer not found.")
        c.name, c.phone = name.strip(), (phone or "").strip()
        c.email, c.address = (email or "").strip(), (address or "").strip()
        c.is_active = bool(is_active)


def delete_customer(customer_id):
    """Delete if no invoices exist, otherwise deactivate."""
    with get_session() as s:
        c = s.get(Customer, customer_id)
        if not c:
            raise ServiceError("Customer not found.")
        if s.query(Invoice).filter(Invoice.customer_id == customer_id).count():
            c.is_active = False
            return "deactivated"
        s.delete(c)
        return "deleted"


def search_customers(query="", active_only=True):
    with get_session() as s:
        q = s.query(Customer)
        if active_only:
            q = q.filter(Customer.is_active.is_(True))
        if query and query.strip():
            term = f"%{query.strip()}%"
            q = q.filter(or_(Customer.name.ilike(term), Customer.phone.ilike(term),
                             Customer.email.ilike(term)))
        return [_cust(c) for c in q.order_by(Customer.name).all()]


def get_customer(customer_id):
    with get_session() as s:
        c = s.get(Customer, customer_id)
        return _cust(c) if c else None


def customer_history(customer_id):
    with get_session() as s:
        rows = s.query(Invoice).filter(Invoice.customer_id == customer_id) \
                .order_by(Invoice.created_at.desc()).all()
        return [{"Invoice": r.invoice_number, "Date": r.created_at,
                 "Total": r.grand_total, "Payment": r.payment_method,
                 "Served by": r.employee_name or ""} for r in rows]


# ----------------------------------------------------------------- invoices
def next_invoice_number(session) -> str:
    """INV-YYYYMMDD-0001 style, sequence resets daily."""
    today = datetime.now().strftime("%Y%m%d")
    prefix = f"{config.INVOICE_PREFIX}-{today}-"
    last = session.query(Invoice.invoice_number) \
        .filter(Invoice.invoice_number.like(prefix + "%")) \
        .order_by(Invoice.invoice_number.desc()).first()
    seq = int(last[0].split("-")[-1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def preview_invoice_number() -> str:
    with get_session() as s:
        return next_invoice_number(s)


def preview_totals(cart, discount_type="amount", discount_value=0) -> dict:
    """Totals for the on-screen cart. cart: list of dicts (unit_price, quantity, gst_percent)."""
    return calculate_invoice(cart, discount_type, discount_value)


def create_invoice(cart, customer_id=None, walkin_name=None, discount_type="amount",
                   discount_value=0, payment_method="Cash", user=None) -> int:
    """Save invoice, items, payment and stock deductions in ONE transaction.

    cart: list of {"product_id", "quantity"}. Prices/GST are read fresh from the
    database and frozen into the invoice items. Raises ServiceError (and rolls
    everything back) if stock is insufficient or anything is invalid.
    """
    if not cart:
        raise ServiceError("The cart is empty.")
    if payment_method not in config.PAYMENT_METHODS:
        raise ServiceError("Invalid payment method.")

    # merge duplicate lines
    merged = {}
    for line in cart:
        qty = int(line["quantity"])
        if qty <= 0:
            raise ServiceError("Quantities must be at least 1.")
        merged[line["product_id"]] = merged.get(line["product_id"], 0) + qty

    try:
        with get_session() as s:
            lines = []
            products = {}
            for pid, qty in merged.items():
                p = s.get(Product, pid)
                if not p or not p.is_active:
                    raise ServiceError("A product in the cart is no longer available.")
                if p.quantity < qty:
                    raise ServiceError(f"Insufficient stock for '{p.name}': "
                                       f"available {p.quantity}, requested {qty}.")
                products[pid] = p
                lines.append({"unit_price": p.selling_price, "quantity": qty,
                              "gst_percent": p.gst_percent})

            totals = calculate_invoice(lines, discount_type, discount_value)

            cust = s.get(Customer, customer_id) if customer_id else None
            inv = Invoice(
                invoice_number=next_invoice_number(s), created_at=datetime.now(),
                customer_id=cust.id if cust else None,
                customer_name=cust.name if cust else (walkin_name or "Walk-in Customer"),
                customer_phone=cust.phone if cust else None,
                customer_address=cust.address if cust else None,
                employee_id=(user or {}).get("id"), employee_name=(user or {}).get("full_name"),
                subtotal=totals["subtotal"], discount_amount=totals["discount"],
                gst_amount=totals["gst"], grand_total=totals["grand_total"],
                payment_method=payment_method)
            s.add(inv)
            s.flush()

            for (pid, qty), calc in zip(merged.items(), totals["lines"]):
                p = products[pid]
                s.add(InvoiceItem(invoice_id=inv.id, product_id=pid, product_name=p.name,
                                  sku=p.sku, bike_name=(p.bike.name if p.bike else None),
                                  quantity=qty, unit_price=p.selling_price,
                                  discount_amount=calc["discount"], gst_percent=p.gst_percent,
                                  gst_amount=calc["gst"], line_total=calc["total"]))
                apply_stock_change(s, pid, -qty, "Sale", (user or {}).get("full_name"),
                                   reference=inv.invoice_number)

            s.add(Payment(invoice_id=inv.id, method=payment_method, amount=totals["grand_total"]))
            return inv.id
    except ServiceError:
        raise
    except ValueError as exc:
        raise ServiceError(str(exc))
