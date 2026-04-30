import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import unicodedata
import os
import re

st.set_page_config(page_title="塗料在庫管理", layout="wide")
st.title("塗料在庫管理")

SPREADSHEET_ID = "1ydFNv3aDZb5x7JZoLFRpqSRWOnEZ93HsEjxSkrQLMgY"
COLOR_FILE = "nittoko_colors.csv"

COLUMNS = ["得意先", "種類", "No", "名称", "HEX", "保有数"]

CUSTOMERS = ["自社", "東洋紡エンジニアリング", "その他"]
TYPES = ["アクリル", "メラミン", "粉体", "ウレタン", "エポキシ", "ラッカー", "その他"]

HEX_PATTERN = re.compile(r'^#[0-9A-Fa-f]{6}$')


# ── ユーティリティ ───────────────────────────────────────────

def clean_code(value):
    """None・空文字ガード付き、全角→半角正規化＋大文字化"""
    if value is None:
        return ""
    value = str(value).strip()
    if value == "":
        return ""
    value = unicodedata.normalize("NFKC", value)
    return value.upper()


def is_valid_hex(value: str) -> bool:
    return bool(HEX_PATTERN.match(str(value).strip()))


def can_display(qty):
    qty = float(qty)
    full = int(qty)
    half = (qty - full) >= 0.5

    display = ""
    for i in range(5):
        if i < min(full, 5):
            display += "🟦"
        elif i == full and half and full < 5:
            display += "◧"
        else:
            display += "⬜"

    if qty > 5:
        extra = qty - 5
        display += f" +{extra:g}"

    return display


# ── Google Sheets 接続（TTL=1時間でトークン期限切れ対策）───────

@st.cache_resource(ttl=3600)
def connect_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).sheet1


sheet = connect_sheet()


# ── データ読み書き（キャッシュ付き、TTL=30秒）─────────────────

@st.cache_data(ttl=30)
def load_data():
    values = sheet.get_all_values()

    if not values:
        sheet.update([COLUMNS])
        return pd.DataFrame(columns=COLUMNS)

    headers = values[0]
    rows = values[1:]

    df = pd.DataFrame(rows, columns=headers)

    # 旧カラム名の互換対応
    if "会社" in df.columns:
        df = df.rename(columns={"会社": "得意先"})

    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNS]
    df["保有数"] = pd.to_numeric(df["保有数"], errors="coerce").fillna(0)
    return df


def save_data(df):
    df = df[COLUMNS].copy()
    df["保有数"] = pd.to_numeric(df["保有数"], errors="coerce").fillna(0)

    sheet.clear()
    sheet.update([COLUMNS] + df.astype(str).values.tolist())

    # キャッシュをクリアして次回 load_data が最新値を返すようにする
    load_data.clear()


# ── カラーマスター読み込み ────────────────────────────────────

@st.cache_data
def load_color_master():
    if os.path.exists(COLOR_FILE):
        df = pd.read_csv(COLOR_FILE)
        df.columns = df.columns.str.strip()
    else:
        df = pd.DataFrame(columns=["日塗工番号", "色名", "HEX"])

    for col in ["日塗工番号", "色名", "HEX"]:
        if col not in df.columns:
            df[col] = ""

    df["検索番号"] = df["日塗工番号"].apply(clean_code)
    return df


# ── データ取得 ────────────────────────────────────────────────

data = load_data()
color_df = load_color_master()

# ── 在庫入力フォーム ──────────────────────────────────────────

st.subheader("在庫入力")

col1, col2, col3 = st.columns(3)

with col1:
    customer = st.selectbox("得意先", CUSTOMERS)
    paint_type = st.selectbox("種類", TYPES)

with col2:
    number = st.text_input("No / 色番号")
    number_clean = clean_code(number)
    name_input = st.text_input("名称")

match = color_df[color_df["検索番号"] == number_clean] if number_clean else pd.DataFrame()

if not match.empty:
    auto_hex = str(match.iloc[0]["HEX"]).strip()
    auto_name = str(match.iloc[0]["色名"]).strip()
    # HEXが不正な場合はフォールバック
    if not is_valid_hex(auto_hex):
        auto_hex = "#999999"
    name = auto_name if name_input == "" else name_input
    st.success(f"{number_clean} の色を自動表示しました")
else:
    auto_hex = "#999999"
    name = name_input if name_input else number_clean
    if number_clean:
        st.warning(f"{number_clean} は nittoko_colors.csv にありません")

with col3:
    hex_color = st.color_picker("色", auto_hex)
    stock = st.number_input("保有数", min_value=0.0, max_value=50.0, step=0.5)

