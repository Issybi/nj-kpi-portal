import streamlit as st
import pandas as pd
import requests
import io
import re

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
        st.error(f"无法加载用户账号表: {e}")
        return None

@st.cache_data(ttl=10)
def load_config_data(spreadsheet_id):
    try:
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet=KPI"
        df = pd.read_csv(url)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"无法加载月份配置表: {e}")
        return None

def convert_drive_url(url):
    """提取 Google Drive 文件 ID 并转换为直接下载链接"""
    if not url or str(url).lower() == "nan":
        return ""
    url = str(url).strip()
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match:
        file_id = match.group(1)
        return f"https://docs.google.com/uc?export=download&id={file_id}"
    match_id = re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if match_id:
        file_id = match_id.group(1)
        return f"https://docs.google.com/uc?export=download&id={file_id}"
    return url

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
        standard_name = str(user_info.get("name", "")).strip()
        user_role = st.session_state.get("selected_role", str(user_info.get("type", "driver")).strip()).lower()
        
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

        target_url = convert_drive_url(link_val)

        if target_url:
            excel_file = None
            sheet_names = []
            
            with st.spinner(f"正在加载 {selected_month} 的数据文件..."):
                try:
                    res = requests.get(target_url, timeout=15)
                    if res.status_code == 200:
                        excel_file = pd.ExcelFile(io.BytesIO(res.content))
                        sheet_names = excel_file.sheet_names
                    else:
                        st.error(f"下载文件失败，HTTP 状态码: {res.status_code}。请检查链接设置。")
                except Exception as e:
                    st.error(f"读取 Excel 文件时出错: {e}")

            if excel_file is not None and sheet_names:
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
                        target_scan_sheet = find_sheet("scan")
                        if target_scan_sheet:
                            df_scan = excel_file.parse(target_scan_sheet)
                            df_scan.columns = [str(c).strip() for c in df_scan.columns]
                            filtered_scan = filter_by_allowed_names(df_scan)
                            if not filtered_scan.empty:
                                st.dataframe(filtered_scan, use_container_width=True)
                            else:
                                st.warning(f"未找到属于 {standard_name} 的 Scanner 绩效记录。")
                        else:
                            st.warning("未找到 Scanner 绩效分页。")

                # ==========================
                # 2. DRIVER 岗位逻辑 (5个分页)
                # ==========================
                else:
                    st.subheader(f"🚚 Driver Performance Portal ({selected_month}) - {standard_name}")
                    
                    tab_summary, tab_error, tab_bonus, tab_picking, tab_putaway = st.tabs([
                        "1. Summary", 
                        "2. Error-OtherTasks", 
                        "3. Bonus", 
                        "4. Picking", 
                        "5. Putaway"
                    ])

                    # --- Tab 1: Summary (双保险解析，防止表头不匹配导致空白) ---
                    with tab_summary:
                        st.markdown("### Summary (个人绩效摘要)")
                        sum_sheet = find_sheet("summary") or sheet_names[0]
                        df_sum = pd.DataFrame()
                        try:
                            # 尝试带 header=6 解析
                            df_sum = excel_file.parse(sum_sheet, header=6)
                            df_sum.columns = [str(c).strip() for c in df_sum.columns]
                            filtered_sum = filter_by_allowed_names(df_sum)
                            if filtered_sum.empty:
                                # 如果 header=6 过滤不到，换默认表头再试一次
                                df_sum = excel_file.parse(sum_sheet)
                                df_sum.columns = [str(c).strip() for c in df_sum.columns]
                        except Exception:
                            df_sum = excel_file.parse(sum_sheet)
                            df_sum.columns = [str(c).strip() for c in df_sum.columns]
                        
                        filtered_sum = filter_by_allowed_names(df_sum)
                        if not filtered_sum.empty:
                            st.dataframe(filtered_sum, use_container_width=True)
                        else:
                            # 如果还是过滤不出来，把整个 Summary 表展现出来以便核对
                            st.info("未在 Summary 中直接精准匹配到名字，为您展示当前 Summary 表：")
                            st.dataframe(df_sum, use_container_width=True)

                    # --- Tab 2: Error-OtherTasks ---
                    with tab_error:
                        st.markdown("### Error & Other Tasks")
                        err_sheet = find_sheet("error") or find_sheet("other")
                        if err_sheet:
                            df_err = excel_file.parse(err_sheet)
                            df_err.columns = [str(c).strip() for c in df_err.columns]
                            filtered_err = filter_col_b_by_allowed_names(df_err)
                            if not filtered_err.empty:
                                st.dataframe(filtered_err, use_container_width=True)
                            else:
                                st.success("No error records found. (No error)")
                        else:
                            st.success("No error records found. (No error)")

                    # --- Tab 3: Bonus ---
                    with tab_bonus:
                        st.markdown("### Bonus Details")
                        bonus_sheet = find_sheet("bonus")
                        if bonus_sheet:
                            df_bonus = excel_file.parse(bonus_sheet)
                            df_bonus.columns = [str(c).strip() for c in df_bonus.columns]
                            filtered_bonus = filter_col_b_by_allowed_names(df