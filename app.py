import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(layout="wide")

# ===== Google Sheets 接続 =====
scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds_dict = st.secrets["gcp_service_account"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)

SPREADSHEET_ID = "1ydFNv3aDZb5x7JZoLFRpqSRWOnEZ93HsEjxSkrQLMgY"
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# ===== データ =====
def load_data():
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def save_data(df):
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

# ===== 視覚表示（1缶=1マス・最大5＋超過表示） =====
def can_display(qty):
    qty = float(qty)

    full = int(qty)
    half = (qty - full) >= 0.5

    display = ""

    # 最大5マス表示
    for i in range(5):
        if i < full:
            display += "🟦"
        elif i == full and half:
            display += "◧"
        else:
            display += "⬜"

    # 5個以上は追加表示
    if qty > 5:
        extra = qty - 5
        display += f" +{extra:g}"

    return display

# ===== UI =====
st.title("塗料在庫管理")

st.subheader("在庫入力")

col1, col2, col3 = st.columns(3)

with col1:
    company = st.selectbox("得意先", ["自社"])
    kind = st.selectbox("種類", ["アクリル", "メラミン", "粉体"])

with col2:
    number = st.text_input("No / 色番号")
    name = st.text_input("名称")

with col3:
    qty = st.number_input("保有数", min_value=0.0, max_value=50.0, step=0.5)

if st.button("追加 / 更新して保存"):

    df = load_data()

    new_row = {
        "得意先": company,
        "種類": kind,
        "No": number,
        "名称": name,
        "HEX": "#999999",
        "保有数": qty
    }

    if len(df) == 0:
        df = pd.DataFrame([new_row])
    else:
        mask = df["No"] == number
        if mask.any():
            df.loc[mask, "保有数"] = qty
        else:
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    save_data(df)
    st.success("保存しました")
    st.rerun()

# ===== 表示 =====
st.subheader("保有リスト")

df = load_data()

if len(df) == 0:
    st.info("データなし")
else:
    for i, row in df.iterrows():
        st.write(f"### {row['No']} / {row['名称']}")
        st.write(f"{row['得意先']} / {row['種類']}")
        st.write(can_display(row["保有数"]))
        st.write(f"{row['保有数']}個")

        col1, col2, col3 = st.columns(3)

        if col1.button(f"+0.5_{i}"):
            df.at[i, "保有数"] += 0.5
            save_data(df)
            st.rerun()

        if col2.button(f"-0.5_{i}"):
            df.at[i, "保有数"] -= 0.5
            if df.at[i, "保有数"] < 0:
                df.at[i, "保有数"] = 0
            save_data(df)
            st.rerun()

        confirm = col3.checkbox(f"削除確認_{i}")
        if confirm and col3.button(f"削除_{i}"):
            df = df.drop(i)
            save_data(df)
            st.rerun()