if st.button("追加 / 更新して保存", use_container_width=True):
    if number_clean == "":
        st.error("No / 色番号を入力してください")
    else:
        data["検索No"] = data["No"].apply(clean_code)

        if number_clean in data["検索No"].values:
            data.loc[data["検索No"] == number_clean, COLUMNS] = [
                customer, paint_type, number_clean, name, hex_color, stock
            ]
            st.success("更新しました")
        else:
            new_row = pd.DataFrame([{
                "得意先": customer,
                "種類": paint_type,
                "No": number_clean,
                "名称": name,
                "HEX": hex_color,
                "保有数": stock,
            }])
            data = pd.concat(
                [data.drop(columns=["検索No"], errors="ignore"), new_row],
                ignore_index=True
            )
            st.success("追加しました")

        data = data.drop(columns=["検索No"], errors="ignore")
        save_data(data)
        st.rerun()

st.divider()

# ── 検索・並び替え ────────────────────────────────────────────

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

# ── 保有リスト ────────────────────────────────────────────────

left, right = st.columns([2, 1])

with left:
    st.subheader("保有リスト")

    if len(owned) == 0:
        st.info("該当する在庫データがありません")
    else:
        for idx, row in owned.iterrows():
            # HEXが不正な値の場合はグレーにフォールバック（表示崩れ防止）
            display_hex = row["HEX"] if is_valid_hex(row["HEX"]) else "#999999"

            st.markdown(
                f"""
                <div style="
                    background-color:#dbeafe;
                    padding:14px;
                    border-radius:12px;
                    margin-bottom:12px;
                    border:1px solid #ccc;
                ">
                    <div style="display:flex; align-items:center; gap:14px; flex-wrap:wrap;">
                        <div style="
                            width:58px;
                            height:58px;
                            background-color:{display_hex};
                            border:1px solid #555;
                            border-radius:8px;
                        "></div>
                        <div style="flex:1; min-width:220px;">
                            <b>{row['得意先']} / {row['種類']}</b><br>
                            <span style="font-size:22px;">{row['No']}　{row['名称']}</span><br>
                            <span style="font-size:28px;">{can_display(row['保有数'])}</span>
                            <span style="font-size:18px;">　{row['保有数']}個</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            b1, b2, b3 = st.columns([1, 1, 2])

            with b1:
                if st.button("＋0.5", key=f"plus_{idx}", use_container_width=True):
                    data.loc[idx, "保有数"] = min(float(data.loc[idx, "保有数"]) + 0.5, 50)
                    save_data(data)
                    st.rerun()

            with b2:
                if st.button("−0.5", key=f"minus_{idx}", use_container_width=True):
                    data.loc[idx, "保有数"] = max(float(data.loc[idx, "保有数"]) - 0.5, 0)
                    save_data(data)
                    st.rerun()

            with b3:
                pending_key = f"pending_delete_{idx}"

                if st.session_state.get(pending_key):
                    # 確認中: 本当に削除 / キャンセル を並べて表示
                    ca, cb = st.columns(2)
                    with ca:
                        if st.button("本当に削除", key=f"confirm_yes_{idx}", use_container_width=True, type="primary"):
                            data = data.drop(index=idx)
                            save_data(data)
                            st.session_state.pop(pending_key, None)
                            st.success("削除しました")
                            st.rerun()
                    with cb:
                        if st.button("キャンセル", key=f"confirm_no_{idx}", use_container_width=True):
                            st.session_state.pop(pending_key, None)
                            st.rerun()
                else:
                    # 通常: 削除ボタン
                    if st.button(f"削除 {row['No']}", key=f"delete_{idx}", use_container_width=True):
                        st.session_state[pending_key] = True
                        st.rerun()

with right:
    st.subheader("保有カラー一覧")

    if len(owned) == 0:
        st.info("保有カラーなし")
    else:
        for _, row in owned.iterrows():
            display_hex = row["HEX"] if is_valid_hex(row["HEX"]) else "#999999"
            st.markdown(
                f"""
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                    <div style="
                        width:28px;
                        height:28px;
                        background-color:{display_hex};
                        border:1px solid #555;
                    "></div>
                    <div>{row['No']}　{row['名称']}　{row['保有数']}個</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.divider()
        st.metric("保有色数", len(owned))
        st.metric("保有数量", owned["保有数"].sum())

st.divider()

# ── 直接テーブル編集 ──────────────────────────────────────────

st.subheader("直接テーブル編集")

edited_data = st.data_editor(
    data,
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "得意先": st.column_config.SelectboxColumn("得意先", options=CUSTOMERS),
        "種類": st.column_config.SelectboxColumn("種類", options=TYPES),
        "HEX": st.column_config.TextColumn("HEX"),
        "保有数": st.column_config.NumberColumn("保有数", min_value=0.0, max_value=50.0, step=0.5),
    }
)

if st.button("テーブル編集を保存", use_container_width=True):
    save_data(edited_data)
    st.success("Googleスプレッドシートに保存しました")
    st.rerun()
