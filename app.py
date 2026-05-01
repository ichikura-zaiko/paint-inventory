import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import unicodedata
import os
import re
from datetime import datetime, timedelta


# =========================
# 画面設定
# =========================
st.set_page_config(page_title="一倉 塗料管理システム", page_icon="🎨", layout="wide")
st.markdown(
    """
    <div style="background:linear-gradient(90deg,#1e3a5f,#2e6da4);padding:10px 18px;border-radius:10px;margin-bottom:6px;display:flex;align-items:center;gap:12px;">
        <span style="font-size:2rem;">🎨</span>
        <div>
            <div style="color:#ffffff;font-size:1.5rem;font-weight:700;letter-spacing:2px;">一倉　塗料管理システム</div>
            <div style="color:#a8c8e8;font-size:0.8rem;">Ichikura Paint Inventory Management System</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("Googleスプレッドシート直結・キャッシュなし / Connected to Google Sheets, no inventory cache")


# =========================
# 基本設定
# =========================
SPREADSHEET_ID = "1BnRviQ1S5rEDFVX3NCkLfGQpm9Jrq1xtFkfDLHba3z0"
COLOR_FILE = "nittoko_colors.csv"

INVENTORY_SHEET = "在庫"
HISTORY_SHEET = "履歴"
CUSTOMER_MASTER_SHEET = "得意先マスタ"
TYPE_MASTER_SHEET = "種類マスタ"

COLUMNS = ["得意先", "種類", "No", "名称", "HEX", "艶", "保有数", "入荷日", "保管場所"]
HISTORY_COLUMNS = ["日時", "操作", "得意先", "種類", "No", "名称", "変更前", "変更後", "差分", "メモ"]
MASTER_COLUMNS = ["名称"]

DEFAULT_CUSTOMERS = ["自社", "東洋紡エンジニアリング", "その他"]
DEFAULT_TYPES = ["アクリル", "メラミン", "粉体", "ウレタン", "エポキシ", "ラッカー", "その他"]

GLOSS_OPTIONS = ["", "Gloss／艶あり", "Semi-gloss／半艶", "Matte／艶なし", "30% Gloss／３分艶", "70% Gloss／７分艶", "Other／その他"]

MAX_STOCK = 50.0
STEP = 0.5
HEX_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
DEFAULT_GRAY_VALUES = {"", "#999999", "#929396"}


# =========================
# コンパクト向けCSS（余白削減・フォームを締める）
# =========================
st.markdown(
    """
    <style>
    /* 全体の余白を削減 */
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }
    /* セクション見出しの余白を削減 */
    h2, h3 {
        margin-top: 0.4rem !important;
        margin-bottom: 0.2rem !important;
        font-size: 1.1rem !important;
    }
    /* タイトルを小さく */
    h1 {
        font-size: 1.4rem !important;
        margin-bottom: 0 !important;
    }
    /* caption の余白削減 */
    .stCaption {
        margin-bottom: 0.2rem !important;
    }
    /* st.metric を小さく */
    [data-testid="metric-container"] {
        padding: 4px 8px !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
    }
    /* input/select の高さを削減 */
    .stTextInput input,
    .stNumberInput input,
    .stSelectbox div[data-baseweb="select"] {
        padding-top: 4px !important;
        padding-bottom: 4px !important;
        min-height: 36px !important;
    }
    /* ボタンをコンパクトに */
    .stButton > button {
        padding: 4px 10px !important;
        min-height: 34px !important;
        font-size: 0.85rem !important;
    }
    /* divider の余白削減 */
    hr {
        margin-top: 0.4rem !important;
        margin-bottom: 0.4rem !important;
    }
    /* フォームラベルのサイズ削減 */
    .stSelectbox label,
    .stTextInput label,
    .stNumberInput label,
    .stDateInput label,
    .stColorPicker label {
        font-size: 0.8rem !important;
        margin-bottom: 1px !important;
    }
    /* カードのコンパクト化 */
    .paint-card {
        background-color:#dbeafe;
        padding:8px 10px;
        border-radius:10px;
        margin-bottom:6px;
        border:1px solid #ccc;
    }
    .paint-card-inner {
        display:flex;
        align-items:center;
        gap:10px;
        flex-wrap:wrap;
    }
    .paint-chip {
        width:46px;
        height:46px;
        border:1px solid #555;
        border-radius:6px;
        flex: 0 0 auto;
    }
    .paint-info {
        flex:1;
        min-width:180px;
    }
    .paint-no-name {
        font-size:16px;
        font-weight:600;
        line-height:1.3;
    }
    .paint-stock {
        font-size:20px;
        letter-spacing:1px;
        white-space:nowrap;
    }
    .badge {
        display:inline-block;
        font-size:11px;
        color:#374151;
        background:#f3f4f6;
        border:1px solid #d1d5db;
        border-radius:999px;
        padding:1px 6px;
        margin-top:2px;
        margin-right:3px;
        margin-bottom:2px;
    }
    .small-color-row {
        display:flex;
        align-items:center;
        gap:6px;
        margin-bottom:5px;
    }
    .small-color-chip {
        width:22px;
        height:22px;
        border:1px solid #555;
        flex: 0 0 auto;
    }
    @media (max-width: 768px) {
        .stButton > button {
            width: 100%;
        }
        div[data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================
# 共通関数
# =========================
def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def unit_label(qty):
    qty = normalize_stock(qty)
    return "pc" if qty == 1 else "pcs"


def clean_code(value):
    if value is None:
        return ""
    value = str(value).strip()
    value = unicodedata.normalize("NFKC", value)
    return value.upper()


def is_valid_hex(value):
    return bool(HEX_PATTERN.match(str(value).strip()))


def normalize_hex(value):
    value = str(value).strip()
    if not value:
        return "#999999"
    if not value.startswith("#"):
        value = f"#{value}"
    value = value.upper()
    return value if is_valid_hex(value) else "#999999"


def normalize_stock(value):
    value = pd.to_numeric(value, errors="coerce")
    if pd.isna(value):
        value = 0.0
    value = max(0.0, min(float(value), MAX_STOCK))
    return round(value * 2) / 2


def shelf_life_days(paint_type):
    return 365 if "粉体" in str(paint_type) else 180


def expiry_info(received_date, paint_type):
    try:
        received = pd.to_datetime(received_date).date()
    except Exception:
        return "No received date", "#6b7280"

    days = shelf_life_days(paint_type)
    expire_date = received + timedelta(days=days)
    remaining = (expire_date - datetime.now().date()).days

    if remaining < 0:
        return f"Expired {abs(remaining)} days ago", "#dc2626"
    if remaining <= 14:
        return f"Expiring soon: {remaining} days left", "#d97706"
    return f"Exp. {expire_date.strftime('%Y-%m-%d')} ({remaining} days left)", "#374151"


def can_display(qty):
    qty = normalize_stock(qty)
    full = int(qty)
    half = (qty - full) >= 0.5
    display = ""
    for i in range(5):
        if i < min(full, 5):
            display += "■"
        elif i == full and half and full < 5:
            display += "◩"
        else:
            display += "□"
    if qty > 5:
        display += f" +{qty - 5:g}"
    return display


def can_display_html(qty, hex_color):
    qty = normalize_stock(qty)
    color = normalize_hex(hex_color)
    full = int(qty)
    half = (qty - full) >= 0.5

    boxes = []
    for i in range(5):
        if i < min(full, 5):
            bg = color
        elif i == full and half and full < 5:
            bg = f"linear-gradient(90deg, {color} 50%, #ffffff 50%)"
        else:
            bg = "#ffffff"

        boxes.append(
            f"<span style='display:inline-block;width:22px;height:22px;margin-right:3px;"
            f"border:1px solid #777;border-radius:4px;background:{bg};"
            f"vertical-align:middle;box-sizing:border-box;'></span>"
        )

    extra = f"<span style='font-size:14px;margin-left:3px;vertical-align:middle;'>+{qty - 5:g}</span>" if qty > 5 else ""
    return f"<span style='display:inline-flex;align-items:center;gap:0;white-space:nowrap;'>{''.join(boxes)}{extra}</span>"


# =========================
# Google Sheets接続
# =========================
@st.cache_resource(ttl=3600)
def connect_spreadsheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID)


def get_or_create_worksheet(spreadsheet, title, columns):
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=1000, cols=max(len(columns), 3))
        ws.update([columns], "A1")
        return ws


