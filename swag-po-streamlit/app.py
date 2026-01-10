# app.py (SWAG PO Creator – Excel + PDF invoice to PO, text-based PDF parser)

import streamlit as st
import pandas as pd
from datetime import datetime
import xmlrpc.client
import io
import pdfplumber

# ========= PAGE CONFIG =========
st.set_page_config(
    page_title="SWAG Purchase Order Creator",
    page_icon="🧾",
    layout="wide",
)

# ========= SESSION STATE =========
if "lang" not in st.session_state:
    st.session_state.lang = "en"

for key, default in {
    "company_chosen": False,
    "company_name": "",
    "company_id": None,
    "df": None,
    "source_type": None,  # "excel" or "pdf"
    "po_lines": None,
    "po_missing_products": None,
    "current_missing_index": 0,
    "vendor_id": None,
    "picking_type_id": None,
    "distribution_id": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ========= TRANSLATIONS =========
T = {
    "title": {
        "en": "SWAG Purchase Order Creator",
        "ar": "منشئ أوامر الشراء SWAG",
    },
    "subtitle": {
        "en": "Upload Excel or PDF invoice → Clean draft Purchase Order in Odoo.",
        "ar": "ارفع ملف إكسل أو فاتورة PDF → إنشاء أمر شراء مسودة في أودو.",
    },
    "badge_main": {
        "en": "Excel + PDF • XML‑RPC • Automation",
        "ar": "إكسل + PDF • XML‑RPC • أتمتة",
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
    "default_supplier": {"en": "Default Supplier ID (fallback)", "ar": "معرّف المورد الافتراضي (احتياطي)"},
    "excel_help_title": {"en": "Excel Format Help", "ar": "مساعدة في تنسيق الإكسل"},
    "excel_help_text": {
        "en": (
            "- Required Excel columns (exact names):\n"
            "  - `order_line/name` → Model / Description\n"
            "  - `order_line/product_uom_qty` → Quantity\n"
            "  - `order_line/price_unit` → Unit Price\n"
        ),
        "ar": (
            "- الأعمدة المطلوبة للإكسل (بنفس الأسماء):\n"
            "  - `order_line/name` → الموديل / الوصف\n"
            "  - `order_line/product_uom_qty` → الكمية\n"
            "  - `order_line/price_unit` → سعر الوحدة\n"
        ),
    },
    "pdf_help_title": {"en": "PDF Invoice Help", "ar": "مساعدة فاتورة PDF"},
    "pdf_help_text": {
        "en": (
            "- PDF format same as SWAG sales invoice like sample S89631:\n"
            "  - Lines containing totals like `SR 2,070.00` and codes like `RVH010`.\n"
            "  - Parser pulls: model code (as name), quantity, price (without tax).\n"
        ),
        "ar": (
            "- شكل فاتورة PDF مثل فاتورة مبيعات SWAG (نموذج S89631):\n"
            "  - أسطر فيها الإجمالي مثل `SR 2,070.00` و كود مثل `RVH010`.\n"
            "  - المعالج يستخرج: كود الموديل (كاسم)، الكمية، السعر بدون ضريبة.\n"
        ),
    },
    "excel_tip": {
        "en": "Tip: Export a PO from Odoo and reuse its format.",
        "ar": "نصيحة: صدّر أمر شراء من أودو واستخدمه كقالب.",
    },
    "tab_upload": {"en": "📁 Upload & Company", "ar": "📁 رفع الملف و اختيار الشركة"},
    "tab_log": {"en": "📒 Log & PO Result", "ar": "📒 السجل و نتيجة أمر الشراء"},
    "step1_upload": {"en": "1️⃣ Upload Excel or PDF", "ar": "1️⃣ رفع ملف إكسل أو PDF"},
    "uploader_label": {
        "en": "Drop file here or click to browse",
        "ar": "أسقط الملف هنا أو اضغط للاختيار",
    },
    "uploader_help": {
        "en": "Supported: Excel (.xlsx, .xls) and PDF invoice.",
        "ar": "يدعم: إكسل (.xlsx, .xls) و فاتورة PDF.",
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
        "en": "Upload file, choose vendor/destination, and confirm company before creating PO.",
        "ar": "ارفع الملف، واختر المورّد ووجهة التسليم، وأكّد الشركة قبل إنشاء أمر الشراء.",
    },
    "btn_create_po": {
        "en": "🚀 Scan File & Prepare PO",
        "ar": "🚀 فحص الملف وتجهيز أمر الشراء",
    },
    "err_upload_first": {
        "en": "Please upload a file first.",
        "ar": "من فضلك ارفع ملفاً أولاً.",
    },
    "err_company_not_confirmed": {
        "en": "Company is not confirmed; press Confirm Company button.",
        "ar": "لم يتم تأكيد الشركة؛ اضغط زر تأكيد الشركة.",
    },
    "err_missing_cols": {
        "en": "These columns are missing in Excel",
        "ar": "هذه الأعمدة مفقودة في ملف الإكسل",
    },
    "err_choose_vendor": {
        "en": "Please choose a vendor.",
        "ar": "الرجاء اختيار المورّد.",
    },
    "err_choose_picking": {
        "en": "Please choose Deliver To / Operation Type.",
        "ar": "الرجاء اختيار نوع عملية الاستلام.",
    },
    "log_missing_warning": {
        "en": "Some products not found in Odoo – they will not be added to the PO.",
        "ar": "بعض الأصناف غير موجودة في أودو – لن تُضاف إلى أمر الشراء.",
    },
    "matched_label": {
        "en": "Matched products",
        "ar": "عدد الأصناف المطابقة",
    },
    "company_label": {"en": "Company", "ar": "الشركة"},
    "success_po": {
        "en": "Draft Purchase Order created",
        "ar": "تم إنشاء أمر شراء (مسودة)",
    },
    "lang_label": {"en": "Language", "ar": "اللغة"},
    "lang_en": {"en": "English", "ar": "الإنجليزية"},
    "lang_ar": {"en": "Arabic", "ar": "العربية"},
    "source_excel": {"en": "Excel", "ar": "إكسل"},
    "source_pdf": {"en": "PDF Invoice", "ar": "فاتورة PDF"},
}

def tr(key):
    return T.get(key, {}).get(st.session_state.lang, T.get(key, {}).get("en", key))

# ========= CSS =========
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
    }
    </style>
    """,
    unsafe_allow_html=True,
)

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

def load_vendors(models, db, uid, password):
    partners = models.execute_kw(
        db, uid, password,
        "res.partner", "search_read",
        [[["supplier_rank", ">", 0]]],
        {"fields": ["name"], "limit": 200},
    )
    return partners

def load_picking_types(models, db, uid, password):
    pickings = models.execute_kw(
        db, uid, password,
        "stock.picking.type", "search_read",
        [[["code", "=", "incoming"]]],
        {"fields": ["name"], "limit": 50},
    )
    return pickings

def load_distributions(models, db, uid, password):
    dists = models.execute_kw(
        db, uid, password,
        "account.analytic.distribution", "search_read",
        [[]],
        {"fields": ["name"], "limit": 200},
    )
    return dists

# ========= PDF PARSER (only model as name, qty, price) =========
def parse_swag_pdf_to_df(file_bytes: bytes) -> pd.DataFrame:
    """
    Parse SWAG invoice PDF into:
    order_line/name (model code only), order_line/product_uom_qty, order_line/price_unit
    """
    import re
    rows = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        full_text = ""
        for page in pdf.pages:
            t = page.extract_text() or ""
            full_text += t + "\n"

    for line in full_text.splitlines():
        if "SR" not in line:
            continue
        try:
            price_match = re.findall(r"SR\s*([\d,]+\.?\d*)", line)
            if len(price_match) < 1:
                continue
            price_str = price_match[-1].replace(",", "")
            price = float(price_str)

            qty_match = re.search(rf"{price_str}[^\d]+(\d+)", line)
            if not qty_match:
                continue
            qty = float(qty_match.group(1))

            # Model code at end
            model_match = re.search(r"([A-Za-z0-9\-]+)\s*$", line)
            if not model_match:
                continue
            model = model_match.group(1)

            rows.append(
                {
                    "order_line/name": model,  # sirf model
                    "order_line/product_uom_qty": qty,
                    "order_line/price_unit": price,
                }
            )
        except Exception:
            continue

    if not rows:
        return pd.DataFrame(
            columns=[
                "order_line/name",
                "order_line/product_uom_qty",
                "order_line/price_unit",
            ]
        )
    return pd.DataFrame(rows)

# ========= HEADER =========
st.markdown(f'<p class="main-title">{tr("title")}</p>', unsafe_allow_html=True)
st.markdown(f'<p class="sub-caption">{tr("subtitle")}</p>', unsafe_allow_html=True)

hero_left, hero_right = st.columns([1.6, 1])
with hero_left:
    st.markdown(
        """
        <div class="glass-card" style="padding:1.1rem 1.3rem; margin-bottom:0.8rem;">
            <div style="font-size:0.82rem; text-transform:uppercase; letter-spacing:0.16em; color:#9ca3af;">
                PURCHASE OPS CONTROL PANEL
            </div>
            <div style="font-size:1.05rem; margin-top:0.35rem; color:#e5e7eb;">
                Scan supplier Excel or SWAG PDF invoice, and spin up a clean draft PO from model, quantity, and price.
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
                Session metrics
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

    st.markdown("### 🔐 " + tr("sidebar_conn"))
    ODOO_URL = st.text_input(tr("odoo_url"), "https://tariqueswag1231.odoo.com")
    ODOO_DB = st.text_input(tr("db"), "tariqueswag1231")
    ODOO_USERNAME = st.text_input(tr("username"), "tarique143111@gmail.com")
    ODOO_API_KEY = st.text_input(tr("api_key"), type="password")

    st.markdown("### 🧷 Vendor & Delivery")

    vendors, pickings, distributions = [], [], []
    if ODOO_URL and ODOO_DB and ODOO_USERNAME and ODOO_API_KEY:
        try:
            db, uid, password, models = get_odoo_connection(
                ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY
            )
            vendors = load_vendors(models, db, uid, password)
            pickings = load_picking_types(models, db, uid, password)
            distributions = load_distributions(models, db, uid, password)
        except Exception as e:
            st.error(f"Odoo master data error: {e}")

    if vendors:
        vendor_names = [v["name"] for v in vendors]
        vendor_choice = st.selectbox("Vendor", vendor_names, key="vendor_select")
        st.session_state.vendor_id = next(
            v["id"] for v in vendors if v["name"] == vendor_choice
        )
    else:
        st.session_state.vendor_id = None

    if pickings:
        picking_names = [p["name"] for p in pickings]
        picking_choice = st.selectbox(
            "Deliver To / Operation Type", picking_names, key="picking_select"
        )
        st.session_state.picking_type_id = next(
            p["id"] for p in pickings if p["name"] == picking_choice
        )
    else:
        st.session_state.picking_type_id = None

    if distributions:
        dist_names = [d["name"] for d in distributions]
        dist_choice = st.selectbox(
            "Analytic Distribution", dist_names, key="dist_select"
        )
        st.session_state.distribution_id = next(
            d["id"] for d in distributions if d["name"] == dist_choice
        )
    else:
        st.session_state.distribution_id = None

    st.markdown("---")
    st.markdown("### 🧾 " + tr("sidebar_defaults"))
    DEFAULT_PARTNER_ID = st.number_input(
        tr("default_supplier"), min_value=1, value=1, step=1
    )

    st.markdown("---")
    with st.expander(tr("excel_help_title"), expanded=False):
        st.write(tr("excel_help_text"))
        st.caption(tr("excel_tip"))
    with st.expander(tr("pdf_help_title"), expanded=False):
        st.write(tr("pdf_help_text"))

connection_status = st.empty()

# ========= TABS =========
tab_upload, tab_log = st.tabs([tr("tab_upload"), tr("tab_log")])

# ---------------- TAB 1: Upload & Company ----------------
with tab_upload:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)

    c1, c2 = st.columns([1.4, 1])
    with c1:
        st.markdown("#### " + tr("step1_upload"))

        source = st.radio(
            "Source type",
            options=["excel", "pdf"],
            format_func=lambda x: tr("source_excel") if x == "excel" else tr("source_pdf"),
            horizontal=True,
        )
        st.session_state.source_type = source

        st.markdown('<div class="upload-box">', unsafe_allow_html=True)
        if source == "excel":
            uploaded_file = st.file_uploader(
                tr("uploader_label"),
                type=["xlsx", "xls"],
                help=tr("uploader_help"),
                key="excel_uploader",
            )
        else:
            uploaded_file = st.file_uploader(
                tr("uploader_label"),
                type=["pdf"],
                help=tr("uploader_help"),
                key="pdf_uploader",
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("#### " + tr("step2_company"))

        if st.button(tr("btn_test_conn"), key="test_conn"):
            if not (ODOO_URL and ODOO_DB and ODOO_USERNAME and ODOO_API_KEY):
                st.error("Fill Odoo connection in sidebar.")
            else:
                try:
                    db, uid, password, models = get_odoo_connection(
                        ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY
                    )
                    connection_status.success(f"Connected to Odoo (UID: {uid})")
                except Exception as e:
                    connection_status.error(f"❌ {e}")

        if st.button(tr("btn_load_company"), key="choose_company_btn"):
            if not (ODOO_URL and ODOO_DB and ODOO_USERNAME and ODOO_API_KEY):
                st.error("Fill Odoo connection in sidebar.")
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
                    st.error("No companies found in Odoo.")
                else:
                    names = [c["name"] for c in companies]
                    selected_name = st.selectbox(
                        tr("select_company_label"),
                        names,
                        key="company_select_runtime",
                    )
                    if selected_name:
                        company_id = next(
                            c["id"] for c in companies if c["name"] == selected_name
                        )
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

    if uploaded_file is not None:
        try:
            file_bytes = uploaded_file.read()
            if source == "excel":
                ext = uploaded_file.name.split(".")[-1].lower()
                if ext == "xlsx":
                    df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
                else:
                    df = pd.read_excel(io.BytesIO(file_bytes), engine="xlrd")
            else:
                df = parse_swag_pdf_to_df(file_bytes)
            st.session_state.df = df
            st.markdown("#### " + tr("step3_preview"))
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"File read / parse error: {e}")
    else:
        st.session_state.df = None

    st.markdown("")
    create_disabled = not (
        st.session_state.company_chosen
        and st.session_state.df is not None
        and st.session_state.vendor_id
        and st.session_state.picking_type_id
    )
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

