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


# 色マスター読み込み
if os.path.exists(COLOR_FILE):
    color_df = pd.read_csv(COLOR_FILE)
    color_df.columns = color_df.columns.str.strip()
else:
    color_df = pd.DataFrame(columns=["日塗工番号", "色名", "HEX"])

for col in ["日塗工番号", "色名", "HEX"]:
    if col not in color_df.columns:
        color_df[col] = ""

color_df["検索番号"] = color_df["日塗工番号"].apply(clean_code)

# 在庫データ読み込み
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
    "日本ペイント": "#fee2e2",
    "関西ペイント": "#ede9fe",
    "その他": "#e5e7eb",
}

st.markdown("""
<style>
.block-container {
    padding-top: 1rem;
    padding-bottom: 1rem;
}
button {
    min-height: 44px;
    font-size: 16px !important;
}
input {
    font-size: 18px !important;
}
@media (max-width: 768px) {
    .block-container {
        padding-left: 0.7rem;
        padding-right: 0.7rem;
    }
    h1 {
        font-size: 30px !important;
    }
    h2, h3 {
        font-size: 23px !important;
    }
}
</style>
""", unsafe_allow_html=True)

st.subheader("在庫入力")

col1, col2, col3 = st.columns(3)

with col1:
    company = st.selectbox(
        "会社",
        ["日塗工", "アクリジョン", "タミヤ", "ガイア", "日本ペイント", "関西ペイント", "その他"]
    )
    series = st.text_input("シリーズ")

with col2:
    number = st.text_input("No / 色番号")
    number_clean = clean_code(number)
    name_input = st.text_input("名称")

match = color_df[color_df["検索番号"] == number_clean] if number_clean else pd.DataFrame()

if not match.empty:
    auto_hex = str(match.iloc[0]["HEX"]).strip()
    auto_name = str(match.iloc[0]["色名"]).strip()
    name = auto_name if name_input == "" else name_input
    st.success(f"{number_clean} の色を自動表示しました")
else:
    auto_hex = "#999999"
    name = name_input if name_input else number_clean
    if number_clean:
        st.warning(f"{number_clean} は nittoko_colors.csv にありません")

with col3:
    hex_color = st.color_picker("色", auto_hex)
    stock = st.number_input("保有数", min_value=0.0, max_value=5.0, step=0.5)

if st.button("追加 / 更新して保存", use_container_width=True):
    if number_clean == "":
        st.error("No / 色番号を入力してください")
    else:
        if series == "":
            series = number_clean

        data["検索No"] = data["No"].apply(clean_code)

        if number_clean in data["検索No"].values:
            data.loc[data["検索No"] == number_clean, ["会社", "シリーズ", "No", "名称", "HEX", "保有数"]] = [
                company, series, number_clean, name, hex_color, stock
            ]
            st.success("既存データを更新しました")
        else:
            new_row = {
                "会社": company,
                "シリーズ": series,
                "No": number_clean,
                "名称": name,
                "HEX": hex_color,
                "保有数": stock,
            }
            data = pd.concat(
                [data.drop(columns=["検索No"], errors="ignore"), pd.DataFrame([new_row])],
                ignore_index=True
            )
            st.success("新規追加しました")

        data = data.drop(columns=["検索No"], errors="ignore")
        data.to_csv(STOCK_FILE, index=False)
        st.rerun()

st.divider()

st.subheader("検索・並び替え")

search_col, sort_col = st.columns([2, 1])

with search_col:
    search = st.text_input("色番号・名称・会社・シリーズで検索")

with sort_col:
    sort_mode = st.selectbox(
        "並び替え",
        ["色番号順", "在庫少ない順", "在庫多い順", "会社順", "シリーズ順"]
    )

owned = data[data["保有数"] > 0].copy()

