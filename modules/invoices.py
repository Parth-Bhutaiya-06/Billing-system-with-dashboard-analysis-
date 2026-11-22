from datetime import date, timedelta

import pandas as pd
import streamlit as st

from pdf.invoice_generator import generate_invoice_pdf
from services import invoice_service as svc
from utils.helpers import fmt_money, get_settings


def render(user):
    st.title("Invoice History")
    c1, c2, c3 = st.columns([2, 2, 3])
    number = c1.text_input("Invoice number")
    customer = c2.text_input("Customer name / phone")
    use_dates = c3.checkbox("Filter by date")
    start = end = None
    if use_dates:
        rng = c3.date_input("Date range", (date.today() - timedelta(days=30), date.today()))
        if isinstance(rng, tuple) and len(rng) == 2:
            start, end = rng
        elif isinstance(rng, tuple) and len(rng) == 1:
            start = end = rng[0]

    rows = svc.search_invoices(number, customer, start, end)
    if not rows:
        st.info("No invoices found.")
        return
    df = pd.DataFrame(rows)
    show = df.drop(columns=["id"]).copy()
    show["Total"] = show["Total"].astype(float).map(fmt_money)
    st.dataframe(show, hide_index=True, width="stretch")
    st.caption(f"{len(df)} invoice(s) | total {fmt_money(df['Total'].astype(float).sum())}")

    st.subheader("Invoice Details")
    labels = {f"{r['Invoice']} - {r['Customer']} - {fmt_money(r['Total'])}": r["id"] for r in rows}
    choice = st.selectbox("Select invoice", list(labels))
    inv = svc.get_invoice(labels[choice])
    m1, m2, m3 = st.columns(3)
    m1.write(f"**Invoice:** {inv['invoice_number']}")
    m1.write(f"**Date:** {inv['created_at']:%d-%b-%Y %H:%M}")
    m2.write(f"**Customer:** {inv['customer_name']}")
    m2.write(f"**Phone:** {inv['customer_phone'] or '-'}")
    m3.write(f"**Payment:** {inv['payment_method']}")
    m3.write(f"**Served by:** {inv['employee_name'] or '-'}")

    items = pd.DataFrame([{"S.No": n, "Part No.": i["sku"], "Description": i["description"],
                           "Qty": i["quantity"], "Price": float(i["unit_price"]),
                           "Total Amount": float(i["unit_price"] * i["quantity"])}
                          for n, i in enumerate(inv["items"], 1)])
    st.dataframe(items, hide_index=True, width="stretch")
    t = st.columns(4)
    t[0].metric("Subtotal", fmt_money(inv["subtotal"]))
    t[1].metric("Discount", fmt_money(inv["discount_amount"]))
    t[2].metric("GST", fmt_money(inv["gst_amount"]))
    t[3].metric("Grand Total", fmt_money(inv["grand_total"]))

    biz = get_settings()
    d1, d2, _ = st.columns([1, 1, 2])
    d1.download_button("Download / Reprint A4", generate_invoice_pdf(inv, biz, "A4"),
                       f"{inv['invoice_number']}_A4.pdf", "application/pdf", width="stretch")
    d2.download_button("Download 80mm Receipt", generate_invoice_pdf(inv, biz, "80mm"),
                       f"{inv['invoice_number']}_80mm.pdf", "application/pdf", width="stretch")
    st.caption("Reprints use the original saved prices, so later product price changes do not affect them.")
