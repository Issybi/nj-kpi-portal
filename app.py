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

@st.cache_data(ttl=300)  # 缓存5分钟，避免频繁请求OneDrive
def load_excel_from_onedrive(url):
    # 将 OneDrive 分享链接转换为直接下载链接
    # 针对 1drv.ms 短链的通用转换与带 Headers 的稳定请求
    download_url = url.replace("https://1drv.ms/x/c/", "https://onedrive.live.com/download?resid=")
    download_url = download_url.replace("?", "&")
    if "download=1" not in download_url:
        download_url += "&download=1"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(download_url, headers=headers, timeout=15)
        response.raise_for_status()
        excel_data = io.BytesIO(response.content)
        # 读取全部 Sheets
        xls = pd.ExcelFile(excel_data, engine='openpyxl')
        return xls
    except Exception as e:
        # 如果常规转换方式被阻断，尝试使用 1drv.ms 重定向跟踪获取直链
        try:
            s = requests.Session()
            res = s.get(url, headers=headers, allow_redirects=True)
            final_url = res.url
            if "resid=" in final_url:
                resid = final_url.split("resid=")[1].split("&")[0]
                authkey = final_url.split("authkey=")[1].split("&")[0] if "authkey=" in final_url else ""
                direct_url = f"https://onedrive.live.com/download?resid={resid}"
                if authkey:
                    direct_url += f"&authkey={authkey}"
                response2 = s.get(direct_url, headers=headers, timeout=15)
                response2.raise_for_status()
                return pd.ExcelFile(io.BytesIO(response2.content), engine='openpyxl')
            else:
                raise Exception(f"Unable to parse direct download URL: {e}")
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
            # 如果没有找到精确匹配，使用所有非 Config 工作表
            matched_sheets = [s for s in sheet_names if "config" not in s.lower()]

        selected_sheet = st.selectbox("Select Data Sheet / 选择数据表", matched_sheets)
        
        if selected_sheet:
            df = pd.read_excel(excel_file, sheet_name=selected_sheet)
            
            # 清理列名空格
            df.columns = [str(c).strip() for c in df.columns]
            
            # 寻找 ID 或 Name 相关的列名（不区分大小写）
            id_cols = [c for c in df.columns if any(k in c.lower() for k in ["id", "code", "工号", "driver", "scanner", "name", "姓名"])]
            
            if id_cols and role != "Admin":
                # 按用户工号过滤数据
                primary_id_col = id_cols[0]
                filtered_df = df[df[primary_id_col].astype(str).str.strip().str.lower() == user_id.lower()]
                
                if not filtered_df.empty:
                    st.subheader(f"📋 Performance Records for ID: {user_id}")
                    st.dataframe(filtered_df, use_container_width=True)
                else:
                    st.warning(f"No records found for Employee ID: {user_id} in sheet '{selected_sheet}'.")
            else:
                # Admin 角色显示全表数据
                st.subheader(f"📋 Full Data Sheet: {selected_sheet}")
                st.dataframe(df, use_container_width=True)
    else:
        st.info("👈 Please enter your Employee ID in the sidebar to view your performance metrics.")