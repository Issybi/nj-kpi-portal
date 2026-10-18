import streamlit as st
import pandas as pd
import io
import requests

# ---------------------------------------------------------
# 1. Page Configuration
# ---------------------------------------------------------
st.set_page_config(page_title="NJ7 Employee KPI Portal", page_icon="📊", layout="wide")

st.title("📊 NJ7 Warehouse Employee KPI Portal")
st.caption("Note: Read-only access to individual performance metrics. Updated daily.")
st.markdown("---")

# ---------------------------------------------------------
# 2. Master Config Link
# OneDrive Direct Link for 'NJ7 KPI checking config.xlsx'
# ---------------------------------------------------------
MASTER_CONFIG_URL = "https://1drv.ms/x/c/21f1717b0dd121e7/IQC2PHbLplJjQ4Japq2ydbwbAd6OCzvcsdnmEaed4QiEYSc?e=elT9dv"


def convert_onedrive_url(url):
    """Automatically convert OneDrive share links to direct download links."""
    if not isinstance(url, str) or not url.strip():
        return None
    url = url.strip()
    if "1drv.ms" in url or "onedrive.live.com" in url:
        if "?e=" in url:
            if "&download=1" not in url:
                return url + "&download=1"
            return url
        else:
            return url + "?download=1"
    return url


@st.cache_data(ttl=60)
def load_excel_file(url):
    """Load ExcelFile object to access multiple sheets dynamically."""
    try:
        direct_url = convert_onedrive_url(url)
        if not direct_url or "YOUR_ONEDRIVE" in direct_url:
            return None
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(direct_url, headers=headers, timeout=20)
        response.raise_for_status()
        
        excel_file = pd.ExcelFile(io.BytesIO(response.content))
        return excel_file
    except Exception as e:
        st.error(f"Error loading Excel file from OneDrive: {e}")
        return None

# Load master config file
master_excel = load_excel_file(MASTER_CONFIG_URL)

# Initialize Session State
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user_info" not in st.session_state:
    st.session_state["user_info"] = {}

# ---------------------------------------------------------
# 3. Login Interface
# ---------------------------------------------------------
if not st.session_state["logged_in"]:
    st.subheader("🔒 Employee Login")
    
    if master_excel is not None and "account" in master_excel.sheet_names:
        account_df = master_excel.parse("account")
        account_df.columns = account_df.columns.astype(str).str.strip()
        
        # Position Selection (Type)
        type_options = ["driver", "scanner"]
        selected_type = st.radio("Select Position (Type):", type_options, horizontal=True)
        
        # Filter account dataframe by type
        type_filtered_df = account_df[account_df["type"].astype(str).str.strip().str.lower() == selected_type]
        
        # Gather all names across Column A (name), Column C (name2), Column D (name3)
        available_names = set()
        for _, row in type_filtered_df.iterrows():
            for col in ["name", "name2", "name3"]:
                if col in row and pd.notna(row[col]):
                    val = str(row[col]).strip()
                    if val and val.lower() != "nan":
                        available_names.add(val)
                        
        sorted_names = sorted(list(available_names))
        
        selected_name = st.selectbox("Select Your Name:", ["-- Please Select --"] + sorted_names)
        input_pwd = st.text_input("Enter Password:", type="password")
        
        if st.button("Log In", use_container_width=True):
            if selected_name == "-- Please Select --":
                st.warning("⚠️ Please select your name.")
            else:
                # Match user across name, name2, or name3
                matched_row = type_filtered_df[
                    (type_filtered_df["name"].astype(str).str.strip().str.lower() == selected_name.lower()) |
                    (type_filtered_df["name2"].astype(str).str.strip().str.lower() == selected_name.lower()) |
                    (type_filtered_df["name3"].astype(str).str.strip().str.lower() == selected_name.lower())
                ]
                
                if not matched_row.empty:
                    correct_pwd = str(matched_row["pw"].values[0]).strip()
                    if correct_pwd.endswith(".0"):
                        correct_pwd = correct_pwd[:-2]
                        
                    if str(input_pwd).strip() == correct_pwd:
                        st.session_state["logged_in"] = True
                        st.session_state["user_info"] = {
                            "name": selected_name,
                            "type": selected_type,
                            "primary_name": str(matched_row["name"].values[0]).strip()
                        }
                        st.rerun()
                    else:
                        st.error("❌ Incorrect password. Please try again.")
                else:
                    st.error("❌ Selected name not found under this Position.")
    else:
        st.info("ℹ️ Loading Master Config... Please make sure MASTER_CONFIG_URL is properly configured.")

