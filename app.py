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

# 使用 Streamlit Secrets 读取 SPREADSHEET_ID
try:
  SPREADSHEET_ID = st.secrets["SPREADSHEET_ID"]
except Exception:
  SPREADSHEET_ID = "1NOLL3GNkIzBIYHIEwV6D55kJ6vsixkSBFj0LVjuTkvI"


@st.cache_data(ttl=0)
def load_portal_data():
  """实时从 Google Sheet 读取 'KPI checking portal AC' 分页的账号密码数据"""
  try:
    csv_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=KPI%20checking%20portal%20AC"
    df = pd.read_csv(csv_url)
    return df
  except Exception as e:
    st.error(f"Failed to load 'KPI checking portal AC' sheet: {e}")
    return pd.DataFrame()


@st.cache_data(ttl=0)
def load_kpi_portal_list():
  """实时从 Google Sheet 读取 'KPI' 分页的月份及下载链接"""
  try:
    csv_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=KPI"
    df = pd.read_csv(csv_url)

    # 规范化列名，清理多余空格
    df.columns = [str(c).strip() for c in df.columns]
    return df
  except Exception as e:
    st.error(f"Failed to load 'KPI' sheet list: {e}")
    return pd.DataFrame()


@st.cache_data(ttl=0)
def get_kpi_update_date():
  """专门读取 'KPI' 分页 E1 单元格的更新日期"""
  try:
    csv_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=KPI&range=A1:E2"
    df_e1 = pd.read_csv(csv_url, header=None)
    if df_e1.shape[1] >= 5:
      val = str(df_e1.iloc[0, 4]).strip()
      if val and val.lower() != "nan":
        return val
    return "N/A"
  except Exception:
    return "N/A"


# 初始化 Session State
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False
  st.session_state.username = ""
  st.session_state.role = ""
  st.session_state.name2 = None
  st.session_state.name3 = None
  st.session_state.available_roles = []

# ==================== 登录页面 ====================
if not st.session_state.logged_in:
  st.title("NJ7 KPI Checking Portal")
  st.markdown("Please log in with your account and password.")

  portal_df = load_portal_data()

  with st.form("login_form"):
    input_user = st.text_input("Account")
    input_pw = st.text_input("Password", type="password")
    submit_btn = st.form_submit_button("Login")

    if submit_btn:
      if portal_df.empty:
        st.error(
            "Portal data could not be loaded. Please check Google Sheet"
            " permissions or sheet name ('KPI checking portal AC')."
        )
      else:
        portal_df.columns = portal_df.columns.astype(str).str.strip()

        matched_rows = []
        for idx, row in portal_df.iterrows():
          acc_val = str(row.get("Account", "")).strip()
          pw_val = str(row.get("Password", "")).strip()

          if acc_val.lower() == input_user.strip().lower() and str(
              pw_val
          ) == str(input_pw).strip():
            matched_rows.append(row)

        if matched_rows:
          st.session_state.logged_in = True
          st.session_state.username = str(matched_rows[0].get("Account"))
          st.session_state.name2 = matched_rows[0].get("Name2", None)
          st.session_state.name3 = matched_rows[0].get("Name3", None)

          roles = [
              str(r.get("Role", "")).strip().lower()
              for r in matched_rows
              if str(r.get("Role", "")).strip()
          ]
          st.session_state.available_roles = list(set(roles))

          if st.session_state.available_roles:
            st.session_state.role = st.session_state.available_roles[0]

          st.rerun()
        else:
          st.error("Invalid Account or Password.")

