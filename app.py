"""RetailBill Pro - entry point. Run with: streamlit run app.py"""
import streamlit as st

import config
from database.init_db import init_db
from utils.authentication import allowed_pages, authenticate
from utils.helpers import CUSTOM_CSS, get_settings

st.set_page_config(page_title=config.APP_TITLE, page_icon=None, layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_resource
def _bootstrap():
    init_db()
    return True


_bootstrap()


def login_screen():
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown(f"## {config.APP_TITLE}")
        st.caption("Billing and Inventory Management")
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Sign in", width="stretch"):
                user = authenticate(username, password)
                if user:
                    st.session_state["user"] = user
                    st.rerun()
                else:
                    st.error("Invalid username or password.")


def render_page(page, user):
    from modules import (billing, customers, dashboard, employees, inventory, invoices,
                         products, reports, settings)
    routes = {"Dashboard": dashboard, "New Bill": billing, "Products": products,
              "Inventory": inventory, "Customers": customers, "Invoice History": invoices,
              "Reports": reports, "Employees": employees, "Settings": settings}
    routes[page].render(user)


def main():
    user = st.session_state.get("user")
    if not user:
        login_screen()
        return
    biz = get_settings()
    pages = allowed_pages(user["role"])
    with st.sidebar:
        st.markdown(f"### {biz['business_name']}")
        st.caption(f"{user['full_name']} ({user['role']})")
        page = st.radio("Navigation", pages, label_visibility="collapsed", key="nav")
        st.divider()
        if st.button("Sign out", width="stretch"):
            st.session_state.clear()
            st.rerun()
    render_page(page, user)


main()
