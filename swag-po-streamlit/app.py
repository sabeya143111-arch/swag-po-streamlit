import streamlit as st
import pandas as pd
from datetime import datetime
import xmlrpc.client
import io
import pdfplumber
from PIL import Image
import requests
import os

# ========= PERPLEXITY AI HELPER =========
PPLX_API_KEY = st.secrets.get("PERPLEXITY_API_KEY", os.getenv("PERPLEXITY_API_KEY", ""))

def ask_perplexity(prompt: str) -> str:
    if not PPLX_API_KEY:
        return "Perplexity API key missing. Please set PERPLEXITY_API_KEY in Streamlit secrets."
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PPLX_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "sonar-small-chat",
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]

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
    "source_type": None,
    "po_lines": None,
    "po_missing_products": None,
    "current_missing_index": 0,
    "vendor_id": None,
    "picking_type_id": None,
    "distribution_id": None,
    "pdf_total": None,
    "selected_rows": None,
    "rfq_df": None,
    "selected_rfq_ids": [],
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
            "- PDF format same as SWAG sales invoice.\n"
            "  - Parser pulls: model code (e.g. TX2442), quantity, price (without tax).\n"
        ),
        "ar": (
            "- شكل فاتورة PDF مثل فاتورة مبيعات SWAG.\n"
            "  - المعالج يستخرج: كود الموديل مثل TX2442، الكمية، السعر بدون ضريبة.\n"
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
        background: radial-gradient(circle at top left, #0f172a 0, #020617 40%, #111827 100%);
        color: #e5e7eb;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #020617, #1f2933);
        border-right: 1px solid rgba(148, 163, 184, 0.35);
    }
    .stSidebar .stMarkdown, .stSidebar label, .stSidebar input, .stSidebar span {
        color: #e5e7eb !important;
    }
    .main-title {
        font-size: 2.6rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
        background: linear-gradient(120deg, #f97316, #fb7185, #38bdf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: 0.03em;
        text-align:center;
    }
    .sub-caption {
        font-size: 0.98rem;
        color: #cbd5f5;
        margin-bottom: 0.9rem;
        text-align:center;
    }
    .glass-card {
        background: radial-gradient(circle at top left, rgba(15,23,42,0.95), rgba(15,23,42,0.85));
        border-radius: 18px;
        padding: 1.5rem 1.6rem;
        border: 1px solid rgba(148,163,184,0.45);
        box-shadow: 0 22px 60px rgba(15, 23, 42, 0.65);
        backdrop-filter: blur(18px);
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
        border: 1px solid rgba(248,250,252,0.2);
        padding: 0.5rem 1.4rem;
        font-size: 0.9rem;
        font-weight: 500;
        background: linear-gradient(135deg, #fb7185 0%, #f97316 40%, #22c55e 100%);
        color: #f9fafb;
    }
    .info-badge {
        display:inline-block;
        padding:0.2rem 0.7rem;
        border-radius:999px;
        border:1px solid rgba(148,163,184,0.5);
        font-size:0.8rem;
        color:#e5e7eb;
        margin-top:0.4rem;
    }
    .warn-badge {
        display:inline-block;
        padding:0.35rem 0.7rem;
        border-radius:999px;
        border:1px solid rgba(248,250,252,0.4);
        background:rgba(248,250,252,0.06);
        font-size:0.8rem;
        color:#facc15;
        margin-top:0.2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ========= CENTER LOGO =========
logo_path = "outfit_logo.png"
try:
    logo = Image.open(logo_path)
    st.markdown(
        """
        <div style="display:flex; justify-content:center; margin-top:0.8rem; margin-bottom:0.4rem;">
        """,
        unsafe_allow_html=True,
    )
    st.image(logo, width=260)
    st.markdown("</div>", unsafe_allow_html=True)
except Exception:
    pass

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

# ---------- RFQ helpers ----------
def load_rfq(models, db, uid, password, company_id=None, limit=100):
    domain = [["state", "in", ["draft", "sent"]]]
    if company_id:
        domain.append(["company_id", "=", company_id])
    rfqs = models.execute_kw(
        db, uid, password,
        "purchase.order", "search_read",
        [domain],
        {"fields": ["name", "partner_id", "date_order", "amount_total", "state", "company_id"], "limit": limit},
    )
    return rfqs

def confirm_rfq(models, db, uid, password, rfq_ids, ctx=None):
    if not rfq_ids:
        return
    ctx = ctx or {}
    models.execute_kw(
        db, uid, password,
        "purchase.order", "button_confirm",
        [rfq_ids],
        {"context": ctx},
    )

# ========= PDF PARSER =========
def parse_swag_pdf_to_df(file_bytes: bytes) -> pd.DataFrame:
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

            tokens = re.findall(r"[A-Za-z0-9\-]+", line)
            model_candidates = [t for t in tokens if re.search(r"[A-Za-z]", t)]
            model = model_candidates[-1] if model_candidates else line.strip()

            rows.append(
                {
                    "order_line/name": model,
                    "order_line/product_uom_qty": qty,
                    "order_line/price_unit": price,
                }
            )
        except Exception:
            continue

    all_amounts = re.findall(r"SR\s*([\d,]+\.?\d*)", full_text)
    if all_amounts:
        total_str = all_amounts[-1].replace(",", "")
        try:
            st.session_state.pdf_total = float(total_str)
        except Exception:
            st.session_state.pdf_total = None
    else:
        st.session_state.pdf_total = None

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

    # ========= FILE PARSE + SELECTION UI =========
    if 'uploaded_file' in locals() and uploaded_file is not None:
        try:
            file_bytes = uploaded_file.read()
            if source == "excel":
                df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
                st.session_state.pdf_total = None
            else:
                df = parse_swag_pdf_to_df(file_bytes)

            name_col = "order_line/name"
            qty_col = "order_line/product_uom_qty"
            price_col = "order_line/price_unit"

            if name_col in df.columns:
                df[name_col] = df[name_col].astype(str)
            for col in [qty_col, price_col]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            st.session_state.df = df

            st.markdown("#### " + tr("step3_preview"))

            event = st.dataframe(
                df,
                use_container_width=True,
                on_select="rerun",
                selection_mode="multi-row",
            )

            total_rows = len(df)
            if st.session_state.selected_rows is None:
                st.session_state.selected_rows = list(range(total_rows))

            st.markdown("")
            select_all_checkbox = st.checkbox(
                "Select all uploaded lines",
                value=len(st.session_state.selected_rows) == total_rows and total_rows > 0,
                help="Tick to select all lines, untick to use manual selection.",
            )

            selected_from_df = event.selection.rows if event is not None else []

            if select_all_checkbox:
                st.session_state.selected_rows = list(range(total_rows))
            else:
                if selected_from_df:
                    st.session_state.selected_rows = selected_from_df

            st.caption(
                f"Selected uploaded lines for PO: {len(st.session_state.selected_rows)} / {total_rows}"
            )

            if source == "pdf" and st.session_state.get("pdf_total") is not None:
                st.info(f"Invoice total (from PDF): SR {st.session_state.pdf_total:,.2f}")
        except Exception as e:
            st.error(f"File read / parse error: {e}")
    else:
        st.session_state.df = None
        st.session_state.selected_rows = None

    st.markdown("")
    create_disabled = not (
        st.session_state.company_chosen
        and st.session_state.df is not None
        and st.session_state.vendor_id
        and st.session_state.picking_type_id
        and st.session_state.selected_rows is not None
        and len(st.session_state.selected_rows) > 0
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

# ---------------- TAB 2: Log + Existing RFQ ----------------
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
        if st.button("🚀 Create Draft Purchase Order in Odoo (using selected lines)"):
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

    st.markdown("---")
    show_rfq = st.checkbox("Show Existing RFQs in Odoo", value=False)

    rfq_df = pd.DataFrame()
    if show_rfq:
        st.markdown("### Existing RFQs in Odoo")
        if ODOO_URL and ODOO_DB and ODOO_USERNAME and ODOO_API_KEY and st.session_state.company_id:
            try:
                db, uid, password, models = get_odoo_connection(
                    ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY
                )
                rfqs = load_rfq(models, db, uid, password, st.session_state.company_id)
                rfq_df = pd.DataFrame(rfqs)
                st.session_state.rfq_df = rfq_df
            except Exception as e:
                st.error(f"RFQ load error: {e}")
                rfq_df = pd.DataFrame()
        else:
            rfq_df = st.session_state.rfq_df if st.session_state.rfq_df is not None else pd.DataFrame()

        if rfq_df is not None and not rfq_df.empty:
            disp_df = rfq_df.copy()
            disp_df["vendor"] = disp_df["partner_id"].apply(
                lambda x: x[1] if isinstance(x, list) and len(x) > 1 else ""
            )
            disp_df["company"] = disp_df["company_id"].apply(
                lambda x: x[1] if isinstance(x, list) and len(x) > 1 else ""
            )
            disp_df_show = disp_df[["id", "name", "vendor", "date_order", "amount_total", "state", "company"]]

            rfq_event = st.dataframe(
                disp_df_show,
                use_container_width=True,
                on_select="rerun",
                selection_mode="multi-row",
            )

            rfq_selected_rows = rfq_event.selection.rows if rfq_event is not None else []
            if rfq_selected_rows:
                st.session_state.selected_rfq_ids = disp_df_show.iloc[rfq_selected_rows]["id"].tolist()

            st.caption(f"Selected RFQs: {len(st.session_state.selected_rfq_ids)}")

            if st.button("✅ Confirm selected RFQs in Odoo"):
                if not st.session_state.selected_rfq_ids:
                    st.warning("Select at least one RFQ to confirm.")
                else:
                    try:
                        db, uid, password, models = get_odoo_connection(
                            ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY
                        )
                        ctx = {
                            "allowed_company_ids": [st.session_state.company_id],
                            "company_id": st.session_state.company_id,
                        }
                        confirm_rfq(models, db, uid, password, st.session_state.selected_rfq_ids, ctx)
                        st.success(f"Confirmed {len(st.session_state.selected_rfq_ids)} RFQs.")
                    except Exception as e:
                        st.error(f"Odoo RFQ confirm error: {e}")
        else:
            st.info("No RFQs found (draft/sent) for this company.")

    st.markdown("</div>", unsafe_allow_html=True)

# ========= STEP 1: scan dataframe (only selected rows) =========
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

    selected_idx_list = st.session_state.selected_rows or []

    for idx in selected_idx_list:
        row = df.iloc[idx]
        if pd.isna(row[qty_col]) or pd.isna(row[price_col]):
            continue
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
        log_messages.append(
            f"✅ Row {idx+2}: {name} → added (selected line, without product_id)"
        )

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

    # ========= AI SUMMARY USING PERPLEXITY =========
    if lines:
        po_text_lines = [
            f"{l['name']} | Qty: {l['product_qty']} | Price: {l['price_unit']}"
            for l in lines
        ]
        po_text = "\n".join(po_text_lines)

        ai_prompt = f"""
        You are a purchasing assistant for a fashion retail company in Saudi Arabia.

        Here are draft purchase order lines:
        {po_text}

        1) Give a short summary: total quantity and price range.
        2) Highlight any suspicious lines (very high qty or unusual price).
        3) Reply in very simple English with some Hindi/Urdu words mixed.
        """

        try:
            ai_answer = ask_perplexity(ai_prompt)
            st.markdown("### 🔍 AI Review of Draft PO")
            st.write(ai_answer)
        except Exception as e:
            st.error(f"AI summary error: {e}")
