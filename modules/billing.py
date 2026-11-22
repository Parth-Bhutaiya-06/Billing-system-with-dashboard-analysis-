"""New Bill screen: shop heading, customer + date, parts search, bill table, totals."""
from datetime import datetime
from html import escape

import streamlit as st

import config
from pdf.invoice_generator import generate_invoice_pdf
from services import billing_service as bs, inventory_service as inv_s, invoice_service as invs
from services.inventory_service import ServiceError
from utils.calculations import D, money
from utils.helpers import fmt_money, get_settings

WALKIN = "Walk-in Customer"
NEW_CUSTOMER = "+ Add new customer"
RESULT_COLS = [1.5, 4.5, 1.4, 1.0, 1.3, 1.0]
BILL_COLS = [0.7, 1.6, 4.4, 1.4, 1.6, 1.9, 1.1]


def _cart():
    return st.session_state.setdefault("cart", {})  # product_id -> qty


def _reset():
    st.session_state["cart"] = {}
    for key in [k for k in list(st.session_state.keys())
                if str(k).startswith("cartq_") or k in ("bill_disc_val", "bill_walkin_name")]:
        st.session_state.pop(key, None)


def _heading(biz):
    sub = " | ".join(x for x in (biz.get("business_address"),
                                 f"Phone: {biz['business_phone']}" if biz.get("business_phone") else "") if x)
    html = f'<div class="bill-head"><h1>{escape(biz["business_name"])}</h1>'
    if sub:
        html += f"<p>{escape(sub)}</p>"
    st.markdown(html + "</div>", unsafe_allow_html=True)


def _saved_screen(invoice_id):
    inv = invs.get_invoice(invoice_id)
    st.success(f"Invoice {inv['invoice_number']} saved. Total {fmt_money(inv['grand_total'])}. Stock updated.")
    biz = get_settings()
    c1, c2, c3 = st.columns(3)
    c1.download_button("Download A4 PDF", generate_invoice_pdf(inv, biz, "A4"),
                       f"{inv['invoice_number']}_A4.pdf", "application/pdf", width="stretch")
    c2.download_button("Download 80mm Receipt", generate_invoice_pdf(inv, biz, "80mm"),
                       f"{inv['invoice_number']}_80mm.pdf", "application/pdf", width="stretch")
    if c3.button("Start New Bill", type="primary", width="stretch"):
        st.session_state.pop("last_invoice_id")
        st.rerun()
    st.caption("Open the PDF and press Ctrl+P to print.")


def _customer_row():
    customers = bs.search_customers("")
    options = [WALKIN] + [f"{c['name']} ({c['phone']})" for c in customers] + [NEW_CUSTOMER]
    pending = st.session_state.pop("_pending_customer", None)  # set before the widget exists
    if pending in options:
        st.session_state["bill_customer"] = pending

    c1, c2, c3 = st.columns([3, 1.5, 1.5])
    customer_id, walkin = None, ""
    with c1:
        sel = st.selectbox("Customer", options, key="bill_customer")
        if sel == WALKIN:
            walkin = st.text_input("Customer name", key="bill_walkin_name",
                                   placeholder="Type customer name")
        elif sel == NEW_CUSTOMER:
            with st.form("quick_customer", clear_on_submit=True):
                name = st.text_input("Name *")
                phone = st.text_input("Phone")
                if st.form_submit_button("Save customer"):
                    try:
                        bs.add_customer(name, phone)
                        st.session_state["_pending_customer"] = f"{name.strip()} ({phone.strip()})"
                        st.rerun()
                    except ServiceError as e:
                        st.error(str(e))
        else:
            customer_id = customers[options.index(sel) - 1]["id"]
    c2.text_input("Date", datetime.now().strftime("%d-%b-%Y"), disabled=True)
    c3.text_input("Invoice No.", bs.preview_invoice_number(), disabled=True)
    return customer_id, walkin


def _add_parts(cart):
    st.subheader("Add Parts")
    f1, f2, f3 = st.columns([3, 1.6, 1.6])
    query = f1.text_input("Search by part no., description or bike", key="bill_q")
    bike = f2.selectbox("Bike", ["All"] + [b["name"] for b in inv_s.list_bikes()], key="bill_bike")
    cat = f3.selectbox("Category", ["All"] + [c["name"] for c in inv_s.list_categories()], key="bill_cat")
    results = inv_s.search_products(query, cat, bike=bike, in_stock_only=True)

    with st.container(height=280, border=True):
        if not results:
            st.info("No in-stock parts match.")
            return
        for col, label in zip(st.columns(RESULT_COLS),
                              ["Part No.", "Description", "Price", "Stock", "Qty", ""]):
            col.markdown(f"**{label}**")
        for p in results[:60]:
            r = st.columns(RESULT_COLS)
            r[0].write(p["sku"])
            r[1].write(p["description"])
            r[2].write(fmt_money(p["selling_price"]))
            r[3].write(p["quantity"])
            qty = r[4].number_input("Qty", 1, p["quantity"], 1, key=f"addq_{p['id']}",
                                    label_visibility="collapsed")
            if r[5].button("Add", key=f"add_{p['id']}", width="stretch"):
                in_cart = cart.get(p["id"], 0)
                if in_cart + qty > p["quantity"]:
                    st.error(f"Only {p['quantity']} of '{p['description']}' in stock "
                             f"({in_cart} already on the bill).")
                else:
                    cart[p["id"]] = in_cart + qty
                    st.session_state[f"cartq_{p['id']}"] = cart[p["id"]]
                    st.rerun()
    if len(results) > 60:
        st.caption("Showing the first 60 matches. Refine the search to narrow down.")