def ensure_master_has_default_values(ws, defaults):
    values = ws.col_values(1)
    if len(values) >= 2:
        return
    ws.clear()
    ws.update([["名称"]] + [[x] for x in defaults], "A1")


@st.cache_resource(ttl=3600)
def get_sheets():
    spreadsheet = connect_spreadsheet()
    inventory_ws = get_or_create_worksheet(spreadsheet, INVENTORY_SHEET, COLUMNS)
    history_ws = get_or_create_worksheet(spreadsheet, HISTORY_SHEET, HISTORY_COLUMNS)
    customer_ws = get_or_create_worksheet(spreadsheet, CUSTOMER_MASTER_SHEET, MASTER_COLUMNS)
    type_ws = get_or_create_worksheet(spreadsheet, TYPE_MASTER_SHEET, MASTER_COLUMNS)
    return inventory_ws, history_ws, customer_ws, type_ws


# =========================
# マスタ読み込み
# =========================
@st.cache_data(ttl=300)
def load_master_by_sheet_name(sheet_name, defaults):
    spreadsheet = connect_spreadsheet()
    ws = spreadsheet.worksheet(sheet_name)
    ensure_master_has_default_values(ws, defaults)

    values = ws.col_values(1)
    items = []
    for value in values[1:]:
        name = str(value).strip()
        if name and name not in items:
            items.append(name)
    return items or defaults


