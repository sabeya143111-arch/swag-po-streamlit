# app.py  (SWAG PO Creator – Clean Premium UI + Multi‑Company + Confirm Step)

import streamlit as st
import pandas as pd
from datetime import datetime
import xmlrpc.client
import io

# ========= PAGE CONFIG =========
st.set_page_config(
    page_title="SWAG PO Creator",
    page_icon="🧾",
    layout="wide",
)

# -------- Session State --------
for key, default in {
    "company_chosen": False,
    "company_name": "",
    "company_id": None,
    "df": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ========= LIGHT GLASS CSS (text clear) =========
st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(135deg, #020617 0%, #020617 55%, #0b1120 100%);
        color: #e5e7eb;
        font-family: "Inter", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    .main-title {
        font-size: 2.3rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
        background: linear-gradient(90deg, #38bdf8, #a855f7, #f97316);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .sub-caption {
        font-size: 0.95rem;
        color: #9ca3af;
        margin-bottom: 0.6rem;
    }
    .glass-card {
        background: rgba(15, 23, 42, 0.85);             /* lighter */
        border-radius: 16px;
        padding: 1.2rem 1.4rem;
        border: 1px solid rgba(148, 163, 184, 0.35);
        box-shadow: 0 12px 32px rgba(15, 23, 42, 0.75);  /* softer shadow */
    }
    .metric-pill {
        border-radius: 999px;
        padding: 0.25rem 0.9rem;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        background: rgba(148, 163, 184, 0.18);
        color: #e5e7eb;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
    }
    .metric-pill span.icon { font-size: 0.95rem; }

    .info-badge, .warn-badge {
        border-radius: 999px;
        padding: 0.25rem 0.8rem;
        font-size: 0.78rem;
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
    }
    .info-badge {
        background: rgba(56, 189, 248, 0.18);
        border: 1px solid rgba(56, 189, 248, 0.6);
        color: #e0f2fe;
    }
    .warn-badge {
        background: rgba(248, 113, 113, 0.16);
        border: 1px solid rgba(248, 113, 113, 0.6);
        color: #fee2e2;
    }
    .accent-text { color: #e5e7eb; font-weight: 500; }

    .upload-box > div[data-testid="stFileUploader"] {
        background: rgba(15, 23, 42, 0.92);
        border-radius: 12px;
        padding: 1rem;
        border: 1px dashed rgba(148, 163, 184, 0.6);
    }

    /* Buttons: light hover animation, but readable */
    .stButton>button {
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.6);
        padding: 0.45rem 1.3rem;
        font-size: 0.9rem;
        font-weight: 500;
        background-color: #0f172a;
        color: #e5e7eb;
        transition: all 0.18s ease-in-out;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        border-color: #38bdf8;
        background: linear-gradient(135deg, #1d4ed8 0%, #0ea5e9 100%);
        color: #f9fafb;
        box-shadow: 0 12px 30px rgba(59, 130, 246, 0.35);
    }

    /* Keep default theme for dataframes so text stays clear */
    .stDataFrame, .stTable {
        font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ========= HEADER =========
st.markdown('<p class="main-title">SWAG Purchase Order Creator</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-caption">Excel upload → Company select & confirm → Draft Purchase Order in Odoo.</p>',
    unsafe_allow_html=True,
)

h1, h2 = st.columns([2, 1])
with h1:
    st.markdown(
        '<div class="metric-pill"><span class="icon">⚡</span>'
        '<span>Multi‑Company • XML‑RPC • Excel Automation</span></div>',
        unsafe_allow_html=True,
    )
with h2:
    st.markdown(
        '<div style="text-align:right;" class="sub-caption">'
        'Made for <span class="accent-text">Buying & Operations</span>'
        '</div>',
        unsafe_allow_html=True,
    )

st.markdown("")

# ========= SIDEBAR =========
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
        st.caption("Best practice: Odoo se ek PO export karo aur uska format use karo.")

connection_status = st.empty()

# ========= XML‑RPC HELPERS =========
@st.cache_resource(show_spinner=False)
def get_odoo_connection(url, db, username, api_key):
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, username, api_key, {})
    if not uid:
        raise Exception("Authentication failed! URL / DB / username / API key check karo.")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return db, uid, api_key, models

def load_companies(models, db, uid, password):
    return models.execute_kw(
        db, uid, password,
        "res.company", "search_read",
        [[]],
        {"fields": ["name"], "limit": 50},
    )

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

# ========= TABS =========
tab_upload, tab_log = st.tabs(["📁 Upload & Company", "📒 Log & PO Result"])

# ---- TAB 1: Upload + Company + Confirm + Create ----
with tab_upload:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)

    c1, c2 = st.columns([1.4, 1])
    with c1:
        st.markdown("#### 1️⃣ Upload Excel")
        st.markdown('<div class="upload-box">', unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            "Drop file here or click to browse",
            type=["xlsx", "xls"],
            help="Single sheet • Header row on top",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("#### 2️⃣ Connect & Choose Company")

        if st.button("🔄 Test Odoo Connection", key="test_conn"):
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

        if st.button("🏢 Load & Choose Company", key="choose_company_btn"):
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
                    st.error("Koi company nahi mili; Odoo multi‑company access check karo.")
                else:
                    names = [c["name"] for c in companies]
                    selected_name = st.selectbox(
                        "Step 1: Company select karo",
                        names,
                        key="company_select_runtime",
                    )
                    if selected_name:
                        company_id = next(c["id"] for c in companies if c["name"] == selected_name)
                        st.session_state.company_name = selected_name
                        st.session_state.company_id = company_id
                        st.session_state.company_chosen = False

        if st.session_state.company_id:
            st.markdown(
                f'<div class="info-badge">Selected: {st.session_state.company_name} '
                f'(ID {st.session_state.company_id})</div>',
                unsafe_allow_html=True,
            )
            if st.button("✅ Confirm Company", key="confirm_company_btn"):
                st.session_state.company_chosen = True
                st.success("Company lock ho gayi; ab PO isi company me banega.")

    st.markdown("---")

    # Data preview
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
    # Create button guard
    create_disabled = not (st.session_state.company_chosen and st.session_state.df is not None)
    if create_disabled:
        st.markdown(
            '<div class="warn-badge">Pehle Excel upload + Company confirm karo, phir PO create kar sakte ho.</div>',
            unsafe_allow_html=True,
        )

    create_po_clicked = st.button(
        "🚀 Create Draft Purchase Order",
        type="primary",
        disabled=create_disabled,
        key="create_po_btn",
    )

    st.markdown("</div>", unsafe_allow_html=True)

# ---- TAB 2: Log & Summary containers ----
with tab_log:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    log_area = st.empty()
    summary_placeholder = st.empty()
    missing_df_placeholder = st.empty()
    st.markdown("</div>", unsafe_allow_html=True)

# ========= MAIN: CREATE PO LOGIC =========
if create_po_clicked:
    if st.session_state.df is None:
        st.error("Excel data missing hai; dubara upload karo.")
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
        connection_status.success(f"Connected to Odoo (UID: {uid})")
    except Exception as e:
        st.error(f"Odoo connection error: {e}")
        st.stop()

    # Required columns
    code_col = "order_line/product_id"
    name_col = "order_line/name"
    qty_col = "order_line/product_uom_qty"
    price_col = "order_line/price_unit"
    required_cols = [code_col, name_col, qty_col, price_col]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(f"Excel me yeh columns missing hain: {missing_cols}")
        st.stop()

    # Product matching
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

    order_lines = [
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
        for line in lines
    ]

    po_vals = {
        "partner_id": int(DEFAULT_PARTNER_ID),
        "date_order": datetime.now().strftime("%Y-%m-%d"),
        "company_id": company_id,
        "order_line": order_lines,
    }

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
