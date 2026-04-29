import streamlit as st
import pandas as pd
import os

st.title("塗料在庫管理")

CSV_FILE = "paint_stock.csv"

# 日塗工番号と色の対応表（仮）
color_map = {
    "N-95": "#F5F5F5",
    "N-90": "#E8E8E8",
    "N-85": "#D9D9D9",
    "N-80": "#CCCCCC",
    "N-70": "#B3B3B3",
    "N-60": "#999999",
    "N-50": "#808080",
    "N-40": "#666666",
    "N-30": "#4D4D4D",
    "N-20": "#333333",
    "N-10": "#1A1A1A",
}

# 保存データを読み込み
if os.path.exists(CSV_FILE):
    data = pd.read_csv(CSV_FILE)
else:
    data = pd.DataFrame(columns=["日塗工番号", "色名", "在庫数", "色コード"])

st.subheader("在庫入力")

nittoko_no = st.text_input("日塗工番号（例：N-95）")
color_name = st.text_input("色名")
stock = st.number_input("在庫数", min_value=0)

# 色番号から色を自動取得
if nittoko_no in color_map:
    default_color = color_map[nittoko_no]
    st.success(f"{nittoko_no} の色を自動表示しました")
else:
    default_color = "#000000"
    if nittoko_no:
        st.warning("この日塗工番号はまだ登録されていません。手動で色を選んでください。")

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
