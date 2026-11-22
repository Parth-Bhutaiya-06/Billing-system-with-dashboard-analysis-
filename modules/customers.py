import pandas as pd
import streamlit as st

from services import billing_service as bs
from services.inventory_service import ServiceError
from utils.authentication import is_admin
from utils.helpers import fmt_money


def render(user):
    st.title("Customers")
    msg = st.session_state.pop("cust_msg", None)
    if msg:
        st.success(msg)
    tab_list, tab_add, tab_edit = st.tabs(["All Customers", "Add Customer", "Edit / Purchase History"])

    with tab_list:
        q = st.text_input("Search by name, phone or email", key="cust_q")
        show_inactive = st.checkbox("Include deactivated customers")
        rows = bs.search_customers(q, active_only=not show_inactive)
        if rows:
            df = pd.DataFrame(rows).rename(columns={"id": "ID", "name": "Name", "phone": "Phone",
                                                    "email": "Email", "address": "Address",
                                                    "is_active": "Active"})
            st.dataframe(df, hide_index=True, width="stretch")
        else:
            st.info("No customers found.")

    with tab_add:
        with st.form("add_customer", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Name *")
            phone = c2.text_input("Phone")
            email = c1.text_input("Email")
            address = c2.text_area("Address", height=80)
            if st.form_submit_button("Add Customer", type="primary"):
                try:
                    bs.add_customer(name, phone, email, address)
                    st.session_state["cust_msg"] = f"Customer '{name}' added."
                    st.rerun()
                except ServiceError as e:
                    st.error(str(e))

    with tab_edit:
        rows = bs.search_customers("", active_only=False)
        if not rows:
            st.info("No customers yet.")
            return
        labels = {f"{r['name']} ({r['phone']})" + ("" if r["is_active"] else " [inactive]"): r["id"]
                  for r in rows}
        choice = st.selectbox("Select customer", list(labels))
        c = bs.get_customer(labels[choice])
        with st.form(f"edit_cust_{c['id']}"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Name", c["name"])
            phone = c2.text_input("Phone", c["phone"])
            email = c1.text_input("Email", c["email"])
            address = c2.text_area("Address", c["address"], height=80)
            active = st.checkbox("Active", c["is_active"])
            if st.form_submit_button("Save Changes", type="primary"):
                try:
                    bs.update_customer(c["id"], name, phone, email, address, active)
                    st.session_state["cust_msg"] = "Customer updated."
                    st.rerun()
                except ServiceError as e:
                    st.error(str(e))

        if is_admin(user):
            confirm = st.checkbox(f"Confirm removal of '{c['name']}'", key=f"cdel_{c['id']}")
            if st.button("Delete / Deactivate Customer", disabled=not confirm):
                result = bs.delete_customer(c["id"])
                st.session_state["cust_msg"] = (f"Customer {result}." + (
                    " They have invoices, so they were deactivated instead." if result == "deactivated" else ""))
                st.rerun()

        st.subheader("Purchase History")
        hist = bs.customer_history(c["id"])
        if hist:
            df = pd.DataFrame(hist)
            total = sum(float(h["Total"]) for h in hist)
            df["Total"] = df["Total"].astype(float).map(fmt_money)
            st.dataframe(df, hide_index=True, width="stretch")
            st.caption(f"{len(hist)} invoice(s), lifetime spend {fmt_money(total)}")
        else:
            st.info("No purchases yet.")
