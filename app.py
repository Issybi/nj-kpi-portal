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
        df.columns = [str(c).strip().lower() for c in df.columns] # 转小写去空格，防止匹配失败
        return df
    except Exception as e:
        st.error(f"加载用户表异常: {e}")
        return None

@st.cache_data(ttl=10)
def load_config_data(spreadsheet_id):
    try:
        url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv&sheet=KPI"
        df = pd.read_csv(url, dtype=str)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"加载配置表异常: {e}")
        return None

def convert_drive_url(url_cell_content):
    if not url_cell_content or str(url_cell_content).lower() == "nan":
        return ""
    content = str(url_cell_content).strip()
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', content)
    if match:
        file_id = match.group(1)
        return f"https://docs.google.com/uc?export=download&id={file_id}"
    match_id = re.search(r'id=([a-zA-Z0-9_-]+)', content)
    if match_id:
        file_id = match_id.group(1)
        return f"https://docs.google.com/uc?export=download&id={file_id}"
    return content

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = None

st.title("📊 NJ7 Warehouse Performance Portal")
st.caption("Note: Read-only access to individual performance metrics.")
st.markdown("---")

users_df = load_users_realtime(SPREADSHEET_ID)
config_df = load_config_data(SPREADSHEET_ID)

if users_df is None or users_df.empty:
    st.error("⚠️ 无法加载账号配置表 (`KPI checking portal AC`)，请检查表格名称及公开共享权限。")
elif config_df is None or config_df.empty:
    st.error("⚠️ 无法加载月份配置表 (`KPI`)，请检查表格名称及公开共享权限。")