# ---------------------------------------------------------
# 4. Main Dashboard Page
# ---------------------------------------------------------
else:
    user_name = st.session_state["user_info"]["name"]
    user_type = st.session_state["user_info"]["type"]
    primary_name = st.session_state["user_info"]["primary_name"]
    
    col_user, col_logout = st.columns([4, 1])
    with col_user:
        badge = "📦 Scanner" if user_type == "scanner" else "🚛 Driver"
        st.success(f"👋 Welcome, **{user_name}** ({badge})")
    with col_logout:
        if st.button("Log Out"):
            st.session_state["logged_in"] = False
            st.session_state["user_info"] = {}
            st.rerun()
            
    st.markdown("---")

    # Read 'KPI' config sheet for monthly file links
    if master_excel is not None and "KPI" in master_excel.sheet_names:
        kpi_config_df = master_excel.parse("KPI")
        kpi_config_df.columns = kpi_config_df.columns.astype(str).str.strip()
        
        valid_kpi_df = kpi_config_df.dropna(subset=["OneDrive_Direct_Link"])
        valid_kpi_df = valid_kpi_df[valid_kpi_df["OneDrive_Direct_Link"].astype(str).str.strip() != ""]
        
        if not valid_kpi_df.empty:
            month_options = valid_kpi_df["Month_Label"].astype(str).str.strip().unique().tolist()
            selected_month = st.selectbox("📅 Select Month:", month_options)
            
            target_url = valid_kpi_df[valid_kpi_df["Month_Label"].astype(str).str.strip() == selected_month]["OneDrive_Direct_Link"].values[0]
            
            # Load selected month's Excel file
            month_excel = load_excel_file(target_url)
            
            if month_excel is not None:
                sheet_names_list = month_excel.sheet_names
                
                # =========================================================
                # A. SCANNER LOGIC
                # =========================================================
                if user_type == "scanner":
                    possible_sheets = [f"{user_name}-scan", f"{primary_name}-scan"]
                    target_sheet = None
                    for s in sheet_names_list:
                        if s.strip().lower() in [p.lower() for p in possible_sheets]:
                            target_sheet = s
                            break
                            
                    if target_sheet:
                        sheet_df = month_excel.parse(target_sheet, header=None)
                        b1_val = str(sheet_df.iloc[0, 1]).strip() if sheet_df.shape[0] > 0 and sheet_df.shape[1] > 1 else ""
                        
                        st.subheader(f"📋 Scanner Performance: [{target_sheet}] ({selected_month})")
                        st.caption(f"Verified B1 Name: **{b1_val}**")
                        st.dataframe(sheet_df, use_container_width=True, height=650)
                    else:
                        st.error(f"❌ Could not find scanner sheet '{user_name}-scan' for {selected_month}.")

                # =========================================================
                # B. DRIVER LOGIC (5 Tabs)
                # =========================================================
                else:
                    st.subheader(f"🚛 Driver KPI Portal - {user_name} ({selected_month})")
                    
                    # Create 5 Tabs for Driver
                    tab1, tab2, tab3, tab4, tab5 = st.tabs([
                        "1. Summary", 
                        "2. Error-OtherTasks", 
                        "3. Bonus", 
                        "4. Picking Detail", 
                        "5. Putaway Detail"
                    ])
                    
                    name_keys = [user_name.lower(), primary_name.lower()]
                    
                    # ---------------- TAB 1: Summary ----------------
                    with tab1:
                        if "Summary" in sheet_names_list:
                            summary_df = month_excel.parse("Summary", header=6)
                            summary_df.columns = summary_df.columns.astype(str).str.strip()
                            
                            if "Name" in summary_df.columns:
                                user_summary = summary_df[summary_df["Name"].astype(str).str.strip().str.lower().isin(name_keys)]
                                
                                if not user_summary.empty:
                                    st.markdown("#### 📊 Summary Metrics")
                                    st.dataframe(user_summary, use_container_width=True)
                                else:
                                    st.info(f"💡 No Summary record found for **{user_name}**.")
                            else:
                                st.error("❌ 'Name' column not found in Summary sheet.")
                        else:
                            st.error("❌ 'Summary' sheet not found in this month's Excel file.")
                            
                    # ---------------- TAB 2: Error-OtherTasks ----------------
                    with tab2:
                        if "Error-OtherTasks" in sheet_names_list:
                            error_df = month_excel.parse("Error-OtherTasks", header=0)
                            error_df.columns = error_df.columns.astype(str).str.strip()
                            
                            name_col = [c for c in error_df.columns if "name" in c.lower()][0] if any("name" in c.lower() for c in error_df.columns) else error_df.columns[1]
                            
                            user_errors = error_df[error_df[name_col].astype(str).str.strip().str.lower().isin(name_keys)]
                            
                            if not user_errors.empty:
                                st.markdown("#### ⚠️ Task Error Records")
                                st.dataframe(user_errors, use_container_width=True)
                            else:
                                st.success("✅ **No Error** found for this month!")
                        else:
                            st.info("ℹ️ 'Error-OtherTasks' sheet not found.")

                    # ---------------- TAB 3: Bonus ----------------
                    with tab3:
                        if "Bonus" in sheet_names_list:
                            bonus_df = month_excel.parse("Bonus", header=0)
                            bonus_df.columns = bonus_df.columns.astype(str).str.strip()
                            
                            name_col = [c for c in bonus_df.columns if "name" in c.lower()][0] if any("name" in c.lower() for c in bonus_df.columns) else bonus_df.columns[1]
                            
                            user_bonus = bonus_df[bonus_df[name_col].astype(str).str.strip().str.lower().isin(name_keys)]
                            
                            if not user_bonus.empty:
                                st.markdown("#### 🎁 Bonus Records")
                                st.dataframe(user_bonus, use_container_width=True)
                            else:
                                st.info("💡 **No Bonus** recorded for this month.")
                        else:
                            st.info("ℹ️ 'Bonus' sheet not found.")

                    # ---------------- TAB 4: Picking Detail ----------------
                    with tab4:
                        picking_sheets = [f"Picking - {user_name}", f"Picking - {primary_name}"]
                        target_pick_sheet = None
                        for s in sheet_names_list:
                            if s.strip().lower() in [p.lower() for p in picking_sheets]:
                                target_pick_sheet = s
                                break
                                
                        if target_pick_sheet:
                            pick_df = month_excel.parse(target_pick_sheet, header=None)
                            b1_pick_name = str(pick_df.iloc[0, 1]).strip() if pick_df.shape[0] > 0 and pick_df.shape[1] > 1 else ""
                            
                            st.markdown(f"#### 📦 Picking Detail: [{target_pick_sheet}]")
                            st.caption(f"Verified B1 Name: **{b1_pick_name}**")
                            st.dataframe(pick_df, use_container_width=True, height=600)
                        else:
                            st.warning(f"⚠️ Picking sheet for **{user_name}** was not found in {selected_month}.")

                    # ---------------- TAB 5: Putaway Detail ----------------
                    with tab5:
                        putaway_sheets = [f"Putaway - {user_name}", f"Putaway - {primary_name}"]
                        target_putaway_sheet = None
                        for s in sheet_names_list:
                            if s.strip().lower() in [p.lower() for p in putaway_sheets]:
                                target_putaway_sheet = s
                                break
                                
                        if target_putaway_sheet:
                            putaway_df = month_excel.parse(target_putaway_sheet, header=None)
                            b1_putaway_name = str(putaway_df.iloc[0, 1]).strip() if putaway_df.shape[0] > 0 and putaway_df.shape[1] > 1 else ""
                            
                            st.markdown(f"#### 🚜 Putaway Detail: [{target_putaway_sheet}]")
                            st.caption(f"Verified B1 Name: **{b1_putaway_name}**")
                            st.dataframe(putaway_df, use_container_width=True, height=600)
                        else:
                            st.warning(f"⚠️ Putaway sheet for **{user_name}** was not found in {selected_month}.")
            else:
                st.error("❌ Failed to load Excel file from OneDrive link.")
        else:
            st.warning("⚠️ No valid OneDrive links configured in KPI sheet.")