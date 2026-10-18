import streamlit as st
import pandas as pd
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# 页面基本设置
st.set_page_config(
    page_title="NJ7 Warehouse Performance Portal",
    page_icon="📊",
    layout="wide"
)

# 你的 Google Sheets 基础 ID
SPREADSHEET_ID = "1NOLL3GNkIzBIYHIEwV6D55kJ6vsixkSBFj0LVjuTkvI"
ACCOUNT_AC_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=KPI%20checking%20portal%20AC"

@st.cache_data(ttl=15)
def load_users_from_gsheets(url):
    try:
        df = pd.read_csv(url)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Error reading accounts from Google Sheets: {e}")
        return None

@st.cache_resource
def get_drive_service():
    try:
        creds_dict = dict(st.secrets["google_service_account"])
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        return None

def get_excel_from_gdrive_folder(folder_name, file_keyword):
    """直接去 Google Drive 的 KPI 文件夹里按关键词（如 Sep-26）搜索并读取对应的 Excel 文件"""
    service = get_drive_service()
    if not service:
        st.error("Google Drive API not configured in Streamlit Secrets.")
        return None
    
    try:
        # 1. 查找 KPI 文件夹 ID
        folder_query = f"mimeType = 'application/vnd.google-apps.folder' and name = '{folder_name}' and trashed = false"
        folder_results = service.files().list(q=folder_query, fields="files(id, name)").execute()
        folders = folder_results.get('files', [])
        
        if not folders:
            st.error(f"Google Drive folder '{folder_name}' not found.")
            return None
        
        folder_id = folders[0]['id']
        
        # 2. 在该文件夹中查找包含关键词的文件
        file_query = f"'{folder_id}' in parents and name contains '{file_keyword}' and trashed = false"
        file_results = service.files().list(q=file_query, fields="files(id, name)").execute()
        files = file_results.get('files', [])
        
        if not files:
            return None
            
        file_id = files[0]['id']
        
        # 3. 下载到内存中解析
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
            
        fh.seek(0)
        return pd.ExcelFile(fh, engine='openpyxl')
    except Exception as e:
        st.error(f"Error loading file from Google Drive: {e}")
        return None

# 网页标题
st.title("📊 NJ7 Warehouse Performance Portal")
st.caption("Note: Read-only access to individual performance metrics. Updated daily.")
st.markdown("---")

# 1. 加载账号表
users_df = load_users_from_gsheets(ACCOUNT_AC_URL)

if users_df is not None:
    st.sidebar.header("🔐 Employee Login")
    
    months = ["Sep-26", "Oct-26", "Nov-26", "Dec-26", "Jan-27", "Feb-27", "Mar-27", "Apr-27", "May-27", "Jun-27", "Jul-27", "Aug-27", "Sep-27"]
    selected_month = st.sidebar.selectbox("Select Month / 选择月份", months)

    input_name = st.sidebar.text_input("Name / 名字", value="").strip()
    input_pw = st.sidebar.text_input("Password / 密码", type="password", value="").strip()

    if input_name and input_pw:
        user_match = users_df[
            (users_df["name"].astype(str).str.strip().str.lower() == input_name.lower()) & 
            (users_df["pw"].astype(str).str.strip() == input_pw)
        ]
        
        if not user_match.empty:
            user_info = user_match.iloc[0]
            user_role = str(user_info.get("type", "driver")).strip()
            st.sidebar.success(f"Welcome, {input_name}! Role: {user_role}")
            
            # 2. 直接根据选择的月份（如 Sep-26）去网盘 KPI 文件夹抓取对应文件
            with st.spinner(f"Loading data for {selected_month} from Google Drive..."):
                excel_file = get_excel_from_gdrive_folder("KPI", selected_month)
                
            if excel_file is not None:
                sheet_names = excel_file.sheet_names
                selected_sheet = st.selectbox("Select Data Sheet / 选择数据子表", sheet_names)
                
                if selected_sheet:
                    df = pd.read_excel(excel_file, sheet_name=selected_sheet)
                    df.columns = [str(c).strip() for c in df.columns]
                    
                    # 过滤个人数据
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
                            st.warning(f"No records found for {input_name} in {selected_month}.")
                    else:
                        st.subheader(f"📋 Full Data Sheet ({selected_month}): {selected_sheet}")
                        st.dataframe(df, use_container_width=True)
            else:
                st.warning(f"未在 Google Drive 的 'KPI' 文件夹中找到包含 **{selected_month}** 的文件，请确保已通过表格自动化工具上传。")
        else:
            st.sidebar.error("Invalid Name or Password / 姓名或密码错误")
    else:
        st.info("👈 Please enter your Name and Password in the sidebar to view performance metrics.")