# ---------------- TAB 2: containers ----------------
with tab_log:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    log_area = st.empty()
    summary_placeholder = st.empty()
    missing_df_placeholder = st.empty()
    st.markdown("</div>", unsafe_allow_html=True)

# ========= STEP 1: scan dataframe =========
if create_po_clicked:
    if st.session_state.df is None:
        st.error(tr("err_upload_first"))
        st.stop()
    if not st.session_state.company_chosen or not st.session_state.company_id:
        st.error(tr("err_company_not_confirmed"))
        st.stop()
    if not st.session_state.vendor_id:
        st.error(tr("err_choose_vendor"))
        st.stop()
    if not st.session_state.picking_type_id:
        st.error(tr("err_choose_picking"))
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

    name_col = "order_line/name"
    qty_col = "order_line/product_uom_qty"
    price_col = "order_line/price_unit"
    required_cols = [name_col, qty_col, price_col]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(f"{tr('err_missing_cols')}: {missing_cols}")
        st.stop()

    lines = []
    log_messages = []

    for idx, row in df.iterrows():
        name = str(row[name_col])
        qty = float(row[qty_col])
        price = float(row[price_col])

        line_vals = {
            "name": name,
            "product_qty": qty,
            "price_unit": price,
        }
        if st.session_state.distribution_id:
            line_vals["analytic_distribution_id"] = st.session_state.distribution_id

        lines.append(line_vals)
        log_messages.append(f"✅ Row {idx+2}: {name} → added without product_id")

    st.session_state.po_lines = lines
    st.session_state.po_missing_products = []
    st.session_state.company_snapshot = {
        "company_id": company_id,
        "company_name": company_name,
        "ctx": ctx,
        "ODOO_URL": ODOO_URL,
        "ODOO_DB": ODOO_DB,
        "ODOO_USERNAME": ODOO_USERNAME,
        "ODOO_API_KEY": ODOO_API_KEY,
        "vendor_id": st.session_state.vendor_id,
        "picking_type_id": st.session_state.picking_type_id,
        "distribution_id": st.session_state.distribution_id,
    }
    st.session_state.log_messages = log_messages
    st.session_state.current_missing_index = 0

# ========= STEP 2: log + PO create =========
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
            f"**Vendor ID:** {company_snapshot['vendor_id']}  |  "
            f"**Picking Type:** {company_snapshot['picking_type_id']}"
        )

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
                vendor_id = company_snapshot["vendor_id"]
                picking_type_id = company_snapshot["picking_type_id"]
                db, uid, password, models = get_odoo_connection(
                    ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY
                )
            except Exception as e:
                st.error(f"Odoo connection error (PO create): {e}")
            else:
                order_lines = [(0, 0, line) for line in lines]
                po_vals = {
                    "partner_id": int(vendor_id),
                    "date_order": datetime.now().strftime("%Y-%m-%d"),
                    "company_id": company_id,
                    "picking_type_id": picking_type_id,
                    "order_line": order_lines,
                }
                try:
                    po_id = models.execute_kw(
                        db, uid, password,
                        "purchase.order", "create",
                        [po_vals],
                        {"context": ctx},
                    )
                    st.success(
                        f"✅ {tr('success_po')} ({company_snapshot['company_name']}) : ID {po_id}"
                    )
                except Exception as e:
                    st.error(f"Odoo PO create error: {e}")

    st.markdown("</div>", unsafe_allow_html=True)
