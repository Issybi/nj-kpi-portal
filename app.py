import streamlit as st
import pandas as pd

# 页面基本设置
st.set_page_config(
    page_title="NJ7 Warehouse Performance Portal",
    page_icon="📊",
    layout="wide"
)

# 你的 Google Sheets 基础 ID
SPREADSHEET_ID = "1NOLL3GNkIzBIYHIEwV6D55kJ6vsixkSBFj0LVjuTkvI"
KPI_CONFIG_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=KPI"
ACCOUNT_AC_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=KPI%20checking%20portal%20AC"

@st.cache_data(ttl=15)
def load_csv_from_google_sheets(url):
    try:
        df = pd.read_csv(url)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        return None

# 网页标题
st.title("📊 NJ7 Warehouse Performance Portal")
st.caption("Note: Read-only access to individual performance metrics. Updated daily.")
st.markdown("---")

# 1. 加载账号表与配置表
users_df = load_csv_from_google_sheets(ACCOUNT_AC_URL)
config_df = load_csv_from_google_sheets(KPI_CONFIG_URL)

if users_df is not None and config_df is not None:
    st.sidebar.header("🔐 Employee Login")
    
    valid_config = config_df.dropna(subset=["Month_Label"])
    months = valid_config["Month_Label"].tolist()
    
    selected_month = st.sidebar.selectbox("Select Month / 选择月份", months)
    
    # 获取对应月份在 B 列填写的链接
    row = valid_config[valid_config["Month_Label"] == selected_month]
    link_cols = [c for c in config_df.columns if "link" in c.lower() or "url" in c.lower() or "file" in c.lower()]
    
    raw_link_val = ""
    if not row.empty and link_cols:
        raw_link_val = str(row[link_cols[0]].values[0]).strip()

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
            
            if raw_link_val and raw_link_val != "nan":
                # 将 Google Drive 的分享链接转换为直接下载链接
                target_url = raw_link_val
                if "drive.google.com" in target_url:
                    if "/file/d/" in target_url:
                        file_id = target_url.split("/file/d/")[1].split("/")[0]
                        target_url = f"https://docs.google.com/uc?export=download&id={file_id}"
                
                with st.spinner(f"Loading data for {selected_month}..."):
                    try:
                        month_df = pd.read_excel(target_url)
                        month_df.columns = [str(c).strip() for c in month_df.columns]
                    except Exception as e:
                        month_df = None

                if month_df is not None:
                    names_to_check = [
                        str(user_info.get(c, "")).strip().lower() 
                        for c in ["name", "name2", "name3"] 
                        if pd.notna(user_info.get(c)) and str(user_info.get(c)).strip() != ""
                    ]
                    id_cols = [c for c in month_df.columns if any(k in c.lower() for k in ["name", "driver", "scanner", "姓名", "工号", "id"])]
                    
                    if id_cols and user_role.lower() != "admin":
                        primary_id_col = id_cols[0]
                        filtered_df = month_df[month_df[primary_id_col].astype(str).str.strip().str.lower().isin(names_to_check)]
                        
                        if not filtered_df.empty:
                            st.subheader(f"📋 Performance Records ({selected_month}) for {input_name}")
                            st.dataframe(filtered_df, use_container_width=True)
                        else:
                            st.warning(f"No records found for {input_name} in {selected_month}.")
                    else:
                        st.subheader(f"📋 Full Data Sheet ({selected_month})")
                        st.dataframe(month_df, use_container_width=True)
                else:
                    st.error(f"无法解析 {selected_month} 的文件，请确保网盘文件已共享或链接有效。")
            else:
                st.warning(f"管理员尚未在表格中上传 **{selected_month}** 的 KPI 文件。")
        else:
            st.sidebar.error("Invalid Name or Password / 姓名或密码错误")
    else:
        st.info("👈 Please enter your Name and Password in the sidebar to view performance metrics.")