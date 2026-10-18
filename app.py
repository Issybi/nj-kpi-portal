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

# OneDrive 配置文件分享链接
ONEDRIVE_ORIGINAL_URL = "https://1drv.ms/x/c/21f1717b0dd121e7/IQC2PHbLplJjQ4Japq2ydbwbAd6OCzvcsdnmEaed4QiEYSc?e=elT9dv"

@st.cache_data(ttl=300)  # 缓存5分钟
def load_excel_from_onedrive(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    try:
        # 直接使用 Session 追踪重定向获取真实直链，最稳妥
        s = requests.Session()
        res = s.get(url, headers=headers, allow_redirects=True, timeout=15)
        final_url = res.url
        
        # 转换为下载直链
        if "resid=" in final_url:
            resid = final_url.split("resid=")[1].split("&")[0]
            authkey = final_url.split("authkey=")[1].split("&")[0] if "authkey=" in final_url else ""
            direct_url = f"https://onedrive.live.com/download?resid={resid}&download=1"
            if authkey:
                direct_url += f"&authkey={authkey}"
            
            response = s.get(direct_url, headers=headers, timeout=15)
            response.raise_for_status()
            return pd.ExcelFile(io.BytesIO(response.content), engine='openpyxl')
        else:
            raise Exception("Could not resolve OneDrive redirect URL.")
            
    except Exception as ex:
        st.error(f"Error loading Excel file from OneDrive: {ex}")
        return None

# 标题栏
st.title("📊 NJ7 Warehouse Performance Portal")
st.caption("Note: Read-only access to individual performance metrics. Updated daily.")
st.markdown("---")

# 加载 OneDrive Excel 文件
excel_file = load_excel_from_onedrive(ONEDRIVE_ORIGINAL_URL)

if excel_file is not None:
    sheet_names = excel_file.sheet_names
    
    # 登录框及身份验证
    st.sidebar.header("🔐 Employee Login")
    role = st.sidebar.selectbox("Select Role / 角色选择", ["Driver", "Scanner", "Admin"])
    user_id = st.sidebar.text_input("Enter Employee ID / 输入工号", value="").strip()

    if user_id:
        st.sidebar.success(f"Logged in as: {user_id} ({role})")
        
        # 匹配对应 Role 的工作表
        matched_sheets = [s for s in sheet_names if role.lower() in s.lower()]
        if not matched_sheets:
            matched_sheets = [s for s in sheet_names if "config" not in s.lower()]

        selected_sheet = st.selectbox("Select Data Sheet / 选择数据表", matched_sheets)
        
        if selected_sheet:
            df = pd.read_excel(excel_file, sheet_name=selected_sheet)
            
            # 清理列名空格
            df.columns = [str(c).strip() for c in df.columns]
            
            # 寻找 ID 或 Name 相关的列名
            id_cols = [c for c in df.columns if any(k in c.lower() for k in ["id", "code", "工号", "driver", "scanner", "name", "姓名"])]
            
            if id_cols and role != "Admin":
                primary_id_col = id_cols[0]
                filtered_df = df[df[primary_id_col].astype(str).str.strip().str.lower() == user_id.lower()]
                
                if not filtered_df.empty:
                    st.subheader(f"📋 Performance Records for ID: {user_id}")
                    st.dataframe(filtered_df, use_container_width=True)
                else:
                    st.warning(f"No records found for Employee ID: {user_id} in sheet '{selected_sheet}'.")
            else:
                st.subheader(f"📋 Full Data Sheet: {selected_sheet}")
                st.dataframe(df, use_container_width=True)
    else:
        st.info("👈 Please enter your Employee ID in the sidebar to view your performance metrics.")