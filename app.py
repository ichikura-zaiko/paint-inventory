import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import unicodedata
import os
import re
from datetime import datetime
from datetime import datetime


# =========================
# 画面設定
# =========================
st.set_page_config(page_title="塗料在庫管理", page_icon="🎨", layout="wide")
st.title("🎨 塗料在庫管理")
st.caption("Googleスプレッドシート直結・キャッシュなし")


# =========================
# 基本設定
# =========================
SPREADSHEET_ID = "1BnRviQ1S5rEDFVX3NCkLfGQpm9Jrq1xtFkfDLHba3z0"
COLORINVENTORY_SHEET = "在庫"
HISTORY_SHEET = "履歴"
CUSTOMER_MASTER_SHEET = "得意先マスタ"
TYPE_MASTER_SHEET = "種類マスタ"MACOLUMNS = ["得意先", "種類", "No", "名称", "HEX", "保有数"]
HISTORY_COLUMNS = ["日時", "操作", "得意先", "種類", "No", "名称", "変更前", "変更後", "差分", "メモ"]
MASTER_COLUMNS = ["名称"], "No", "名称", "HEX", "保有数"]
HISTORY_COLUMNS = ["日時", "操作", "得意先", "種類", "No", "名称", "変更前", "変更後", "差分", "メモ"]
MASTER_COLUMNS = ["名称"]

DEFAULT_CUSTOMERS = ["自社", "東洋紡エンジニアリング", "その他"]
DEFAULT_TYPES = ["アクリル", "メラミン", "粉体", "ウレタン", "エポキシ", "ラッカー", "その他"]

MAX_STOCK = 50.0
STEP = 0.5
HEX_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


# =========================
# スマホ向けCSS
# =========================
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
    }
    .paint-card {
        background-color:#dbeafe;
        padding:14px;
        border-radius:12px;
        margin-bottom:12px;
        border:1px solid #ccc;
    }
    .paint-card-inner {
        display:flex;
        align-items:center;
        gap:14px;
        flex-wrap:wrap;
    }
    .paint-chip {
        width:58px;
        height:58px;
        border:1px solid #555;
        border-radius:8px;
        flex: 0 0 auto;
    }
    .paint-info {
        flex:1;
        min-width:220px;
    }
    .paint-no-name {
        font-size:22px;
        font-weight:600;
    }
    .paint-stock {
        font-size:28px;
        letter-spacing:1px;
        white-space:nowrap;
    }
    .small-color-row {
        display:flex;
        align-items:center;
        gap:8px;
        margin-bottom:8px;
    }
    .small-color-chip {
        width:28px;
        height:28px;
        border:1px solid #555;
        flex: 0 0 auto;
    }
    @media (max-width: 768px) {
        .stButton > button {
            width: 100%;
            min-height: 42px;
        }
        div[data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
        }
        .paint-no-name {
            font-size:20px;
        }
        .paint-stock {
            font-size:24px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================
# 共通関数
# =========================
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


def can_display(qty):
    """テキスト用の簡易表示。data_editorなどHTMLが使えない場所用。"""
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
    """実際の塗料色で、1マス=1缶として横並び表示する。"""
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
            f"<span style='display:inline-block;width:28px;height:28px;margin-right:5px;"
            f"border:1px solid #777;border-radius:5px;background:{bg};"
            f"vertical-align:middle;box-sizing:border-box;'></span>"
        )

    extra = f"<span style='font-size:18px;margin-left:4px;vertical-align:middle;'>+{qty - 5:g}</span>" if qty > 5 else ""
    return f"<span style='display:inline-flex;align-items:center;gap:0;white-space:nowrap;'>{''.join(boxes)}{extra}</span>"


# =========================
# Google Sheets接続
# connect_spreadsheetだけは接続再利用のため cache_resource OK
# load_dataにはキャッシュを使わない
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
    """シート取得。存在しなければ作成。
    Google APIの読み取り回数を減らすため、既存シートには毎回 get_all_values() しない。
    """
    try:
        return spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=1000, cols=max(len(columns), 3))
        ws.update([columns], "A1")
        return ws


