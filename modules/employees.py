import pandas as pd
import streamlit as st

from database.connection import get_session
from database.models import User
from services.inventory_service import ServiceError
from utils.authentication import hash_password, is_admin


def _list():
    with get_session() as s:
        return [{"id": u.id, "username": u.username, "full_name": u.full_name,
                 "role": u.role, "is_active": u.is_active} for u in s.query(User).order_by(User.id)]


def _add(username, full_name, password, role):
    if not username.strip() or not full_name.strip():
        raise ServiceError("Username and full name are required.")
    if len(password) < 6:
        raise ServiceError("Password must be at least 6 characters.")
    with get_session() as s:
        if s.query(User).filter(User.username == username.strip()).first():
            raise ServiceError("That username is already taken.")
        s.add(User(username=username.strip(), full_name=full_name.strip(),
                   password_hash=hash_password(password), role=role))


def _update(user_id, full_name, role, active, new_password, acting_user):
    with get_session() as s:
        u = s.get(User, user_id)
        if not u:
            raise ServiceError("User not found.")
        if u.id == acting_user["id"] and (not active or role != "admin"):
            raise ServiceError("You cannot deactivate or demote your own account.")
        if new_password:
            if len(new_password) < 6:
                raise ServiceError("Password must be at least 6 characters.")
            u.password_hash = hash_password(new_password)
        u.full_name, u.role, u.is_active = full_name.strip(), role, bool(active)


def render(user):
    st.title("Employees")
    if not is_admin(user):
        st.error("Only administrators can manage employees.")
        return
    msg = st.session_state.pop("emp_msg", None)
    if msg:
        st.success(msg)

    users = _list()
    st.dataframe(pd.DataFrame(users).rename(columns={"id": "ID", "username": "Username",
                                                     "full_name": "Name", "role": "Role",
                                                     "is_active": "Active"}),
                 hide_index=True, width="stretch")

    tab_add, tab_edit = st.tabs(["Add Employee", "Edit / Reset Password"])
    with tab_add:
        with st.form("add_emp", clear_on_submit=True):
            c1, c2 = st.columns(2)
            username = c1.text_input("Username *")
            full = c2.text_input("Full name *")
            pw = c1.text_input("Password * (min 6 chars)", type="password")
            role = c2.selectbox("Role", ["employee", "admin"])
            if st.form_submit_button("Create Account", type="primary"):
                try:
                    _add(username, full, pw, role)
                    st.session_state["emp_msg"] = f"Account '{username}' created."
                    st.rerun()
                except ServiceError as e:
                    st.error(str(e))

    with tab_edit:
        labels = {f"{u['full_name']} ({u['username']})": u for u in users}
        choice = st.selectbox("Select user", list(labels))
        u = labels[choice]
        with st.form(f"edit_emp_{u['id']}"):
            full = st.text_input("Full name", u["full_name"])
            role = st.selectbox("Role", ["employee", "admin"], index=0 if u["role"] == "employee" else 1)
            active = st.checkbox("Active", u["is_active"])
            new_pw = st.text_input("New password (leave blank to keep)", type="password")
            if st.form_submit_button("Save", type="primary"):
                try:
                    _update(u["id"], full, role, active, new_pw, user)
                    st.session_state["emp_msg"] = "Account updated."
                    st.rerun()
                except ServiceError as e:
                    st.error(str(e))