@st.cache_data
def load_color_master():
    if os.path.exists(COLOR_FILE):
        df = pd.read_csv(COLOR_FILE, dtype=str).fillna("")
        df.columns = df.columns.str.strip()
    else:
        df = pd.DataFrame(columns=["日塗工番号", "色名", "HEX"])

    rename_map = {}
    for col in df.columns:
        c = str(col).strip().lower()
        if c in ["no", "番号", "色番号", "日塗工", "日塗工番号", "code", "color_code"]:
            rename_map[col] = "日塗工番号"
        elif c in ["色名", "名称", "name", "color_name"]:
            rename_map[col] = "色名"
        elif c in ["hex", "hex値", "カラー", "color", "colour"]:
            rename_map[col] = "HEX"
    df = df.rename(columns=rename_map)

    for col in ["日塗工番号", "色名", "HEX"]:
        if col not in df.columns:
            df[col] = ""

    df = df[["日塗工番号", "色名", "HEX"]].copy()
    df["検索番号"] = df["日塗工番号"].apply(clean_code)
    df["HEX"] = df["HEX"].apply(normalize_hex)
    return df


def color_lookup(number, color_df):
    number_clean = clean_code(number)

    if number_clean == "":
        return "", "#999999", False

    def key(value):
        value = clean_code(value)
        value = value.replace("-", "")
        value = value.replace(" ", "")
        value = value.replace("　", "")
        return value

    match = color_df[color_df["検索番号"] == number_clean]

    if match.empty:
        search_key = key(number_clean)
        tmp = color_df.copy()
        tmp["検索キー"] = tmp["検索番号"].apply(key)
        match = tmp[tmp["検索キー"] == search_key]

    if not match.empty:
        hex_value = normalize_hex(match.iloc[0]["HEX"])
        name_value = str(match.iloc[0]["色名"]).strip()
        return name_value, hex_value, True

    return number_clean, "#999999", False


