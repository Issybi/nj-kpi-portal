import streamlit as st
import pandas as pd
import requests
import io
import re

st.set_page_config(
    page_title="NJ7 Warehouse Performance Portal",
    page_icon="📊",
    layout="wide"
)

SPREADSHEET_ID = "1NOLL3GNkIzBIYHIEwV6D55kJ6vsixkSBFj0LVjuTkvI"

@st.cache_data(ttl=5)
def load_users_realtime(spreadsheet_id):
    try:
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet=KPI%20checking%20portal%20AC"
        df = pd.read_csv(url, dtype=str)
        df.columns = [str(c).strip().lower() for c in df.columns]
        return df
    except Exception as e:
        return None

@st.cache_data(ttl=5)
def load_config_data(spreadsheet_id):
    try:
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet=KPI"
        df = pd.read_csv(url, dtype=str)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        return None

def convert_drive_url(url_cell_content):
    if not url_cell_content or str(url_cell_content).lower() == "nan":
        return ""
    content = str(url_cell_content).strip()
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', content)
    if match:
        return f"https://docs.google.com/uc?export=download&id={match.group(1)}"
    match_id = re.search(r'id=([a-zA-Z0-9_-]+)', content)
    if match_id:
        return f"https://docs.google.com/uc?export=download&id={match_id.group(1)}"
    return content

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None

st.title("📊 NJ7 Warehouse Performance Portal")
st.markdown("---")

users_df = load_users_realtime(SPREADSHEET_ID)
config_df = load_config_data(SPREADSHEET_ID)

if users_df is None or users_df.empty:
    st.error("⚠️ 无法加载账号配置表")
elif config_df is None or config_df.empty:
    st.error("⚠️ 无法加载月份配置表")
else:
    st.sidebar.header("🔐 Employee Portal")
    
    valid_config = config_df.dropna(subset=[config_df.columns[0]])
    months = valid_config.iloc[:, 0].dropna().tolist()
    
    if not months:
        st.sidebar.warning("KPI 表的 A 列没有找到月份数据。")
    else:
        selected_month = st.sidebar.selectbox("Select Month / 选择月份", months)
        
        link_val = ""
        for idx, val in enumerate(valid_config.iloc[:, 0].astype(str)):
            if str(selected_month).strip() in val.strip():
                if len(valid_config.columns) > 2:
                    link_val = str(valid_config.iloc[idx, 2]).strip()
                break
        if (not link_val or link_val.lower() == "nan") and not valid_config.empty:
            if len(valid_config.columns) > 2:
                link_val = str(valid_config.iloc[-1, 2]).strip()

        if not st.session_state.logged_in:
            with st.sidebar.form("login_form"):
                st.subheader("Login / 登录")
                input_name = st.text_input("Name / 名字 (A列标准名)").strip()
                input_pw = st.text_input("Password / 密码", type="password").strip()
                input_role = st.selectbox("Role / 职位选择", ["driver", "scanner"])
                submit_btn = st.form_submit_button("Login / 登录")
                
                if submit_btn:
                    name_col = "name" if "name" in users_df.columns else users_df.columns[0]
                    pw_col = "pw" if "pw" in users_df.columns else users_df.columns[1]
                    type_col = "type" if "type" in users_df.columns else users_df.columns[2]
                    
                    match_rows = users_df[
                        (users_df[name_col].fillna("").astype(str).str.strip().str.lower() == input_name.lower()) &
                        (users_df[pw_col].fillna("").astype(str).str.strip() == input_pw) &
                        (users_df[type_col].fillna("").astype(str).str.strip().str.lower() == input_role.lower())
                    ]
                    
                    if not match_rows.empty:
                        user_record = match_rows.iloc[0]
                        st.session_state.logged_in = True
                        st.session_state.user_info = user_record.to_dict()
                        st.session_state.selected_role = input_role
                        st.rerun()
                    else:
                        st.error("Invalid Name, Password or Role")
        else:
            user_info = st.session_state.user_info
            std_name_key = next((c for c in user_info.keys() if c.lower() == "name"), list(user_info.keys())[0])
            standard_name = str(user_info.get(std_name_key, "")).strip()
            user_role = st.session_state.get("selected_role", "driver").lower()
            
            allowed_names = set()
            for col_key in ["name", "name2", "name3"]:
                matched_key = next((c for c in user_info.keys() if c.lower() == col_key), None)
                if matched_key:
                    val = str(user_info.get(matched_key, "")).strip().lower()
                    if val and val != "nan":
                        allowed_names.add(val)
            if not allowed_names:
                allowed_names.add(standard_name.lower())

            st.sidebar.success(f"Welcome, {standard_name}!\nRole: {user_role.upper()}")
            
            if st.sidebar.button("Log out / 登出"):
                st.session_state.logged_in = False
                st.session_state.user_info = None
                st.rerun()

            target_url = convert_drive_url(link_val)

            if target_url:
                try:
                    res = requests.get(target_url, timeout=20)
                    if res.status_code == 200:
                        excel_file = pd.ExcelFile(io.BytesIO(res.content))
                        sheet_names = excel_file.sheet_names
                        
                        if user_role == "scanner":
                            # Scanner 逻辑保持原样
                            st.subheader(f"📋 Scanner Performance - {standard_name}")
                            scan_sheet = next((s for s in sheet_names if "scan" in s.lower() and s.lower() != "scantime"), sheet_names[0])
                            st.dataframe(excel_file.parse(scan_sheet).head(45))
                        else:
                            # Driver 调试透视面板
                            st.subheader(f"🚚 Driver Debug Panel - {standard_name}")
                            st.info(f"当前识别的允许匹配名字库 (Allowed Names): `{allowed_names}`")
                            
                            st.markdown("### 1. 检查 Summary 表格原始数据的前 15 行：")
                            sum_sheet = next((s for s in sheet_names if "summary" in s.lower()), sheet_names[0])
                            df_sum_raw = excel_file.parse(sum_sheet)
                            st.dataframe(df_sum_raw.head(15))
                            
                            st.markdown("### 2. 当前 Excel 文件的所有分页名称列表：")
                            st.write(sheet_names)
                            
                            st.markdown("### 3. 专属 Picking / Putaway 分页排查：")
                            for s in sheet_names:
                                for name in allowed_names:
                                    if name in s.lower():
                                        st.success(f"找到匹配分页 -> {s}")
                    else:
                        st.error("下载文件失败。")
                except Exception as e:
                    st.error(f"出错: {e}")