"""Products, categories and stock operations."""
from decimal import Decimal

from sqlalchemy import case, func, or_

from database.connection import get_session
from database.models import Bike, Category, InvoiceItem, Product, StockHistory
from utils.calculations import D, money
from utils.helpers import describe_part


class ServiceError(Exception):
    """Raised for validation / business-rule failures shown to the user."""


# ------------------------------------------------------------ categories
def list_categories():
    with get_session() as s:
        return [{"id": c.id, "name": c.name} for c in s.query(Category).order_by(Category.name)]


def get_or_create_category(session, name: str):
    name = (name or "").strip()
    if not name:
        return None
    cat = session.query(Category).filter(Category.name.ilike(name)).first()
    if not cat:
        cat = Category(name=name)
        session.add(cat)
        session.flush()
    return cat


# --------------------------------------------------------------- products
# ------------------------------------------------------------------ bikes
def list_bikes():
    with get_session() as s:
        return [{"id": b.id, "name": b.name,
                 "parts": s.query(Product).filter(Product.bike_id == b.id).count()}
                for b in s.query(Bike).order_by(Bike.name)]


def add_bike(name) -> int:
    name = (name or "").strip()
    if not name:
        raise ServiceError("Bike name is required.")
    with get_session() as s:
        if s.query(Bike).filter(func.lower(Bike.name) == name.lower()).first():
            raise ServiceError(f"Bike '{name}' already exists.")
        b = Bike(name=name)
        s.add(b)
        s.flush()
        return b.id


def rename_bike(bike_id, name):
    """Renames the master record only; saved invoices keep the name they were billed with."""
    name = (name or "").strip()
    if not name:
        raise ServiceError("Bike name is required.")
    with get_session() as s:
        b = s.get(Bike, bike_id)
        if not b:
            raise ServiceError("Bike not found.")
        clash = s.query(Bike).filter(func.lower(Bike.name) == name.lower(), Bike.id != bike_id).first()
        if clash:
            raise ServiceError(f"Bike '{name}' already exists.")
        b.name = name


def delete_bike(bike_id):
    with get_session() as s:
        b = s.get(Bike, bike_id)
        if not b:
            raise ServiceError("Bike not found.")
        used = s.query(Product).filter(Product.bike_id == bike_id).count()
        if used:
            raise ServiceError(f"{used} part(s) use this bike. Change those parts to another bike first.")
        s.delete(b)


# --------------------------------------------------------------- products
def _product_dict(p: Product) -> dict:
    return {"id": p.id, "name": p.name, "sku": p.sku,
            "category": p.category.name if p.category else "",
            "category_id": p.category_id,
            "bike": p.bike.name if p.bike else "", "bike_id": p.bike_id,
            "description": describe_part(p.name, p.bike.name if p.bike else ""),
            "purchase_price": p.purchase_price, "selling_price": p.selling_price,
            "gst_percent": p.gst_percent, "quantity": p.quantity,
            "min_stock": p.min_stock}


def _validate_product(name, sku, purchase, selling, gst, qty, min_stock):
    if not (name or "").strip():
        raise ServiceError("Product name is required.")
    if not (sku or "").strip():
        raise ServiceError("Part No. is required.")
    if D(purchase) < 0 or D(selling) < 0:
        raise ServiceError("Prices cannot be negative.")
    if not (Decimal("0") <= D(gst) <= Decimal("100")):
        raise ServiceError("GST percentage must be between 0 and 100.")
    if int(qty) < 0 or int(min_stock) < 0:
        raise ServiceError("Quantity and minimum stock cannot be negative.")


def add_product(name, sku, category, purchase_price, selling_price, gst_percent,
                quantity, min_stock, user_name="system", bike_id=None) -> int:
    _validate_product(name, sku, purchase_price, selling_price, gst_percent, quantity, min_stock)
    with get_session() as s:
        if s.query(Product).filter(Product.sku == sku.strip()).first():
            raise ServiceError(f"Part No. '{sku}' already exists.")
        cat = get_or_create_category(s, category)
        p = Product(name=name.strip(), sku=sku.strip(), category_id=cat.id if cat else None,
                    bike_id=bike_id or None,
                    purchase_price=money(purchase_price), selling_price=money(selling_price),
                    gst_percent=money(gst_percent), quantity=int(quantity),
                    min_stock=int(min_stock))
        s.add(p)
        s.flush()
        if int(quantity) > 0:
            s.add(StockHistory(product_id=p.id, change=int(quantity), old_quantity=0,
                               new_quantity=int(quantity), reason="Opening stock",
                               user_name=user_name))
        return p.id