# =========================
# 在庫読み込み・保存
# =========================
def load_data(sheet, color_df):
    values = sheet.get_all_values()

    if not values:
        sheet.update([COLUMNS], "A1")
        return pd.DataFrame(columns=COLUMNS)

    headers = values[0]
    rows = values[1:]

    if not rows:
        return pd.DataFrame(columns=COLUMNS)

    df = pd.DataFrame(rows, columns=headers)

    if "会社" in df.columns:
        df = df.rename(columns={"会社": "得意先"})

    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNS]
    df["得意先"] = df["得意先"].astype(str)
    df["種類"] = df["種類"].astype(str)
    df["No"] = df["No"].astype(str).apply(clean_code)
    df["名称"] = df["名称"].astype(str)
    df["艶"] = df["艶"].astype(str)
    df["保管場所"] = df["保管場所"].astype(str)
    df["保有数"] = df["保有数"].apply(normalize_stock)
    df["入荷日"] = df["入荷日"].astype(str)
    df.loc[df["入荷日"].str.strip() == "", "入荷日"] = today_str()

    changed = False
    fixed_hex_list = []
    fixed_name_list = []

    for _, row in df.iterrows():
        raw_hex = str(row["HEX"]).strip().upper()
        raw_name = str(row["名称"]).strip()
        auto_name, auto_hex, found_color = color_lookup(row["No"], color_df)

        if is_valid_hex(raw_hex) and raw_hex not in DEFAULT_GRAY_VALUES:
            fixed_hex = raw_hex
        elif found_color:
            fixed_hex = auto_hex
            if fixed_hex != raw_hex:
                changed = True
        elif is_valid_hex(raw_hex):
            fixed_hex = raw_hex
        else:
            fixed_hex = "#999999"
            if fixed_hex != raw_hex:
                changed = True

        if raw_name:
            fixed_name = raw_name
        else:
            fixed_name = auto_name
            if fixed_name != raw_name:
                changed = True

        fixed_hex_list.append(fixed_hex)
        fixed_name_list.append(fixed_name)

    df["HEX"] = fixed_hex_list
    df["名称"] = fixed_name_list

    if changed:
        save_data(sheet, df)

    return df


def save_data(sheet, df):
    df = df.copy()

    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNS]
    df["No"] = df["No"].apply(clean_code)
    df["HEX"] = df["HEX"].apply(normalize_hex)
    df["保有数"] = df["保有数"].apply(normalize_stock)
    df["入荷日"] = df["入荷日"].apply(lambda x: x.strftime("%Y-%m-%d") if hasattr(x, "strftime") else str(x))

    sheet.clear()
    sheet.update([COLUMNS] + df.astype(str).values.tolist(), "A1")