else:
    st.sidebar.header("🔐 Employee Portal")
    
    valid_config = config_df.dropna(subset=[config_df.columns[0]])
    months = valid_config.iloc[:, 0].dropna().tolist()
    
    if not months:
        st.sidebar.warning("KPI 表的 A 列没有找到月份数据。")
    else:
        selected_month = st.sidebar.selectbox("Select Month / 选择月份", months)
        
        # 精准定位当前选中月份，读取 C 列（索引 2）
        row = valid_config[valid_config.iloc[:, 0].astype(str).str.strip() == str(selected_month).strip()]
        link_val = ""
        if not row.empty and len(row.columns) > 2:
            link_val = str(row.iloc[0, 2]).strip()

        if not st.session_state.logged_in:
            with st.sidebar.form("login_form"):
                st.subheader("Login / 登录")
                input_name = st.text_input("Name / 名字 (A列标准名)").strip()
                input_pw = st.text_input("Password / 密码", type="password").strip()
                input_role = st.selectbox("Role / 职位选择", ["driver", "scanner"])
                submit_btn = st.form_submit_button("Login / 登录")
                
                if submit_btn:
                    # 宽松匹配登录信息
                    name_col = "name" if "name" in users_df.columns else users_df.columns[0]
                    pw_col = "pw" if "pw" in users_df.columns else users_df.columns[1]
                    type_col = "type" if "type" in users_df.columns else users_df.columns[2]
                    
                    match_rows = users_df[
                        (users_df[name_col].fillna("").astype(str).str.strip().str.lower() == input_name.lower()) &
                        (users_df[pw_col].fillna("").astype(str).str.strip() == input_pw) &
                        (users_df[type_col].fillna("").astype(str).str.strip().str.lower() == input_role.lower())
                    ]
                    
                    if not match_rows.empty:
                        user_record = match_rows.iloc[0]
                        st.session_state.logged_in = True
                        st.session_state.user_info = user_record.to_dict()
                        st.session_state.selected_role = input_role
                        st.rerun()
                    else:
                        st.error("Invalid Name, Password or Role / 姓名、密码或职位错误")
        else:
            user_info = st.session_state.user_info
            # 兼容不同列名大小写
            std_name_key = next((c for c in user_info.keys() if c.lower() == "name"), list(user_info.keys())[0])
            standard_name = str(user_info.get(std_name_key, "")).strip()
            user_role = st.session_state.get("selected_role", "driver").lower()
            
            allowed_names = set()
            for col_key in ["name", "name2", "name3"]:
                matched_key = next((c for c in user_info.keys() if c.lower() == col_key), None)
                if matched_key:
                    val = str(user_info.get(matched_key, "")).strip().lower()
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
                
                with st.spinner(f"正在加载 {selected_month} 的实时固化数据..."):
                    try:
                        res = requests.get(target_url, timeout=20)
                        if res.status_code == 200:
                            excel_file = pd.ExcelFile(io.BytesIO(res.content))
                            sheet_names = excel_file.sheet_names
                        else:
                            st.error(f"下载文件失败，HTTP 状态码: {res.status_code}。请检查 C 列链接设置。")
                    except Exception as e:
                        st.error(f"读取 Excel 文件时出错: {e}")

                if excel_file is not None and sheet_names:
                    def match_any_name_in_row(row_series):
                        for val in row_series.values:
                            v_str = str(val).strip().lower()
                            for name in allowed_names:
                                if name in v_str:
                                    return True
                        return False

                    def match_col_b(df):
                        if df is None or df.empty or len(df.columns) < 2:
                            return pd.DataFrame()
                        col_b = df.columns[1]
                        mask = pd.Series(False, index=df.index)
                        for name in allowed_names:
                            b_series = df[col_b].fillna("").astype(str).str.strip().str.lower()
                            mask = mask | (b_series == name)
                        return df[mask]

                    def find_sheet_by_keyword(kw):
                        matches = [s for s in sheet_names if kw.lower() in s.lower()]
                        return matches[0] if matches else None

                    # 1. SCANNER 逻辑
                    if user_role == "scanner":
                        st.subheader(f"📋 Scanner Performance ({selected_month}) - {standard_name}")
                        scan_sheet_name = None
                        for s in sheet_names:
                            s_clean = s.lower().replace(" ", "").replace("-", "")
                            if "scan" in s_clean and s_clean != "scantime":
                                for name in allowed_names:
                                    if name.lower().replace(" ", "") in s_clean:
                                        scan_sheet_name = s
                                        break
                        if not scan_sheet_name:
                            scan_sheet_name = find_sheet_by_keyword("scan")
                            
                        if scan_sheet_name:
                            df_scan = excel_file.parse(scan_sheet_name)
                            df_scan.columns = [str(c).strip() for c in df_scan.columns]
                            df_scan_45 = df_scan.head(45)
                            
                            score_avg = None
                            for col in df_scan_45.columns:
                                if col.lower().strip() in ["d", "score"] or "score" in col.lower():
                                    numeric_vals = pd.to_numeric(df_scan_45[col], errors='coerce')
                                    if not numeric_vals.dropna().empty:
                                        score_avg = numeric_vals.mean()
                                        break
                            if score_avg is None and len(df_scan_45.columns) > 3:
                                numeric_vals = pd.to_numeric(df_scan_45.iloc[:, 3], errors='coerce')
                                if not numeric_vals.dropna().empty:
                                    score_avg = numeric_vals.mean()

                            if score_avg is not None:
                                st.metric(label="⭐ Average Score (D列平均分)", value=f"{score_avg:.2f}")

                            st.markdown("### 📊 Scan Details (只读，前45行)")
                            st.dataframe(df_scan_45, use_container_width=True)
                        else:
                            st.warning("未找到对应的 Scanner 分页。")

                    # 2. DRIVER 逻辑
                    else:
                        st.subheader(f"🚚 Driver Performance Portal ({selected_month}) - {standard_name}")
                        
                        tab_summary, tab_error, tab_bonus, tab_picking, tab_putaway = st.tabs([
                            "1. Summary", 
                            "2. Error-OtherTasks", 
                            "3. Bonus", 
                            "4. Picking", 
                            "5. Putaway"
                        ])

                        with tab_summary:
                            st.markdown("### Summary (个人绩效摘要)")
                            sum_sheet = find_sheet_by_keyword("summary") or sheet_names[0]
                            try:
                                df_sum = excel_file.parse(sum_sheet, header=6)
                                df_sum.columns = [str(c).strip() for c in df_sum.columns]
                                filtered_sum = df_sum[df_sum.apply(match_any_name_in_row, axis=1)]
                                if filtered_sum.empty:
                                    df_sum_raw = excel_file.parse(sum_sheet)
                                    df_sum_raw.columns = [str(c).strip() for c in df_sum_raw.columns]
                                    filtered_sum = df_sum_raw[df_sum_raw.apply(match_any_name_in_row, axis=1)]
                                    
                                if not filtered_sum.empty:
                                    st.dataframe(filtered_sum, use_container_width=True)
                                else:
                                    st.info("未在 Summary 中找到您的专属记录。")
                            except Exception as e:
                                st.error(f"解析 Summary 出错: {e}")

                        with tab_error:
                            st.markdown("### Error & Other Tasks")
                            err_sheet = find_sheet_by_keyword("error") or find_sheet_by_keyword("other")
                            if err_sheet:
                                df_err = excel_file.parse(err_sheet)
                                df_err.columns = [str(c).strip() for c in df_err.columns]
                                filtered_err = match_col_b(df_err)
                                if not filtered_err.empty:
                                    st.dataframe(filtered_err, use_container_width=True)
                                else:
                                    st.success("No error. (没有查到您的错误记录)")
                            else:
                                st.success("No error. (没有错误记录表)")

                        with tab_bonus:
                            st.markdown("### Bonus Details")
                            bonus_sheet = find_sheet_by_keyword("bonus")
                            if bonus_sheet:
                                df_bonus = excel_file.parse(bonus_sheet)
                                df_bonus.columns = [str(c).strip() for c in df_bonus.columns]
                                filtered_bonus = match_col_b(df_bonus)
                                if not filtered_bonus.empty:
                                    st.dataframe(filtered_bonus, use_container_width=True)
                                else:
                                    st.info("No bonus. (没有查到您的奖金记录)")
                            else:
                                st.info("No bonus. (没有奖金记录表)")

                        with tab_picking:
                            st.markdown(f"### Picking Records ({standard_name})")
                            pick_sheet_name = None
                            for s in sheet_names:
                                s_clean = s.lower().replace(" ", "").replace("-", "")
                                if "picking" in s_clean:
                                    for name in allowed_names:
                                        if name.lower().replace(" ", "") in s_clean:
                                            pick_sheet_name = s
                                            break
                            if not pick_sheet_name:
                                pick_sheet_name = find_sheet_by_keyword("picking")

                            if pick_sheet_name:
                                df_pick = excel_file.parse(pick_sheet_name)
                                df_pick.columns = [str(c).strip() for c in df_pick.columns]
                                st.dataframe(df_pick, use_container_width=True)
                            else:
                                st.warning("未找到专属的 Picking 绩效分页。")

                        with tab_putaway:
                            st.markdown(f"### Putaway Records ({standard_name})")
                            put_sheet_name = None
                            for s in sheet_names:
                                s_clean = s.lower().replace(" ", "").replace("-", "")
                                if "putaway" in s_clean:
                                    for name in allowed_names:
                                        if name.lower().replace(" ", "") in s_clean:
                                            put_sheet_name = s
                                            break
                            if not put_sheet_name:
                                put_sheet_name = find_sheet_by_keyword("putaway")

                            if put_sheet_name:
                                df_put = excel_file.parse(put_sheet_name)
                                df_put.columns = [str(c).strip() for c in df_put.columns]
                                st.dataframe(df_put, use_container_width=True)
                            else:
                                st.warning("未找到专属的 Putaway 绩效分页。")
                else:
                    st.error(f"无法下载或解析 {selected_month} 的数据文件。请确认 C 列填入的是形如 `https://docs.google.com/uc?export=download&id=...` 的直接下载直链，且该文件已设置为公开共享。")
            else:
                st.warning(f"未找到 **{selected_month}** 对应的文件直链（C列为空）。请前往 Google 表格点击顶部菜单 **「🚀 KPI 智能自动化 -> 🔄 一键提取 B 列直链并填入 C 列」** 补全直链！")