def update_product(product_id, name, sku, category, purchase_price, selling_price,
                   gst_percent, min_stock, bike_id=None):
    _validate_product(name, sku, purchase_price, selling_price, gst_percent, 0, min_stock)
    with get_session() as s:
        p = s.get(Product, product_id)
        if not p:
            raise ServiceError("Product not found.")
        clash = s.query(Product).filter(Product.sku == sku.strip(), Product.id != product_id).first()
        if clash:
            raise ServiceError(f"Part No. '{sku}' already exists.")
        cat = get_or_create_category(s, category)
        p.name, p.sku = name.strip(), sku.strip()
        p.category_id = cat.id if cat else None
        p.purchase_price, p.selling_price = money(purchase_price), money(selling_price)
        p.gst_percent, p.min_stock = money(gst_percent), int(min_stock)
        p.bike_id = bike_id or None


def delete_product(product_id):
    """Hard delete if never sold, otherwise deactivate to protect history."""
    with get_session() as s:
        p = s.get(Product, product_id)
        if not p:
            raise ServiceError("Product not found.")
        sold = s.query(InvoiceItem).filter(InvoiceItem.product_id == product_id).count()
        if sold:
            p.is_active = False
            return "deactivated"
        s.query(StockHistory).filter(StockHistory.product_id == product_id).delete()
        s.delete(p)
        return "deleted"


def get_product(product_id):
    with get_session() as s:
        p = s.get(Product, product_id)
        return _product_dict(p) if p else None


def search_products(query="", category=None, active_only=True, in_stock_only=False,
                    bike=None):
    """Search by name, Part No. or numeric ID; optional category filter."""
    with get_session() as s:
        q = s.query(Product) \
            .outerjoin(Category, Product.category_id == Category.id) \
            .outerjoin(Bike, Product.bike_id == Bike.id)
        if active_only:
            q = q.filter(Product.is_active.is_(True))
        if query and query.strip():
            term = f"%{query.strip()}%"
            conds = [Product.name.ilike(term), Product.sku.ilike(term), Bike.name.ilike(term)]
            if query.strip().isdigit():
                conds.append(Product.id == int(query.strip()))
            q = q.filter(or_(*conds))
        if category and category != "All":
            q = q.filter(Category.name == category)
        if bike and bike != "All":
            q = q.filter(Bike.name == bike)
        if in_stock_only:
            q = q.filter(Product.quantity > 0)
        order = [Product.name]
        if query and query.strip().isdigit():
            # an exact ID or part-number match is listed first
            order.insert(0, case((Product.id == int(query.strip()), 0),
                                 (Product.sku == query.strip(), 0), else_=1))
        return [_product_dict(p) for p in q.order_by(*order).all()]


def low_stock_products():
    with get_session() as s:
        rows = s.query(Product).filter(Product.is_active.is_(True),
                                       Product.quantity <= Product.min_stock).order_by(Product.quantity).all()
        return [_product_dict(p) for p in rows]


# ------------------------------------------------------------------ stock
def apply_stock_change(session, product_id, change, reason, user_name=None, reference=None,
                       absolute=None):
    """Change stock inside an existing session/transaction and log it.

    Use `change` for add/reduce or `absolute` to set the quantity directly.
    """
    p = session.get(Product, product_id)
    if not p:
        raise ServiceError("Product not found.")
    old = p.quantity
    new = int(absolute) if absolute is not None else old + int(change)
    if new < 0:
        raise ServiceError(f"Insufficient stock for '{p.name}': available {old}, "
                           f"requested reduction {abs(new - old)}.")
    p.quantity = new
    session.add(StockHistory(product_id=p.id, change=new - old, old_quantity=old,
                             new_quantity=new, reason=reason, reference=reference,
                             user_name=user_name))
    return old, new


def adjust_stock(product_id, mode, value, reason="", user_name=None):
    """mode: 'add', 'reduce' or 'set'."""
    value = int(value)
    if value < 0:
        raise ServiceError("Quantity cannot be negative.")
    if mode == "add":
        kw = {"change": value}
        label = "Stock added"
    elif mode == "reduce":
        kw = {"change": -value}
        label = "Stock reduced"
    elif mode == "set":
        kw = {"change": 0, "absolute": value}
        label = "Manual stock update"
    else:
        raise ServiceError("Invalid adjustment mode.")
    with get_session() as s:
        return apply_stock_change(s, product_id, reason=f"{label}: {reason}".strip(": "),
                                  user_name=user_name, **kw)


def stock_history(product_id=None, limit=500):
    with get_session() as s:
        q = s.query(StockHistory)
        if product_id:
            q = q.filter(StockHistory.product_id == product_id)
        rows = q.order_by(StockHistory.id.desc()).limit(limit).all()
        return [{"Date": r.created_at, "Product": r.product.name if r.product else "",
                 "Change": r.change, "Old": r.old_quantity, "New": r.new_quantity,
                 "Reason": r.reason or "", "Reference": r.reference or "",
                 "User": r.user_name or ""} for r in rows]


def inventory_value():
    """Returns (cost_value, retail_value) of active stock."""
    with get_session() as s:
        cost = retail = Decimal("0")
        for p in s.query(Product).filter(Product.is_active.is_(True)):
            cost += D(p.purchase_price) * p.quantity
            retail += D(p.selling_price) * p.quantity
        return money(cost), money(retail)
