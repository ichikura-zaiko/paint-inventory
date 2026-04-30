import streamlit as st
import pandas as pd
import os

st.title("塗料在庫管理")

CSV_FILE = "paint_stock.csv"
COLOR_FILE = "nittoko_colors.csv"

# 日塗工カラーCSV読み込み
if os.path.exists(COLOR_FILE):
    color_df = pd.read_csv(COLOR_FILE)
else:
    color_df = pd.DataFrame(columns=["日塗工番号", "色名", "HEX"])

# 在庫データ読み込み
if os.path.exists(CSV_FILE):
    data = pd.read_csv(CSV_FILE)
else:
    data = pd.DataFrame(columns=["日塗工番号", "色名", "在庫数", "色コード"])

st.subheader("在庫入力")

nittoko_no = st.text_input("日塗工番号（例：P15-60V）")
color_name = st.text_input("色名")
stock = st.number_input("在庫数", min_value=0)

# CSVから色取得
match = color_df[color_df["日塗工番号"] == nittoko_no]

if not match.empty:
    default_color = match.iloc[0]["HEX"]
    st.success(f"{nittoko_no} の色を自動表示しました")
else:
    default_color = "#000000"
    if nittoko_no:
        st.warning("この日塗工番号はCSVにありません")

color_code = st.color_picker("色を選択", default_color)

if st.button("追加して保存"):
    new_data = pd.DataFrame(
        [[nittoko_no, color_name, stock, color_code]],
        columns=["日塗工番号", "色名", "在庫数", "色コード"]
    )

    data = pd.concat([data, new_data], ignore_index=True)
    data.to_csv(CSV_FILE, index=False)

    st.success("保存しました")

st.subheader("在庫一覧")

if len(data) == 0:
    st.info("まだ在庫データがありません")
else:
    for i, row in data.iterrows():
        st.markdown(f"### {row['日塗工番号']}　{row['色名']}")
        st.markdown(f"在庫数: {row['在庫数']}")
        st.markdown(
            f"<div style='width:120px;height:50px;background-color:{row['色コード']};border:1px solid #999;'></div>",
            unsafe_allow_html=True
        )
        st.divider()

st.subheader("CSVデータ")
st.dataframe(data)
