import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="塗料在庫管理", layout="wide")

# ===== Google接続 =====
scope = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file("cred.json", scopes=scope)
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
        ["BN03","ベースレッド","#C00000","ベースカラー",12],
        ["BN04","ベースイエロー","#FFD400","ベースカラー",8],
    ]
    sheet.update("A1", init)
    data = sheet.get_all_records()

df = pd.DataFrame(data)

st.title("塗料在庫管理（Google連動）")

menu = st.sidebar.radio("メニュー", ["在庫確認", "在庫更新"])

# ===== 在庫確認 =====
if menu == "在庫確認":
    def color_box(c):
        return f'<div style="width:40px;height:20px;background:{c};border:1px solid #555;"></div>'

    df["色見本"] = df["色"].apply(color_box)

    st.markdown(
        df[["No","色見本","名称","分類","在庫"]]
        .to_html(escape=False, index=False),
        unsafe_allow_html=True
    )

# ===== 在庫更新 =====
if menu == "在庫更新":
    selected = st.selectbox("選択", df["No"] + " - " + df["名称"])
    row = df[df["No"] == selected.split(" - ")[0]].iloc[0]

    st.write(f"現在在庫：{row['在庫']}")

    add = st.number_input("増減（+入庫 / -出庫）", value=0)

    if st.button("更新"):
        new = int(row["在庫"]) + add

        # シート更新
        cell = sheet.find(row["No"])
        sheet.update_cell(cell.row, 5, new)

        st.success("更新しました")
        st.experimental_rerun()
