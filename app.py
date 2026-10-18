import streamlit as st
import pandas as pd
import time
import requests
import io

# 页面基本设置
st.set_page_config(
    page_title="NJ7 Warehouse Performance Portal",
    page_icon="📊",
    layout="wide"
)

SPREADSHEET_ID = "1NOLL3GNkIzBIYHIEwV6D55kJ6vsixkSBFj0LVjuTkvI"

@st.cache_data(ttl=10)
def load_users_realtime(spreadsheet_id):
    try:
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet=KPI%20checking%20portal%20AC"
        df = pd.read_csv(url, dtype=str)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        return None

@st.cache_data(ttl=10)
def load_config_data(spreadsheet_id):
    try:
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet=KPI"
        df = pd.read_csv(url)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        return None

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None

st.title("📊 NJ7 Warehouse Performance Portal")
st.caption("Note: Read-only access to individual performance metrics.")
st.markdown("---")

users_df = load_users_realtime(SPREADSHEET_ID)
config_df = load_config_data(SPREADSHEET_ID)

if users_df is not None and config_df is not None:
    st.sidebar.header("🔐 Employee Portal")
    
    valid_config = config_df.dropna(subset=["Month_Label"])
    months = valid_config["Month_Label"].tolist()
    selected_month = st.sidebar.selectbox("Select Month / 选择月份", months)
    
    row = valid_config[valid_config["Month_Label"] == selected_month]
    link_val = ""
    if not row.empty:
        cols = config_df.columns
        if len(cols) > 2:
            val_c = str(row.iloc[0, 2]).strip()
            if "http" in val_c:
                link_val = val_c
        if not link_val:
            link_cols = [c for c in cols if any(k in c.lower() for k in ["link", "url", "file", "direct"])]
            for c in link_cols:
                v = str(row[c].values[0]).strip()
                if "http" in v:
                    link_val = v
                    break

    if not st.session_state.logged_in:
        with st.sidebar.form("login_form"):
            st.subheader("Login / 登录")
            input_name = st.text_input("Name / 名字 (A列标准名)").strip()
            input_pw = st.text_input("Password / 密码", type="password").strip()
            input_role = st.selectbox("Role / 职位选择", ["driver", "scanner"])
            submit_btn = st.form_submit_button("Login / 登录")
            
            if submit_btn:
                # 登录时支持在 A/C/D 列（name, name2, name3）中匹配输入的名字
                match_rows = users_df[
                    (users_df["pw"].fillna("").astype(str).str.strip() == input_pw) &
                    (
                        (users_df["name"].fillna("").astype(str).str.strip().str.lower() == input_name.lower()) |
                        (users_df["name2"].fillna("").astype(str).str.strip().str.lower() == input_name.lower()) |
                        (users_df["name3"].fillna("").astype(str).str.strip().str.lower() == input_name.lower())
                    ) &
                    (users_df["type"].fillna("").astype(str).str.strip().str.lower() == input_role.lower())
                ]
                
                if not match_rows.empty:
                    user_record = match_rows.iloc[0]
                    st.session_state.logged_in = True
                    st.session_state.user_info = user_record.to_dict()
                    st.session_state.selected_role = input_role
                    st.session_state.searched_name = input_name
                    st.rerun()
                else:
                    st.error("Invalid Name, Password or Role / 姓名、密码或职位错误")
    else:
        user_info = st.session_state.user_info
        standard_name = str(user_info.get("name", "")).strip() # A列标准分页名
        user_role = st.session_state.get("selected_role", str(user_info.get("type", "driver")).strip()).lower()
        
        # 收集当前账号的所有名字（name, name2, name3）
        allowed_names = set()
        for col_key in ["name", "name2", "name3"]:
            val = str(user_info.get(col_key, "")).strip().lower()
            if val and val != "nan":
                allowed_names.add(val)
        if not allowed_names:
            allowed_names.add(standard_name.lower())

        st.sidebar.success(f"Welcome, {standard_name}!\nRole: {user_role.upper()}")
        
        if st.sidebar.button("Log out / 登出"):
            st.session_state.logged_in = False
            st.session_state.user_info = None
            st.rerun()

        if link_val and link_val != "nan":
            target_url = link_val
            if "drive.google.com" in target_url and "export=download" not in target_url:
                if "/file/d/" in target_url:
                    file_id = target_url.split("/file/d/")[1].split("/")[0]
                    target_url = f"https://docs.google.com/uc?export=download&id={file_id}"
            
            with st.spinner(f"正在加载 {selected_month} 数据..."):
                try:
                    res = requests.get(target_url)
                    excel_file = pd.ExcelFile(io.BytesIO(res.content))
                    sheet_names = excel_file.sheet_names
                except Exception as e:
                    excel_file = None
                    sheet_names = []

            if excel_file is not None:
                def filter_by_allowed_names(df):
                    if df is None or df.empty:
                        return pd.DataFrame()
                    mask = pd.Series(False, index=df.index)
                    for col in df.columns:
                        col_series = df[col].fillna("").astype(str).str.strip().str.lower()
                        for name in allowed_names:
                            mask = mask | (col_series == name)
                    return df[mask]

                def filter_col_b_by_allowed_names(df):
                    if df is None or df.empty:
                        return pd.DataFrame()
                    if len(df.columns) < 2:
                        return pd.DataFrame()
                    col_b_name = df.columns[1]
                    col_b_series = df[col_b_name].fillna("").astype(str).str.strip().str.lower()
                    mask = pd.Series(False, index=df.index)
                    for name in allowed_names:
                        mask = mask | (col_b_series == name)
                    return df[mask]

                def find_sheet(kw):
                    matches = [s for s in sheet_names if kw.lower() in s.lower()]
                    return matches[0] if matches else None

                def find_sheet_by_exact(prefix):
                    for s in sheet_names:
                        s_lower = s.lower()
                        if prefix.lower() in s_lower:
                            for name in allowed_names:
                                if name in s_lower:
                                    return s
                    return None

                def find_scan_sheet():
                    """专门匹配 Scanner 专属分页（支持 'Lucia-scan'、'lucia - scan' 等命名）"""
                    for s in sheet_names:
                        s_lower = s.lower()
                        if "scan" in s_lower:
                            for name in allowed_names:
                                if name in s_lower:
                                    return s
                    return None

                # ==========================
                # 1. SCANNER 岗位逻辑
                # ==========================
                if user_role == "scanner":
                    st.subheader(f"📋 Scanner Performance ({selected_month}) - {standard_name}")
                    scan_sheet_name = find_scan_sheet()
                    
                    if scan_sheet_name:
                        df_scan = excel_file.parse(scan_sheet_name)
                        df_scan.columns = [str(c).strip() for c in df_scan.columns]
                        st.dataframe(df_scan, use_container_width=True)
                    else:
                        # 兜底逻辑：如果没找到专属分页，尝试读总 scan 表并过滤
                        target_scan_sheet = find_sheet("scan")
                        if target_scan_sheet:
                            df_scan = excel_file.parse(target_scan_sheet)
                            df_