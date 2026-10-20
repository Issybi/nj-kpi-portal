import io
import pandas as pd
import requests
import streamlit as st

# 页面基本设置
st.set_page_config(
    page_title="NJ7 KPI Checking Portal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==================== 安全保密核心修改 ====================
# 使用 st.secrets 从 Streamlit Cloud 后台读取 SPREADSHEET_ID
# 即使你的 GitHub 仓库是 Public（公开的），别人也无法看到你的表格 ID
try:
  SPREADSHEET_ID = st.secrets["SPREADSHEET_ID"]
except Exception:
  # 本地调试时的备用回退（如果在本地运行，可以在本地配置 .streamlit/secrets.toml）
  SPREADSHEET_ID = "1NOLL3GNkIzBIYHIEwV6D55kJ6vsixkSBFj0LVjuTkvI"


@st.cache_data(ttl=0)
def load_portal_data():
  """实时从 Google Sheet 读取 AC 分页的账号密码数据"""
  try:
    csv_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=AC"
    df = pd.read_csv(csv_url)
    return df
  except Exception as e:
    st.error(f"Failed to load AC portal sheet: {e}")
    return pd.DataFrame()


@st.cache_data(ttl=0)
def load_kpi_portal_list():
  """实时从 Google Sheet 读取 KPI 分页的月份及下载链接"""
  try:
    csv_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=KPI"
    df = pd.read_csv(csv_url)
    return df
  except Exception as e:
    st.error(f"Failed to load KPI sheet list: {e}")
    return pd.DataFrame()


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
            " permissions or sheet name ('AC')."
        )
      else:
        portal_df.columns = portal_df.columns.astype(str).str.strip()
        matched = False
        user_row = None

        for idx, row in portal_df.iterrows():
          name_val = str(row.get("name", "")).strip()
          pw_val = str(row.get("pw", "")).strip()
          type_val = str(row.get("type", "")).strip().lower()

          if (
              name_val.lower() == input_user.strip().lower()
              and str(pw_val) == str(input_pw).strip()
              and type_val == input_role.strip().lower()
          ):
            matched = True
            user_row = row
            break

        if matched:
          st.session_state.logged_in = True
          st.session_state.username = str(user_row.get("name"))
          st.session_state.role = input_role.lower()
          st.session_state.name2 = user_row.get("name2", None)
          st.session_state.name3 = user_row.get("name3", None)
          st.rerun()
        else:
          st.error("Invalid Account, Password, or Position.")

else:
  # ==================== 登录后的 KPI 查询主界面 ====================
  st.sidebar.title("Portal Menu")
  st.sidebar.write(f"**User:** {st.session_state.username}")
  st.sidebar.write(f"**Position:** {st.session_state.role.capitalize()}")

  if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.rerun()

  st.title("Employee KPI Checking Portal")

  # 加载 KPI 分页数据
  kpi_list_df = load_kpi_portal_list()

  if kpi_list_df.empty or "Month_Label" not in kpi_list_df.columns:
    st.error(
        "Could not load KPI monthly links from the 'KPI' sheet. Please check"
        " sheet format."
    )
  else:
    valid_months = kpi_list_df.dropna(subset=["OneDrive_Direct_Link"])
    month_options = valid_months["Month_Label"].tolist()

    if not month_options:
      st.warning("No KPI data files available.")
    else:
      selected_month = st.selectbox("Select Month to View KPI", month_options)

      row_data = valid_months[
          valid_months["Month_Label"] == selected_month
      ].iloc[0]
      file_url = row_data["OneDrive_Direct_Link"]

      @st.cache_data
      def load_monthly_excel(url):
        try:
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
            " Please check the link."
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
          sheet_name = f"{current_user}-scan"
          matched_sheet = None
          for s in excel_file.sheet_names:
            if s.strip().lower() == sheet_name.lower():
              matched_sheet = s
              break

          if matched_sheet:
            df_scan = pd.read_excel(excel_file, sheet_name=matched_sheet)
            st.subheader(f"Scanner KPI Report - {current_user}")

            if len(df_scan) > 45:
              df_scan = df_scan.iloc[:45]

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

          with tab1:
            st.subheader("Summary Report")
            if "Summary" in excel_file.sheet_names:
              df_sum = pd.read_excel(
                  excel_file, sheet_name="Summary", header=None
              )
              if len(df_sum) >= 7:
                header_row = df_sum.iloc[6].values
                data_rows = df_sum.iloc[7:]
                df_sum_clean = pd.DataFrame(
                    data_rows.values, columns=header_row
                )
                name_col_sum = None
                for col in df_sum_clean.columns:
                  if "name" in str(col).lower():
                    name_col_sum = col
                    break

                if name_col_sum:
                  user_summary = df_sum_clean[
                      df_sum_clean[name_col_sum]
                      .astype(str)
                      .str.strip()
                      .str.lower()
                      .isin(match_names)
                  ]
                  if not user_summary.empty:
                    st.dataframe(user_summary, use_container_width=True)
                  else:
                    st.info("No summary record found matching your name.")
                else:
                  st.warning("Summary sheet structure mismatch.")
              else:
                st.warning("Summary sheet rows are less than 7.")
            else:
              st.warning("Summary sheet not found.")

          with tab2:
            st.subheader("Error & Other Tasks")
            if "Error-OtherTasks" in excel_file.sheet_names:
              df_err = pd.read_excel(excel_file, sheet_name="Error-OtherTasks")
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
                st.success("no error")
            else:
              st.success("no error")

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

          with tab4:
            st.subheader("Picking Details")
            picking_sheet = None
            for s in excel_file.sheet_names:
              if s.lower().startswith("picking -"):
                try:
                  temp_df = pd.read_excel(
                      excel_file, sheet_name=s, header=None
                  )
                  b1_val = str(temp_df.iloc[0, 1]).strip().lower()
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

          with tab5:
            st.subheader("Putaway Details")
            putaway_sheet = None
            for s in excel_file.sheet_names:
              if s.lower().startswith("putaway -"):
                try:
                  temp_df = pd.read_excel(
                      excel_file, sheet_name=s, header=None
                  )
                  b1_val = str(temp_df.iloc[0, 1]).strip().lower()
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