def ensure_master_has_default_values(ws, defaults):
    """マスタが空のときだけ初期値を入れる。
    読み取り回数節約のためA列だけ確認する。
    """
    values = ws.col_values(1)
    if ledef get_sheets():
    """ワークシートオブジェクトはキャッシュする。
    実データ load_data はキャッシュしないので、在庫変更は反映される。
    """
    spreadsheet = connect_spreadsheet()
    inventory_ws = get_or_create_worksheet(spreadsheet, INVENTORY_SHEET, COLUMNS)
    history_ws = get_or_create_worksheet(spreadsheet, HISTORY_SHEET, HISTORY_COLUMNS)
    customer_ws = get_or_create_worksheet(spreadsheet, CUSTOMER_MASTER_SHEET, MASTER_COLUMNS)
    type_ws = get_or_create_worksheet(spreadsheet, TYPE_MASTER_SHEET, MASTER_COLUMNS)
    return inventory_ws, history_ws, customer_ws, type_wsstomer_ws = get_or_create_worksheet(spreadsheet, CUSTOMER_MASTER_SHEET, MASTER_COLUMNS)
    type_ws = get_or_create_worksheet(spreadsheet, TYPE_MASTER_SHEET, MASTER_COLUMNS)
    return inventory_ws, history_ws, customer_ws, type_ws


# =========================
# マスタ読み込み
# =========================
@st.cache_data(ttl=300)
def load_master_by_sheet_name(sheet_name, defaults):
    """得意先・種類マスタは5分キャッシュ。
    在庫データ本体ではないため、API制限対策としてキャッシュする。
    マスタを変更したら『マスタ再読み込み』ボタンでクリアできる。
    """
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

    # CSVの列名ゆれ対策
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
    """日塗工CSVから色名・HEXを探す。
    入力ゆれ対策として、完全一致のほかにハイフンなし・スペースなしでも照合する。
    例：90-25A / 9025A、N-5 / N5 など。
    """
    number_clean = clean_code(number)

    if number_clean == "":
        return "", "#999999", False

    def key(value):
        value = clean_code(value)
        value = value.replace("-", "")
        value = value.replace(" ", "")
        value = value.replace("　", "")
        return value

    # 完全一致
    match = color_df[color_df["検索番号"] == number_clean]

    # ゆれ吸収一致
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
# load_dataはキャッシュなし
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
    df["保有数"] = df["保有数"].apply(normalize_stock)

    # HEXを自動補完する。
    # 1. シートのHEXが正しい場合は、シート側を優先する
    # 2. HEXが空欄・不正・仮グレーの場合だけ nittoko_colors.csv から取得する
    # 3. 名称が空欄の場合も nittoko_colors.csv から補完する
    #
    # 注意：CSVを常に優先すると、スプレッドシートで手修正したHEXが
    # アプリ側で上書きされるため、ここではシート側の有効HEXを優先する。
    changed = False
    fixed_hex_list = []
    fixed_name_list = []

    DEFAULT_GRAY_VALUES = {"", "#999999", "#929396"}

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

    # シート側のHEX/名称も自動で埋め戻す。
    # これにより、スプレッドシートにNoだけ入力しても次回読み込み時にHEXが入る。
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


