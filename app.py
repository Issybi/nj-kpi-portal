import streamlit as st
import pandas as pd
import requests
import io
import re

# 页面基本设置
st.set_page_config(
    page_title="NJ7 Portal Debug",
    page_icon="🐛",
    layout="wide"
)

SPREADSHEET_ID = "1NOLL3GNkIzBIYHIEwV6D55kJ6vsixkSBFj0LVjuTkvI"

st.title("📊 NJ7 网页运行诊断页面")
st.markdown("---")

# 1. 测试加载账号表
st.subheader("步骤 1: 测试加载用户账号表 (`KPI checking portal AC`)")
try:
    url_users = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=KPI%20checking%20portal%20AC"
    users_df = pd.read_csv(url_users, dtype=str)
    users_df.columns = [str(c).strip() for c in users_df.columns]
    st.success(f"✅ 账号表加载成功！共读取到 {len(users_df)} 个用户。")
    with st.expander("点击查看账号表前几行"):
        st.dataframe(users_df.head(5))
except Exception as e:
    st.error(f"❌ 账号表加载失败！错误原因: {e}")
    users_df = None

# 2. 测试加载月份配置表
st.subheader("步骤 2: 测试加载月份配置表 (`KPI`)")
try:
    url_config = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=KPI"
    config_df = pd.read_csv(url_config, dtype=str)
    config_df.columns = [str(c).strip() for c in config_df.columns]
    st.success(f"✅ 月份配置表加载成功！共读取到 {len(config_df)} 行月份配置。")
    with st.expander("点击查看月份配置表内容"):
        st.dataframe(config_df)
except Exception as e:
    st.error(f"❌ 月份配置表加载失败！错误原因: {e}")
    config_df = None

if users_df is not None and config_df is not None:
    st.markdown("---")
    st.success("🎉 **太棒了！两张核心 Google 表格连接完全正常。** 如果你能看到这段话，说明基础网络和表格权限没有问题。")
    st.info("这代表之前的空白是由完整的登录/侧边栏状态逻辑引起的。你可以把上一个版本的完整代码贴回来，或者告诉我上面这两个诊断步骤中，哪一个出现了红色的 `❌ 失败`。")
else:
    st.markdown("---")
    st.error("⚠️ **诊断发现表格无法读取！** 这通常是由以下两个原因之一导致的：\n1. **权限没公开**：请打开你的 Google 电子表格，点击右上角「共享」，将权限改为**「知道链接的任何人都可查看」**。\n2. **分页名字写错**：请确认 Google 表格里确实有名为 `KPI checking portal AC` 和 `KPI` 的分页标签。")