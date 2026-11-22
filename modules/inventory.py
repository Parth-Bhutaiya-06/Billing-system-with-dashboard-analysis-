import pandas as pd
import streamlit as st

from services import inventory_service as svc
from services.inventory_service import ServiceError
from utils.helpers import fmt_money, kpi


def render(user):
    st.title("Inventory")
    msg = st.session_state.pop("inv_msg", None)
    if msg:
        st.success(msg)

    cost, retail = svc.inventory_value()
    low = svc.low_stock_products()
    rows = svc.search_products("")
    c = st.columns(4)
    c[0].markdown(kpi("Products", str(len(rows))), unsafe_allow_html=True)
    c[1].markdown(kpi("Units in Stock", f"{sum(r['quantity'] for r in rows):,}"), unsafe_allow_html=True)
    c[2].markdown(kpi("Value (Cost)", fmt_money(cost)), unsafe_allow_html=True)
    c[3].markdown(kpi("Value (Retail)", fmt_money(retail)), unsafe_allow_html=True)
    st.write("")

    tab_stock, tab_adj, tab_hist = st.tabs(["Available Stock", "Adjust Stock", "Adjustment History"])

    with tab_stock:
        if low:
            st.warning(f"Low stock: {', '.join(p['name'] for p in low)}")
        q = st.text_input("Search", key="inv_q")
        data = svc.search_products(q)
        if data:
            df = pd.DataFrame([{"ID": r["id"], "Part No.": r["sku"], "Description": r["description"],
                                "Category": r["category"], "Available": r["quantity"],
                                "Minimum": r["min_stock"],
                                "Status": "LOW" if r["quantity"] <= r["min_stock"] else "OK",
                                "Stock Value (Cost)": float(r["purchase_price"] * r["quantity"])}
                               for r in data])
            st.dataframe(df, hide_index=True, width="stretch")

    with tab_adj:
        if not rows:
            st.info("Add products first.")
        else:
            labels = {f"{r['description']} ({r['sku']}) - in stock: {r['quantity']}": r["id"] for r in rows}
            with st.form("adjust_stock", clear_on_submit=True):
                choice = st.selectbox("Product", list(labels))
                mode_label = st.radio("Action", ["Add stock", "Reduce stock", "Set exact quantity"],
                                      horizontal=True)
                value = st.number_input("Quantity", min_value=0, step=1)
                reason = st.text_input("Reason / note")
                if st.form_submit_button("Apply", type="primary"):
                    mode = {"Add stock": "add", "Reduce stock": "reduce",
                            "Set exact quantity": "set"}[mode_label]
                    try:
                        old, new = svc.adjust_stock(labels[choice], mode, value, reason, user["full_name"])
                        st.session_state["inv_msg"] = f"Stock updated: {old} -> {new}."
                        st.rerun()
                    except ServiceError as e:
                        st.error(str(e))

    with tab_hist:
        hist = svc.stock_history()
        if hist:
            st.dataframe(pd.DataFrame(hist), hide_index=True, width="stretch")
        else:
            st.info("No stock movements yet.")