def _bill_table(cart):
    st.subheader("Bill")
    display, lines = [], []
    for col, label in zip(st.columns(BILL_COLS),
                          ["S.No", "Part No.", "Description", "Qty", "Price", "Total Amount", ""]):
        col.markdown(f"**{label}**")

    for pid, qty in list(cart.items()):
        p = inv_s.get_product(pid)
        if not p or p["quantity"] <= 0:
            cart.pop(pid, None)
            continue
        qty = min(qty, p["quantity"])
        cart[pid] = qty
        key = f"cartq_{pid}"
        st.session_state[key] = max(1, min(int(st.session_state.get(key, qty)), p["quantity"]))
        n = len(display) + 1
        r = st.columns(BILL_COLS)
        r[0].write(n)
        r[1].write(p["sku"])
        r[2].write(p["description"])
        new_qty = r[3].number_input("Qty", min_value=1, max_value=p["quantity"], key=key,
                                    label_visibility="collapsed")
        r[4].write(fmt_money(p["selling_price"]))
        r[5].write(fmt_money(money(D(p["selling_price"]) * qty)))
        if new_qty != qty:
            cart[pid] = int(new_qty)
            st.rerun()
        if r[6].button("Remove", key=f"rm_{pid}"):
            cart.pop(pid, None)
            st.session_state.pop(key, None)
            st.rerun()
        lines.append({"unit_price": p["selling_price"], "quantity": qty, "gst_percent": p["gst_percent"]})
        display.append((pid, p, qty))

    if not display:
        st.info("No parts on the bill yet. Search above and press Add.")
    return display, lines


def _bill_footer(display, lines, customer_id, walkin, user):
    st.divider()
    left, right = st.columns(2, gap="large")
    with left:
        d1, d2 = st.columns(2)
        dtype_label = d1.selectbox("Discount type", ["Amount", "Percent"], key="bill_dtype")
        dtype = "percent" if dtype_label == "Percent" else "amount"
        dval = d2.number_input("Discount", min_value=0.0, step=1.0, format="%.2f", key="bill_disc_val")
        method = st.selectbox("Payment method", config.PAYMENT_METHODS, key="bill_method")

    totals = None
    with right:
        if lines:
            try:
                totals = bs.preview_totals(lines, dtype, dval)
            except ValueError as e:
                st.error(str(e))
        if totals:
            html = f'<div class="row"><span>Subtotal</span><span>{fmt_money(totals["subtotal"])}</span></div>'
            if totals["discount"] > 0:
                html += f'<div class="row"><span>Discount</span><span>- {fmt_money(totals["discount"])}</span></div>'
            if totals["gst"] > 0:
                html += f'<div class="row"><span>GST</span><span>{fmt_money(totals["gst"])}</span></div>'
            html += (f'<div class="row grand"><span>Total Amount</span>'
                     f'<span>{fmt_money(totals["grand_total"])}</span></div>')
            st.markdown(f'<div class="totals-box">{html}</div>', unsafe_allow_html=True)
        st.write("")
        b1, b2 = st.columns(2)
        if b2.button("Clear Bill", width="stretch", disabled=not display):
            _reset()
            st.rerun()
        if b1.button("Save Invoice", type="primary", width="stretch",
                     disabled=not display or totals is None):
            try:
                invoice_id = bs.create_invoice(
                    [{"product_id": pid, "quantity": qty} for pid, _, qty in display],
                    customer_id=customer_id, walkin_name=(walkin or "").strip() or WALKIN,
                    discount_type=dtype, discount_value=dval, payment_method=method, user=user)
                _reset()
                st.session_state["last_invoice_id"] = invoice_id
                st.rerun()
            except ServiceError as e:
                st.error(str(e))


def render(user):
    last = st.session_state.get("last_invoice_id")
    if last:
        _saved_screen(last)
        return
    cart = _cart()
    _heading(get_settings())
    customer_id, walkin = _customer_row()
    _add_parts(cart)
    display, lines = _bill_table(cart)
    _bill_footer(display, lines, customer_id, walkin, user)
