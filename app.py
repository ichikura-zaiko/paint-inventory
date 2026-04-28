import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="塗料在庫管理", layout="wide")

# ===== Google接続 =====
scope = ["https://www.googleapis.com/auth/spreadsheets"]

creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"],
    scopes=scope
)

client = gspread.authorize(creds)

# スプレッドシート開く
sheet = client.open("inventory").sheet1

# データ取得
data = sheet.get_all_records()

# 初回（空なら初期データ作成）
if len(data) == 0:
    init = [
        ["No","名称","色","分類","在庫"],
        ["BN01","ベースホワイト","#FFFFFF","ベースカラー",30],
        ["BN02","ベースグレー","#888888","ベースカラー",31],
        ["BN03","ベースレッド","#CC0000","ベースカラー",12],
        ["BN04","ベースイエロー","#FFD400","ベースカラー",8],
    ]
    sheet.update("A1", init)
    data = sheet.get_all_records()

df = pd.DataFrame(data)

st.title("塗料在庫管理（Google連動）")

menu = st.sidebar.radio("メニュー", ["在庫確認", "在庫更新"])

# ===== 在庫確認 =====
if menu == "在庫確認":
    st.subheader("在庫一覧")

    def color_box(c):
        return f'<div style="width:40px;height:20px;background:{c};border:1px solid #555;"></div>'

    df["色表示"] = df["色"].apply(color_box)

    st.write(df.to_html(escape=False), unsafe_allow_html=True)

# ===== 在庫更新 =====
if menu == "在庫更新":
    st.subheader("在庫更新")

    name = st.selectbox("塗料選択", df["名称"])
    qty = st.number_input("数量変更", step=1)

    if st.button("更新"):
        row = df[df["名称"] == name].index[0] + 2
        current = df.loc[df["名称"] == name, "在庫"].values[0]
        new_val = current + qty
        sheet.update_cell(row, 5, new_val)
        st.success("更新しました")