def append_history(history_sheet, operation, row, before_qty="", after_qty="", diff="", memo=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history_row = [
        now,
        operation,
        str(row.get("得意先", "")),
        str(row.get("種類", "")),
        str(row.get("No", "")),
        str(row.get("名称", "")),
        str(before_qty),
        str(after_qty),
        str(diff),
        str(memo),
    ]
    history_sheet.append_row(history_row, value_input_option="USER_ENTERED")


def add_or_update_data(data, customer, paint_type, number_clean, name, hex_color, gloss, stock, received_date, location):
    data = data.copy()
    data["検索No"] = data["No"].apply(clean_code)

    if number_clean in data["検索No"].values:
        data.loc[data["検索No"] == number_clean, COLUMNS] = [
            customer, paint_type, number_clean, name, hex_color, gloss, stock, received_date, location,
        ]
    else:
        new_row = pd.DataFrame([{
            "得意先": customer, "種類": paint_type, "No": number_clean, "名称": name,
            "HEX": hex_color, "艶": gloss, "保有数": stock, "入荷日": received_date, "保管場所": location,
        }])
        data = pd.concat([data.drop(columns=["検索No"], errors="ignore"), new_row], ignore_index=True)

    return data.drop(columns=["検索No"], errors="ignore")


# =========================
# 初期読み込み
# =========================
try:
    inventory_sheet, history_sheet, customer_master_sheet, type_master_sheet = get_sheets()
    color_df = load_color_master()
    customers = load_master_by_sheet_name(CUSTOMER_MASTER_SHEET, DEFAULT_CUSTOMERS)
    types = load_master_by_sheet_name(TYPE_MASTER_SHEET, DEFAULT_TYPES)
    data = load_data(inventory_sheet, color_df)
except Exception as e:
    st.error("データ読み込みでエラーが発生しました。 / Failed to load data.")
    st.exception(e)
    st.stop()


# =========================
# 上部操作（1行にまとめてコンパクト化）
# =========================
top1, top2, top3, top4 = st.columns([1, 1, 1.5, 1.5])
with top1:
    st.metric("登録件数 / Items", len(data))
with top2:
    st.metric("総保有数 / Total Stock", f"{data['保有数'].sum():g}")
with top3:
    if st.button("🔄 在庫再読み込み / Reload", use_container_width=True):
        load_color_master.clear()
        st.rerun()
with top4:
    if st.button("⚙️ マスタ再読み込み / Masters", use_container_width=True):
        load_master_by_sheet_name.clear()
        st.rerun()

gray_rows = data[data["HEX"].astype(str).str.upper().isin(DEFAULT_GRAY_VALUES)].copy()
if len(gray_rows) > 0:
    with st.expander(f"⚠️ 色がグレーのデータ / Gray Color Data ({len(gray_rows)}件)"):
        st.dataframe(gray_rows[["No", "名称", "HEX", "保有数", "保管場所"]], use_container_width=True)

st.divider()


# =========================
# 在庫入力（4列レイアウトでコンパクト化）
# =========================
st.subheader("在庫入力 / Add or Update Stock")

# 1行目：得意先・種類・No・名称
r1c1, r1c2, r1c3, r1c4 = st.columns([1.2, 1.2, 1, 1.5])
with r1c1:
    customer = st.selectbox("得意先 / Customer", customers)
with r1c2:
    paint_type = st.selectbox("種類 / Type", types)
with r1c3:
    number = st.text_input("No / 色番号")
    number_clean = clean_code(number)
with r1c4:
    name_input = st.text_input("名称 / Name")

auto_name, auto_hex, found_color = color_lookup(number_clean, color_df)

if number_clean:
    if found_color:
        st.success(f"✅ {number_clean} の色を自動表示しました", icon=None)
    else:
        st.warning(f"⚠️ {number_clean} は色マスタにありません")

name = name_input if name_input else auto_name

# 2行目：色・Finish・保有数・入荷日・場所・缶表示
r2c1, r2c2, r2c3, r2c4, r2c5 = st.columns([0.7, 1, 0.8, 1, 1.5])
with r2c1:
    hex_color = st.color_picker("色 / Color", auto_hex)
with r2c2:
    gloss = st.selectbox("艶 / Finish", GLOSS_OPTIONS)
with r2c3:
    stock = st.number_input("保有数 / Stock", min_value=0.0, max_value=MAX_STOCK, step=STEP)
with r2c4:
    received_date = st.date_input("入荷日 / Received", value=datetime.now().date())
with r2c5:
    location = st.text_input("保管場所 / Location", placeholder="例: A-1")
    st.markdown(f"<div style='margin-top:2px;'>{can_display_html(stock, hex_color)}</div>", unsafe_allow_html=True)

if st.button("追加 / 更新して保存 / Add or Update", type="primary", use_container_width=True):
    if number_clean == "":
        st.error("No / 色番号を入力してください / Please enter Color No.")
    else:
        before_qty = ""
        existing_mask = data["No"].apply(clean_code) == number_clean
        if existing_mask.any():
            before_qty = data.loc[existing_mask, "保有数"].iloc[0]

        data = add_or_update_data(
            data, customer, paint_type, number_clean, name, hex_color, gloss,
            stock, received_date.strftime("%Y-%m-%d"), location,
        )
        save_data(inventory_sheet, data)

        saved_row = data.loc[data["No"].apply(clean_code) == number_clean].iloc[0]
        operation = "追加" if before_qty == "" else "更新"
        diff = "" if before_qty == "" else normalize_stock(stock) - normalize_stock(before_qty)
        append_history(history_sheet, operation, saved_row, before_qty, stock, diff, "入力フォーム")

        st.success("保存しました / Saved")
        st.rerun()

st.divider()


# =========================
# 検索・並び替え（横並びでコンパクト化）
# =========================
st.subheader("検索・並び替え / Search and Sort")

sc1, sc2, sc3, sc4 = st.columns([2, 1, 1, 1])
with sc1:
    search = st.text_input("🔍 番号・名称・得意先・種類・場所", placeholder="Search...")
with sc2:
    gloss_filter = st.selectbox("艶 / Finish Filter", ["All／すべて"] + GLOSS_OPTIONS)
with sc3:
    location_filter = st.text_input("📍 場所フィルター", placeholder="例: A-1")
with sc4:
    sort_mode = st.selectbox("並び替え / Sort", ["色番号順", "保有数順", "得意先順", "種類順", "場所順", "入荷日順"])

owned = data[data["保有数"] > 0].copy()

if search:
    s = clean_code(search)
    owned = owned[
        owned["No"].astype(str).apply(clean_code).str.contains(s, na=False)
        | owned["名称"].astype(str).apply(clean_code).str.contains(s, na=False)
        | owned["得意先"].astype(str).apply(clean_code).str.contains(s, na=False)
        | owned["種類"].astype(str).apply(clean_code).str.contains(s, na=False)
        | owned["保管場所"].astype(str).apply(clean_code).str.contains(s, na=False)
    ]

if gloss_filter != "All／すべて":
    owned = owned[owned["艶"] == gloss_filter]

if location_filter:
    lf = clean_code(location_filter)
    owned = owned[owned["保管場所"].astype(str).apply(clean_code).str.contains(lf, na=False)]

if sort_mode == "色番号順":
    owned = owned.sort_values("No")
elif sort_mode == "保有数順":
    owned = owned.sort_values("保有数", ascending=False)
elif sort_mode == "得意先順":
    owned = owned.sort_values("得意先")
elif sort_mode == "種類順":
    owned = owned.sort_values("種類")
elif sort_mode == "場所順":
    owned = owned.sort_values("保管場所")
elif sort_mode == "入荷日順":
    owned = owned.sort_values("入荷日")

left, right = st.columns([2, 1])


# =========================
# 保有リスト
# =========================
with left:
    st.subheader("保有リスト / Stock List")

    if len(owned) == 0:
        st.info("該当する在庫データがありません / No matching stock data.")
    else:
        for idx, row in owned.iterrows():
            display_hex = normalize_hex(row["HEX"])
            expiry_text, expiry_color = expiry_info(row.get("入荷日", ""), row.get("種類", ""))
            qty = normalize_stock(row["保有数"])
            location_text = str(row.get("保管場所", "")).strip() or "No Location"
            gloss_text = str(row.get("艶", "")).strip() or "No Finish"

            st.markdown(
                f"""
                <div class="paint-card">
                    <div class="paint-card-inner">
                        <div class="paint-chip" style="background-color:{display_hex};"></div>
                        <div class="paint-info">
                            <span style="font-size:11px;color:#6b7280;">{row['得意先']} / {row['種類']}</span><br>
                            <span class="paint-no-name">{row['No']}　{row['名称']}</span><br>
                            <span class="badge">{gloss_text}</span>
                            <span class="badge" style="color:{expiry_color};">📅 {row.get('入荷日', '')} ｜ {expiry_text}</span>
                            <span class="badge">📍 {location_text}</span><br>
                            <span>{can_display_html(qty, display_hex)}</span>
                            <span style="font-size:15px; margin-left:8px; vertical-align:middle;">{qty:g} {unit_label(qty)}</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            b1, b2, b3, b4, b5 = st.columns([1, 1, 1, 1, 2])

            with b1:
                if st.button("＋0.5", key=f"plus05_{idx}", use_container_width=True):
                    before_qty = normalize_stock(data.loc[idx, "保有数"])
                    after_qty = min(before_qty + 0.5, MAX_STOCK)
                    data.loc[idx, "保有数"] = after_qty
                    save_data(inventory_sheet, data)
                    append_history(history_sheet, "入庫", data.loc[idx], before_qty, after_qty, after_qty - before_qty, "保有リスト +0.5")
                    st.rerun()

            with b2:
                if st.button("＋1", key=f"plus1_{idx}", use_container_width=True):
                    before_qty = normalize_stock(data.loc[idx, "保有数"])
                    after_qty = min(before_qty + 1.0, MAX_STOCK)
                    data.loc[idx, "保有数"] = after_qty
                    save_data(inventory_sheet, data)
                    append_history(history_sheet, "入庫", data.loc[idx], before_qty, after_qty, after_qty - before_qty, "保有リスト +1")
                    st.rerun()

            with b3:
                if st.button("−0.5", key=f"minus05_{idx}", use_container_width=True):
                    before_qty = normalize_stock(data.loc[idx, "保有数"])
                    after_qty = max(before_qty - 0.5, 0)
                    data.loc[idx, "保有数"] = after_qty
                    save_data(inventory_sheet, data)
                    append_history(history_sheet, "出庫", data.loc[idx], before_qty, after_qty, after_qty - before_qty, "保有リスト -0.5")
                    st.rerun()

            with b4:
                if st.button("−1", key=f"minus1_{idx}", use_container_width=True):
                    before_qty = normalize_stock(data.loc[idx, "保有数"])
                    after_qty = max(before_qty - 1.0, 0)
                    data.loc[idx, "保有数"] = after_qty
                    save_data(inventory_sheet, data)
                    append_history(history_sheet, "出庫", data.loc[idx], before_qty, after_qty, after_qty - before_qty, "保有リスト -1")
                    st.rerun()

            with b5:
                edit_key = f"edit_{idx}"
                pending_key = f"pending_delete_{idx}"

                e1, e2 = st.columns(2)
                with e1:
                    if st.button("編集 / Edit", key=f"edit_button_{idx}", use_container_width=True):
                        st.session_state[edit_key] = not st.session_state.get(edit_key, False)
                        st.rerun()

                with e2:
                    if st.button(f"削除 {row['No']}", key=f"delete_{idx}", use_container_width=True):
                        st.session_state[pending_key] = True
                        st.rerun()

                if st.session_state.get(edit_key):
                    with st.form(f"edit_form_{idx}"):
                        st.write(f"**{row['No']} を編集 / Edit**")
                        ec1, ec2, ec3 = st.columns(3)

                        with ec1:
                            edit_customer = st.selectbox(
                                "得意先", customers,
                                index=customers.index(row["得意先"]) if row["得意先"] in customers else 0,
                                key=f"edit_customer_{idx}",
                            )
                            edit_type = st.selectbox(
                                "種類", types,
                                index=types.index(row["種類"]) if row["種類"] in types else 0,
                                key=f"edit_type_{idx}",
                            )
                            edit_name = st.text_input("名称", value=str(row["名称"]), key=f"edit_name_{idx}")

                        with ec2:
                            edit_gloss = st.selectbox(
                                "艶 / Finish", GLOSS_OPTIONS,
                                index=GLOSS_OPTIONS.index(row["艶"]) if row["艶"] in GLOSS_OPTIONS else 0,
                                key=f"edit_gloss_{idx}",
                            )
                            edit_location = st.text_input("保管場所", value=str(row.get("保管場所", "")), key=f"edit_loc_{idx}")
                            edit_hex = st.color_picker("色", normalize_hex(row["HEX"]), key=f"edit_hex_{idx}")

                        with ec3:
                            edit_qty = st.number_input(
                                "保有数", min_value=0.0, max_value=MAX_STOCK, step=STEP,
                                value=normalize_stock(row["保有数"]), key=f"edit_qty_{idx}",
                            )
                            try:
                                default_received = pd.to_datetime(row.get("入荷日", today_str())).date()
                            except Exception:
                                default_received = datetime.now().date()
                            edit_received_date = st.date_input(
                                "入荷日", value=default_received, key=f"edit_received_{idx}",
                            )
                            st.markdown(f"<div>{can_display_html(edit_qty, edit_hex)}</div>", unsafe_allow_html=True)

                        memo = st.text_input("メモ / Memo", value="保有リストから編集", key=f"edit_memo_{idx}")
                        s1, s2 = st.columns(2)
                        with s1:
                            submitted = st.form_submit_button("変更を保存 / Save", use_container_width=True)
                        with s2:
                            cancelled = st.form_submit_button("キャンセル / Cancel", use_container_width=True)

                        if submitted:
                            before_qty = normalize_stock(data.loc[idx, "保有数"])
                            data.loc[idx, "得意先"] = edit_customer
                            data.loc[idx, "種類"] = edit_type
                            data.loc[idx, "名称"] = edit_name
                            data.loc[idx, "HEX"] = edit_hex
                            data.loc[idx, "艶"] = edit_gloss
                            data.loc[idx, "保有数"] = edit_qty
                            data.loc[idx, "入荷日"] = edit_received_date.strftime("%Y-%m-%d")
                            data.loc[idx, "保管場所"] = edit_location
                            save_data(inventory_sheet, data)
                            append_history(
                                history_sheet, "編集", data.loc[idx],
                                before_qty, edit_qty, normalize_stock(edit_qty) - before_qty, memo,
                            )
                            st.session_state.pop(edit_key, None)
                            st.success("変更しました / Updated")
                            st.rerun()

                        if cancelled:
                            st.session_state.pop(edit_key, None)
                            st.rerun()

                if st.session_state.get(pending_key):
                    ca, cb = st.columns(2)

                    with ca:
                        if st.button("本当に削除 / Confirm Delete", key=f"confirm_yes_{idx}", use_container_width=True):
                            deleted_row = data.loc[idx].copy()
                            before_qty = normalize_stock(deleted_row["保有数"])
                            data = data.drop(index=idx)
                            save_data(inventory_sheet, data)
                            append_history(history_sheet, "削除", deleted_row, before_qty, 0, -before_qty, "保有リストから削除")
                            st.session_state.pop(pending_key, None)
                            st.success("削除しました / Deleted")
                            st.rerun()

                    with cb:
                        if st.button("キャンセル / Cancel", key=f"confirm_no_{idx}", use_container_width=True):
                            st.session_state.pop(pending_key, None)
                            st.rerun()


# =========================
# 保有カラー一覧
# =========================
with right:
    st.subheader("カラー一覧 / Colors")

    if len(owned) == 0:
        st.info("保有カラーなし / No colors in stock.")
    else:
        for _, row in owned.iterrows():
            display_hex = normalize_hex(row["HEX"])
            qty = normalize_stock(row["保有数"])

            st.markdown(
                f"""
                <div class="small-color-row">
                    <div class="small-color-chip" style="background-color:{display_hex};"></div>
                    <div style="font-size:12px;">{row['No']}　{row['名称']}　<b>{qty:g}</b> {unit_label(qty)}<br>
                    <span style="color:#6b7280;font-size:11px;">📍 {row.get('保管場所', '')}</span></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.divider()
        st.metric("保有色数 / Colors", len(owned))
        st.metric("保有数量 / Quantity", f"{owned['保有数'].sum():g}")

st.divider()


# =========================
# 直接テーブル編集
# =========================
st.subheader("直接テーブル編集 / Direct Table Edit")
st.caption("ここで編集して保存すると、Googleスプレッドシートに反映されます。")

editor_data = data.copy()
editor_data["入荷日"] = pd.to_datetime(editor_data["入荷日"], errors="coerce").dt.date

edited_data = st.data_editor(
    editor_data,
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "得意先": st.column_config.SelectboxColumn("得意先 / Customer", options=customers),
        "種類": st.column_config.SelectboxColumn("種類 / Type", options=types),
        "HEX": st.column_config.TextColumn("HEX / Color Code"),
        "艶": st.column_config.SelectboxColumn("艶 / Finish", options=GLOSS_OPTIONS),
        "保有数": st.column_config.NumberColumn("保有数 / Stock", min_value=0.0, max_value=MAX_STOCK, step=STEP),
        "入荷日": st.column_config.DateColumn("入荷日 / Received Date"),
        "保管場所": st.column_config.TextColumn("保管場所 / Location"),
    },
)

if st.button("テーブル編集を保存 / Save Table Edits", use_container_width=True):
    edited_data = edited_data.copy()
    edited_data["入荷日"] = edited_data["入荷日"].apply(lambda x: x.strftime("%Y-%m-%d") if hasattr(x, "strftime") else str(x))
    save_data(inventory_sheet, edited_data)
    append_history(
        history_sheet, "テーブル編集",
        {"得意先": "", "種類": "", "No": "一括", "名称": "直接テーブル編集"},
        "", "", "", "直接テーブル編集で保存",
    )
    st.success("Googleスプレッドシートに保存しました / Saved to Google Sheets.")
    st.rerun()

st.divider()


# =========================
# 履歴表示
# =========================
st.subheader("変更履歴 / Change History")

try:
    history_values = history_sheet.get_all_values()
    if len(history_values) <= 1:
        st.info("まだ履歴はありません。 / No history yet.")
    else:
        history_df = pd.DataFrame(history_values[1:], columns=history_values[0])
        history_df = history_df.tail(30).iloc[::-1]
        st.dataframe(history_df, use_container_width=True, hide_index=True)
except Exception as e:
    st.warning("履歴の読み込みに失敗しました。 / Failed to load history.")
    st.caption(str(e))

st.divider()


# =========================
# マスタ管理説明
# =========================
with st.expander("⚙️ 得意先マスタ・種類マスタの使い方 / How to Use Master Sheets"):
    st.write("同じGoogleスプレッドシート内に以下のシートを作成・使用します。")
    st.write("- 在庫 / 履歴 / 得意先マスタ / 種類マスタ")
    st.write("得意先マスタ・種類マスタは、A列の見出しを `名称` にして、その下に選択肢を入力してください。")
    st.write("在庫シートは、必要な列が無い場合でもアプリ側で空欄として扱います。保存時に列が整います。")
