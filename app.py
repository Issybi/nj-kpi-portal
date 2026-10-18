import streamlit as st
import pandas as pd
import time

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

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None

st.title("📊 NJ7 Warehouse Performance Portal")
st.caption("Note: Read-only access to individual performance metrics.")
st.markdown("---")

users_df = load_users_realtime(SPREADSHEET_ID)

if users_df is not None:
    st.sidebar.header("🔐 Employee Portal & Upload")
    
    if not st.session_state.logged_in:
        with st.sidebar.form("login_form"):
            st.subheader("Login / 登录")
            input_name = st.text_input("Name / 名字 (A/C/D列)").strip()
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
                    )
                ]
                
                if not match_rows.empty:
                    role_match = match_rows[match_rows["type"].fillna("").astype(str).str.strip().str.lower() == input_role.lower()]
                    user_record = role_match.iloc[0] if not role_match.empty else match_rows.iloc[0]
                    
                    st.session_state.logged_in = True
                    st.session_state.user_info = user_record.to_dict()
                    st.session_state.selected_role = input_role
                    st.session_state.searched_name = input_name
                    st.rerun()
                else:
                    st.error("Invalid Name or Password / 姓名或密码错误")
    else:
        user_info = st.session_state.user_info
        input_name = st.session_state.get("searched_name", user_info.get("name", ""))
        user_role = st.session_state.get("selected_role", str(user_info.get("type", "driver")).strip()).lower()
        
        st.sidebar.success(f"Welcome, {input_name}!\nRole: {user_role.upper()}")
        
        if st.sidebar.button("Log out / 登出"):
            st.session_state.logged_in = False
            st.session_state.user_info = None
            st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.subheader("📂 Upload KPI Excel File")
    uploaded_file = st.sidebar.file_uploader("请上传对应月份的原始 KPI Excel 文件 (.xlsx)", type=["xlsx", "xls"])

    if uploaded_file is not None:
        try:
            excel_file = pd.ExcelFile(uploaded_file)
            sheet_names = excel_file.sheet_names
        except Exception as e:
            excel_file = None
            sheet_names = []

        if excel_file is not None and st.session_state.logged_in:
            employee_names = [
                str(user_info.get(c, "")).strip().lower() 
                for c in ["name", "name2", "name3"] 
                if pd.notna(user_info.get(c)) and str(user_info.get(c)).strip() != ""
            ]
            if input_name.lower() not in employee_names:
                employee_names.append(input_name.lower())

            def smart_filter_df(df):
                """精准过滤包含员工姓名的行"""
                if df is None or df.empty:
                    return pd.DataFrame()
                mask = pd.Series(False, index=df.index)
                for col in df.columns:
                    col_series = df[col].fillna("").astype(str).str.strip().str.lower()
                    for name in employee_names:
                        mask = mask | col_series.str.contains(name, na=False)
                return df[mask]

            def find_sheet(kw):
                matches = [s for s in sheet_names if kw.lower() in s.lower()]
                return matches[0] if matches else None

            # ==========================
            # 1. SCANNER 岗位逻辑
            # ==========================
            if user_role == "scanner":
                st.subheader(f"📋 Scanner Performance - {input_name}")
                target_scan_sheet = find_sheet("scan") or sheet_names[0]
                df_scan = excel_file.parse(target_scan_sheet)
                df_scan.columns = [str(c).strip() for c in df_scan.columns]
                
                filtered_scan = smart_filter_df(df_scan)
                if not filtered_scan.empty:
                    st.dataframe(filtered_scan, use_container_width=True)
                else:
                    st.dataframe(df_scan, use_container_width=True)

            # ==========================
            # 2. DRIVER 岗位逻辑 (5个分页)
            # ==========================
            else:
                st.subheader(f"🚚 Driver Performance Portal - {input_name}")
                
                tab_summary, tab_error, tab_bonus, tab_picking, tab_putaway = st.tabs([
                    "1. Summary", 
                    "2. Error-OtherTasks", 
                    "3. Bonus", 
                    "4. Picking", 
                    "5. Putaway"
                ])

                # --- Tab 1: Summary ---
                with tab_summary:
                    st.markdown("### Summary (个人绩效摘要)")
                    sum_sheet = find_sheet("summary") or sheet_names[0]
                    try:
                        df_sum = excel_file.parse(sum_sheet, header=6) # 适配第7行表头
                    except Exception:
                        df_sum = excel_file.parse(sum_sheet)
                    df_sum.columns = [str(c).strip() for c in df_sum.columns]
                    filtered_sum = smart_filter_df(df_sum)
                    if not filtered_sum.empty:
                        st.dataframe(filtered_sum, use_container_width=True)
                    else:
                        st.info("No summary record found for this employee.")

                # --- Tab 2: Error-OtherTasks ---
                with tab_error:
                    st.markdown("### Error & Other Tasks")
                    err_sheet = find_sheet("error") or find_sheet("other")
                    if err_sheet:
                        df_err = excel_file.parse(err_sheet)
                        df_err.columns = [str(c).strip() for c in df_err.columns]
                        filtered_err = smart_filter_df(df_err)
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
                        filtered_bonus = smart_filter_df(df_bonus)
                        if not filtered_bonus.empty:
                            st.dataframe(filtered_bonus, use_container_width=True)
                        else:
                            st.info("No bonus records found. (No bonus)")
                    else:
                        st.info("No bonus records found. (No bonus)")

                # --- Tab 4: Picking (带入名字筛选) ---
                with tab_picking:
                    st.markdown(f"### Picking Records ({input_name})")
                    pick_sheet = find_sheet("picking")
                    if pick_sheet:
                        df_pick = excel_file.parse(pick_sheet)
                        df_pick.columns = [str(c).strip() for c in df_pick.columns]
                        filtered_pick = smart_filter_df(df_pick)
                        if not filtered_pick.empty:
                            st.dataframe(filtered_pick, use_container_width=True)
                        else:
                            st.warning(f"在 Picking 中未找到与 {input_name} 直接匹配的行，展示全表：")
                            st.dataframe(df_pick, use_container_width=True)
                    else:
                        st.warning("未找到 Picking 分页。")

                # --- Tab 5: Putaway (带入名字筛选) ---
                with tab_putaway:
                    st.markdown(f"### Putaway Records ({input_name})")
                    put_sheet = find_sheet("putaway")
                    if put_sheet:
                        df_put = excel_file.parse(put_sheet)
                        df_put.columns = [str(c).strip() for c in df_put.columns]
                        filtered_put = smart_filter_df(df_put)
                        if not filtered_put.empty:
                            st.dataframe(filtered_put, use_container_width=True)
                        else:
                            st.warning(f"在 Putaway 中未找到与 {input_name} 直接匹配的行，展示全表：")
                            st.dataframe(df_put, use_container_width=True)
                    else:
                        st.warning("未找到 Putaway 分页。")
        else:
            if not st.session_state.logged_in:
                st.sidebar.warning("👈 请先在上方登录！")
            else:
                st.info("👈 请在左侧上传 KPI Excel 文件。")
    else:
        st.info("👈 请先登录并上传 Excel 文件。")
else:
    st.error("无法加载员工账号表。")