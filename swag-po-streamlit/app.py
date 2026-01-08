# app.py  (Premium UI – SWAG PO Creator, Multi‑Company)

import streamlit as st
import pandas as pd
from datetime import datetime
import xmlrpc.client
import io

# ========= PAGE CONFIG & CUSTOM CSS =========
st.set_page_config(
    page_title="SWAG PO Creator",
    page_icon="🧾",
    layout="wide",
)

# Minimal custom CSS for premium look
st.markdown(
    """
    <style>
    .stApp {
        background: radial-gradient(circle at top left, #111827 0, #020617 45%, #000000 100%);
        color: #e5e7eb;
        font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    .main-title {
        font-size: 2.4rem;
        font-weight: 700;
        padding-bottom: 0.3rem;
        background: linear-gradient(90deg, #38bdf8, #a855f7, #f97316);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .sub-caption {
        font-size: 0.9rem;
        color: #9ca3af;
    }
    .glass-card {
        background: rgba(15, 23, 42, 0.85);
        border-radius: 16px;
        padding: 1.2rem 1.4rem;
        border: 1px solid rgba(148, 163, 184, 0.25);
        box-shadow: 0 18px 45px rgba(15, 23, 42, 0.95);
    }
    .metric-pill {
        border-radius: 999px;
        padding: 0.25rem 0.8rem;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        background: rgba(148, 163, 184, 0.16);
        color: #cbd5f5;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
    }
    .metric-pill span.icon {
        font-size: 0.8rem;
    }
    .accent-text {
        color: #e5e7eb;
        font-weight: 500;
    }
    .upload-box > div[data-testid="stFileUploader"] {
        background: rgba(15, 23, 42, 0.8);
        border-radius: 14px;
        padding: 1.2rem;
        border: 1px dashed rgba(148, 163, 184, 0.5);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ========= HEADER =========
st.markdown('<p class="main-title">SWAG Purchase Order Creator</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-caption">Upload Excel → Auto‑create draft Purchase Orders in Odoo for your selected company.</p>',
    unsafe_allow_html=True,
)

top_left, top_right = st.columns([2, 1])
with top_left:
    st.markdown(
        '<div class="metric-pill"><span class="icon">⚡</span>'
        '<span>XML‑RPC • Multi‑Company • Excel → PO</span></div>',
        unsafe_allow_html=True,
    )
with top_right:
    st.markdown(
        '<div style="text-align:right;" class="sub-caption">'
        'Built for <span class="accent-text">Operations & Buying Teams</span>'
        '</div>',
        unsafe_allow_html=True,
    )

st.markdown("")

# ========= SIDEBAR: ODOO & HELP =========
with st.sidebar:
    st.markdown("### 🔐 Odoo Connection")
    ODOO_URL = st.text_input("Odoo URL", "https://tariqueswag1231.odoo.com")
    ODOO_DB = st.text_input("Database", "tariqueswag1231")
    ODOO_USERNAME = st.text_input("Username / Email", "tarique143111@gmail.com")
    ODOO_API_KEY = st.text_input("API Key / Password", type="password")

    st.markdown("---")
    st.markdown("### 🧾 Default Settings")
    DEFAULT_PARTNER_ID = st.number_input("Default Supplier ID", min_value=1, value=1, step=1)

    st.markdown("---")
    with st.expander("ℹ️ Excel Format Help", expanded=False):
        st.write(
            "- Required columns (exact names):\n"
            "  - `order_line/product_id` → Internal Reference / SKU\n"
            "  - `order_line/name` → Description\n"
            "  - `order_line/product_uom_qty` → Quantity\n"
            "  - `order_line/price_unit` → Unit Price\n"
        )
        st.caption("Tip: Export a PO from Odoo, use it as a template.")

connection_status = st.empty()

# ========= XML-RPC HELPERS =========
@st.cache_resource(show_spinner=False)
def get_odoo_connection(url, db, username, api_key):
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, api_key, {})
    if not uid:
        raise Exception("Authentication failed! URL / DB / username / API key check karo.")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return db, uid, api_key, models

def load_companies(models, db, uid, password):
    companies = models.execute_kw(
        db, uid, password,
        "res.company", "search_read",
        [[]],
        {"fields": ["name"], "limit": 50},
    )
    return companies

def get_product_id_by_code(models, db, uid, password, code, context=None):
    if context is None:
        context = {}
    product_ids = models.execute_kw(
        db, uid, password,
        "product.product", "search",
        [[["default_code", "=", code]]],
        {"limit": 1, "context": context},
    )
    return product_ids[0] if product_ids else False

# ========= LAYOUT: TABS =========
tab_upload, tab_log = st.tabs(["📁 Upload & Company", "📒 Matching Log & Summary"])

with tab_upload:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)

    up_left, up_right = st.columns([1.4, 1])
    with up_left:
        st.markdown("#### 1️⃣ Upload Excel")
        st.markdown(
            '<div class="upload-box">',
            unsafe_allow_html=True,
        )
        uploaded_file = st.file_uploader(
            "Drop file here or browse",
            type=["xlsx", "xls"],
            help="Max ~20MB • One sheet • Headers in first row",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with up_right:
        st.markdown("#### 2️⃣ Connect to Odoo")
        st.caption("Optional: Test connection before creating PO.")
        test_conn = st.button("🔄 Test Odoo Connection", key="test_conn")
        if test_conn:
            if not (ODOO_URL and ODOO_DB and ODOO_USERNAME and ODOO_API_KEY):
                st.error("Sidebar me Odoo connection details complete karo.")
            else:
                try:
                    db, uid, password, models = get_odoo_connection(
                        ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY
                    )
                    connection_status.success(f"Connected to Odoo (UID: {uid})")
                except Exception as e:
                    connection_status.error(f"❌ Connection failed: {e}")

    st.markdown("---")

    st.markdown("#### 3️⃣ Company & Action")
    act_left, act_right = st.columns([1, 1])

    with act_left:
        company_placeholder = st.empty()
        selected_company_name = st.text_input(
            "Selected Company (auto after connect)",
            value="",
            disabled=True,
        )

    with act_right:
        create_po_clicked = st.button("🚀 Create Draft Purchase Order", type="primary")

    st.markdown("</div>", unsafe_allow_html=True)

with tab_log:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    log_area = st.empty()
    summary_placeholder = st.empty()
    missing_df_placeholder = st.empty()
    st.markdown("</div>", unsafe_allow_html=True)

# ========= MAIN ACTION: CREATE PO =========
if create_po_clicked:
    if not uploaded_file:
        st.error("Pehle Excel file upload karo.")
        st.stop()

    if not (ODOO_URL and ODOO_DB and ODOO_USERNAME and ODOO_API_KEY):
        st.error("Sidebar me Odoo connection details fill karo.")
        st.stop()

    # Connect
    try:
        db, uid, password, models = get_odoo_connection(
            ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY
        )
        connection_status.success(f"Connected to Odoo (UID: {uid})")
    except Exception as e:
        st.error(f"Odoo connection error: {e}")
        st.stop()

    # Load companies and let user choose
    try:
        companies = load_companies(models, db, uid, password)
    except Exception as e:
        st.error(f"Companies load error: {e}")
        st.stop()

    if not companies:
        st.error("Koi company nahi mili; Odoo me rights check karo.")
        st.stop()

    company_map = {c["name"]: c["id"] for c in companies}
    company_name = st.selectbox(
        "PO kis company me banana hai?",
        list(company_map.keys()),
        key="company_select_runtime",
    )
    company_id = company_map[company_name]
    ctx = {"allowed_company_ids": [company_id], "company_id": company_id}

    company_placeholder.text(f"Active company: {company_name}  (ID {company_id})")

    # Read Excel
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

    with tab_upload:
        st.markdown("#### 4️⃣ Data Preview")
        st.dataframe(
            df.head(),
            use_container_width=True,
        )

    # Validate columns
    code_col = "order_line/product_id"
    name_col = "order_line/name"
    qty_col = "order_line/product_uom_qty"
    price_col = "order_line/price_unit"

    required_cols = [code_col, name_col, qty_col, price_col]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(f"Excel me yeh columns missing hain: {missing_cols}")
        st.stop()

    # Build lines, log product matching
    lines = []
    missing_products = []
    log_messages = []

    for idx, row in df.iterrows():
        code = str(row[code_col]).strip()
        name = str(row[name_col])
        qty = float(row[qty_col])
        price = float(row[price_col])

        product_id = get_product_id_by_code(models, db, uid, password, code, context=ctx)
        if not product_id:
            missing_products.append(
                {
                    "Excel Row": idx + 2,
                    "Internal Reference": code,
                    "Description": name,
                }
            )
            log_messages.append(f"❌ Row {idx+2}: {code} → {name} (NOT FOUND)")
        else:
            lines.append(
                {
                    "product_id": product_id,
                    "product_qty": qty,
                    "price_unit": price,
                    "name": name,
                }
            )
            log_messages.append(f"✅ Row {idx+2}: {code} → Product ID {product_id}")

        log_area.text("\n".join(log_messages[-18:]))

    matched_count = len(lines)
    total_rows = len(df)

    with tab_log:
        summary_placeholder.markdown(
            f"**Matched products:** {matched_count}/{total_rows} rows\n\n"
            f"**Company:** {company_name}  |  **Supplier ID:** {int(DEFAULT_PARTNER_ID)}"
        )
        if missing_products:
            st.warning("Kuch products Odoo me nahi mile – ye PO me add nahi honge.")
            missing_df_placeholder.dataframe(
                pd.DataFrame(missing_products),
                use_container_width=True,
            )

    if not lines:
        st.error("Koi bhi product match nahi hua, PO create nahi kar sakte.")
        st.stop()

    # Prepare order lines
    order_lines = []
    for line in lines:
        order_lines.append(
            (
                0,
                0,
                {
                    "product_id": line["product_id"],
                    "product_qty": line["product_qty"],
                    "price_unit": line["price_unit"],
                    "name": line["name"],
                },
            )
        )

    po_date = datetime.now().strftime("%Y-%m-%d")

    po_vals = {
        "partner_id": int(DEFAULT_PARTNER_ID),
        "date_order": po_date,
        "company_id": company_id,
        "order_line": order_lines,
    }

    # Create PO
    try:
        po_id = models.execute_kw(
            db, uid, password,
            "purchase.order", "create",
            [po_vals],
            {"context": ctx},
        )
    except Exception as e:
        st.error(f"Odoo PO create error: {e}")
        st.stop()

    st.success(f"✅ Draft Purchase Order created in {company_name}: ID {po_id}")
    st.info(
        "Next steps Odoo me:\n"
        f"- PO #{po_id} open karo\n"
        "- Supplier change karo (agar needed ho)\n"
        "- Confirm, Receive, aur Bill create karo"
    )
