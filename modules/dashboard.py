import pandas as pd
import plotly.express as px
import streamlit as st

from services import inventory_service as inv_s, invoice_service as inv
from utils.helpers import fmt_money, kpi

COLOR = "#1f4e79"


def render(user):
    st.title("Dashboard")
    stats = inv.dashboard_stats()
    cols = st.columns(4)
    items = [("Today's Sales", fmt_money(stats["sales_today"])),
             ("Total Invoices", f"{stats['total_invoices']:,}"),
             ("Total Products", f"{stats['total_products']:,}"),
             ("Total Customers", f"{stats['total_customers']:,}")]
    for col, (label, value) in zip(cols, items):
        col.markdown(kpi(label, value), unsafe_allow_html=True)
    st.write("")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Daily Sales (last 30 days)")
        df = inv.daily_sales(30)
        fig = px.bar(df, x="Date", y="Revenue", color_discrete_sequence=[COLOR])
        fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="white")
        st.plotly_chart(fig, width="stretch")
    with c2:
        st.subheader("Monthly Sales")
        mdf = inv.monthly_sales(12)
        if mdf.empty:
            st.info("No sales recorded yet.")
        else:
            fig = px.line(mdf, x="Month", y="Revenue", markers=True, color_discrete_sequence=[COLOR])
            fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="white")
            st.plotly_chart(fig, width="stretch")

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Top-Selling Products")
        top = inv.top_products(limit=5)
        if top.empty:
            st.info("No sales recorded yet.")
        else:
            fig = px.bar(top.sort_values("Units Sold"), x="Units Sold", y="Product",
                         orientation="h", color_discrete_sequence=[COLOR])
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="white")
            st.plotly_chart(fig, width="stretch")
    with c4:
        st.subheader("Low-Stock Alerts")
        low = inv_s.low_stock_products()
        if not low:
            st.success("All products are sufficiently stocked.")
        else:
            st.warning(f"{len(low)} product(s) at or below minimum stock.")
            st.dataframe(pd.DataFrame([{"Part No.": p["sku"], "Description": p["description"],
                                        "Available": p["quantity"], "Minimum": p["min_stock"]}
                                       for p in low]), hide_index=True, width="stretch")

    st.subheader("Recent Invoices")
    recent = inv.recent_invoices(8)
    if recent:
        df = pd.DataFrame(recent).drop(columns=["id"])
        df["Total"] = df["Total"].astype(float).map(fmt_money)
        st.dataframe(df, hide_index=True, width="stretch")
    else:
        st.info("No invoices yet. Create one from New Bill.")
