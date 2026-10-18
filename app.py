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

# 你的 Config 总配置表原始分享链接
CONFIG_ORIGINAL_URL = "https://1drv.ms/x/c/21f1717b0dd121e7/IQC2PHbLplJjQ4Japq2ydbwbAd6OCzvcsdnmEaed4QiEYSc?e=wc6rvF"

@st.cache_data(ttl=60)
def load_excel_from_onedrive(share_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    try:
        # 方法一：利用 Session 跟随微软的 302 重定向拿到真实文件流
        session = requests.Session()
        response = session.get(share_url, headers=headers, allow_redirects=True, timeout=15)
        
        # 如果直接请求拿到的不是二进制文件，尝试将重定向链接转为 download=1 模式
        final_url = response.url
        if "download=1" not in final_url:
            if "?" in final_url:
                download_url = final_url + "&download=1"
            else:
                download_url = final_url + "?download=1"
            response = session.get(download_url, headers=headers, timeout=15)
            
        response.raise_for_status()
        
        # 验证是否为合法的 Excel (Zip) 数据流
        content = response.content
        if content.startswith(b'PK'):  _ = io.BytesIO(content) # zip 格式签名校验
        
        return pd.ExcelFile(io.BytesIO(content), engine='openpyxl')
        
    except Exception as ex:
        st.error(f"Error loading Excel file from OneDrive: {ex}")
        return None

# 网页标题栏
st.title("📊 NJ7 Warehouse Performance Portal")
st.caption("Note: Read-only access to individual performance metrics. Updated daily.")
st.markdown("---")

# 1. 加载 Config 总表
config_excel = load_excel_from_onedrive(CONFIG_ORIGINAL_URL)

if config_excel is not None:
    # 默认读取 Config 表的第一个工作表
    config_df = pd.read_excel(config_excel, sheet_name=0)
    config_df.columns = [str(c).strip() for c in config_df.columns]
    
    # 侧边栏：月份选择、角色及工号
    st.sidebar.header("🔐 Portal Navigation & Login")
    
    if "Month_Label" in config_df.columns and "OneDrive_Direct_Link" in config_df.columns:
        valid_config = config_df.dropna(subset=["Month_Label", "OneDrive_Direct_Link"])
        months = valid_config["Month_Label"].tolist()
        
        selected_month = st.sidebar.selectbox("Select Month / 选择月份", months)
        
        # 获取对应月份的链接
        row = valid_config[valid_config["Month_Label"] == selected_month]
        target_url = row["OneDrive_Direct_Link"].values[0].strip() if not row.empty else ""
        
        role = st.sidebar.selectbox("Select Role / 角色选择", ["Driver", "Scanner", "Admin"])
        user_id = st.sidebar.text_input("Enter Employee ID / 输入工号", value="").strip()

        if user_id and target_url:
            st.sidebar.success(f"Logged in as: {user_id} ({role}) for {selected_month}")
            
            # 2. 根据选中的月份链接，加载该月份的具体 Excel 表格
            with st.spinner(f"Loading data for {selected_month}..."):
                month_excel = load_excel_from_onedrive(target_url)
                
            if month_excel is not None:
                sheet_names = month_excel.sheet_names
                
                # 匹配对应 Role 的工作表
                matched_sheets = [s for s in sheet_names if role.lower() in s.lower()]
                if not matched_sheets:
                    matched_sheets = [s for s in sheet_names if "config" not in s.lower()]

                selected_sheet = st.selectbox("Select Data Sheet / 选择数据表", matched_sheets)
                
                if selected_sheet:
                    df = pd.read_excel(month_excel, sheet_name=selected_sheet)
                    df.columns = [str(c).strip() for c in df.columns]
                    
                    # 寻找 ID 或 Name 相关的列名
                    id_cols = [c for c in df.columns if any(k in c.lower() for k in ["id", "code", "工号", "driver", "scanner", "name", "姓名"])]
                    
                    if id_cols and role != "Admin":
                        primary_id_col = id_cols[0]
                        filtered_df = df[df[primary_id_col].astype(str).str.strip().str.lower() == user_id.lower()]
                        
                        if not filtered_df.empty:
                            st.subheader(f"📋 Performance Records ({selected_month}) for ID: {user_id}")
                            st.dataframe(filtered_df, use_container_width=True)
                        else:
                            st.warning(f"No records found for Employee ID: {user_id} in {selected_month} ('{selected_sheet}').")
                    else:
                        st.subheader(f"📋 Full Data Sheet ({selected_month}): {selected_sheet}")
                        st.dataframe(df, use_container_width=True)
            else:
                st.error(f"Could not load the data file linked for {selected_month}.")
        else:
            st.info("👈 Please enter your Employee ID in the sidebar and ensure a month is selected.")
    else:
        st.error("Config table columns 'Month_Label' or 'OneDrive_Direct_Link' not found.")