else:
  # ==================== 登录后的 KPI 查询主界面 ====================
  st.sidebar.title("Portal Menu")
  st.sidebar.write(f"**User:** {st.session_state.username}")

  if len(st.session_state.available_roles) > 1:
    current_index = 0
    if st.session_state.role in st.session_state.available_roles:
      current_index = st.session_state.available_roles.index(
          st.session_state.role
      )

    selected_role = st.sidebar.selectbox(
        "Switch Position (Role)",
        st.session_state.available_roles,
        index=current_index,
        format_func=lambda x: x.capitalize(),
    )
    if selected_role != st.session_state.role:
      st.session_state.role = selected_role
      st.rerun()
  else:
    st.sidebar.write(
        f"**Position:** {st.session_state.role.capitalize()}"
    )

  if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.available_roles = []
    st.rerun()

  st.title("Employee KPI Checking Portal")

  # 1. 动态展示免责声明与 E1 单元格日期
  update_date = get_kpi_update_date()
  st.info(
      "📌 **Disclaimer & Notice:** Content is for reference only. Please"
      " confirm your final score with **Amanda** during your KPI review. If"
      " you find any data inaccuracies, please contact **Isabella** promptly."
      f" Currently, KPI Data is updated as of **{update_date}**."
  )

  # 2. 读取 KPI 列表数据
  kpi_list_df = load_kpi_portal_list()

  # 兼容查找 Month_Label 列名
  month_col = None
  for col in kpi_list_df.columns:
    if "month_label" in str(col).lower():
      month_col = col
      break

  if kpi_list_df.empty or not month_col:
    st.error(
        "Could not load KPI monthly links from the 'KPI' sheet. Please check"
        " sheet format."
    )
  else:
    link_col = None
    for c in ["File_URL", "OneDrive_Direct_Link", "Link"]:
      for real_col in kpi_list_df.columns:
        if c.lower() == str(real_col).lower():
          link_col = real_col
          break
      if link_col:
        break

    if not link_col:
      st.error("Could not find a valid link column in the 'KPI' sheet.")
    else:
      valid_months = kpi_list_df.dropna(subset=[link_col])
      month_options = valid_months[month_col].dropna().tolist()

      if not month_options:
        st.warning("No KPI data files available.")
      else:
        selected_month = st.selectbox("Select Month to View KPI", month_options)

        row_data = valid_months[
            valid_months[month_col] == selected_month
        ].iloc[0]
        file_url = str(row_data[link_col]).strip()


        def load_monthly_excel(url):
          try:
            if not url.startswith("http"):
              st.error(
                  f"Invalid URL for {selected_month}: '{url}'. Make sure it's"
                  " a full http link."
              )
              return None

            session = requests.Session()

            if "drive.google.com" in url:
              if "/file/d/" in url:
                file_id = url.split("/file/d/")[1].split("/")[0]
              elif "id=" in url:
                file_id = url.split("id=")[1].split("&")[0]
              else:
                file_id = ""

              if file_id:
                url = f"https://drive.google.com/uc?export=download&id={file_id}"

            response = session.get(url, stream=True)

            for key, value in response.cookies.items():
              if key.startswith("download_warning"):
                url = url + "&confirm=" + value
                response = session.get(url, stream=True)
                break

            return pd.ExcelFile(io.BytesIO(response.content))
          except Exception as e:
            st.error(f"Excel download/parsing error detail: {e}")
            return None


        with st.spinner(f"Loading KPI data for {selected_month}..."):
          excel_file = load_monthly_excel(file_url)

        if excel_file is None:
          st.error(
              f"Failed to download or read the Excel file for {selected_month}."
              " Please check that the Google Drive link is set to 'Anyone with"
              " the link can view'."
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
              df_raw = pd.read_excel(
                  excel_file, sheet_name=matched_sheet, header=None
              )

              st.subheader(f"Scanner KPI Report - {current_user}")

              header_idx = None
              for idx, row in df_raw.iterrows():
                row_str_vals = [str(val).strip().lower() for val in row.values]
                if "date" in row_str_vals:
                  header_idx = idx
                  break

              if header_idx is not None:
                headers = list(df_raw.iloc[header_idx].values)

                if len(headers) > 0:
                  headers[0] = "Date"
                if len(headers) > 1:
                  headers[1] = "Scan Quantity (B)"
                if len(headers) > 2:
                  headers[2] = "Time Spent (C)"
                if len(headers) > 3:
                  headers[3] = "Score (D)"

                cleaned_headers = []
                for i, h in enumerate(headers):
                  h_str = str(h).strip()
                  if h_str == "" or h_str.lower() == "nan":
                    cleaned_headers.append(f"Column_{i+1}")
                  else:
                    cleaned_headers.append(h_str)

                df_scan = df_raw.iloc[header_idx + 1 :].copy()
                df_scan.columns = cleaned_headers

                date_col = cleaned_headers[0]

                df_scan = df_scan[
                    df_scan[date_col].notna()
                    & (df_scan[date_col].astype(str).str.strip() != "")
                    & (df_scan[date_col].astype(str).str.strip() != "0")
                ]

                if len(df_scan) > 45:
                  df_scan = df_scan.iloc[:45]

                score_col = (
                    cleaned_headers[3] if len(cleaned_headers) > 3 else None
                )
                if not score_col or "score" not in score_col.lower():
                  for col in df_scan.columns:
                    if "score" in str(col).strip().lower():
                      score_col = col
                      break

                if score_col is not None:
                  avg_score = pd.to_numeric(
                      df_scan[score_col], errors="coerce"
                  ).mean()
                  st.metric(
                      label="📊 Average Score (D Column - Score)",
                      value=f"{avg_score:.2f}"
                      if pd.notna(avg_score)
                      else "N/A",
                  )

                st.dataframe(df_scan, use_container_width=True)
              else:
                if len(df_raw) > 45:
                  df_raw = df_raw.iloc[:45]
                st.dataframe(df_raw, use_container_width=True)

            else:
              st.warning(
                  f"No scan records found for your account ({sheet_name} not"
                  " found)."
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