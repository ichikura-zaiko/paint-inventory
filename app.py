import streamlit as st
import pandas as pd
import os
import unicodedata

st.set_page_config(page_title="塗料在庫管理", layout="wide")
st.title("塗料在庫管理")

STOCK_FILE = "paint_stock.csv"
COLOR_FILE = "nittoko_colors.csv"

def clean_code(value):
    value = str(value).strip()
    value = unicodedata.normalize("NFKC", value)
    return value.upper()

if os.path.exists(COLOR_FILE):
    color_df = pd.read_csv(COLOR_FILE)
    color_df.columns = color_df.columns.str.strip()
else:
    color_df = pd.DataFrame(columns=["日塗工番号", "色名", "HEX"])

for col in ["日塗工番号", "色名", "HEX"]:
    if col not in color_df.columns:
        color_df[col] = ""

color_df["検索番号"] = color_df["日塗工番号"].apply(clean_code)

if os.path.exists(STOCK_FILE):
    data = pd.read_csv(STOCK_FILE)
else:
    data = pd.DataFrame(columns=["会社", "シリーズ", "No", "名称", "HEX", "保有数"])

for col in ["会社", "シリーズ", "No", "名称", "HEX", "保有数"]:
    if col not in data.columns:
        data[col] = ""

data["保有数"] = pd.to_numeric(data["保有数"], errors="coerce").fillna(0)

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
    series = st.text_input("シリーズ")

with col2:
    number = st.text_input("No / 色番号")
    number_clean = clean_code(number)
    name_input = st.text_input("名称")

match = color_df[color_df["検索番号"] == number_clean] if number_clean else pd.DataFrame()

if not match.empty:
    auto_hex = str(match.iloc[0]["HEX"]).strip()
    auto_name = str(match.iloc[0]["色名"]).strip()

    if name_input == "":
        name = auto_name
    else:
        name = name_input

    st.success(f"{number_clean} の色を自動表示しました")
else:
    auto_hex = "#999999"
    name = name_input if name_input else number_clean

    if number_clean:
        st.warning(f"{number_clean} は nittoko_colors.csv にありません")

with col3:
    hex_color = st.color_picker("色", auto_hex)
    stock = st.number_input("保有数", min_value=0.0, max_value=5.0, step=0.5)

if st.button("追加 / 更新して保存"):
    if number_clean == "":
        st.error("No / 色番号を入力してください")
    else:
        if series == "":
            series = number_clean

        new_row = {
            "会社": company,
            "シリーズ": series,
            "No": number_clean,
            "名称": name,
            "HEX": hex_color,
            "保有数": stock,
        }

        data["検索No"] = data["No"].apply(clean_code)

        if number_clean in data["検索No"].values:
            data.loc[data["検索No"] == number_clean, ["会社", "シリーズ", "No", "名称", "HEX", "保有数"]] = [
                company, series, number_clean, name, hex_color, stock
            ]
            st.success("既存データを更新しました")
        else:
            data = pd.concat([data.drop(columns=["検索No"], errors="ignore"), pd.DataFrame([new_row])], ignore_index=True)
            st.success("新規追加しました")

        data = data.drop(columns=["検索No"], errors="ignore")
        data.to_csv(STOCK_FILE, index=False)
        st.rerun()

st.divider()

left, right = st.columns([2, 1])

owned = data[data["保有数"] > 0].copy()

with left:
    st.subheader("保有リスト")

    if len(owned) == 0:
        st.info("まだ在庫データがありません")
    else:
        for _, row in owned.iterrows():
            bg = company_colors.get(row["会社"], "#e5e7eb")

            st.markdown(
                f"""
                <div style="
                    background-color:{bg};
                    padding:14px;
                    border-radius:10px;
                    margin-bottom:10px;
                    border:1px solid #ccc;
                ">
                    <div style="display:flex; align-items:center; gap:14px;">
                        <div style="
                            width:52px;
                            height:52px;
                            background-color:{row['HEX']};
                            border:1px solid #555;
                            border-radius:8px;
                        "></div>
                        <div style="flex:1;">
                            <b>{row['会社']} / {row['シリーズ']}</b><br>
                            <span style="font-size:22px;">{row['No']}　{row['名称']}</span><br>
                            <span style="font-size:26px;">{can_display(row['保有数'])}</span>
                            <span style="font-size:18px;">　{row['保有数']}缶</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

with right:
    st.subheader("保有カラー一覧")

    if len(owned) == 0:
        st.info("保有カラーなし")
    else:
        for _, row in owned.iterrows():
            st.markdown(
                f"""
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                    <div style="
                        width:26px;
                        height:26px;
                        background-color:{row['HEX']};
                        border:1px solid #555;
                    "></div>
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