if search:
    s = clean_code(search)
    owned = owned[
        owned["No"].astype(str).apply(clean_code).str.contains(s, na=False)
        | owned["名称"].astype(str).apply(clean_code).str.contains(s, na=False)
        | owned["会社"].astype(str).apply(clean_code).str.contains(s, na=False)
        | owned["シリーズ"].astype(str).apply(clean_code).str.contains(s, na=False)
    ]

if sort_mode == "色番号順":
    owned = owned.sort_values("No")
elif sort_mode == "在庫少ない順":
    owned = owned.sort_values("保有数")
elif sort_mode == "在庫多い順":
    owned = owned.sort_values("保有数", ascending=False)
elif sort_mode == "会社順":
    owned = owned.sort_values("会社")
elif sort_mode == "シリーズ順":
    owned = owned.sort_values("シリーズ")

left, right = st.columns([2, 1])

with left:
    st.subheader("保有リスト")

    if len(owned) == 0:
        st.info("該当する在庫データがありません")
    else:
        for idx, row in owned.iterrows():
            qty = float(row["保有数"])

            if qty <= 1:
                bg = "#fee2e2"
                alert_text = "⚠ 在庫少"
            elif qty <= 2:
                bg = "#fef3c7"
                alert_text = "注意"
            else:
                bg = company_colors.get(row["会社"], "#e5e7eb")
                alert_text = ""

            st.markdown(
                f"""
                <div style="
                    background-color:{bg};
                    padding:14px;
                    border-radius:12px;
                    margin-bottom:12px;
                    border:1px solid #ccc;
                ">
                    <div style="display:flex; align-items:center; gap:14px; flex-wrap:wrap;">
                        <div style="
                            width:58px;
                            height:58px;
                            background-color:{row['HEX']};
                            border:1px solid #555;
                            border-radius:8px;
                        "></div>
                        <div style="flex:1; min-width:220px;">
                            <b>{row['会社']} / {row['シリーズ']}</b><br>
                            <span style="font-size:22px;">{row['No']}　{row['名称']}</span><br>
                            <span style="font-size:28px;">{can_display(row['保有数'])}</span>
                            <span style="font-size:18px;">　{row['保有数']}缶</span>
                            <span style="font-size:18px; color:#b91c1c;">　{alert_text}</span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            c1, c2, c3 = st.columns([1, 1, 2])

            with c1:
                if st.button("＋0.5", key=f"plus_{idx}", use_container_width=True):
                    data.loc[idx, "保有数"] = min(float(data.loc[idx, "保有数"]) + 0.5, 5)
                    data.to_csv(STOCK_FILE, index=False)
                    st.rerun()

            with c2:
                if st.button("−0.5", key=f"minus_{idx}", use_container_width=True):
                    data.loc[idx, "保有数"] = max(float(data.loc[idx, "保有数"]) - 0.5, 0)
                    data.to_csv(STOCK_FILE, index=False)
                    st.rerun()

            with c3:
                if st.button(f"削除 {row['No']}", key=f"delete_{idx}", use_container_width=True):
                    data = data.drop(index=idx)
                    data.to_csv(STOCK_FILE, index=False)
                    st.rerun()

with right:
    st.subheader("保有カラー一覧")

    if len(owned) == 0:
        st.info("保有カラーなし")
    else:
        for _, row in owned.iterrows():
            qty = float(row["保有数"])
            alert = " ⚠️" if qty <= 1 else ""

            st.markdown(
                f"""
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                    <div style="
                        width:28px;
                        height:28px;
                        background-color:{row['HEX']};
                        border:1px solid #555;
                    "></div>
                    <div>{row['No']}　{row['名称']}　{row['保有数']}缶{alert}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.divider()
        st.metric("保有色数", len(owned))
        st.metric("保有缶数", owned["保有数"].sum())

        low_stock = owned[owned["保有数"] <= 1]
        if len(low_stock) > 0:
            st.warning(f"在庫少：{len(low_stock)}色あります")

st.divider()

st.subheader("CSVデータ")
st.dataframe(data, use_container_width=True)
