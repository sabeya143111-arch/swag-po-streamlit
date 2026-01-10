# app.py  (SWAG PO Creator – EN+AR, with login + secrets Odoo credentials)

import streamlit as st
import pandas as pd
from datetime import datetime
import xmlrpc.client
import io

# ========= PAGE CONFIG =========
st.set_page_config(
    page_title="SWAG Purchase Order Creator",
    page_icon="🧾",
    layout="wide",
)

# ========= SIMPLE LOGIN (demo) =========
def check_credentials(username, password):
    users = st.secrets.get("app_users", {})
    # Very basic check; for production prefer streamlit-authenticator
    return username in users and users[username] == password

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("SWAG PO Creator – Login")

    login_col1, login_col2 = st.columns([1, 1])
    with login_col1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            if check_credentials(username, password):
                st.session_state.logged_in = True
                st.experimental_rerun()
            else:
                st.error("Invalid username or password. Please try again.")
    st.stop()

# ========= SESSION STATE =========
if "lang" not in st.session_state:
    st.session_state.lang = "en"   # default english

for key, default in {
    "company_chosen": False,
    "company_name": "",
    "company_id": None,
    "df": None,
    "po_lines": None,
    "po_missing_products": None,
    "current_missing_index": 0,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ========= TRANSLATIONS (EN + AR) =========
T = {
    "title": {
        "en": "SWAG Purchase Order Creator",
        "ar": "منشئ أوامر الشراء SWAG",
    },
    "subtitle": {
        "en": "Upload Excel → Choose company → Confirm → Draft Purchase Order in Odoo.",
        "ar": "ارفع ملف إكسل → اختر الشركة → تأكيد → إنشاء أمر شراء مسودة في أودو.",
    },
    "badge_main": {
        "en": "Multi‑Company • XML‑RPC • Excel Automation",
        "ar": "متعدد الشركات • XML‑RPC • أتمتة من إكسل",
    },
    "badge_for": {
        "en": "Made for Buying & Operations",
        "ar": "مخصص لقسم المشتريات والعمليات",
    },
    "sidebar_conn": {"en": "Odoo Connection", "ar": "اتصال أودو"},
    "odoo_url": {"en": "Odoo URL", "ar": "رابط أودو"},
    "db": {"en": "Database", "ar": "قاعدة البيانات"},
    "username": {"en": "Username / Email", "ar": "اسم المستخدم / البريد الإلكتروني"},
    "api_key": {"en": "API Key / Password", "ar": "مفتاح API / كلمة المرور"},
    "sidebar_defaults": {"en": "Default Settings", "ar": "الإعدادات الافتراضية"},
    "default_supplier": {"en": "Default Supplier ID", "ar": "معرّف المورد الافتراضي"},
    "excel_help_title": {"en": "Excel Format Help", "ar": "مساعدة في تنسيق الإكسل"},
    "excel_help_text": {
        "en": (
            "- Required columns (exact names):\n"
            "  - `order_line/product_id` → Internal Reference / SKU\n"
            "  - `order_line/name` → Description\n"
            "  - `order_line/product_uom_qty` → Quantity\n"
            "  - `order_line/price_unit` → Unit Price\n"
        ),
        "ar": (
            "- الأعمدة المطلوبة (بنفس الأسماء):\n"
            "  - `order_line/product_id` → الكود الداخلي / SKU\n"
            "  - `order_line/name` → الوصف\n"
            "  - `order_line/product_uom_qty` → الكمية\n"
            "  - `order_line/price_unit` → سعر الوحدة\n"
        ),
    },
    "excel_tip": {
        "en": "Tip: Export a PO from Odoo and reuse its format.",
        "ar": "نصيحة: صدّر أمر شراء من أودو واستخدمه كقالب.",
    },
    "tab_upload": {"en": "📁 Upload & Company", "ar": "📁 رفع الملف و اختيار الشركة"},
    "tab_log": {"en": "📒 Log & PO Result", "ar": "📒 السجل و نتيجة أمر الشراء"},
    "step1_upload": {"en": "1️⃣ Upload Excel", "ar": "1️⃣ رفع ملف الإكسل"},
    "uploader_label": {
        "en": "Drop file here or click to browse",
        "ar": "أسقط الملف هنا أو اضغط للاختيار",
    },
    "uploader_help": {
        "en": "Single sheet with header row on top.",
        "ar": "ورقة واحدة مع صف عناوين في الأعلى.",
    },
    "step2_company": {"en": "2️⃣ Connect & Choose Company", "ar": "2️⃣ الاتصال واختيار الشركة"},
    "btn_test_conn": {"en": "🔄 Test Odoo Connection", "ar": "🔄 تجربة الاتصال بأودو"},
    "btn_load_company": {"en": "🏢 Load & Choose Company", "ar": "🏢 تحميل واختيار الشركة"},
    "select_company_label": {
        "en": "Step 1: Select company",
        "ar": "الخطوة 1: اختر الشركة",
    },
    "selected_company_badge": {
        "en": "Selected",
        "ar": "الشركة المختارة",
    },
    "btn_confirm_company": {"en": "✅ Confirm Company", "ar": "✅ تأكيد الشركة"},
    "company_locked": {
        "en": "Company locked; PO will be created in this company.",
        "ar": "تم تثبيت الشركة؛ سيتم إنشاء أمر الشراء على هذه الشركة.",
    },
    "step3_preview": {"en": "3️⃣ Data Preview", "ar": "3️⃣ معاينة البيانات"},
    "guard_msg": {
        "en": "Upload Excel and confirm company before creating PO.",
        "ar": "ارفع ملف الإكسل وأكّد الشركة قبل إنشاء أمر الشراء.",
    },
    "btn_create_po": {
        "en": "🚀 Scan Excel & Prepare PO",
        "ar": "🚀 فحص الإكسل وتجهيز أمر الشراء",
    },
    "err_fill_conn": {
        "en": "Odoo connection misconfigured on server (ask admin).",
        "ar": "إعداد اتصال أودو غير صحيح (تواصل مع المسؤول).",
    },
    "err_upload_first": {
        "en": "Please upload an Excel file first.",
        "ar": "من فضلك ارفع ملف الإكسل أولاً.",
    },
    "err_company_not_confirmed": {
        "en": "Company is not confirmed; press Confirm Company button.",
        "ar": "لم يتم تأكيد الشركة؛ اضغط زر تأكيد الشركة.",
    },
    "err_missing_cols": {
        "en": "These columns are missing in Excel",
        "ar": "هذه الأعمدة مفقودة في ملف الإكسل",
    },
    "log_missing_warning": {
        "en": "Some products not found in Odoo – they will not be added to the PO.",
        "ar": "بعض الأصناف غير موجودة في أودو – لن تُضاف إلى أمر الشراء.",
    },
    "log_no_match": {
        "en": "No product matched; cannot create PO.",
        "ar": "لم يتم مطابقة أي صنف؛ لا يمكن إنشاء أمر الشراء.",
    },
    "matched_label": {
        "en": "Matched products",
        "ar": "عدد الأصناف المطابقة",
    },
    "company_label": {"en": "Company", "ar": "الشركة"},
    "supplier_label": {"en": "Supplier ID", "ar": "معرّف المورد"},
    "success_po": {
        "en": "Draft Purchase Order created",
        "ar": "تم إنشاء أمر شراء (مسودة)",
    },
    "lang_label": {"en": "Language", "ar": "اللغة"},
    "lang_en": {"en": "English", "ar": "الإنجليزية"},
    "lang_ar": {"en": "Arabic", "ar": "العربية"},
}

def tr(key):
    return T.get(key, {}).get(st.session_state.lang, T.get(key, {}).get("en", key))

# ========= PREMIUM CSS (same as before) =========
st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] {
        background: radial-gradient(circle at top left, #1f2937 0, #020617 45%, #000000 100%);
        color: #e5e7eb;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #020617, #111827);
        border-right: 1px solid rgba(148, 163, 184, 0.35);
    }
    .stSidebar .stMarkdown, .stSidebar label, .stSidebar input, .stSidebar span {
        color: #e5e7eb !important;
    }
    .main-title {
        font-size: 2.6rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
        background: linear-gradient(120deg, #38bdf8, #a855f7, #f97316);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: 0.03em;
    }
    .sub-caption {
        font-size: 0.98rem;
        color: #9ca3af;
        margin-bottom: 0.9rem;
    }
    .glass-card {
        background: radial-gradient(circle at top left, rgba(15,23,42,0.96), rgba(15,23,42,0.86));
        border-radius: 18px;
        padding: 1.5rem 1.6rem;
        border: 1px solid rgba(148,163,184,0.45);
        box-shadow: 0 22px 60px rgba(15, 23, 42, 0.65);
        backdrop-filter: blur(16px);
    }
    .metric-pill {
        border-radius: 999px;
        padding: 0.35rem 1.1rem;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        background: rgba(15,23,42,0.85);
        border: 1px solid rgba(56,189,248,0.7);
        color: #e5e7eb;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
    }
    .metric-pill span.icon { font-size: 1rem; }
    .info-badge, .warn-badge {
        border-radius: 999px;
        padding: 0.3rem 0.9rem;
        font-size: 0.8rem;
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
    }
    .info-badge {
        background: rgba(8,47,73,0.92);
        border: 1px solid rgba(56,189,248,0.7);
        color: #e0f2fe;
    }
    .warn-badge {
        background: rgba(127,29,29,0.92);
        border: 1px solid rgba(248,113,113,0.7);
        color: #fee2e2;
    }
    .upload-box > div[data-testid="stFileUploader"] {
        background: rgba(15,23,42,0.9);
        border-radius: 14px;
        padding: 1rem;
        border: 1px dashed rgba(148,163,184,0.7);
        color: #e5e7eb;
    }
    .stButton>button {
        border-radius: 999px;
        border: 1px solid rgba(56,189,248,0.9);
        padding: 0.5rem 1.4rem;
        font-size: 0.9rem;
        font-weight: 500;
        background: linear-gradient(135deg, #0ea5e9 0%, #6366f1 50%, #a855f7 100%);
        color: #f9fafb;
        box-shadow: 0 16px 35px rgba(37,99,235,0.45);
        transition: all 0.18s ease-in-out;
    }
    .stButton>button:hover {
        transform: translateY(-2px) scale(1.02);
        box-shadow: 0 22px 45px rgba(59,130,246,0.75);
    }
    .stButton>button:active {
        transform: translateY(0px) scale(0.99);
        box-shadow: 0 8px 18px rgba(15,23,42,0.9);
    }
    .stDataFrame, .stTable {
        font-size: 0.9rem;
        color: #e5e7eb;
    }
    button[data-baseweb="tab"] {
        background: transparent !important;
        border: none !important;
        color: #9ca3af !important;
        font-weight: 500;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #e5e7eb !important;
        border-bottom: 2px solid #38bdf8 !important;
    }
    @keyframes fadeInUp {
        from { opacity:0; transform: translateY(6px); }
        to { opacity:1; transform: translateY(0px); }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ========= ODOO CREDENTIALS FROM SECRETS =========
ODOO_URL = st.secrets["odoo"]["url"]
ODOO_DB = st.secrets["odoo"]["db"]
ODOO_USERNAME = st.secrets["odoo"]["username"]
ODOO_API_KEY = st.secrets["odoo"]["api_key"]

# ========= HEADER =========
st.markdown(f'<p class="main-title">{tr("title")}</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-caption">{tr("subtitle")}</p>', unsafe_allow_html=True)

h1, h2 = st.columns([2, 1])
with h1:
    st.markdown(
        f'<div class="metric-pill"><span class="icon">⚡</span>'
        f'<span>{tr("badge_main")}</span></div>',
        unsafe_allow_html=True,
    )
with h2:
    st.markdown(
        f'<div style="text-align:right;" class="sub-caption">{tr("badge_for")}</div>',
        unsafe_allow_html=True,
    )

# ========= HERO CARDS =========
hero_left, hero_right = st.columns([1.6, 1])

with hero_left:
    st.markdown(
        """
        <div class="glass-card" style="padding:1.1rem 1.3rem; margin-bottom:0.8rem;">
            <div style="font-size:0.82rem; text-transform:uppercase; letter-spacing:0.16em; color:#9ca3af;">
                PURCHASE OPS CONTROL PANEL
            </div>
            <div style="font-size:1.05rem; margin-top:0.35rem; color:#e5e7eb;">
                Scan supplier Excel, validate SKUs, and spin up a clean draft PO in under
                <span style="color:#38bdf8; font-weight:600;">30 seconds</span>.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with hero_right:
    rows = len(st.session_state.df) if st.session_state.get("df") is not None else 0
    matched = len(st.session_state.po_lines) if st.session_state.get("po_lines") else 0
    st.markdown(
        f"""
        <div class="glass-card" style="padding:0.9rem 1.1rem; margin-bottom:0.8rem;">
            <div style="font-size:0.8rem; color:#9ca3af; margin-bottom:0.4rem;">
                Today's session
            </div>
            <div style="display:flex; justify-content:space-between; font-size:0.9rem;">
                <div>
                    <div style="color:#e5e7eb;">Uploaded lines</div>
                    <div style="color:#38bdf8; font-size:1.1rem; font-weight:600;">
                        {rows}
                    </div>
                </div>
                <div>
                    <div style="color:#e5e7eb;">Matched SKUs</div>
                    <div style="color:#22c55e; font-size:1.1rem; font-weight:600;">
                        {matched}
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("")

# ========= SIDEBAR =========
with st.sidebar:
    st.markdown("### 🌐 " + tr("lang_label"))
    lang_choice = st.radio(
        "",
        options=["en", "ar"],
        index=0 if st.session_state.lang == "en" else 1,
        format_func=lambda x: tr("lang_en") if x == "en" else tr("lang_ar"),
    )
    st.session_state.lang = lang_choice

    st.markdown("---")
    st.markdown("### 🧾 " + tr("sidebar_defaults"))
    DEFAULT_PARTNER_ID = st.number_input(tr("default_supplier"), min_value=1, value=1, step=1)

    st.markdown("---")
    with st.expander(tr("excel_help_title"), expanded=False):
        st.write(tr("excel_help_text"))
        st.caption(tr("excel_tip"))

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
tab_upload, tab_log = st.tabs([tr("tab_upload"), tr("tab_log")])

# ---------------- TAB 1: Upload & Company ----------------
with tab_upload:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)

    c1, c2 = st.columns([1.4, 1])
    with c1:
        st.markdown("#### " + tr("step1_upload"))
        st.markdown('<div class="upload-box">', unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            tr("uploader_label"),
            type=["xlsx", "xls"],
            help=tr("uploader_help"),
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("#### " + tr("step2_company"))

        if st.button(tr("btn_test_conn"), key="test_conn"):
            try:
                db, uid, password, models = get_odoo_connection(
                    ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY
                )
                connection_status.success(f"Connected to Odoo (UID: {uid})")
            except Exception as e:
                connection_status.error(f"❌ {e}")

        if st.button(tr("btn_load_company"), key="choose_company_btn"):
            try:
                db, uid, password, models = get_odoo_connection(
                    ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY
                )
                companies = load_companies(models, db, uid, password)
            except Exception as e:
                st.error(f"Company load error: {e}")
                companies = []

            if not companies:
                st.error("No companies found in Odoo.")
            else:
                names = [c["name"] for c in companies]
                selected_name = st.selectbox(
                    tr("select_company_label"),
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
                f'<div class="info-badge">{tr("selected_company_badge")}: '
                f'{st.session_state.company_name} (ID {st.session_state.company_id})</div>',
                unsafe_allow_html=True,
            )
            if st.button(tr("btn_confirm_company"), key="confirm_company_btn"):
                st.session_state.company_chosen = True
                st.success(tr("company_locked"))

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
            st.markdown("#### " + tr("step3_preview"))
            st.dataframe(df.head(), use_container_width=True)
        except Exception as e:
            st.error(f"Excel read error: {e}")
    else:
        st.session_state.df = None

    st.markdown("")
    create_disabled = not (st.session_state.company_chosen and st.session_state.df is not None)
    if create_disabled:
        st.markdown(
            f'<div class="warn-badge">{tr("guard_msg")}</div>',
            unsafe_allow_html=True,
        )

    create_po_clicked = st.button(
        tr("btn_create_po"),
        type="primary",
        disabled=create_disabled,
        key="create_po_btn",
    )

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------- TAB 2: Containers ----------------
with tab_log:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    log_area = st.empty()
    summary_placeholder = st.empty()
    missing_df_placeholder = st.empty()
    st.markdown("</div>", unsafe_allow_html=True)

# ========= STEP 1: Scan Excel & store in state =========
if create_po_clicked:
    if st.session_state.df is None:
        st.error(tr("err_upload_first"))
        st.stop()
    if not st.session_state.company_chosen or not st.session_state.company_id:
        st.error(tr("err_company_not_confirmed"))
        st.stop()

    df = st.session_state.df
    company_id = st.session_state.company_id
    company_name = st.session_state.company_name
    ctx = {"allowed_company_ids": [company_id], "company_id": company_id}

    try:
        db, uid, password, models = get_odoo_connection(
            ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY
        )
        connection_status.success(f"Connected to Odoo (UID: {uid})")
    except Exception as e:
        st.error(f"Odoo connection error: {e}")
        st.stop()

    code_col = "order_line/product_id"
    name_col = "order_line/name"
    qty_col = "order_line/product_uom_qty"
    price_col = "order_line/price_unit"
    required_cols = [code_col, name_col, qty_col, price_col]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(f"{tr('err_missing_cols')}: {missing_cols}")
        st.stop()

    lines = []
    missing_products = []
    log_messages = []

    for idx, row in df.iterrows():
        code = str(row[code_col]).strip()
        name = str(row[name_col])
        qty = float(row[qty_col])
        price = float(row[price_col])

        try:
            db, uid, password, models = get_odoo_connection(
                ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY
            )
            product_id = get_product_id_by_code(models, db, uid, password, code, context=ctx)
        except Exception as e:
            product_id = False
            log_messages.append(f"⚠ Row {idx+2}: {code} lookup error: {e}")

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

    st.session_state.po_lines = lines
    st.session_state.po_missing_products = missing_products
    st.session_state.company_snapshot = {
        "company_id": company_id,
        "company_name": company_name,
        "ctx": ctx,
        "ODOO_URL": ODOO_URL,
        "ODOO_DB": ODOO_DB,
        "ODOO_USERNAME": ODOO_USERNAME,
        "ODOO_API_KEY": ODOO_API_KEY,
    }
    st.session_state.log_messages = log_messages
    st.session_state.current_missing_index = 0

# ========= STEP 2: Log tab + wizard =========
with tab_log:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    log_area = st.empty()
    summary_placeholder = st.empty()
    missing_df_placeholder = st.empty()

    lines = st.session_state.po_lines or []
    missing_products = st.session_state.po_missing_products or []
    log_messages = st.session_state.get("log_messages", [])
    company_snapshot = st.session_state.get("company_snapshot", {})

    if log_messages:
        log_area.text("\n".join(log_messages[-20:]))

    if company_snapshot:
        company_name = company_snapshot["company_name"]
        summary_placeholder.markdown(
            f"**{tr('matched_label')}:** {len(lines)}/{len(lines) + len(missing_products)}  "
            f"|  **{tr('company_label')}:** {company_name}  |  "
            f"**{tr('supplier_label')}:** {int(DEFAULT_PARTNER_ID)}"
        )

    # ----- Missing product wizard -----
    if missing_products:
        st.markdown(
            f'<div class="info-badge">Missing products: {len(missing_products)}</div>',
            unsafe_allow_html=True,
        )
        st.warning(tr("log_missing_warning"))

        missing_df_placeholder.dataframe(
            pd.DataFrame(missing_products),
            use_container_width=True,
        )

        st.markdown("### ➕ Create missing products (one by one)")

        idx = st.session_state.get("current_missing_index", 0)
        if idx >= len(missing_products):
            idx = 0
            st.session_state.current_missing_index = 0

        current = missing_products[idx]

        st.markdown(
            f"""
            <div style="
                margin-top:0.8rem;
                margin-bottom:0.5rem;
                padding:0.9rem 1.0rem;
                border-radius:14px;
                border:1px solid rgba(148,163,184,0.55);
                background:radial-gradient(circle at top left, rgba(15,23,42,0.98), rgba(15,23,42,0.92));
                box-shadow:0 16px 40px rgba(15,23,42,0.75);
                animation: fadeInUp 0.45s ease-out;
            ">
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f"Working on Excel Row **{current['Excel Row']}** "
            f"({current['Internal Reference']} - {current['Description']})"
        )

        left_col, right_col = st.columns(2)

        with st.form(key="create_single_missing_product"):
            with left_col:
                internal_ref = st.text_input(
                    "Internal Reference (SKU)",
                    value=current["Internal Reference"],
                    key="f_internal_ref",
                )
                barcode = st.text_input("Barcode", key="f_barcode")
                old_barcode = st.text_input("Old Barcode", key="f_old_barcode")

            with right_col:
                season = st.text_input("Season", key="f_season")
                brand = st.text_input("Brand", key="f_brand")
                cost_price = st.number_input(
                    "Cost Price", min_value=0.0, step=0.01, key="f_cost_price"
                )
                sale_price = st.number_input(
                    "Sales Price", min_value=0.0, step=0.01, key="f_sale_price"
                )

            b1, b2 = st.columns(2)
            with b1:
                create_clicked = st.form_submit_button("✅ Create product in Odoo")
            with b2:
                skip_clicked = st.form_submit_button("➡ Skip this product")

        st.markdown("</div>", unsafe_allow_html=True)

        if create_clicked or skip_clicked:
            try:
                ODOO_URL = company_snapshot["ODOO_URL"]
                ODOO_DB = company_snapshot["ODOO_DB"]
                ODOO_USERNAME = company_snapshot["ODOO_USERNAME"]
                ODOO_API_KEY = company_snapshot["ODOO_API_KEY"]
                company_id = company_snapshot["company_id"]
                ctx = company_snapshot["ctx"]
                db, uid, password, models = get_odoo_connection(
                    ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY
                )
            except Exception as e:
                st.error(f"Odoo connection error (product create): {e}")
            else:
                if create_clicked:
                    try:
                        model_fields = models.execute_kw(
                            db, uid, password,
                            "product.template", "fields_get",
                            [],
                            {"attributes": ["string"]}
                        )
                        existing_field_names = set(model_fields.keys())

                        product_vals = {
                            "name": current["Description"],
                            "default_code": internal_ref,
                            "barcode": barcode or False,
                            "standard_price": cost_price,
                            "list_price": sale_price,
                            "company_id": company_id,
                        }

                        custom_field_candidates = {
                            "old_barcode": ["x_old_barcode", "x_studio_old_barcode"],
                            "season": ["x_season", "x_studio_season"],
                            "brand": ["x_brand", "x_studio_brand"],
                        }

                        if old_barcode:
                            for fname in custom_field_candidates["old_barcode"]:
                                if fname in existing_field_names:
                                    product_vals[fname] = old_barcode
                                    break
                        if season:
                            for fname in custom_field_candidates["season"]:
                                if fname in existing_field_names:
                                    product_vals[fname] = season
                                    break
                        if brand:
                            for fname in custom_field_candidates["brand"]:
                                if fname in existing_field_names:
                                    product_vals[fname] = brand
                                    break

                        template_id = models.execute_kw(
                            db, uid, password,
                            "product.template", "create",
                            [product_vals],
                            {"context": ctx},
                        )

                        st.success(
                            f"✅ Product created (template ID {template_id}) "
                            f"for {internal_ref}"
                        )

                        missing_products.pop(idx)
                        st.session_state.po_missing_products = missing_products
                        st.session_state.current_missing_index = 0

                    except Exception as e:
                        st.error(f"Odoo product create error: {e}")
                elif skip_clicked:
                    if len(missing_products) > 0:
                        new_idx = (idx + 1) % len(missing_products)
                        st.session_state.current_missing_index = new_idx
                        st.info("➡ Moved to next missing product.")
    else:
        if company_snapshot:
            st.info("No missing products. You can now create Purchase Order.")

    # ----- Final PO create button -----
    if lines:
        st.markdown("---")
        if st.button("🚀 Create Draft Purchase Order in Odoo (using matched lines)"):
            try:
                ODOO_URL = company_snapshot["ODOO_URL"]
                ODOO_DB = company_snapshot["ODOO_DB"]
                ODOO_USERNAME = company_snapshot["ODOO_USERNAME"]
                ODOO_API_KEY = company_snapshot["ODOO_API_KEY"]
                company_id = company_snapshot["company_id"]
                ctx = company_snapshot["ctx"]
                db, uid, password, models = get_odoo_connection(
                    ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY
                )
            except Exception as e:
                st.error(f"Odoo connection error (PO create): {e}")
            else:
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
                    st.success(f"✅ {tr('success_po')} ({company_snapshot['company_name']}) : ID {po_id}")
                except Exception as e:
                    st.error(f"Odoo PO create error: {e}")

    st.markdown("</div>", unsafe_allow_html=True)
