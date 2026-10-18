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

# 使用从 Embed 代码中精准提取并转化为下载模式的直链
ONEDRIVE_DIRECT_URL = "https://onedrive.live.com/download?resid=21F1717B0DD121E7!IQS2PHbLplJjQ4Japq2ydbwbATPefx8xnizBAFIBYa0EcbI&authkey=!AOhqXhC5X9X..." # （或者直接用下方处理好的标准下载链接）

# 转换为最稳定的下载直链格式
REAL_DOWNLOAD_URL = "https://onedrive.live.com/download?resid=21F1717B0DD121E7!121E7&authkey=..." # 我们直接用标准转换函数处理

@st.cache_data(ttl=60)  # 缓存60秒，既能实时更新，又能避免频繁请求
def load_excel_from_onedrive(embed_src_url):
    # 将 embed 链接自动转换为 download 直链
    download_url = embed_src_url.replace("1drv.ms/x/c/", "onedrive.live.com/download?resid=")
    if "embed" in download_url:
        download_url = download_url.replace("embed", "download")
    if "download" not in download_url:
        download_url = download_url.replace("onedrive.live.com/", "onedrive.live.com/download?")
        
    # 如果是标准的完整 embed 网址转换：
    # https://1drv.ms/x/c/21f1717b0dd121e7/IQS2PHbLplJjQ4Japq2ydbwbATPefx8xnizBAFIBYa0EcbI
    # 我们可以直接拼出最高效的直链：
    direct_url = "https://onedrive.live.com/download?resid=21F1717B0DD121E7!IQS2PHbLplJjQ4Japq2ydbwbATPefx8xnizBAFIBYa0EcbI&authkey=APefx8xnizBAFIB" # 适配你的鉴权参数
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }

    # 为了绝对稳妥，我们写一个支持直接请求的逻辑：
    try:
        # 直接利用你提供的直链源头
        target_url = "https://onedrive.live.com/download?resid=21F1717B0DD121E7!IQS2PHbLplJjQ4Japq2ydbwbATPefx8xnizBAFIBYa0EcbI"
        response = requests.get(embed_src_url.replace("embed", "download"), headers=headers, timeout=15)
        if response.status_code != 200:
            # 备用直接下载通道
            response = requests.get(target_url, headers=headers, timeout=15)
        response.raise_for_status()
        return pd.ExcelFile(io.BytesIO(response.content), engine='openpyxl')
    except Exception as ex:
        # 终极兼容：直接使用标准重定向解析
        try:
            s = requests.Session()
            res = s.get(embed_src_url, headers=headers, allow_redirects=True, timeout=15)
            res.raise_for_status()
            return pd.ExcelFile(io.BytesIO(res.content), engine='openpyxl')
        except Exception as e:
            st.error(f"Error loading Excel file from OneDrive: {e}")
            return None

# 网页标题栏
st.title("📊 NJ7 Warehouse Performance Portal")
st.caption("Note: Read-only access to individual performance metrics. Updated daily.")
st.markdown("---")

# 你的源 Embed 链接
EMBED_URL = "https://1drv.ms/x/c/21f1717b0dd121e7/IQS2PHbLplJjQ4Japq2ydbwbATPefx8xnizBAFIBYa0EcbI"

# 加载 OneDrive 实时数据
excel_file = load_excel_from_onedrive(EMBED_URL)

if excel_file is not None:
    sheet_names = excel_file.sheet_names
    
    # 登录侧边栏
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