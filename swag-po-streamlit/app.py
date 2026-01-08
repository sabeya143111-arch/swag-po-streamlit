# app.py  (Streamlit + Odoo PO Creator)

import streamlit as st
import pandas as pd
from datetime import datetime
import xmlrpc.client
import io

# ========= PAGE CONFIG =========
st.set_page_config(
    page_title="SWAG Purchase Order Creator",
    page_icon="🧾",
    layout="centered",
)

st.title("🧾 SWAG Purchase Order Creator")
st.caption("Excel upload → Draft Purchase Order in Odoo (supplier, approval, receiving manually).")

st.markdown("---")

# ========= SIDEBAR: ODOO SETTINGS =========
st.sidebar.header("Odoo Connection Settings")

ODOO_URL = st.sidebar.text_input("Odoo URL", "https://tariqueswag1231.odoo.com")
ODOO_DB = st.sidebar.text_input("Database", "tariqueswag1231")
ODOO_USERNAME = st.sidebar.text_input("Username / Email", "tarique143111@gmail.com")
ODOO_API_KEY = st.sidebar.text_input("API Key / Password", type="password")

DEFAULT_PARTNER_ID = st.sidebar.number_input("Default Supplier ID", min_value=1, value=1, step=1)

st.sidebar.markdown("---")
st.sidebar.caption("Products Excel columns: `order_line/product_id`, `order_line/name`, `order_line/product_uom_qty`, `order_line/price_unit`.")

# ========= CONNECT TO ODOO (BUTTON) =========
@st.cache_resource(show_spinner=False)
def get_odoo_connection(url, db, username, api_key):
    """Return (db, uid, password, models) or raise error."""
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, api_key, {})
    if not uid:
        raise Exception("Authentication failed! URL / DB / username / API key check karo.")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return db, uid, api_key, models

connection_status = st.empty()

# ========= FILE UPLOADER =========
uploaded_file = st.file_uploader(
    "📤 Excel file upload karo (.xlsx / .xls)",
    type=["xlsx", "xls"]
)

# ========= PRODUCT HELPER =========
def get_product_id_by_code(models, db, uid, password, code):
    product_ids = models.execute_kw(
        db, uid, password,
        "product.product", "search",
        [[["default_code", "=", code]]],
        {"limit": 1},
    )
    return product_ids[0] if product_ids else False

# ========= MAIN ACTION =========
if st.button("🚀 Create Draft Purchase Order"):
    if not uploaded_file:
        st.error("Please upload an Excel file first.")
    elif not (ODOO_URL and ODOO_DB and ODOO_USERNAME and ODOO_API_KEY):
        st.error("Odoo connection details fill karo sidebar me.")
    else:
        try:
            db, uid, password, models = get_odoo_connection(
                ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY
            )
            connection_status.success(f"Connected to Odoo (UID: {uid})")
        except Exception as e:
            st.error(f"Odoo connection error: {e}")
            st.stop()

        # --- Read Excel ---
        try:
            file_bytes = uploaded_file.read()
            file_ext = uploaded_file.name.split(".")[-1].lower()

            if file_ext == "xlsx":
                df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
            else:
                df = pd.read_excel(io.BytesIO(file_bytes), engine="xlrd")
        except Exception as e:
            st.error(f"Excel read error: {e}")
            st.stop()

        st.write("### 📊 Uploaded Data Preview")
        st.dataframe(df.head())

        # Column names
        code_col = "order_line/product_id"
        name_col = "order_line/name"
        qty_col = "order_line/product_uom_qty"
        price_col = "order_line/price_unit"

        # Validate columns
        required_cols = [code_col, name_col, qty_col, price_col]
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            st.error(f"Excel me yeh columns missing hain: {missing_cols}")
            st.stop()

        # --- Build lines ---
        lines = []
        missing_products = []

        st.write("### 🔍 Product matching log")
        log_area = st.empty()
        log_messages = []

        for idx, row in df.iterrows():
            code = str(row[code_col]).strip()
            name = str(row[name_col])
            qty = float(row[qty_col])
            price = float(row[price_col])

            product_id = get_product_id_by_code(models, db, uid, password, code)
            if not product_id:
                missing_products.append({
                    "Excel Row": idx + 2,  # header + 1-index
                    "Internal Reference": code,
                    "Description": name,
                })
                log_messages.append(f"❌ Row {idx+2}: {code} → {name} (NOT FOUND)")
                log_area.text("\n".join(log_messages[-15:]))
                continue

            lines.append({
                "product_id": product_id,
                "product_qty": qty,
                "price_unit": price,
                "name": name,
            })
            log_messages.append(f"✅ Row {idx+2}: {code} → Product ID {product_id}")
            log_area.text("\n".join(log_messages[-15:]))

        st.write(f"**Matched products:** {len(lines)}/{len(df)} rows")

        if missing_products:
            st.warning("Kuch products Odoo me nahi mile – ye PO me add nahi honge.")
            st.dataframe(pd.DataFrame(missing_products))

        if not lines:
            st.error("Koi bhi product match nahi hua, PO create nahi kar sakte.")
            st.stop()

        # --- Prepare order lines ---
        order_lines = []
        for line in lines:
            order_lines.append((0, 0, {
                "product_id": line["product_id"],
                "product_qty": line["product_qty"],
                "price_unit": line["price_unit"],
                "name": line["name"],
            }))

        po_date = datetime.now().strftime("%Y-%m-%d")

        po_vals = {
            "partner_id": int(DEFAULT_PARTNER_ID),
            "date_order": po_date,
            "order_line": order_lines,
        }

        try:
            po_id = models.execute_kw(
                db, uid, password,
                "purchase.order", "create",
                [po_vals],
            )
        except Exception as e:
            st.error(f"Odoo PO create error: {e}")
            st.stop()

        st.success(f"✅ Draft Purchase Order created: ID {po_id}")
        st.info(
            "Next steps Odoo me:\n"
            f"- PO #{po_id} open karo\n"
            "- Supplier change karo (agar needed ho)\n"
            "- Confirm, Receive, aur Bill create karo"
        )
