import streamlit as st
import pandas as pd
import requests
import io

# 页面基本设置
st.set_page_config(
    page_title="NJ7 KPI Checking Portal",
    page_icon="📊",
    layout="wide"
)

# 你的 Google Sheets 基础 ID
SPREADSHEET_ID = "1NOLL3GNkIzBIYHIEwV6D55kJ6vsixkSBFj0LVjuTkvI"

# 直接通过 Sheet Name 导出 CSV 格式的绝对 URL
KPI_CONFIG_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=KPI"
ACCOUNT_AC_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=KPI%20checking%20portal%20AC"

@st.cache_data(ttl=30)
def load_csv_from_google_sheets(url):
    try:
        df = pd.read_csv(url)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Error reading Google Sheets data: {e}")
        return None

@st.cache_data(ttl=60)
def load_excel_from_onedrive(share_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    try:
        # 将 1drv.ms 短链接自动转换为 direct download 格式
        session = requests.Session()
        res = session.get(share_url, headers=headers, allow_redirects=True, timeout=15)
        final_url = res.url
        
        if "download=1" not in final_url:
            download_url = final_url + ("&download=1" if "?" in final_url else "?download=1")
            res = session.get(download_url, headers=headers, timeout=15)
            
        res.raise_for_status()
        return pd.ExcelFile(io.BytesIO(res.content), engine='openpyxl')
    except Exception as ex:
        st.error(f"Error loading Excel file from OneDrive: {ex}")
        return None

# 标题栏
st.title("📊 NJ7 Warehouse Performance Portal")
st.caption("Note: Read-only access to individual performance metrics. Updated daily.")
st.markdown("---")

# 1. 读取账号验证表 (KPI checking portal AC) 与 配置表 (KPI)
users_df = load_csv_from_google_sheets(ACCOUNT_AC_URL)
config_df = load_csv_from_google_sheets(KPI_CONFIG_URL)

if users_df is not None and config_df is not None:
    # 侧边栏：登录与导航
    st.sidebar.header("🔐 Employee Login")
    
    # 获取可用月份列表
    valid_config = config_df.dropna(subset=["Month_Label", "OneDrive_Direct_Link"])
    months = valid_config["Month_Label"].tolist()
    
    selected_month = st.sidebar.selectbox("Select Month / 选择月份", months)
    
    # 获取对应月份的链接
    row = valid_config[valid_config["Month_Label"] == selected_month]
    target_url = str(row["OneDrive_Direct_Link"].values[0]).strip() if not row.empty else ""

    # 用户输入账号与密码
    input_name = st.sidebar.text_input("Name / 名字", value="").strip()
    input_pw = st.sidebar.text_input("Password / 密码", type="password", value="").strip()

    if input_name and input_pw:
        # 匹配账号密码
        user_match = users_df[
            (users_df["name"].astype(str).str.strip().str.lower() == input_name.lower()) & 
            (users_df["pw"].astype(str).str.strip() == input_pw)
        ]
        
        if not user_match.empty:
            user_info = user_match.iloc[0]
            user_role = str(user_info.get("type", "driver")).strip()
            st.sidebar.success(f"Welcome, {input_name}! Role: {user_role}")
            
            # 2. 读取对应月份的 OneDrive Excel
            if target_url:
                with st.spinner(f"Loading performance data for {selected_month}..."):
                    month_excel = load_excel_from_onedrive(target_url)
                    
                if month_excel is not None:
                    sheet_names = month_excel.sheet_names
                    
                    # 匹配对应 Role 的工作表
                    matched_sheets = [s for s in sheet_names if user_role.lower() in s.lower()]
                    if not matched_sheets:
                        matched_sheets = [s for s in sheet_names if "config" not in s.lower()]

                    selected_sheet = st.selectbox("Select Data Sheet / 选择数据表", matched_sheets)
                    
                    if selected_sheet:
                        df = pd.read_excel(month_excel, sheet_name=selected_sheet)
                        df.columns = [str(c).strip() for c in df.columns]
                        
                        # 查找员工姓名相关列过滤数据（支持 name, name2, name3 匹配）
                        names_to_check = [
                            str(user_info.get(c, "")).strip().lower() 
                            for c in ["name", "name2", "name3"] 
                            if pd.notna(user_info.get(c)) and str(user_info.get(c)).strip() != ""
                        ]
                        
                        id_cols = [c for c in df.columns if any(k in c.lower() for k in ["name", "driver", "scanner", "姓名", "工号", "id"])]
                        
                        if id_cols and user_role.lower() != "admin":
                            primary_id_col = id_cols[0]
                            filtered_df = df[df[primary_id_col].astype(str).str.strip().str.lower().isin(names_to_check)]
                            
                            if not filtered_df.empty:
                                st.subheader(f"📋 Performance Records ({selected_month}) for {input_name}")
                                st.dataframe(filtered_df, use_container_width=True)
                            else:
                                st.warning(f"No records found for {input_name} in {selected_month} ('{selected_sheet}').")
                        else:
                            st.subheader(f"📋 Full Data Sheet ({selected_month}): {selected_sheet}")
                            st.dataframe(df, use_container_width=True)
                else:
                    st.error(f"Could not load data for {selected_month}. Please check the OneDrive link.")
        else:
            st.sidebar.error("Invalid Name or Password / 姓名或密码错误")
    else:
        st.info("👈 Please enter your Name and Password in the sidebar to view performance metrics.")