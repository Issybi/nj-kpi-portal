import io
import requests
import pandas as pd
import streamlit as st
import openpyxl

# 页面基本设置
st.set_page_config(
    page_title="NJ7 KPI Checking Portal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Google Sheet 链接
PORTAL_SHEET_URL = "https://docs.google.com/spreadsheets/d/1NOLL3GNkIzBIYHIEwV6D55kJ6vsixkSBFj0LVjuTkvI/edit?usp=sharing"


@st.cache_data(ttl=0)
def load_portal_data():
  """实时从 Google Sheet AC 分页读取登录账号、密码和职位映射表"""
  try:
    csv_url = PORTAL_SHEET_URL.replace("/edit?usp=sharing", "/export?format=csv")
    df = pd.read_csv(csv_url)
    return df
  except Exception as e:
    st.error(f"Failed to load portal configuration: {e}")
    return pd.DataFrame()


@st.cache_data(ttl=0)
def load_kpi_list():
  """读取 KPI 分页获取月份及对应下载链接"""
  try:
    # 默认读取名为 KPI 的分页 (gid 需要根据实际情况，通常通过 csv export 获取)
    csv_url = (
        PORTAL_SHEET_URL.replace("/edit?usp=sharing", "/export?format=csv")
        + "&gid=0"
    )
    # 如果 KPI 分页不是第一个，可以通过指定 sheet 名读取
    # 为稳妥起见，我们直接用 pandas 读取整个 gsheet 的 excel 或通过 gspread，
    # 或者直接读取公开的 csv 对应 sheet。这里使用 gsheet 导出的标准 csv 链接：
    excel_export_url = PORTAL_SHEET_URL.replace(
        "/edit?usp=sharing", "/export?format=xlsx"
    )
    xls = pd.ExcelFile(excel_export_url)
    # 查找包含 Month_Label 或 KPI 的分页
    for sheet in xls.sheet_names:
      temp_df = pd.read_excel(xls, sheet_name=sheet)
      if "Month_Label" in temp_df.columns or "OneDrive_Direct_Link" in temp_df.columns:
        return temp_df
    # 如果没找到，默认返回第一页
    return pd.read_excel(xls, sheet_name=0)
  except Exception as e:
    # 备用硬编码或提示
    return pd.DataFrame()


def match_user_name(target_name, row_b, row_name2, row_name3):
  """使用 name, name2, name3 同时匹配，满足其中一个即可"""
  if pd.isna(target_name):
    return False
  target_str = str(target_name).strip().lower()

  for val in [row_b, row_name2, row_name3]:
    if pd.notna(val):
      if str(val).strip().lower() == target_str:
        return st.write or True  # 匹配成功
        return True
  return False


# 初始化 Session State
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False
  st.session_state.username = ""
  st.session_state.role = ""

# ==================== 登录页面 ====================
if not st.session_state.logged_in:
  st.title("NJ7 KPI Checking Portal")
  st.markdown("Please log in with your account, password, and position.")

  portal_df = load_portal_data()

  with st.form("login_form"):
    input_user = st.text_input("Account (Name)")
    input_pw = st.text_input("Password", type="password")
    input_role = st.selectbox("Position", ["scanner", "driver"])
    submit_btn = st.form_submit_button("Login")

    if submit_btn:
      if portal_df.empty:
        st.error(
            "Portal data could not be loaded. Please check Google Sheet"
            " permissions."
        )
      else:
        # 查找匹配的账号与密码 (A列 name, B列 pw, E列 type)
        # 清理列名空格
        portal_df.columns = portal_df.columns.astype(str).str.strip()

        matched = False
        user_row = None

        for idx, row in portal_df.iterrows():
          name_val = str(row.get("name", "")).strip()
          pw_val = str(row.get("pw", "")).strip()
          type_val = str(row.get("type", "")).strip().lower()

          if (
              name_val.lower() == input_user.strip().lower()
              and pw_val == input_pw.strip()
              and type_val == input_role.strip().lower()
          ):
            matched = True
            user_row = row
            break

        if matched:
          st.session_state.logged_in = True
          st.session_state.username = str(user_row.get("name"))
          st.session_state.role = input_role.lower()
          # 保存备用匹配名
          st.session_state.name2 = user_row.get("name2", None)
          st.session_state.name3 = user_row.get("name3", None)
          st.rerun()
        else:
          st.error("Invalid Account, Password, or Position.")

else:
  # ==================== 登入后的 KPI 查询主界面 ====================
  st.sidebar.title("Portal Menu")
  st.sidebar.write(f"**User:** {st.session_state.username}")
  st.sidebar.write(f"**Position:** {st.session_state.role.capitalize()}")

  if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.rerun()

  st.title("Employee KPI Checking Portal")

  # 加载月份与文件列表
  kpi_list_df = load_kpi_list()

  if kpi_list_df.empty or "OneDrive_Direct_Link" not in kpi_list_df.columns:
    st.error(
        "Could not load KPI monthly links from the Google Sheet. Please check"
        " the sheet format."
    )
  else:
    # 提取有链接的月份
    valid_months = kpi_list_df.dropna(subset=["OneDrive_Direct_Link"])
    month_options = valid_months["Month_Label"].tolist()

    if not month_options:
      st.warning("No KPI data files available.")
    else:
      selected_month = st.selectbox("Select Month to View KPI", month_options)

      # 获取对应月份的下载链接
      row_data = valid_months[
          valid_months["Month_Label"] == selected_month
      ].iloc[0]
      file_url = row_data["OneDrive_Direct_Link"]

      # 加载对应的 Excel 文件
      @st.cache_data
      def load_monthly_excel(url):
        try:
          # 处理 google drive / onedrive 直链
          if "export=download" not in url and "drive.google.com" in url:
            url = url.replace("uc?id=", "uc?export=download&id=")
          res = requests.get(url)
          return pd.ExcelFile(io.BytesIO(res.content))
        except Exception as e:
          return None

      with st.spinner(f"Loading KPI data for {selected_month}..."):
        excel_file = load_monthly_excel(file_url)

      if excel_file is None:
        st.error(
            f"Failed to download or read the Excel file for {selected_month}."
        )
      else:
        current_user = st.session_state.username.strip()
        n2 = (
            str(st.session_state.name2).strip()
            if pd.notna(st.session_state.name2)
            else ""
        )
        n3 = (
            str(st.session_state.name3).strip()
            if pd.notna(st.session_state.name3)
            else ""
        )

        match_names = [
            n.lower()
            for n in [current_user, n2, n3]
            if n and n.lower() != "nan"
        ]

        # ==================== 角色 1: SCANNER ====================
        if st.session_state.role == "scanner":
          # 返回名字-scan的分页（无空格）
          sheet_name = f"{current_user}-scan"
          # 尝试不区分大小写查找分页
          matched_sheet = None
          for s in excel_file.sheet_names:
            if s.strip().lower() == sheet_name.lower():
              matched_sheet = s
              break

          if matched_sheet:
            df_scan = pd.read_excel(excel_file, sheet_name=matched_sheet)
            st.subheader(f"Scanner KPI Report - {current_user}")

            # 只需要显示到第 45 行
            if len(df_scan) > 45:
              df_scan = df_scan.iloc[:45]

            # 计算 D 列 (score) 的平均分显示
            # 自动寻找包含 score 或类似名称的列，或者直接按索引 D列 (第4列, index 3)
            score_col = None
            for col in df_scan.columns:
              if "score" in str(col).lower():
                score_col = col
                break

            if score_col is not None:
              avg_score = pd.to_numeric(
                  df_scan[score_col], errors="coerce"
              ).mean()
              st.metric(
                  label="Average Score (D Column)",
                  value=f"{avg_score:.2f}" if pd.notna(avg_score) else "N/A",
              )

            st.dataframe(df_scan, use_container_width=True)
          else:
            st.warning(
                f"No scan records found for your account ({sheet_name})."
            )

        # ==================== 角色 2: DRIVER ====================
        elif st.session_state.role == "driver":
          tab1, tab2, tab3, tab4, tab5 = st.tabs([
              "Summary",
              "Error-OtherTasks",
              "Bonus",
              f"Picking - {current_user}",
              f"Putaway - {current_user}",
          ])

          # --- Tab 1: Summary ---
          with tab1:
            st.subheader("Summary Report")
            if "Summary" in excel_file.sheet_names:
              df_sum = pd.read_excel(
                  excel_file, sheet_name="Summary", header=None
              )
              # 第 7 行是标题 (index 6)，从第 8 行开始是数据 (index 7 onwards)
              if len(df_sum) >= 7:
                header_row = df_sum.iloc[6].values  # 第7行
                data_rows = df_sum.iloc[7:]  # 从第8行开始

                # 构建带正确表头的 DataFrame
                df_sum_clean = pd.DataFrame(
                    data_rows.values, columns=header_row
                )
                # 寻找 Name 列进行过滤
                name_col_sum = None
                for col in df_sum_clean.columns:
                  if "name" in str(col).lower():
                    name_col_sum = col
                    break

                if name_col_sum:
                  # 过滤匹配名字行
                  user_summary = df_sum_clean[
                      df_sum_clean[name_col_sum]
                      .astype(str)
                      .str.strip()
                      .str.lower()
                      .isin(match_names)
                  ]
                  # 组合表头行 + 用户行显示
                  header_display = pd.DataFrame(
                      [header_row], columns=header_row
                  )
                  if not user_summary.empty:
                    st.dataframe(user_summary, use_container_width=True)
                  else:
                    st.info(
                        "No summary record found matching your name in A8+"
                        " range."
                    )
                else:
                  st.warning("Summary sheet structure mismatch: Name column not found.")
            else:
              st.warning("Summary sheet not found in the workbook.")

          # --- Tab 2: Error-OtherTasks ---
          with tab2:
            st.subheader("Error & Other Tasks")
            if "Error-OtherTasks" in excel_file.sheet_names:
              df_err = pd.read_excel(excel_file, sheet_name="Error-OtherTasks")
              # 寻找 Name 列
              name_col_err = None
              for col in df_err.columns:
                if "name" in str(col).lower():
                  name_col_err = col
                  break

              if name_col_err:
                user_err = df_err[
                    df_err[name_col_err]
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .isin(match_names)
                ]
                if not user_err.empty:
                  st.dataframe(user_err, use_container_width=True)
                else:
                  st.success("no error")
              else:
                st.warning("Error-OtherTasks sheet missing Name column.")
            else:
              st.success("no error")

          # --- Tab 3: Bonus ---
          with tab3:
            st.subheader("Bonus Record")
            if "Bonus" in excel_file.sheet_names:
              df_bonus = pd.read_excel(excel_file, sheet_name="Bonus")
              name_col_bon = None
              for col in df_bonus.columns:
                if "name" in str(col).lower():
                  name_col_bon = col
                  break

              if name_col_bon:
                user_bon = df_bonus[
                    df_bonus[name_col_bon]
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .isin(match_names)
                ]
                if not user_bon.empty:
                  st.dataframe(user_bon, use_container_width=True)
                else:
                  st.info("no bonus")
              else:
                st.info("no bonus")
            else:
              st.info("no bonus")

          # --- Tab 4: Picking (带空格，对应 B1) ---
          with tab4:
            st.subheader("Picking Details")
            picking_sheet = None
            for s in excel_file.sheet_names:
              if s.lower().startswith("picking -"):
                # 读取 B1 判断名字是否匹配
                try:
                  temp_df = pd.read_excel(
                      excel_file, sheet_name=s, header=None
                  )
                  b1_val = str(temp_df.iloc[0, 1]).strip().lower()  # B1 单元格
                  if b1_val in match_names or any(
                      m in b1_val for m in match_names
                  ):
                    picking_sheet = s
                    break
                except:
                  continue

            if picking_sheet:
              df_pick = pd.read_excel(excel_file, sheet_name=picking_sheet)
              st.dataframe(df_pick, use_container_width=True)
            else:
              st.warning("No Picking sheet matched for your profile.")

          # --- Tab 5: Putaway (带空格，对应 B1) ---
          with tab5:
            st.subheader("Putaway Details")
            putaway_sheet = None
            for s in excel_file.sheet_names:
              if s.lower().startswith("putaway -"):
                try:
                  temp_df = pd.read_excel(
                      excel_file, sheet_name=s, header=None
                  )
                  b1_val = str(temp_df.iloc[0, 1]).strip().lower()  # B1 单元格
                  if b1_val in match_names or any(
                      m in b1_val for m in match_names
                  ):
                    putaway_sheet = s
                    break
                except:
                  continue

            if putaway_sheet:
              df_put = pd.read_excel(excel_file, sheet_name=putaway_sheet)
              st.dataframe(df_put, use_container_width=True)
            else:
              st.warning("No Putaway sheet matched for your profile.")