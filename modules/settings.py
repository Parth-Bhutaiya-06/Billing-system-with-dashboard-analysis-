import os

import streamlit as st

import config
from utils.authentication import is_admin
from utils.helpers import get_settings, save_settings


def render(user):
    st.title("Business Settings")
    if not is_admin(user):
        st.error("Only administrators can change settings.")
        return
    msg = st.session_state.pop("set_msg", None)
    if msg:
        st.success(msg)

    cur = get_settings()
    with st.form("settings"):
        c1, c2 = st.columns(2)
        name = c1.text_input("Business name", cur["business_name"])
        phone = c2.text_input("Mobile number", cur["business_phone"])
        email = c1.text_input("Email", cur["business_email"])
        gstin = c2.text_input("GSTIN (optional)", cur["gstin"])
        address = st.text_area("Business address", cur["business_address"], height=80)
        footer = st.text_input("Invoice footer message", cur["invoice_footer"])
        logo = st.file_uploader("Business logo (PNG or JPG)", type=["png", "jpg", "jpeg"])
        if st.form_submit_button("Save Settings", type="primary"):
            if not name.strip():
                st.error("Business name is required.")
            else:
                values = {"business_name": name.strip(), "business_phone": phone.strip(),
                          "business_email": email.strip(), "gstin": gstin.strip(),
                          "business_address": address.strip(), "invoice_footer": footer.strip()}
                if logo is not None:
                    ext = os.path.splitext(logo.name)[1].lower() or ".png"
                    path = os.path.join(config.ASSETS_DIR, f"business_logo{ext}")
                    with open(path, "wb") as f:
                        f.write(logo.getbuffer())
                    values["logo_path"] = path
                save_settings(values)
                st.session_state["set_msg"] = "Settings saved."
                st.rerun()

    st.subheader("Current Logo")
    if os.path.exists(cur["logo_path"]):
        st.image(cur["logo_path"], width=120)
