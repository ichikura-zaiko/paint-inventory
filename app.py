import streamlit as st
import pandas as pd

st.title("塗料在庫管理")

# 初期データ
if "data" not in st.session_state:
    st.session_state.data = pd.DataFrame(columns=["色名", "在庫数", "色コード"])

# 入力フォーム
st.subheader("在庫入力")

color_name = st.text_input("色名")
stock = st.number_input("在庫数", min_value=0)
color_code = st.color_picker("色を選択")

if st.button("追加"):
    new_data = pd.DataFrame([[color_name, stock, color_code]],
                            columns=["色名", "在庫数", "色コード"])
    st.session_state.data = pd.concat([st.session_state.data, new_data], ignore_index=True)

# 一覧表示
st.subheader("在庫一覧")

for i, row in st.session_state.data.iterrows():
    st.markdown(f"### {row['色名']}")
    st.markdown(f"在庫数: {row['在庫数']}")
    st.markdown(f"<div style='width:100px;height:50px;background-color:{row['色コード']}'></div>", unsafe_allow_html=True)
