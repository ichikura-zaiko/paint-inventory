import streamlit as st
import pandas as pd
import os
import unicodedata

st.set_page_config(page_title="塗料在庫管理", layout="wide")
st.title("塗料在庫管理")

STOCK_FILE = "paint_stock.csv"
COLOR_FILE = "nittoko_colors.csv"

CUSTOMERS = ["自社", "東洋紡エンジニアリング", "その他"]
TYPES = ["アクリル", "メラミン", "粉体", "ウレタン", "エポキシ", "ラッカー", "その他"]

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
        if i < full / 10:
            cans += "🟦"
        elif i == int(full / 10) and qty % 10 >= 5:
            cans += "◧"
        else:
            cans += "⬜"
    return cans

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
    data = pd.DataFrame(columns=["得意先", "種類", "No", "名称", "HEX", "保有数"])

# 旧データ対応
if "会社" in data.columns:
    data = data.rename(columns={"会社": "得意先"})
if "シリーズ" in data.columns:
    data = data.rename(columns={"シリーズ": "種類"})

for col in ["得意先", "種類", "No", "名称", "HEX", "保有数"]:
    if col not in data.columns:
        data[col] = ""

data["保有数"] = pd.to_numeric(data["保有数"], errors="coerce").fillna(0)

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
            data.loc[data["検索No"] == number_clean, ["得意先", "種類", "No", "名称", "HEX", "保有数"]] = [
                customer, paint_type, number_clean, name, hex_color, stock
            ]
            st.success("既存データを更新しました")
        else:
            new_row = {
                "得意先": customer,
                "種類": paint_type,
                "No": number_clean,
                "名称": name,
                "HEX": hex_color,
                "保有数": stock,
            }
            data = pd.concat([data.drop(columns=["検索No"], errors="ignore"), pd.DataFrame([new_row])], ignore_index=True)
            st.success("新規追加しました")

        data = data.drop(columns=["検索No"], errors="ignore")
        data.to_csv(STOCK_FILE, index=False)
        st.rerun()

st.divider()

st.subheader("検索・並び替え")

search_col, sort_col = st.columns([2, 1])

with search_col:
    search = st.text_input("色番号・名称・得意先・種類で検索")

with sort_col:
    sort_mode = st.selectbox("並び替え", ["色番号順", "在庫少ない順", "在庫多い順", "得意先順", "種類順"])

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
elif sort_mode == "在庫少ない順":
    owned = owned.sort_values("保有数")
elif sort_mode == "在庫多い順":
    owned = owned.sort_values("保有数", ascending=False)
elif sort_mode == "得意先順":
    owned = owned.sort_values("得意先")
elif sort_mode == "種類順":
    owned = owned.sort_values("種類")

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
            elif qty <= 5:
                bg = "#fef3c7"
                alert_text = "注意"
            else:
                bg = "#dbeafe"
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
                            <b>{row['得意先']} / {row['種類']}</b><br>
                            <span style="font-size:22px;">{row['No']}　{row['名称']}</span><br>
                            <span style="font-size:28px;">{can_display(row['保有数'])}</span>
                            <span style="font-size:18px;">　{row['保有数']}個</span>
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
                    data.loc[idx, "保有数"] = min(float(data.loc[idx, "保有数"]) + 0.5, 50)
                    data.to_csv(STOCK_FILE, index=False)
                    st.rerun()

            with c2:
                if st.button("−0.5", key=f"minus_{idx}", use_container_width=True):
                    data.loc[idx, "保有数"] = max(float(data.loc[idx, "保有数"]) - 0.5, 0)
                    data.to_csv(STOCK_FILE, index=False)
                    st.rerun()

            with c3:
                confirm = st.checkbox(f"{row['No']} を削除確認", key=f"confirm_{idx}")
                if st.button(f"削除 {row['No']}", key=f"delete_{idx}", use_container_width=True):
                    if confirm:
                        data = data.drop(index=idx)
                        data.to_csv(STOCK_FILE, index=False)
                        st.success("削除しました")
                        st.rerun()
                    else:
                        st.warning("削除する場合は確認チェックを入れてください")

with right:
    st.subheader("保有カラー一覧")

    if len(owned) == 0:
        st.info("保有カラーなし")
    else:
        for _, row in owned.iterrows():
            alert = " ⚠️" if float(row["保有数"]) <= 1 else ""
            st.markdown(
                f"""
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                    <div style="
                        width:28px;
                        height:28px;
                        background-color:{row['HEX']};
                        border:1px solid #555;
                    "></div>
                    <div>{row['No']}　{row['名称']}　{row['保有数']}個{alert}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

        st.divider()
        st.metric("保有色数", len(owned))
        st.metric("保有数量", owned["保有数"].sum())

st.divider()

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
    edited_data.to_csv(STOCK_FILE, index=False)
    st.success("テーブル編集を保存しました")
    st.rerun()
