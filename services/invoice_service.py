"""Invoice lookup, dashboard statistics and report queries."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pandas as pd
from sqlalchemy import func, or_

from database.connection import get_session
from database.models import Customer, Invoice, InvoiceItem, Product
from utils.calculations import D, money
from utils.helpers import describe_part


def _day_start(d):
    return datetime.combine(d, time.min)


def _day_end(d):
    return datetime.combine(d, time.max)


def get_invoice(invoice_id) -> dict | None:
    """Full invoice as a plain dict (all values are frozen snapshots)."""
    with get_session() as s:
        inv = s.get(Invoice, invoice_id)
        if not inv:
            return None
        return {
            "id": inv.id, "invoice_number": inv.invoice_number, "created_at": inv.created_at,
            "customer_name": inv.customer_name, "customer_phone": inv.customer_phone or "",
            "customer_address": inv.customer_address or "",
            "employee_name": inv.employee_name or "",
            "subtotal": inv.subtotal, "discount_amount": inv.discount_amount,
            "gst_amount": inv.gst_amount, "grand_total": inv.grand_total,
            "payment_method": inv.payment_method,
            "items": [{"product_name": i.product_name, "sku": i.sku or "",
                       "bike_name": i.bike_name or "",
                       "description": describe_part(i.product_name, i.bike_name or ""),
                       "quantity": i.quantity, "unit_price": i.unit_price,
                       "discount_amount": i.discount_amount, "gst_percent": i.gst_percent,
                       "gst_amount": i.gst_amount, "line_total": i.line_total}
                      for i in inv.items]}


def search_invoices(number="", customer="", start=None, end=None, limit=1000):
    with get_session() as s:
        q = s.query(Invoice)
        if number and number.strip():
            q = q.filter(Invoice.invoice_number.ilike(f"%{number.strip()}%"))
        if customer and customer.strip():
            t = f"%{customer.strip()}%"
            q = q.filter(or_(Invoice.customer_name.ilike(t), Invoice.customer_phone.ilike(t)))
        if start:
            q = q.filter(Invoice.created_at >= _day_start(start))
        if end:
            q = q.filter(Invoice.created_at <= _day_end(end))
        rows = q.order_by(Invoice.created_at.desc()).limit(limit).all()
        return [{"id": r.id, "Invoice": r.invoice_number, "Date": r.created_at,
                 "Customer": r.customer_name, "Items": len(r.items),
                 "Total": r.grand_total, "Payment": r.payment_method,
                 "Served by": r.employee_name or ""} for r in rows]


# ---------------------------------------------------------------- dashboard
def dashboard_stats() -> dict:
    today = date.today()
    with get_session() as s:
        sales_today = s.query(func.coalesce(func.sum(Invoice.grand_total), 0)) \
            .filter(Invoice.created_at >= _day_start(today),
                    Invoice.created_at <= _day_end(today)).scalar()
        invoices_today = s.query(func.count(Invoice.id)) \
            .filter(Invoice.created_at >= _day_start(today),
                    Invoice.created_at <= _day_end(today)).scalar()
        return {
            "sales_today": money(sales_today),
            "invoices_today": invoices_today,
            "total_invoices": s.query(func.count(Invoice.id)).scalar(),
            "total_products": s.query(func.count(Product.id)).filter(Product.is_active.is_(True)).scalar(),
            "total_customers": s.query(func.count(Customer.id)).filter(Customer.is_active.is_(True)).scalar(),
        }


def recent_invoices(n=8):
    return search_invoices(limit=n)


def daily_sales(days=30) -> pd.DataFrame:
    start = date.today() - timedelta(days=days - 1)
    df = sales_by_day(start, date.today())
    full = pd.DataFrame({"Date": pd.date_range(start, date.today())})
    df["Date"] = pd.to_datetime(df["Date"])
    return full.merge(df, on="Date", how="left").fillna({"Revenue": 0, "Invoices": 0})


def monthly_sales(months=12) -> pd.DataFrame:
    start = (date.today().replace(day=1) - timedelta(days=31 * (months - 1))).replace(day=1)
    with get_session() as s:
        rows = s.query(Invoice.created_at, Invoice.grand_total) \
            .filter(Invoice.created_at >= _day_start(start)).all()
    if not rows:
        return pd.DataFrame({"Month": [], "Revenue": []})
    df = pd.DataFrame(rows, columns=["created_at", "total"])
    df["total"] = df["total"].astype(float)
    df["Month"] = pd.to_datetime(df["created_at"]).dt.to_period("M").astype(str)
    return df.groupby("Month", as_index=False)["total"].sum().rename(columns={"total": "Revenue"})


# ------------------------------------------------------------------ reports
def sales_by_day(start, end) -> pd.DataFrame:
    with get_session() as s:
        rows = s.query(Invoice.created_at, Invoice.grand_total) \
            .filter(Invoice.created_at >= _day_start(start),
                    Invoice.created_at <= _day_end(end)).all()
    if not rows:
        return pd.DataFrame({"Date": [], "Invoices": [], "Revenue": []})
    df = pd.DataFrame(rows, columns=["created_at", "total"])
    df["total"] = df["total"].astype(float)
    df["Date"] = pd.to_datetime(df["created_at"]).dt.date
    out = df.groupby("Date").agg(Invoices=("total", "count"), Revenue=("total", "sum")).reset_index()
    return out


def sales_summary(start, end) -> dict:
    with get_session() as s:
        total, count = s.query(func.coalesce(func.sum(Invoice.grand_total), 0),
                               func.count(Invoice.id)) \
            .filter(Invoice.created_at >= _day_start(start),
                    Invoice.created_at <= _day_end(end)).one()
    total = money(total)
    avg = money(total / count) if count else Decimal("0.00")
    return {"revenue": total, "invoices": count, "average": avg}


def top_products(start=None, end=None, limit=10) -> pd.DataFrame:
    with get_session() as s:
        q = s.query(InvoiceItem.product_name, func.sum(InvoiceItem.quantity),
                    func.sum(InvoiceItem.line_total)).join(Invoice)
        if start:
            q = q.filter(Invoice.created_at >= _day_start(start))
        if end:
            q = q.filter(Invoice.created_at <= _day_end(end))
        rows = q.group_by(InvoiceItem.product_name) \
            .order_by(func.sum(InvoiceItem.quantity).desc()).limit(limit).all()
    return pd.DataFrame([(r[0], int(r[1]), float(r[2])) for r in rows],
                        columns=["Product", "Units Sold", "Revenue"])


def payment_breakdown(start, end) -> pd.DataFrame:
    with get_session() as s:
        rows = s.query(Invoice.payment_method, func.count(Invoice.id),
                       func.sum(Invoice.grand_total)) \
            .filter(Invoice.created_at >= _day_start(start),
                    Invoice.created_at <= _day_end(end)) \
            .group_by(Invoice.payment_method).all()
    return pd.DataFrame([(r[0], r[1], float(r[2])) for r in rows],
                        columns=["Payment Method", "Invoices", "Revenue"])


def invoices_in_range(start, end) -> pd.DataFrame:
    rows = search_invoices(start=start, end=end, limit=100000)
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["Invoice", "Date", "Customer", "Items", "Total",
                                     "Payment", "Served by"])
    df["Total"] = df["Total"].astype(float)
    return df.drop(columns=["id"])