def add_or_update_data(data, customer, paint_type, number_clean, name, hex_color, stock):
    data = data.copy()
    data["検索No"] = data["No"].apply(clean_code)

    # 現状仕様：Noが同じなら更新
    # 得意先・種類ごとに同じNoを別管理したい場合は、ここを複合キーに変更する
    if number_clean in data["検索No"].values:
        data.loc[data["検索No"] == number_clean, COLUMNS] = [
            customer,
            paint_type,
            number_clean,
            name,
            hex_color,
            stock,
        ]
    else:
        new_row = pd.DataFrame([
            {
                "得意先": customer,
                "種類": paint_type,
                "No": number_clean,
                "名称": name,
                "HEX": hex_color,
                "保有数": stock,
            }
        ])
   _row], ignore_index=True)

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
    st.error("データ読み込みでエラーが発生しました。")
    st.exception(e)
    st.stop()


# =========================
# 上部操作
# =========================
top1, top2, top3 = st.columns([1, 1, 1])
with top1:
    st.metric("登録件数", len(data))
with top2:
    st.metric("総保有数", f"{data['保有数'].sum():g}")
with top3:
    if st.button("🔄 在庫を再読み込み", use_container_width=True):
        load_color_master.clear()
        st.rerun()

if st.button("⚙️ マスタ再読み込み", use_container_width=True):
    load_master_by_sheet_name.clear()
    st.rerun()

# 色が見つからないデータを画面に出す
DEFAULT_GRAY_VALUES = {"", "#999999", "#929396"}
gray_rows = data[data["HEX"].astype(str).str.upper().isin(DEFAULT_GRAY_VALUES)].copy()
if len(gray_rows) > 0:
    with st.expander("⚠️ 色がグレー表示になっているデータ"):
        st.write("以下は、スプレッドシートのHEXが空欄・仮グレー、または nittoko_colors.csv で色が見つからない可能性があります。")
        st.dataframe(gray_rows[["No", "名称", "HEX", "保有数"]], use_container_width=True)
        st.write("対処方法：GoogleスプレッドシートのHEX列に正しい `#RRGGBB` を入れるか、nittoko_colors.csv に該当番号とHEXを追加してください。")

st.divider()


# =========================
# 在庫入力
# =========================
st.subheader("在庫入力")

col1, col2, col3 = st.columns(3)

with col1:
    customer = st.selectbox("得意先", customers)
    paint_type = st.selectbox("種類", types)

with col2:
    number = st.text_input("No / 色番号")
    number_clean = clean_code(number)
    name_input = st.text_input("名称")

auto_name, auto_hex, found_color = color_lookup(number_clean, color_df)

if number_clean:
    if found_color:
        st.success(f"{number_clean} の色を自動表示しました")
    else:
        st.warning(f"{number_clean} は nittoko_colors.csv にありません")

name = name_input if name_input else auto_name

