import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="塗料在庫管理", layout="wide")
st.title("塗料在庫管理")

STOCK_FILE = "paint_stock.csv"
COLOR_FILE = "nittoko_colors.csv"

if os.path.exists(COLOR_FILE):
    color_df = pd.read_csv(COLOR_FILE)
else:
    color_df = pd.DataFrame(columns=["日塗工番号", "色名", "HEX"])

if os.path.exists(STOCK_FILE):
    data = pd.read_csv(STOCK_FILE)
else:
    data = pd.DataFrame(columns=["会社", "シリーズ", "No", "名称", "HEX", "保有数"])

company_colors = {
    "日塗工": "#dbeafe",
    "アクリジョン": "#dcfce7",
    "タミヤ": "#fef3c7",
    "ガイア": "#fce7f3",
    "その他": "#e5e7eb",
}

def can_display(qty):
    qty = float(qty)
    full = int(qty)
    half = qty - full >= 0.5
    cans = ""
    for i in range(5):
        if i < full:
            cans += "🟦"
        elif i == full and half:
            cans += "◧"
        else:
            cans += "⬜"
    return cans

st.subheader("在庫入力")

col1, col2, col3 = st.columns(3)

with col1:
    company = st.selectbox("会社", ["日塗工", "アクリジョン", "タミヤ", "ガイア", "その他"])
    series = st.text_input("シリーズ", value="")

with col2:
    number = st.text_input("No / 色番号")
    name = st.text_input("名称")

# 日塗工CSVから色を探す
match = color_df[color_df["日塗工番号"] == number]

if not match.empty:
    auto_hex = match.iloc[0]["HEX"]
    auto_name = match.iloc[0]["色名"]
    st.success(f"{number} の色を自動表示しました")
else:
    auto_hex = "#999999"
    auto_name = name
    if number:
        st.warning(f"{number} は nittoko_colors.csv にありません")

with col3:
    hex_color = st.color_picker("色", auto_hex)
    stock = st.number_input("保有数", min_value=0.0, max_value=5.0, step=0.5)

if name == "" and not match.empty:
    name = number

if st.button("追加して保存"):
    new_row = pd.DataFrame(
        [[company, series, number, name, hex_color, stock]],
        columns=["会社", "シリーズ", "No", "名称", "HEX", "保有数"]
    )
    data = pd.concat([data, new_row], ignore_index=True)
    data.to_csv(STOCK_FILE, index=False)
    st.success("保存しました")
    st.rerun()

st.divider()

left, right = st.columns([2, 1])

with left:
    st.subheader("保有リスト")

    if len(data) == 0:
        st.info("まだ在庫データがありません")
    else:
        for idx, row in data.iterrows():
            bg = company_colors.get(row["会社"], "#e5e7eb")
            st.markdown(
                f"""
                <div style="background-color:{bg}; padding:12px; border-radius:10px; margin-bottom:8px; border:1px solid #ccc;">
                    <div style="display:flex; align-items:center; gap:12px;">
                        <div style="width:44px; height:44px; background-color:{row['HEX']}; border:1px solid #555; border-radius:6px;"></div>
                        <div style="flex:1;">
                            <b>{row['会社']} / {row['シリーズ']}</b><br>
                            <span style="font-size:20px;">{row['No']}　{row['名称']}</span><br>
                            <span style="font-size:24px;">{can_display(row['保有数'])}</span>
                            <span>　{row['保有数']}缶</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

with right:
    st.subheader("保有カラー一覧")

    if len(data) > 0:
        owned = data[data["保有数"] > 0]

        for _, row in owned.iterrows():
            st.markdown(
                f"""
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
                    <div style="width:24px; height:24px; background-color:{row['HEX']}; border:1px solid #555;"></div>
                    <div>{row['No']}　{row['名称']}　{row['保有数']}缶</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.divider()
        st.metric("保有色数", len(owned))
        st.metric("保有缶数", owned["保有数"].sum())

st.divider()
st.subheader("CSVデータ")
st.dataframe(data, use_container_width=True)
