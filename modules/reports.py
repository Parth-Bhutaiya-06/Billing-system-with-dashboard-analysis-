from datetime import date, timedelta

import plotly.express as px
import streamlit as st

from services import invoice_service as svc
from utils.helpers import fmt_money, kpi


def _csv(df):
    return df.to_csv(index=False).encode("utf-8")


def render(user):
    st.title("Reports")
    today = date.today()
    period = st.radio("Period", ["Daily", "Weekly", "Monthly", "Custom"], horizontal=True)
    if period == "Daily":
        d = st.date_input("Day", today)
        start = end = d
    elif period == "Weekly":
        d = st.date_input("Any date in the week", today)
        start = d - timedelta(days=d.weekday())
        end = start + timedelta(days=6)
    elif period == "Monthly":
        d = st.date_input("Any date in the month", today)
        start = d.replace(day=1)
        end = (start.replace(month=start.month % 12 + 1, day=1) if start.month < 12
               else start.replace(year=start.year + 1, month=1, day=1)) - timedelta(days=1)
    else:
        rng = st.date_input("Date range", (today - timedelta(days=30), today))
        if not (isinstance(rng, tuple) and len(rng) == 2):
            st.info("Select both a start and an end date.")
            return
        start, end = rng
    st.caption(f"Reporting {start:%d-%b-%Y} to {end:%d-%b-%Y}")

    summ = svc.sales_summary(start, end)
    c = st.columns(3)
    c[0].markdown(kpi("Total Revenue", fmt_money(summ["revenue"])), unsafe_allow_html=True)
    c[1].markdown(kpi("Invoices", str(summ["invoices"])), unsafe_allow_html=True)
    c[2].markdown(kpi("Average Invoice", fmt_money(summ["average"])), unsafe_allow_html=True)
    st.write("")

    if summ["invoices"] == 0:
        st.info("No sales in this period.")
        return

    st.subheader("Sales by Day")
    by_day = svc.sales_by_day(start, end)
    fig = px.bar(by_day, x="Date", y="Revenue", color_discrete_sequence=["#1f4e79"])
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="white")
    st.plotly_chart(fig, width="stretch")
    st.download_button("Export sales by day (CSV)", _csv(by_day), f"sales_by_day_{start}_{end}.csv", "text/csv")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Best-Selling Products")
        top = svc.top_products(start, end, 10)
        st.dataframe(top, hide_index=True, width="stretch")
        st.download_button("Export best sellers (CSV)", _csv(top), f"best_sellers_{start}_{end}.csv", "text/csv")
    with c2:
        st.subheader("Payment-Method Breakdown")
        pay = svc.payment_breakdown(start, end)
        st.dataframe(pay, hide_index=True, width="stretch")
        fig = px.pie(pay, names="Payment Method", values="Revenue", hole=0.45)
        fig.update_layout(height=240, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, width="stretch")
        st.download_button("Export payments (CSV)", _csv(pay), f"payments_{start}_{end}.csv", "text/csv")

    st.subheader("All Invoices in Period")
    inv_df = svc.invoices_in_range(start, end)
    st.dataframe(inv_df, hide_index=True, width="stretch")
    st.download_button("Export invoices (CSV)", _csv(inv_df), f"invoices_{start}_{end}.csv", "text/csv",
                       type="primary")
