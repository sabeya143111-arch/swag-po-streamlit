# app.py  (SWAG PO Creator – Premium UI + Multi‑Company + Confirm Step)

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

# Session state init
for key, default in {
    "company_chosen": False,
    "company_name": "",
    "company_id": None,
    "df": None,
    "log_messages": [],
    "missing_products": [],
    "lines": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

st.markdown(
    """
    <style>
    .stApp {
        background: radial-gradient(circle at top left, #020617 0, #020617 40%, #000000 100%);
        color: #e5e7eb;
        font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    .main-title {
        font-size: 2.5rem;
        font-weight: 800;
        padding-bottom: 0.3rem;
        background: linear-gradient(90deg, #38bdf8, #a855f7, #f97316);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .sub-caption {
        font-size: 0.95rem;
        color: #9ca3af;
    }
    .glass-card {
        background: rgba(15, 23, 42, 0.88);
        border-radius: 18px;
        padding: 1.3rem 1.5rem;
        border: 1px solid rgba(148, 163, 184, 0.25);
        box-shadow: 0 22px 60px rgba(15, 23, 42, 0.98);
    }
    .metric-pill {
        border-radius: 999px;
        padding: 0.25rem 0.9rem;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        background: rgba(148, 163, 184, 0.18);
        color: #cbd5f5;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
    }
    .metric-pill span.icon {
        font-size: 0.9rem;
    }
    .accent-text {
        color: #e5e7eb;
        font-weight: 500;
    }
    .upload-box > div[data-testid="stFileUploader"] {
        background: rgba(15, 23, 42, 0.85);
        border-radius: 14px;
        padding: 1.2rem;
        border: 1px dashed rgba(148, 163, 184, 0.6);
    }
    .confirm-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.2rem 0.7rem;
        border-radius: 999px;
        font-size: 0.75rem;
        background: rgba(34, 197, 94, 0.15);
        border: 1px solid rgba(34, 197, 94, 0.4);
        color: #bbf7d0;
    }
    .danger-badge {
        background: rgba(239, 68, 68, 0.15);
        border: 1px solid rgba(239, 68, 68, 0.4);
        color: #fecaca;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ========= HEADER =========
st.markdown('<p class="main-title">SWAG Purchase Order Creator</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-caption">Upload Excel → Choose Company → Confirm → Draft PO created directly in Odoo.</p>',
    unsafe_allow_html=True,
)

h_left, h_right = st.columns([2, 1])
with h_left:
    st.markdown(
        '<div class="metric-pill"><span class="icon">⚡</span>'
        '<span>Multi‑Company • XML‑RPC • Excel Automation</span></div>',
        unsafe_allow_html=True,
    )
with h_right:
    st.markdown(
        '<div style="text-align:right;" class="sub-caption">'
        'Streamlined for <span class="accent-text">Buying & Operations</span>'
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
        st.caption("Suggestion: Export one PO from Odoo and reuse as template.")


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

# ========= TAB 1: UPLOAD + COMPANY + CONFIRM =========
with tab_upload:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)

    c1, c2 = st.columns([1.4, 1])
    with c1:
        st.markdown("#### 1️⃣ Upload Excel")
        st.markdown('<div class="upload-box">', unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            "Drop file here or browse",
            type=["xlsx", "xls"],
            help="Max ~20MB • Single sheet with header row",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("#### 2️⃣ Connect & Choose Company")

        test_conn = st.button("🔄 Test Odoo Connection", key="test_conn")
        if test_conn:
            if not (ODOO_URL and ODOO_DB and ODOO_USERNAME and ODOO_API_KEY):
                st.error("Sidebar me Odoo connection details complete karo.")
            else:
                try:
                    db, uid, password, models = get_odoo_connection(
                        ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY
                    )
                    connection_status.success(f"Connected (UID: {uid})")
                except Exception as e:
                    connection_status.error(f"❌ Connection failed: {e}")

        # Step 1: choose company
        choose_company_clicked = st.button("🏢 Load & Choose Company", key="choose_company_btn")
        if choose_company_clicked:
            if not (ODOO_URL and ODOO_DB and ODOO_USERNAME and ODOO_API_KEY):
                st.error("Pehle Odoo connection details bhar do.")
            else:
                try:
                    db, uid, password, models = get_odoo_connection(
                        ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY
                    )
                    companies = load_companies(models, db, uid, password)
                except Exception as e:
                    st.error(f"Company load error: {e}")
                    companies = []

                if not companies:
                    st.error("Koi company nahi mili; Odoo multi‑company rights check karo.")
                else:
                    names = [c["name"] for c in companies]
                    company_name = st.selectbox(
                        "Step 1: Company select karo",
                        names,
                        key="company_select_runtime",
                    )
                    if company_name:
                        company_id = next(c["id"] for c in companies if c["name"] == company_name)
                        st.session_state.company_name = company_name
                        st.session_state.company_id = company_id
                        st.session_state.company_chosen = False  # wait for confirm

        # Step 2: confirm company
        if st.session_state.company_id:
            st.markdown(
                f'<div class="confirm-badge">🏢 Selected: '
                f'<strong>{st.session_state.company_name}</strong> (ID {st.session_state.company_id})</div>',
                unsafe_allow_html=True,
            )
            confirm_company = st.button("✅ Confirm Company", key="confirm_company_btn")
            if confirm_company:
                st.session_state.company_chosen = True
                st.success(f"Company locked: {st.session_state.company_name}")

    st.markdown("---")

    # Data preview after upload
    if uploaded_file is not None:
        try:
            file_bytes = uploaded_file.read()
            file_ext = uploaded_file.name.split(".")[-1].lower()
            if file_ext == "xlsx":
                df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
            else:
                df = pd.read_excel(io.BytesIO(file_bytes), engine="xlrd")
            st.session_state.df = df
            st.markdown("#### 3️⃣ Data Preview")
            st.dataframe(df.head(), use_container_width=True)
        except Exception as e:
            st.error(f"Excel read error: {e}")
    else:
        st.session_state.df = None

    st.markdown("")

    # Step 3: create PO button – enabled only after company confirm
    create_disabled = not (st.session_state.company_chosen and st.session_state.df is not None)
    if create_disabled:
        st.markdown(
            '<div class="danger-badge">⚠️ Pehle company confirm karo '
            'aur Excel upload karo, tabhi PO create hoga.</div>',
            unsafe_allow_html=True,
        )

    create_po_clicked = st.button(
        "🚀 Create Draft Purchase Order",
        type="primary",
        disabled=create_disabled,
        key="create_po_btn",
    )

    st.markdown("</div>", unsafe_allow_html=True)

# ========= TAB 2: LOG & SUMMARY =========
with tab_log:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    log_area = st.empty()
    summary_placeholder = st.empty()
    missing_df_placeholder = st.empty()
    st.markdown("</div>", unsafe_allow_html=True)

# ========= MAIN: WHEN CREATE BUTTON PRESSED =========
if create_po_clicked:
    if st.session_state.df is None:
        st.error("Excel data missing hai; dobara upload karo.")
        st.stop()
    if not st.session_state.company_chosen or not st.session_state.company_id:
        st.error("Company confirm nahi hui; pehle Confirm Company dabao.")
        st.stop()
    if not (ODOO_URL and ODOO_DB and ODOO_USERNAME and ODOO_API_KEY):
        st.error("Odoo connection details sidebar me complete karo.")
        st.stop()

    df = st.session_state.df
    company_id = st.session_state.company_id
    company_name = st.session_state.company_name
    ctx = {"allowed_company_ids": [company_id], "company_id": company_id}

    # Connect
    try:
        db, uid, password, models = get_odoo_connection(
            ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY
        )
        connection_status.success(f"Connected (UID: {uid})")
    except Exception as e:
        st.error(f"Odoo connection error: {e}")
        st.stop()

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

    # Matching
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

        log_area.text("\n".join(log_messages[-20:]))

    st.session_state.lines = lines
    st.session_state.missing_products = missing_products
    st.session_state.log_messages = log_messages

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

    po_vals = {
        "partner_id": int(DEFAULT_PARTNER_ID),
        "date_order": datetime.now().strftime("%Y-%m-%d"),
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