with col3:
    hex_color = st.color_picker("色", auto_hex)
    stock = st.number_input("保有数", min_value=0.0, max_value=MAX_STOCK, step=STEP)
    st.markdown(f"<div>{can_display_html(stock, hex_color)}</div>", unsafe_allow_html=Tran
        if existing_mask.any():
            before_qty = data.loc[existing_mask, "保有数"].iloc[0]

        data = add_or_update_data(data, customer, paint_type, number_clean, name, hex_color, stock)
        save_data(inventory_sheet, data)

        saved_row = data.loc[data["No"].apply(clean_code) == number_clean].iloc[0]
        operation = "追加" if before_qty == "" else "更新"
        diff = "" if before_qty == "" else normalize_stock(stock) - normalize_stock(before_qty)
        append_history(history_sheet, operation, saved_row, before_qty, stock, diff, "入力フォーム")

        st.success("保存しました")
        st.rerun()

st.divider()


# =========================
# 検索・並び替え
# =========================
st.subheader("検索・並び替え")

c1, c2 = st.columns([2, 1])

with c1:
    search = st.text_input("色番号・名称・得意先・種類で検索")

with c2:
    sort_mode = st.selectbox("並び替え", ["色番号順", "保有数順", "得意先順", "種類順"])

owned = data[data["保有数"] > 0].copy()

if search:
    s = clean_code(search)
    owned = owned[
        owned["No"].astype(str).apply(clean_code).str.contains(s, na=False)
        | owned["名称"].astype(str).apply(clean_code).str.contains(s, na=False)
        | owned["得意先"].astype(str).apply(clean_code).str.contains(s, na=False)
        | owned["種類"].astype(str).apply(clean_code).str.contains(s, na=False)
    ]

if sort_mode == "色番号順":
    owned = owned.sort_values("No")
elif sort_mode == "保有数順":
    owned = owned.sort_values("保有数", ascending=False)
elif sort_mode == "得意先順":
    owned = owned.sort_values("得意先")
elif sort_mode == "種類順":
    owned = owned.sort_values("種類")

left, right = st.columns([2, 1])


# =========================
# 保有リスト
# =========================
with left:
    st.subheader("保有リスト")

    if len(owned) == 0:
        st.info("該当する在庫データがありません")
    else:
        for idx, row in owned.iterrows():
            display_hex = normalize_hex(row["HEX"])

            st.markdown(
                f"""
                <div class="paint-card">
                    <div class="paint-card-inner">
                        <div class="paint-chip" style="background-color:{display_hex};"></div>
                        <div class="paint-info">
                            <b>{row['得意先']} / {row['種類']}</b><br>
                            <span class="paint-no-name">{row['No']}　{row['名称']}</span><br>
                            <span>{can_display_html(row['保有数'], display_hex)}</span>
                            <span style="font-size:18px; margin-left:10px; vertical-align:middle;">{row['保有数']:g}個</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            b1, b2, b3 = st.columns([1, 1, 2])

            wit("−0.5", key=f"minus_{idx}", use_container_width=True):
                    before_qty = normalize_stock(data.loc[idx, "保有数"])
                    after_qty = max(before_qty - STEP, 0)
                    data.loc[idx, "保有数"] = after_qty
                    save_data(inventory_sheet, data)
                    append_history(history_sheet, "出庫", data.loc[idx], before_qty, after_qty, after_qty - before_qty, "保有リスト -0.5")
                    st.rerun()

            with b3:
                edit_key = f"edit_{idx}"
                pending_key = f"pending_delete_{idx}"

                e1, e2 = st.columns(2)
                with e1:
                    if st.button("編集", key=f"edit_button_{idx}", use_container_width=True):
                        st.session_state[edit_key] = not st.session_state.get(edit_key, False)
                        st.rerun()

                with e2:
                    if st.button(f"削除 {row['No']}", key=f"delete_{idx}", use_container_width=True):
                        st.sesse=str(row["名称"]), key=f"edit_name_{idx}")

                        with ec2:
                            edit_hex = st.color_picker("色", normalize_hex(row["HEX"]), key=f"edit_hex_{idx}")
                            edit_qty = st.number_input(
                                "保有数",
                                min_value=0.0,
                                max_value=MAX_STOCK,
                                step=STEP,
                                value=normalize_stock(row["保有数"]),
                                key=f"edit_qty_{idx}",
                            )
                            st.markdown(f"<div>{can_display_html(edit_qty, edit_hex)}</div>", unsafe_allow_html=True)

                        memo = st.text_input("メモ", value="保有リストから編集", key=f"edit_memo_{idx}")
                        s1, s2 = st.columns(2)
                        with s1:
                            submitted = st.form_submit_button("変更を保存", use_container_width=True)
                        with s2:
                            cancelled = st.form_submit_button("キャンセル", use_container_width=True)

                        if submitted:
                            before_qty = normalize_stock(data.loc[idx, "保有数"])
                            data.loc[idx, "得意先"] = edit_customer
                            data.loc[idx, "種類"] = edit_type
                            data.loc[idx, "名称"] = edit_name
                            data.loc[idx, "HEX"] = edit_hex
                            data.loc[idx, "保有数"] = edit_qty
                            save_data(inventory_sheet, data)
                            append_history(
                                history_sheet,
                                "編集",
                                data.loc[idx],
                                before_qty,
                                edit_qty,
                                normalize_stock(edit_qty) - before_qty,
                                memo,
                            )
                            st.session_state.pop(edit_key, None)
                            st.success("変更しました")
                            st.rerun()

                        if cancelled:
                            st.session_state.pop(edit_key, None)
                            st.rerun()

                if st.session_state.get(pending_key):
                    ca, cb = st.columns(2)

                    with ca:
                        if st.button("本当に削除", key=f"confirm_yes_{idx}", use_container_width=True):
                            deleted_row = data.loc[idx].copy()
                            before_qty = normalize_stock(deleted_row["保有数"])
                            data = data.drop(index=idx)
                            save_data(inventory_sheet, data)
                            append_history(history_sheet, "削除", deleted_row, before_qty, 0, -before_qty, "保有リストから削除")
                            st.session_state.pop(pending_key, None)
                            st.success("削除しました")
                            st.rerun()

                    with cb:
                        if st.button("キャンセル", key=f"confirm_no_{idx}", use_container_width=True):
                            st.session_state.pop(pending_key, None)
                            st.rerun()


# =========================
# 保有カラー一覧
# =========================
with right:
    st.subheader("保有カラー一覧")

    if len(owned) == 0:
        st.info("保有カラーなし")
    else:
        for _, row in owned.iterrows():
            display_hex = normalize_hex(row["HEX"])

            st.markdown(
                f"""
                <div class="small-color-row">
                    <div class="small-color-chip" style="background-color:{display_hex};"></div>
                    <div>{row['No']}　{row['名称']}　{row['保有数']:g}個</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.divider()
        st.metric("保有色数", len(owned))
        st.metric("保有数量", f"{owned['保有数'].sum():g}")

st.divider()


# =========================
# 直接テーブル編集
# =========================
st.subheader("直接テーブル編集")
st.caption("ここで編集して保存すると、Googleスプレッドシートに反映されます。")

edited_data = st.data_editor(
    data,
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "得意先": st.column_config.SelectboxColumn("得意先", options=customers),
        "種類": st.column_config.SelectboxColumn("種類", options=types),
        "HEX": st.column_config.TextColumn("HEX"),
        "保有数": st.column_config.NumberColumn("保有数", min_value=0.0, max_value=MAX_STOCK, step=STEP),
    },
)

if st.button("テーブル編集を保存", use_container_width=True):
    save_data(inventory_sheet, edited_data)
    append_history(
        history_sheet,
        "テーブル編集",
        {"得意先": "", "種類": "", "No": "一括", "名称": "直接テーブル編集"},
        "",
        "",
        "",
        "直接テーブル編集で保存",
    )
    st.success("Googleスプレッドシートに保存しました")
    st.rerun()

st.divider()


# =========================
# 履歴表示
# =========================
st.subheader("変更履歴")

try:
    history_values = history_sheet.get_all_values()
    if len(history_values) <= 1:
        st.info("まだ履歴はありません。")
    else:
        history_df = pd.DataFrame(history_values[1:], columns=history_values[0])
        history_df = history_df.tail(30).iloc[::-1]
        st.dataframe(history_df, use_container_width=True, hide_index=True)
except Exception as e:
    st.warning("履歴の読み込みに失敗しました。")
    st.caption(str(e))

st.divider()


# =========================
# マスタ管理説明
# =========================
with st.expander("⚙️ 得意先マスタ・種類マスタの使い方"):
    st.write("同じGoogleスプレッドシート内に以下のシートを作成・使用します。")
    st.write("- 在庫")
    st.write("- 得意先マスタ")
    st.write("- 種類マスタ")
    st.write("得意先マスタ・種類マスタは、A列の見出しを `名称` にして、その下に選択肢を入力してください。")
    st.write("スプレッドシート側でマスタを編集した後は、上部の『スプレッドシートを再読み込み』を押してください。")
