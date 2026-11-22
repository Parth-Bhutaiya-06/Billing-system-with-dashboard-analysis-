import pandas as pd
import streamlit as st

from services import inventory_service as svc
from services.inventory_service import ServiceError
from utils.authentication import is_admin

NO_BIKE = "(none / universal)"


def _flash():
    msg = st.session_state.pop("prod_msg", None)
    if msg:
        st.success(msg)


def _bikes_tab(bikes, bike_ids):
    st.caption("Bikes added here can be chosen for any part and appear in the description on every bill. "
               "Renaming a bike does not change bills that are already saved.")
    if bikes:
        st.dataframe(pd.DataFrame([{"ID": b["id"], "Bike": b["name"], "Parts": b["parts"]} for b in bikes]),
                     hide_index=True, width="stretch")
    with st.form("add_bike", clear_on_submit=True):
        new_name = st.text_input("New bike name (for example: Hero Splendor Plus)")
        if st.form_submit_button("Add Bike", type="primary"):
            try:
                svc.add_bike(new_name)
                st.session_state["prod_msg"] = f"Bike '{new_name.strip()}' added."
                st.rerun()
            except ServiceError as e:
                st.error(str(e))
    if not bikes:
        return
    st.divider()
    sel = st.selectbox("Select bike to rename or delete", list(bike_ids), key="bike_sel")
    bid = bike_ids[sel]
    with st.form(f"rename_bike_{bid}"):
        renamed = st.text_input("Bike name", sel)
        if st.form_submit_button("Rename"):
            try:
                svc.rename_bike(bid, renamed)
                st.session_state["prod_msg"] = "Bike renamed."
                st.rerun()
            except ServiceError as e:
                st.error(str(e))
    confirm = st.checkbox(f"I confirm I want to delete '{sel}'", key=f"bike_del_{bid}")
    if st.button("Delete Bike", disabled=not confirm):
        try:
            svc.delete_bike(bid)
            st.session_state["prod_msg"] = f"Bike '{sel}' deleted."
            st.rerun()
        except ServiceError as e:
            st.error(str(e))


def render(user):
    st.title("Products")
    _flash()
    admin = is_admin(user)
    tabs = st.tabs(["All Parts", "Add Part", "Edit / Delete"] + (["Bikes"] if admin else []))
    bikes = svc.list_bikes()
    bike_ids = {b["name"]: b["id"] for b in bikes}
    bike_names = list(bike_ids)

    with tabs[0]:
        c1, c2, c3 = st.columns([3, 1.5, 1.5])
        query = c1.text_input("Search by part no., description, bike or ID", key="prod_q")
        cat = c2.selectbox("Category", ["All"] + [c["name"] for c in svc.list_categories()], key="prod_cat")
        bike = c3.selectbox("Bike", ["All"] + bike_names, key="prod_bike")
        rows = svc.search_products(query, cat, bike=bike)
        if rows:
            df = pd.DataFrame(rows)[["id", "sku", "name", "bike", "category", "purchase_price",
                                     "selling_price", "gst_percent", "quantity", "min_stock"]]
            for col in ("purchase_price", "selling_price", "gst_percent"):
                df[col] = df[col].astype(float)
            df.columns = ["ID", "Part No.", "Description", "Bike", "Category", "Purchase Price",
                          "Selling Price", "GST %", "Qty", "Min Stock"]
            st.dataframe(df, hide_index=True, width="stretch")
            st.caption(f"{len(df)} part(s)")
        else:
            st.info("No parts match your search.")

    with tabs[1]:
        existing = [c["name"] for c in svc.list_categories()]
        if not bike_names:
            st.caption("No bikes have been added yet. An administrator can add them in the Bikes tab.")
        with st.form("add_product", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Part Description *")
            sku = c2.text_input("Part No. *")
            bike_choice = c1.selectbox("Bike", [NO_BIKE] + bike_names)
            cat_choice = c2.selectbox("Category", ["(none)"] + existing + ["+ New category"])
            new_cat = c1.text_input("New category name (if selected above)")
            pp = c2.number_input("Purchase Price", min_value=0.0, step=1.0, format="%.2f")
            sp = c1.number_input("Selling Price", min_value=0.0, step=1.0, format="%.2f")
            gst = c2.number_input("GST %", min_value=0.0, max_value=100.0, step=1.0, format="%.2f")
            qty = c1.number_input("Opening Quantity", min_value=0, step=1)
            mn = c2.number_input("Minimum Stock Level", min_value=0, step=1)
            if st.form_submit_button("Add Part", type="primary"):
                category = new_cat if cat_choice == "+ New category" else \
                    ("" if cat_choice == "(none)" else cat_choice)
                try:
                    svc.add_product(name, sku, category, pp, sp, gst, qty, mn, user["full_name"],
                                    bike_id=bike_ids.get(bike_choice))
                    st.session_state["prod_msg"] = f"Part '{name}' added."
                    st.rerun()
                except ServiceError as e:
                    st.error(str(e))

    with tabs[2]:
        rows = svc.search_products("")
        if not rows:
            st.info("No parts to edit.")
        else:
            labels = {f"{r['sku']} - {r['description']}": r["id"] for r in rows}
            choice = st.selectbox("Select part", list(labels), key="prod_edit_sel")
            p = svc.get_product(labels[choice])
            existing = [c["name"] for c in svc.list_categories()]
            with st.form(f"edit_product_{p['id']}"):
                c1, c2 = st.columns(2)
                name = c1.text_input("Part Description", p["name"])
                sku = c2.text_input("Part No.", p["sku"])
                options = [NO_BIKE] + bike_names
                idx = options.index(p["bike"]) if p["bike"] in options else 0
                bike_choice = c1.selectbox("Bike", options, index=idx)
                cat = c2.text_input("Category", p["category"], help="Type an existing or new category.")
                c1.caption("Existing categories: " + ", ".join(existing))
                pp = c1.number_input("Purchase Price", 0.0, value=float(p["purchase_price"]), step=1.0, format="%.2f")
                sp = c2.number_input("Selling Price", 0.0, value=float(p["selling_price"]), step=1.0, format="%.2f")
                gst = c1.number_input("GST %", 0.0, 100.0, value=float(p["gst_percent"]), step=1.0, format="%.2f")
                mn = c2.number_input("Minimum Stock Level", 0, value=int(p["min_stock"]), step=1)
                st.caption(f"Available quantity: {p['quantity']} (change it from the Inventory page)")
                if st.form_submit_button("Save Changes", type="primary"):
                    try:
                        svc.update_product(p["id"], name, sku, cat, pp, sp, gst, mn,
                                           bike_id=bike_ids.get(bike_choice))
                        st.session_state["prod_msg"] = "Part updated. Old invoices are unaffected."
                        st.rerun()
                    except ServiceError as e:
                        st.error(str(e))

            st.divider()
            if admin:
                st.markdown("**Delete part**")
                confirm = st.checkbox(f"I confirm I want to delete '{p['name']}'", key=f"del_conf_{p['id']}")
                if st.button("Delete Part", disabled=not confirm):
                    try:
                        result = svc.delete_product(p["id"])
                        st.session_state["prod_msg"] = (
                            f"Part {result}." + (" It has sales history, so it was hidden "
                                                "instead of removed." if result == "deactivated" else ""))
                        st.rerun()
                    except ServiceError as e:
                        st.error(str(e))
            else:
                st.caption("Only an administrator can delete parts.")

    if admin:
        with tabs[3]:
            _bikes_tab(bikes, bike_ids)
