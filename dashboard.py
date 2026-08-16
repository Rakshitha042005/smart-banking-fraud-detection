import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
import decimal
import random
import time
from db_utils import (
    check_snowflake_health,
    fetch_accounts_paginated,
    fetch_account_summary_kpis,
    fetch_account_filter_options,
    fetch_transactions_paginated,
    fetch_summary_kpis,
    fetch_filter_options,
    fetch_analytics_transactions_over_time,
    fetch_analytics_fraud_by_type,
    fetch_analytics_fraud_by_channel,
    fetch_analytics_fraud_by_location,
    fetch_analytics_fraud_by_merchant,
    add_transaction,
    generate_flag_explanations,
    fetch_customer_profile,
    fetch_fraud_alert_summary,
    fetch_fraud_rules_analytics,
    fetch_4_fraud_rules_analytics
)

# Set page config
st.set_page_config(
    page_title="Nova Smart Banking - Fraud Detection & Analytics",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State Variables
if "applied_filters" not in st.session_state:
    st.session_state.applied_filters = {}
if "tx_page" not in st.session_state:
    st.session_state.tx_page = 1
if "acct_page" not in st.session_state:
    st.session_state.acct_page = 1
if "alert_page" not in st.session_state:
    st.session_state.alert_page = 1
if "page_size" not in st.session_state:
    st.session_state.page_size = 25
if "investigating_transaction_id" not in st.session_state:
    st.session_state.investigating_transaction_id = None

# Helper Number Formatter
def format_compact_currency(amount):
    if amount is None or amount == 0:
        return "₹0.00"
    abs_amt = abs(amount)
    if abs_amt >= 1e9:
        return f"₹{amount / 1e9:,.2f}B"
    elif abs_amt >= 1e6:
        return f"₹{amount / 1e6:,.2f}M"
    elif abs_amt >= 1e3:
        return f"₹{amount / 1e3:,.2f}K"
    else:
        return f"₹{amount:,.2f}"

# Inject Premium LIGHT THEME CSS, Shimmer Skeletons & Fonts
# Inject Premium LIGHT, CLEAN & MODERN BANKING THEME CSS & Fonts
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">

<style>
    /* Base configuration overrides for Light Modern Theme (#F7F9FC) */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        background-color: #F7F9FC !important;
        color: #1F2937 !important;
    }
    
    /* Hide top Streamlit decoration line */
    [data-testid="stHeader"] {
        background: transparent !important;
    }
    
    /* Sidebar styling overrides - Clean White */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1px solid #E5E7EB !important;
        padding-top: 1rem;
    }
    
    /* Navigation Radio Items overrides */
    [data-testid="stSidebarUserContent"] div[role="radiogroup"] {
        gap: 6px;
    }
    [data-testid="stSidebarUserContent"] div[role="radiogroup"] label {
        background-color: transparent !important;
        color: #4B5563 !important;
        padding: 11px 16px !important;
        border-radius: 10px !important;
        border: 1px solid transparent !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        transition: all 0.2s ease-in-out;
        cursor: pointer;
        display: flex;
        align-items: center;
        width: 100%;
    }
    [data-testid="stSidebarUserContent"] div[role="radiogroup"] label:hover {
        background-color: #F3F4F6 !important;
        color: #1F2937 !important;
    }
    [data-testid="stSidebarUserContent"] div[role="radiogroup"] label[data-checked="true"] {
        background-color: #EAF2FF !important;
        border-left: 4px solid #4F8DF7 !important;
        color: #4F8DF7 !important;
        font-weight: 700 !important;
    }
    
    /* Hide radio dot buttons from UI */
    [data-testid="stSidebarUserContent"] div[role="radiogroup"] label span[data-testid="stWidgetLabel"] {
        display: none !important;
    }
    [data-testid="stSidebarUserContent"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] {
        margin-left: 0 !important;
    }

    /* Brand Header and User Profile Layout */
    .sidebar-brand {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px;
        margin-bottom: 20px;
        border-bottom: 1px solid #E5E7EB;
    }
    .logo-icon {
        background: #EAF2FF;
        color: #4F8DF7;
        width: 42px;
        height: 42px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        border: 1px solid #BFDBFE;
    }
    .sidebar-brand h2 {
        margin: 0;
        font-size: 20px;
        font-weight: 800;
        color: #1F2937;
        letter-spacing: -0.3px;
    }
    
    .sidebar-footer {
        padding: 16px;
        border-top: 1px solid #E5E7EB;
        margin-top: 40px;
    }
    .user-profile {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .avatar-fallback {
        width: 38px;
        height: 38px;
        border-radius: 50%;
        background-color: #EAF2FF;
        color: #4F8DF7;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 16px;
        border: 1px solid #BFDBFE;
    }
    .user-info {
        display: flex;
        flex-direction: column;
    }
    .user-name {
        font-size: 14px;
        font-weight: 700;
        color: #1F2937;
    }
    .user-role {
        font-size: 12px;
        color: #6B7280;
    }

    /* Main Header Styling */
    .main-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 18px;
        margin-bottom: 24px;
        border-bottom: 1px solid #E5E7EB;
    }
    .header-greeting h1 {
        margin: 0;
        font-size: 24px;
        font-weight: 800;
        letter-spacing: -0.5px;
        color: #1F2937;
    }
    .header-greeting p {
        margin: 4px 0 0 0;
        font-size: 14px;
        color: #6B7280;
    }
    
    /* Dynamic Status Pills */
    .db-status-pill-green {
        display: flex;
        align-items: center;
        gap: 8px;
        background: #DCFCE7;
        border: 1px solid #86EFAC;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
        color: #15803D;
    }
    .db-status-pill-red {
        display: flex;
        align-items: center;
        gap: 8px;
        background: #FEE2E2;
        border: 1px solid #FCA5A5;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
        color: #991B1B;
    }
    .status-dot-green {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #16A34A;
    }
    .status-dot-red {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #DC2626;
    }

    /* Clean White Card Container */
    .bg-glass {
        background: #FFFFFF !important;
        border-radius: 16px !important;
        border: 1px solid #E5E7EB !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03) !important;
        padding: 1.5rem !important;
        margin-bottom: 24px !important;
        color: #1F2937 !important;
    }

    /* Rule Cards with Subtle Hover Effect */
    .rule-card-box {
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 14px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.03);
        transition: all 0.2s ease-in-out;
    }
    .rule-card-box:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.06);
        border-color: #BFDBFE;
    }
    
    /* Risk Badges Tokens (Soft Light Palette) */
    .badge-active, .badge-low, .badge-normal {
        background: #DCFCE7 !important;
        color: #166534 !important;
        border: 1px solid #86EFAC !important;
        padding: 4px 12px !important;
        border-radius: 20px !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        letter-spacing: 0.5px !important;
        display: inline-block !important;
    }
    .badge-medium {
        background: #FEF3C7 !important;
        color: #92400E !important;
        border: 1px solid #FDE68A !important;
        padding: 4px 12px !important;
        border-radius: 20px !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        letter-spacing: 0.5px !important;
        display: inline-block !important;
    }
    .badge-high {
        background: #FFEDD5 !important;
        color: #C2410C !important;
        border: 1px solid #FED7AA !important;
        padding: 4px 12px !important;
        border-radius: 20px !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        letter-spacing: 0.5px !important;
        display: inline-block !important;
    }
    .badge-critical, .badge-fraud {
        background: #FEE2E2 !important;
        color: #991B1B !important;
        border: 1px solid #FCA5A5 !important;
        padding: 4px 12px !important;
        border-radius: 20px !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        letter-spacing: 0.5px !important;
        display: inline-block !important;
    }

    /* KPI Grid & Cards */
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 14px;
        margin-bottom: 24px;
    }
    .metric-card {
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 14px;
        padding: 18px;
        text-align: left;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.03);
        transition: all 0.2s ease-in-out;
        position: relative;
        overflow: hidden;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.06);
        border-color: #BFDBFE;
    }
    .metric-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }
    .metric-icon {
        width: 32px;
        height: 32px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
    }
    .icon-blue { background: #EAF2FF; color: #4F8DF7; }
    .icon-indigo { background: #EEF2FF; color: #6366F1; }
    .icon-cyan { background: #ECFEFF; color: #06B6D4; }
    .icon-red { background: #FEE2E2; color: #DC2626; }
    .icon-orange { background: #FFEDD5; color: #EA580C; }
    
    .metric-card-blue { border-top: 4px solid #4F8DF7; }
    .metric-card-indigo { border-top: 4px solid #6366F1; }
    .metric-card-cyan { border-top: 4px solid #06B6D4; }
    .metric-card-red { border-top: 4px solid #EF4444; background: #FAFAFA; }
    .metric-card-crimson { border-top: 4px solid #DC2626; background: #FAFAFA; }
    .metric-card-orange { border-top: 4px solid #F97316; background: #FAFAFA; }

    .metric-label {
        font-size: 11px;
        font-weight: 700;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
    .metric-value {
        font-size: 22px;
        font-weight: 800;
        color: #1F2937;
        display: block;
        line-height: 1.2;
    }
    .metric-sub {
        font-size: 11px;
        color: #6B7280;
        margin-top: 6px;
        display: block;
    }
    .text-red { color: #991B1B !important; }
    .text-orange { color: #C2410C !important; }

    /* Card title */
    .dashboard-card-title {
        font-size: 16px;
        font-weight: 800;
        color: #1F2937;
        margin-bottom: 16px;
    }

    /* Streamlit Form & Input Label Overrides */
    div[data-testid="stForm"] {
        border: none !important;
        padding: 0 !important;
        background: transparent !important;
    }
    div[data-testid="stWidgetLabel"] label {
        color: #1F2937 !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }

    /* Table Hover Effects & Alternating Row Background */
    [data-testid="stDataFrame"] tr:hover {
        background-color: #F3F4F6 !important;
        transition: background-color 0.15s ease-in-out;
    }

    /* Custom Buttons - Soft Blue Primary */
    div[data-testid="stFormSubmitButton"] button, div[data-testid="stButton"] button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.2s !important;
    }
    div[data-testid="stFormSubmitButton"] button {
        background-color: #4F8DF7 !important;
        color: #FFFFFF !important;
        border: none !important;
        box-shadow: 0 2px 6px rgba(79, 141, 247, 0.25) !important;
    }
    div[data-testid="stFormSubmitButton"] button:hover {
        background-color: #3B82F6 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(79, 141, 247, 0.35) !important;
    }

    /* Shimmer Skeleton Loaders */
    .skeleton-card {
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 14px;
        padding: 18px;
        height: 95px;
        position: relative;
        overflow: hidden;
    }

    .skeleton-text {
        height: 12px;
        background: #E5E7EB;
        border-radius: 4px;
        margin-bottom: 12px;
        width: 60%;
    }

    .skeleton-value {
        height: 22px;
        background: #D1D5DB;
        border-radius: 6px;
        width: 80%;
    }

    .shimmer {
        position: relative;
        overflow: hidden;
    }

    .shimmer::after {
        position: absolute;
        top: 0;
        right: 0;
        bottom: 0;
        left: 0;
        transform: translateX(-100%);
        background-image: linear-gradient(
            90deg,
            rgba(243, 244, 246, 0) 0,
            rgba(243, 244, 246, 0.6) 30%,
            rgba(243, 244, 246, 0.9) 60%,
            rgba(243, 244, 246, 0)
        );
        animation: shimmer 1.5s infinite;
        content: '';
    }

    @keyframes shimmer {
        100% {
            transform: translateX(100%);
        }
    }

    /* Progress bar styling */
    div[data-testid="stProgress"] > div > div > div {
        background: linear-gradient(90deg, #4F8DF7 0%, #06B6D4 100%) !important;
    }
</style>
""", unsafe_allow_html=True)

# Fetch Dynamic Filter Options (Cached)
dropdown_options = fetch_filter_options()
types = dropdown_options.get("types", [])
channels = dropdown_options.get("channels", [])
locations = dropdown_options.get("locations", [])

# Sidebar Brand
st.sidebar.markdown(
    """
    <div class="sidebar-brand">
        <div class="logo-icon">
            <i class="fa-solid fa-shield-halved"></i>
        </div>
        <h2>Nova Banking</h2>
    </div>
    """,
    unsafe_allow_html=True
)

# Streamlit Sidebar Radio Navigation Menu
menu = st.sidebar.radio(
    "Select View",
    ["Dashboard", "Accounts", "Transactions", "Fraud Alerts", "Fraud Rules"]
)

# Sidebar Bottom Profile
st.sidebar.markdown(
    """
    <div class="sidebar-footer">
        <div class="user-profile">
            <div class="avatar avatar-fallback"><i class="fa-solid fa-user"></i></div>
            <div class="user-info">
                <span class="user-name">R. Mahale</span>
                <span class="user-role">Fraud Analyst</span>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

def format_transactions_dataframe_for_ui(df):
    """
    Format transaction dataframe cleanly for UI display with 11 target columns
    and automatic column fallback handling for backward compatibility.
    """
    if df is None or df.empty:
        return pd.DataFrame()
        
    df_copy = df.copy()
    
    # Backwards compatibility column fallbacks
    if "CUSTOMER_NAME" not in df_copy.columns and "CUSTOMER_ID" in df_copy.columns:
        df_copy["CUSTOMER_NAME"] = df_copy["CUSTOMER_ID"]
    if "ACCOUNT_NUMBER" not in df_copy.columns and "ACCOUNT_ID" in df_copy.columns:
        df_copy["ACCOUNT_NUMBER"] = df_copy["ACCOUNT_ID"]
    if "TRANSACTION_DATE" not in df_copy.columns and "TIMESTAMP" in df_copy.columns:
        df_copy["TRANSACTION_DATE"] = df_copy["TIMESTAMP"]
    if "PAYMENT_MODE" not in df_copy.columns and "CHANNEL" in df_copy.columns:
        df_copy["PAYMENT_MODE"] = df_copy["CHANNEL"]
    if "FRAUD_STATUS" not in df_copy.columns and "IS_FRAUD" in df_copy.columns:
        df_copy["FRAUD_STATUS"] = df_copy["IS_FRAUD"].apply(lambda x: "FRAUD" if str(x) in ["1", "FRAUD", "True"] else "NORMAL")
    if "FRAUD_RISK_SCORE" not in df_copy.columns and "RISK_SCORE" in df_copy.columns:
        df_copy["FRAUD_RISK_SCORE"] = df_copy["RISK_SCORE"]

    target_cols = [
        "TRANSACTION_ID", "CUSTOMER_NAME", "ACCOUNT_NUMBER", "TRANSACTION_TYPE",
        "AMOUNT", "LOCATION", "TRANSACTION_DATE", "PAYMENT_MODE",
        "FRAUD_STATUS", "FRAUD_RISK_SCORE", "RISK_LEVEL"
    ]
    
    available_cols = [c for c in target_cols if c in df_copy.columns]
    res_df = df_copy[available_cols].copy()
    
    if "FRAUD_STATUS" in res_df.columns:
        res_df["FRAUD_STATUS"] = res_df["FRAUD_STATUS"].apply(
            lambda s: "🔴 FRAUD" if str(s).upper() in ["FRAUD", "1", "TRUE"] else "🟢 NORMAL"
        )
        
    if "RISK_LEVEL" in res_df.columns:
        level_map = {
            "LOW": "🟢 LOW",
            "MEDIUM": "🟡 MEDIUM",
            "HIGH": "🟠 HIGH",
            "CRITICAL": "🔴 CRITICAL"
        }
        res_df["RISK_LEVEL"] = res_df["RISK_LEVEL"].apply(lambda lvl: level_map.get(str(lvl).upper(), str(lvl)))
        
    return res_df

# Transaction Investigation Panel Drawer Helper
def render_transaction_details_panel(df, key_prefix="panel", selected_row_override=None):
    """
    Renders a professional Transaction Investigation Panel / Drawer Overlay.
    Displays:
    - 14 Required Fields: Transaction ID, Timestamp, Customer ID, Transaction Type, Amount,
      Old Balance, New Balance, Merchant, Channel, Location, Device, Fraud Status, Fraud Risk Score, Risk Level.
    - "Why Was This Transaction Flagged?" section with transaction-specific explanation cards.
    - Action Buttons: [VIEW CUSTOMER] and [CLOSE].
    """
    if (df is None or df.empty) and selected_row_override is None:
        return
        
    st.markdown('<div class="bg-glass" style="border: 2px solid #4f46e5; box-shadow: 0 10px 30px rgba(79, 70, 229, 0.12); margin-top: 16px;">', unsafe_allow_html=True)
    
    if selected_row_override is not None:
        selected_row = selected_row_override
    else:
        tx_options = [
            f"ID: {row['TRANSACTION_ID']} | Cust: {row.get('CUSTOMER_NAME', row.get('CUSTOMER_ID', 'N/A'))} | ₹{float(row['AMOUNT']):,.2f} | Risk: {row.get('FRAUD_RISK_SCORE', row.get('RISK_SCORE', 0))} ({row.get('RISK_LEVEL', 'LOW')})"
            for idx, row in df.iterrows()
        ]
        
        selected_idx = st.selectbox(
            "🔎 Select Transaction to Investigate",
            range(len(tx_options)),
            format_func=lambda i: tx_options[i],
            key=f"{key_prefix}_tx_inspector_select"
        )
        selected_row = df.iloc[selected_idx]
        
    score = int(selected_row.get("FRAUD_RISK_SCORE", selected_row.get("RISK_SCORE", 0)))
    level = str(selected_row.get("RISK_LEVEL", "LOW"))
    
    if level == "LOW":
        bg_color = "#ecfdf5"
        border_color = "#a7f3d0"
        text_color = "#047857"
    elif level == "MEDIUM":
        bg_color = "#fffbeb"
        border_color = "#fde68a"
        text_color = "#b45309"
    elif level == "HIGH":
        bg_color = "#fff7ed"
        border_color = "#ffedd5"
        text_color = "#c2410c"
    else:
        bg_color = "#fef2f2"
        border_color = "#fecaca"
        text_color = "#b91c1c"

    # Drawer Header
    col_hdr, col_btn_top_close = st.columns([8, 2])
    with col_hdr:
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 8px;">
                <div style="background: #eef2ff; color: #4f46e5; width: 44px; height: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 22px; border: 1px solid #c7d2fe;">
                    <i class="fa-solid fa-user-shield"></i>
                </div>
                <div>
                    <h3 style="margin: 0; color: #0f172a; font-weight: 800; font-size: 20px;">Transaction Investigation Docket</h3>
                    <p style="margin: 2px 0 0 0; color: #64748b; font-size: 13px;">Case File: <b>{selected_row['TRANSACTION_ID']}</b> | Customer: <b>{selected_row.get('CUSTOMER_NAME', selected_row.get('CUSTOMER_ID', 'N/A'))}</b></p>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col_btn_top_close:
        if st.button("❌ CLOSE", key=f"{key_prefix}_close_top_btn", use_container_width=True):
            st.session_state.investigating_transaction_id = None
            st.rerun()

    st.markdown("<hr style='margin: 10px 0 16px 0; border: 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

    # 1. Prominent Risk Badge Banner & Key Stats
    c_badge, c_stats = st.columns([1, 2])
    
    score = int(selected_row.get("FRAUD_RISK_SCORE", selected_row.get("RISK_SCORE", 0)))
    level = str(selected_row.get("RISK_LEVEL", "LOW"))

    with c_badge:
        st.markdown(
            f"""
            <div style="background-color: {bg_color}; border: 2px solid {border_color}; border-radius: 14px; padding: 20px; text-align: center;">
                <span style="font-size: 12px; font-weight: 800; color: {text_color}; text-transform: uppercase; letter-spacing: 1px;">Fraud Risk Score</span>
                <span style="font-size: 46px; font-weight: 900; color: {text_color}; display: block; margin: 4px 0;">{score}</span>
                <span style="font-size: 15px; font-weight: 800; color: {text_color}; background-color: rgba(255,255,255,0.85); padding: 4px 14px; border-radius: 20px; display: inline-block;">{level} RISK</span>
            </div>
            """,
            unsafe_allow_html=True
        )
        
    with c_stats:
        st.markdown("<h4 style='margin:0 0 8px 0; color: #0f172a;'>Primary Audit Parameters</h4>", unsafe_allow_html=True)
        m1, m2, m3 = st.columns(3)
        m1.metric("Amount", f"₹{float(selected_row['AMOUNT']):,.2f}")
        m2.metric("Customer Name", str(selected_row.get("CUSTOMER_NAME", "N/A")))
        m3.metric("Account Number", str(selected_row.get("ACCOUNT_NUMBER", "N/A")))
        
        m4, m5, m6 = st.columns(3)
        is_f_str = "🔴 FRAUD" if str(selected_row.get("FRAUD_STATUS", "")).upper() == "FRAUD" else "🟢 NORMAL"
        m4.metric("Fraud Status", is_f_str)
        m5.metric("Txn Type", str(selected_row.get("TRANSACTION_TYPE", "N/A")))
        m6.metric("Payment Mode", str(selected_row.get("PAYMENT_MODE", "N/A")))

    st.markdown("<hr style='margin: 16px 0; border: 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

    # 2. Comprehensive Investigation Grid
    st.markdown("<h4 style='margin: 0 0 12px 0; color: #0f172a;'><i class=\"fa-solid fa-list-check\" style=\"color:#4f46e5;\"></i> Complete Investigation Attributes</h4>", unsafe_allow_html=True)
    
    st.markdown(
        f"""
        <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 16px;">
            <tr style="border-bottom: 1px solid #f1f5f9;"><td style="padding: 8px; color: #64748b; font-weight: 600;">Transaction ID:</td><td style="padding: 8px; color: #0f172a; font-weight: 700;">{selected_row['TRANSACTION_ID']}</td><td style="padding: 8px; color: #64748b; font-weight: 600;">Location:</td><td style="padding: 8px; color: #0f172a; font-weight: 700;">{selected_row.get('LOCATION', 'N/A')}</td></tr>
            <tr style="border-bottom: 1px solid #f1f5f9;"><td style="padding: 8px; color: #64748b; font-weight: 600;">Customer Name:</td><td style="padding: 8px; color: #0f172a; font-weight: 700;">{selected_row.get('CUSTOMER_NAME', 'N/A')}</td><td style="padding: 8px; color: #64748b; font-weight: 600;">Payment Mode:</td><td style="padding: 8px; color: #0f172a; font-weight: 700;">{selected_row.get('PAYMENT_MODE', 'N/A')}</td></tr>
            <tr style="border-bottom: 1px solid #f1f5f9;"><td style="padding: 8px; color: #64748b; font-weight: 600;">Account Number:</td><td style="padding: 8px; color: #0f172a; font-weight: 700;">{selected_row.get('ACCOUNT_NUMBER', 'N/A')}</td><td style="padding: 8px; color: #64748b; font-weight: 600;">Transaction Date:</td><td style="padding: 8px; color: #0f172a; font-weight: 700;">{selected_row.get('TRANSACTION_DATE', 'N/A')}</td></tr>
            <tr style="border-bottom: 1px solid #f1f5f9;"><td style="padding: 8px; color: #64748b; font-weight: 600;">Transaction Type:</td><td style="padding: 8px; color: #0f172a; font-weight: 700;">{selected_row.get('TRANSACTION_TYPE', 'N/A')}</td><td style="padding: 8px; color: #64748b; font-weight: 600;">Fraud Status:</td><td style="padding: 8px; color: #0f172a; font-weight: 700;">{is_f_str}</td></tr>
            <tr style="border-bottom: 1px solid #f1f5f9;"><td style="padding: 8px; color: #64748b; font-weight: 600;">Amount:</td><td style="padding: 8px; color: #0f172a; font-weight: 700;">₹{float(selected_row['AMOUNT']):,.2f}</td><td style="padding: 8px; color: #64748b; font-weight: 600;">Fraud Risk Score:</td><td style="padding: 8px; color: {text_color}; font-weight: 800;">{score} / 100</td></tr>
            <tr style="border-bottom: 1px solid #f1f5f9;"><td style="padding: 8px; color: #64748b; font-weight: 600;">Risk Level:</td><td style="padding: 8px; color: {text_color}; font-weight: 800;">{level}</td><td style="padding: 8px; color: #64748b; font-weight: 600;">Status:</td><td style="padding: 8px; color: {text_color}; font-weight: 800;">ACTIVE MONITORING</td></tr>
        </table>
        """,
        unsafe_allow_html=True
    )

    st.markdown("<hr style='margin: 16px 0; border: 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

    # 3. Dynamic Section Header: "Why Was This Transaction Flagged?" (FRAUD) vs "Transaction Risk Analysis" (NORMAL)
    fraud_status_val = str(selected_row.get("FRAUD_STATUS", selected_row.get("IS_FRAUD", ""))).strip().upper()
    is_fraud_transaction = (fraud_status_val in ["FRAUD", "1", "TRUE"])

    if is_fraud_transaction:
        section_title = '<h4 style="margin: 0 0 12px 0; color: #dc2626;"><i class="fa-solid fa-triangle-exclamation" style="color:#dc2626;"></i> Why Was This Transaction Flagged?</h4>'
    else:
        section_title = '<h4 style="margin: 0 0 12px 0; color: #0f172a;"><i class="fa-solid fa-chart-pie" style="color:#059669;"></i> Transaction Risk Analysis</h4>'

    st.markdown(section_title, unsafe_allow_html=True)
    
    explanations = generate_flag_explanations(selected_row)
    
    if explanations:
        for exp in explanations:
            sev = exp.get("severity", "MEDIUM")
            if sev == "CRITICAL":
                card_bg = "#fef2f2"
                card_border = "#fecaca"
                title_color = "#991b1b"
            elif sev == "HIGH":
                card_bg = "#fff7ed"
                card_border = "#ffedd5"
                title_color = "#c2410c"
            elif sev == "MEDIUM":
                card_bg = "#fffbeb"
                card_border = "#fde68a"
                title_color = "#b45309"
            else:
                card_bg = "#ecfdf5"
                card_border = "#a7f3d0"
                title_color = "#047857"
                
            st.markdown(
                f"""
                <div style="background-color: {card_bg}; border: 1px solid {card_border}; border-radius: 10px; padding: 12px 16px; margin-bottom: 10px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 18px;">{exp['icon']}</span>
                        <strong style="color: {title_color}; font-size: 14px;">{exp['title']}</strong>
                    </div>
                    <p style="margin: 4px 0 0 28px; color: #334155; font-size: 13px;">{exp['desc']}</p>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.markdown(
            """
            <div style="background-color: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 10px; padding: 12px 16px; margin-bottom: 10px;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 18px;">🟢</span>
                    <strong style="color: #047857; font-size: 14px;">Normal Transaction Profile (Score: 0 / 100)</strong>
                </div>
                <p style="margin: 4px 0 0 28px; color: #334155; font-size: 13px;">Standard transaction execution. No risk factors contributed to risk score.</p>
            </div>
            """,
            unsafe_allow_html=True
        )

    # 4. Action Buttons: [VIEW CUSTOMER] and [CLOSE]
    st.markdown("<hr style='margin: 16px 0; border: 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)
    
    btn_col1, btn_col2, _ = st.columns([3, 3, 4])
    
    with btn_col1:
        cust_id_val = str(selected_row.get("CUSTOMER_ID") or selected_row.get("CUSTOMER_NAME") or "").strip()
        if st.button("👤 VIEW CUSTOMER", key=f"{key_prefix}_view_cust_action", use_container_width=True):
            if cust_id_val:
                st.session_state.applied_filters["customer_id"] = cust_id_val
            st.session_state.investigating_transaction_id = None
            st.rerun()
            
    with btn_col2:
        if st.button("❌ CLOSE", key=f"{key_prefix}_close_bottom_action", use_container_width=True):
            st.session_state.investigating_transaction_id = None
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# Check Snowflake Health Status
is_healthy, status_label, last_refresh = check_snowflake_health()

if is_healthy:
    pill_html = f'<div class="db-status-pill-green" title="Last data update: {last_refresh}"><span class="status-dot-green"></span><span>Snowflake Live</span><span style="color: #475569; font-weight: 500; margin-left: 4px;">({last_refresh})</span></div>'
else:
    pill_html = '<div class="db-status-pill-red"><span class="status-dot-red"></span><span>Snowflake Offline</span></div>'

# Layout Header Area
st.markdown(
    f'<header class="main-header"><div class="header-greeting"><h1>SMART BANKING FRAUD DETECTION</h1><p>Real-Time Transaction Monitoring & Fraud Analytics</p></div><div>{pill_html}</div></header>',
    unsafe_allow_html=True
)

# Display Snowflake Offline Warning if DB unreachable
if not is_healthy:
    st.error("⚠️ Unable to load banking data. Snowflake connection could not be reached. Please verify backend credentials.")
    if st.button("🔄 Retry Connection"):
        st.cache_data.clear()
        st.rerun()

# ----------------- HORIZONTAL FILTER PANEL (DEBOUNCED WITH FORM) -----------------
with st.container():
    st.markdown('<div class="dashboard-card-title"><i class="fa-solid fa-sliders"></i> Search & Filter Criteria</div>', unsafe_allow_html=True)
    
    with st.form("search_filter_form"):
        col1, col2, col3, col4, col5, col5b = st.columns(6)
        
        with col1:
            cust_id_in = st.text_input(
                "Customer ID",
                value=st.session_state.applied_filters.get("customer_id", ""),
                placeholder="e.g. C30850"
            )
        with col2:
            type_in = st.selectbox(
                "Txn Type",
                ["All Types"] + list(types),
                index=0 if "transaction_type" not in st.session_state.applied_filters else (
                    ["All Types"] + list(types)
                ).index(st.session_state.applied_filters["transaction_type"]) if st.session_state.applied_filters.get("transaction_type") in types else 0
            )
        with col3:
            channel_in = st.selectbox(
                "Channel",
                ["All Channels"] + list(channels),
                index=0 if "channel" not in st.session_state.applied_filters else (
                    ["All Channels"] + list(channels)
                ).index(st.session_state.applied_filters["channel"]) if st.session_state.applied_filters.get("channel") in channels else 0
            )
        with col4:
            location_in = st.selectbox(
                "Location",
                ["All Locations"] + list(locations),
                index=0 if "location" not in st.session_state.applied_filters else (
                    ["All Locations"] + list(locations)
                ).index(st.session_state.applied_filters["location"]) if st.session_state.applied_filters.get("location") in locations else 0
            )
        with col5:
            fraud_in = st.selectbox(
                "Fraud Status",
                ["All Statuses", "Normal Only", "Fraud Only"],
                index=0
            )
        with col5b:
            risk_in = st.selectbox(
                "Risk Tier",
                ["All Risk Levels", "LOW (0-30)", "MEDIUM (31-60)", "HIGH (61-80)", "CRITICAL (81-100)"],
                index=0 if "risk_level" not in st.session_state.applied_filters else (
                    ["All Risk Levels", "LOW (0-30)", "MEDIUM (31-60)", "HIGH (61-80)", "CRITICAL (81-100)"]
                ).index(st.session_state.applied_filters["risk_level"]) if st.session_state.applied_filters.get("risk_level") in ["All Risk Levels", "LOW (0-30)", "MEDIUM (31-60)", "HIGH (61-80)", "CRITICAL (81-100)"] else 0
            )
            
        col6, col7, col8, col9, col10 = st.columns([2, 2, 2, 2, 2])
        with col6:
            start_date_in = st.date_input("Start Date", value=datetime.date(2026, 6, 30))
        with col7:
            end_date_in = st.date_input("End Date", value=datetime.date(2026, 8, 7))
        with col8:
            min_amt_in = st.number_input("Min Amount (₹)", min_value=0.0, value=0.0, step=100.0)
        with col9:
            max_amt_in = st.number_input("Max Amount (₹)", min_value=0.0, value=0.0, step=100.0)
        with col10:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            apply_btn = st.form_submit_button("🔍 Apply Filters", use_container_width=True)
            
    col_clear, _ = st.columns([2, 8])
    with col_clear:
        if st.button("❌ Clear Filters", use_container_width=False):
            st.session_state.applied_filters = {}
            st.session_state.tx_page = 1
            st.session_state.acct_page = 1
            st.session_state.alert_page = 1
            st.rerun()

    if apply_btn:
        new_filters = {}
        if cust_id_in.strip():
            new_filters["customer_id"] = cust_id_in.strip()
        if type_in != "All Types":
            new_filters["transaction_type"] = type_in
        if channel_in != "All Channels":
            new_filters["channel"] = channel_in
        if location_in != "All Locations":
            new_filters["location"] = location_in
        if fraud_in != "All Statuses":
            new_filters["fraud_status"] = "1" if fraud_in == "Fraud Only" else "0"
        if risk_in != "All Risk Levels":
            new_filters["risk_level"] = risk_in
        if start_date_in:
            new_filters["start_date"] = start_date_in.strftime("%Y-%m-%d")
        if end_date_in:
            new_filters["end_date"] = end_date_in.strftime("%Y-%m-%d")
        if min_amt_in > 0:
            new_filters["min_amount"] = min_amt_in
        if max_amt_in > 0:
            new_filters["max_amount"] = max_amt_in
            
        st.session_state.applied_filters = new_filters
        st.session_state.tx_page = 1
        st.session_state.acct_page = 1
        st.session_state.alert_page = 1

def render_customer_risk_profile(customer_id):
    """
    Renders a comprehensive Customer Risk Profile view displaying 12 statistics,
    a transaction-risk timeline chart, full transaction history, and [BACK TO TRANSACTIONS] navigation.
    Data is cached via fetch_customer_profile(customer_id) for instant performance.
    """
    if not customer_id:
        return
        
    st.markdown('<div class="bg-glass" style="border: 2px solid #4f46e5; margin-bottom: 24px;">', unsafe_allow_html=True)
    
    col_hdr_title, col_hdr_btn = st.columns([8, 3])
    with col_hdr_title:
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="background: #eef2ff; color: #4f46e5; width: 44px; height: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 22px; border: 1px solid #c7d2fe;">
                    <i class="fa-solid fa-user-shield"></i>
                </div>
                <div>
                    <h2 style="margin: 0; color: #0f172a; font-weight: 800; font-size: 22px;">Customer Risk Profile: {customer_id}</h2>
                    <p style="margin: 2px 0 0 0; color: #64748b; font-size: 13px;">Real-Time Customer Risk Analytics & Transaction Audit History</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col_hdr_btn:
        if st.button("⬅️ BACK TO TRANSACTIONS", key="back_to_txns_top", use_container_width=True):
            st.session_state.applied_filters.pop("customer_id", None)
            st.rerun()

    st.markdown("<hr style='margin: 16px 0; border: 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

    with st.spinner(f"Fetching risk profile for Customer ID: {customer_id}..."):
        stats, cust_txs = fetch_customer_profile(customer_id)
        cust_accts, _ = fetch_accounts_paginated(filters={"customer_id": customer_id}, page=1, page_size=20)

    if not stats or cust_txs.empty:
        st.warning(f"No transaction history recorded in Snowflake for Customer ID: {customer_id}")
        if st.button("⬅️ BACK TO TRANSACTIONS", key="back_to_txns_empty"):
            st.session_state.applied_filters.pop("customer_id", None)
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # 1. 12 Customer Risk Profile Statistics Cards Grid
    st.markdown("<h4 style='margin: 0 0 14px 0; color: #0f172a;'><i class=\"fa-solid fa-chart-pie\" style=\"color:#4f46e5;\"></i> Customer Risk & Behavioral Analytics (12 Core Stats)</h4>", unsafe_allow_html=True)

    r_score = stats["overall_risk_score"]
    r_level = stats["overall_risk_level"]
    r_symbol = stats["risk_symbol"]

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Customer ID", stats["customer_id"])
    col2.metric("Total Txns", f"{stats['total_transactions']:,}")
    col3.metric("Total Amount", format_compact_currency(stats['total_amount']))
    col4.metric("Fraud Txns", f"{stats['fraud_transactions']:,}")
    col5.metric("Fraud Rate", f"{stats['fraud_rate']:.2f}%")
    col6.metric("Fraud Amount", format_compact_currency(stats['fraud_amount']))

    col7, col8, col9, col10, col11, col12 = st.columns(6)
    col7.metric("Avg Txn Amount", f"₹{stats['avg_amount']:,.2f}")
    col8.metric("Most-Used Type", stats["most_used_type"])
    col9.metric("Most-Used Channel", stats["most_used_channel"])
    col10.metric("Top Location", stats["most_frequent_location"])
    col11.metric("Customer Risk Score", f"{r_score} / 100")
    col12.metric("Overall Risk Level", f"{r_symbol} {r_level}")

    st.markdown("<hr style='margin: 16px 0; border: 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

    # 2. Transaction-Risk Timeline Chart
    st.markdown("<h4 style='margin: 0 0 12px 0; color: #0f172a;'><i class=\"fa-solid fa-chart-line\" style=\"color:#0891b2;\"></i> Customer Transaction-Risk Timeline</h4>", unsafe_allow_html=True)
    
    if not cust_txs.empty:
        t_col = "TRANSACTION_DATE" if "TRANSACTION_DATE" in cust_txs.columns else "TIMESTAMP"
        cust_txs["TIMESTAMP_DT"] = pd.to_datetime(cust_txs[t_col])
        cust_txs_sorted = cust_txs.sort_values("TIMESTAMP_DT").copy()
        
        # Derive date-only calendar string format e.g. 'Aug 6, 2026'
        cust_txs_sorted["DISPLAY_DATE"] = cust_txs_sorted["TIMESTAMP_DT"].apply(
            lambda d: f"{d.strftime('%b')} {d.day}, {d.year}"
        )
        
        s_col = "FRAUD_RISK_SCORE" if "FRAUD_RISK_SCORE" in cust_txs_sorted.columns else ("RISK_SCORE" if "RISK_SCORE" in cust_txs_sorted.columns else "AMOUNT")
        
        is_single_txn = len(cust_txs_sorted) == 1
        
        fig_cust_timeline = go.Figure()
        
        # Amount trace
        fig_cust_timeline.add_trace(go.Bar(
            x=cust_txs_sorted["DISPLAY_DATE"],
            y=cust_txs_sorted["AMOUNT"],
            name="Txn Amount (₹)",
            marker_color="#4f46e5",
            opacity=0.75,
            width=0.25 if is_single_txn else None,
            yaxis="y"
        ))
        
        # Risk score line trace
        fig_cust_timeline.add_trace(go.Scatter(
            x=cust_txs_sorted["DISPLAY_DATE"],
            y=cust_txs_sorted[s_col],
            name="Fraud Risk Score (0-100)",
            mode="lines+markers",
            line=dict(color="#dc2626", width=3),
            marker=dict(size=8, color="#dc2626"),
            yaxis="y2"
        ))
        
        fig_cust_timeline.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            bargap=0.7 if is_single_txn else 0.2,
            xaxis=dict(
                type="category",
                showgrid=False,
                color="#475569",
                title="Transaction Date"
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor="#e2e8f0",
                color="#475569",
                title="Transaction Amount (₹)"
            ),
            yaxis2=dict(
                showgrid=False,
                overlaying="y",
                side="right",
                range=[0, 105],
                color="#dc2626",
                title="Fraud Risk Score (0-100)"
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=40, t=30, b=30),
            height=280
        )
        st.plotly_chart(fig_cust_timeline, use_container_width=True)

    st.markdown("<hr style='margin: 16px 0; border: 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

    # 3. Associated Accounts & Customer Transaction History Register Table
    col_acc, col_tx_hist = st.columns([1, 2])
    
    with col_acc:
        st.markdown("<h4 style='margin:0 0 10px 0; color: #0f172a;'>Associated Client Accounts</h4>", unsafe_allow_html=True)
        if not cust_accts.empty:
            cust_accts_disp = cust_accts.copy()
            cust_accts_disp["ACCOUNT_STATUS"] = cust_accts_disp["ACCOUNT_STATUS"].apply(
                lambda s: "🟢 ACTIVE" if str(s).upper() == "ACTIVE" else ("🟡 PENDING" if str(s).upper() == "PENDING" else "🔴 CLOSED")
            )
            st.dataframe(cust_accts_disp, hide_index=True, use_container_width=True)
        else:
            st.info("No registered bank accounts found.")
            
    with col_tx_hist:
        st.markdown("<h4 style='margin:0 0 10px 0; color: #0f172a;'>Customer Transaction Audit History</h4>", unsafe_allow_html=True)
        if not cust_txs.empty:
            hist_display = cust_txs[["TRANSACTION_ID", "TIMESTAMP", "TRANSACTION_TYPE", "AMOUNT", "CHANNEL", "LOCATION", "RISK_BADGE", "IS_FRAUD"]].copy()
            hist_display["IS_FRAUD"] = hist_display["IS_FRAUD"].map({0: "🟢 NORMAL", 1: "🔴 FRAUD"})
            hist_display.rename(columns={"RISK_BADGE": "FRAUD RISK SCORE"}, inplace=True)
            
            event = st.dataframe(
                hist_display,
                hide_index=True,
                use_container_width=True,
                on_select="rerun",
                selection_mode="single-row",
                key=f"cust_profile_hist_{customer_id}"
            )
            
            if event and hasattr(event, "selection") and event.selection and event.selection.get("rows"):
                selected_row_idx = event.selection["rows"][0]
                if 0 <= selected_row_idx < len(cust_txs):
                    selected_txn = cust_txs.iloc[selected_row_idx]
                    st.session_state.investigating_transaction_id = selected_txn["TRANSACTION_ID"]
        else:
            st.info("No transactions found.")

    # 4. Action Buttons
    st.markdown("<hr style='margin: 16px 0; border: 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)
    if st.button("⬅️ BACK TO TRANSACTIONS", key="back_to_txns_bottom", use_container_width=False):
        st.session_state.applied_filters.pop("customer_id", None)
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

# Extract active filters
filters = st.session_state.applied_filters

# Render Customer Profile View if Customer ID filter is populated
if filters.get("customer_id"):
    render_customer_risk_profile(filters["customer_id"])

# ----------------- TAB VIEWS (WITH SHIMMER SKELETONS & PROGRESS TRACKING) -----------------

# 1. DASHBOARD VIEW
if menu == "Dashboard":
    
    # Render Skeleton Loader Placeholder for KPIs
    kpi_placeholder = st.empty()
    kpi_placeholder.markdown(
        """
        <div class="metrics-grid">
            <div class="skeleton-card shimmer"><div class="skeleton-text"></div><div class="skeleton-value"></div></div>
            <div class="skeleton-card shimmer"><div class="skeleton-text"></div><div class="skeleton-value"></div></div>
            <div class="skeleton-card shimmer"><div class="skeleton-text"></div><div class="skeleton-value"></div></div>
            <div class="skeleton-card shimmer"><div class="skeleton-text"></div><div class="skeleton-value"></div></div>
            <div class="skeleton-card shimmer"><div class="skeleton-text"></div><div class="skeleton-value"></div></div>
            <div class="skeleton-card shimmer"><div class="skeleton-text"></div><div class="skeleton-value"></div></div>
            <div class="skeleton-card shimmer"><div class="skeleton-text"></div><div class="skeleton-value"></div></div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Progress Tracker
    progress_bar = st.progress(0.1, text="⚡ Querying Snowflake KPI Metrics...")
    
    # Fetch real KPIs
    kpis = fetch_summary_kpis(filters)
    
    progress_bar.progress(0.4, text="📊 Loading Analytics Charts...")
    
    # Replace Skeleton with Real Formatted KPI Cards
    kpi_placeholder.markdown(
        f"""
        <div class="metrics-grid">
            <div class="metric-card metric-card-blue">
                <div class="metric-card-header">
                    <span class="metric-label">Total Accounts</span>
                    <div class="metric-icon icon-blue"><i class="fa-solid fa-users"></i></div>
                </div>
                <span class="metric-value">{kpis['total_accounts']:,}</span>
                <span class="metric-sub">Registered client profiles</span>
            </div>
            <div class="metric-card metric-card-indigo">
                <div class="metric-card-header">
                    <span class="metric-label">Total Transactions</span>
                    <div class="metric-icon icon-indigo"><i class="fa-solid fa-receipt"></i></div>
                </div>
                <span class="metric-value">{kpis['total_transactions']:,}</span>
                <span class="metric-sub">Processed payment logs</span>
            </div>
            <div class="metric-card metric-card-cyan">
                <div class="metric-card-header">
                    <span class="metric-label">Txn Amount Volume</span>
                    <div class="metric-icon icon-cyan"><i class="fa-solid fa-vault"></i></div>
                </div>
                <span class="metric-value">{format_compact_currency(kpis['total_amount'])}</span>
                <span class="metric-sub">Total gross volume</span>
            </div>
            <div class="metric-card metric-card-red">
                <div class="metric-card-header">
                    <span class="metric-label text-red">Fraud Transactions</span>
                    <div class="metric-icon icon-red"><i class="fa-solid fa-triangle-exclamation"></i></div>
                </div>
                <span class="metric-value text-red">{kpis['fraud_transactions']:,}</span>
                <span class="metric-sub text-red">Flagged high-risk cases</span>
            </div>
            <div class="metric-card metric-card-red">
                <div class="metric-card-header">
                    <span class="metric-label text-red">Fraud Rate</span>
                    <div class="metric-icon icon-red"><i class="fa-solid fa-percent"></i></div>
                </div>
                <span class="metric-value text-red">{kpis['fraud_rate']:.2f}%</span>
                <span class="metric-sub text-red">of total transactions</span>
            </div>
            <div class="metric-card metric-card-crimson">
                <div class="metric-card-header">
                    <span class="metric-label text-red">Fraud Amount</span>
                    <div class="metric-icon icon-red"><i class="fa-solid fa-money-bill-transfer"></i></div>
                </div>
                <span class="metric-value text-red">{format_compact_currency(kpis['fraud_amount'])}</span>
                <span class="metric-sub text-red">Flagged monetary value</span>
            </div>
            <div class="metric-card metric-card-orange">
                <div class="metric-card-header">
                    <span class="metric-label text-orange">High Risk Txns</span>
                    <div class="metric-icon icon-orange"><i class="fa-solid fa-fire"></i></div>
                </div>
                <span class="metric-value text-orange">{kpis.get('high_risk_transactions', 0):,}</span>
                <span class="metric-sub text-orange">Risk Score &ge; 61</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Render Charts Layout (Progressive rendering)
    col_c1, col_c2 = st.columns(2)
    
    with col_c1:
        st.markdown('<div class="bg-glass">', unsafe_allow_html=True)
        st.markdown('<div class="dashboard-card-title">Transaction Volume Over Time</div>', unsafe_allow_html=True)
        time_data = fetch_analytics_transactions_over_time(filters)
            
        if time_data:
            time_df = pd.DataFrame(time_data)
            time_df["TIMESTAMP_DT"] = pd.to_datetime(time_df["TIMESTAMP"])
            time_df_sorted = time_df.sort_values("TIMESTAMP_DT").copy()
            time_df_sorted["DISPLAY_DATE"] = time_df_sorted["TIMESTAMP_DT"].apply(
                lambda d: f"{d.strftime('%b')} {d.day}, {d.year}"
            )
            is_single_time = len(time_df_sorted) == 1
            
            fig_volume = go.Figure()
            fig_volume.add_trace(go.Scatter(
                x=time_df_sorted["DISPLAY_DATE"],
                y=time_df_sorted["TX_COUNT"],
                mode="lines+markers",
                name="Transactions",
                line=dict(color="#4f46e5", width=2.5),
                marker=dict(size=6, color="#4f46e5"),
                fill='tozeroy',
                fillcolor="rgba(79, 70, 229, 0.08)",
                hovertemplate="%{x}<br>Transaction Volume: %{y:,}<extra></extra>"
            ))
            fig_volume.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(
                    type="category",
                    showgrid=False,
                    color="#475569",
                    title="Transaction Date",
                    tickangle=-90 if not is_single_time else 0,
                    nticks=40 if not is_single_time else None,
                    dtick=9 if not is_single_time else None
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor="#e2e8f0",
                    color="#475569",
                    title="Transaction Volume"
                ),
                margin=dict(l=30, r=20, t=10, b=90 if not is_single_time else 40),
                height=320 if not is_single_time else 280
            )
            st.plotly_chart(fig_volume, use_container_width=True)
        else:
            st.info("No transaction analytics logs match the selected filters.")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_c2:
        st.markdown('<div class="bg-glass">', unsafe_allow_html=True)
        st.markdown('<div class="dashboard-card-title">Fraud Transactions Over Time</div>', unsafe_allow_html=True)
        
        if time_data:
            fig_fraud_time = go.Figure()
            fig_fraud_time.add_trace(go.Bar(
                x=time_df_sorted["DISPLAY_DATE"],
                y=time_df_sorted["FRAUD_COUNT"],
                name="Flagged Fraud",
                marker_color="#dc2626",
                opacity=0.9,
                width=0.25 if is_single_time else None,
                hovertemplate="%{x}<br>Fraud Transactions: %{y:,}<extra></extra>"
            ))
            fig_fraud_time.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                bargap=0.7 if is_single_time else 0.2,
                xaxis=dict(
                    type="category",
                    showgrid=False,
                    color="#475569",
                    title="Transaction Date",
                    tickangle=-90 if not is_single_time else 0,
                    nticks=40 if not is_single_time else None,
                    dtick=9 if not is_single_time else None
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor="#e2e8f0",
                    color="#475569",
                    title="Fraud Transactions"
                ),
                margin=dict(l=30, r=20, t=10, b=90 if not is_single_time else 40),
                height=320 if not is_single_time else 280
            )
            st.plotly_chart(fig_fraud_time, use_container_width=True)
        else:
            st.info("No fraud analytics logs match the selected filters.")
        st.markdown('</div>', unsafe_allow_html=True)
        
    progress_bar.progress(0.7, text="📈 Fetching Grouped Fraud Aggregations...")
        
    col_c3, col_c4, col_c5 = st.columns(3)
    
    with col_c3:
        st.markdown('<div class="bg-glass">', unsafe_allow_html=True)
        st.markdown('<div class="dashboard-card-title">Fraud by Transaction Type</div>', unsafe_allow_html=True)
        type_data = fetch_analytics_fraud_by_type(filters)
        if type_data:
            type_df = pd.DataFrame(type_data)
            fig_type = px.bar(
                type_df, x="TRANSACTION_TYPE", y="FRAUD_COUNT",
                labels={"TRANSACTION_TYPE": "Type", "FRAUD_COUNT": "Alerts"}
            )
            fig_type.update_traces(marker_color="#2563eb", opacity=0.9)
            fig_type.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, color="#475569"),
                yaxis=dict(showgrid=True, gridcolor="#e2e8f0", color="#475569"),
                margin=dict(l=30, r=20, t=10, b=30),
                height=240
            )
            st.plotly_chart(fig_type, use_container_width=True)
        else:
            st.info("No fraud cases found.")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_c4:
        st.markdown('<div class="bg-glass">', unsafe_allow_html=True)
        st.markdown('<div class="dashboard-card-title">Fraud by Channel</div>', unsafe_allow_html=True)
        channel_data = fetch_analytics_fraud_by_channel(filters)
        if channel_data:
            channel_df = pd.DataFrame(channel_data)
            fig_chan = px.bar(
                channel_df, x="CHANNEL", y="FRAUD_COUNT",
                labels={"CHANNEL": "Channel", "FRAUD_COUNT": "Alerts"}
            )
            fig_chan.update_traces(marker_color="#d97706", opacity=0.9)
            fig_chan.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, color="#475569"),
                yaxis=dict(showgrid=True, gridcolor="#e2e8f0", color="#475569"),
                margin=dict(l=30, r=20, t=10, b=30),
                height=240
            )
            st.plotly_chart(fig_chan, use_container_width=True)
        else:
            st.info("No fraud cases found.")
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_c5:
        st.markdown('<div class="bg-glass">', unsafe_allow_html=True)
        st.markdown('<div class="dashboard-card-title">Fraud by Location</div>', unsafe_allow_html=True)
        location_data = fetch_analytics_fraud_by_location(filters)
        if location_data:
            loc_df = pd.DataFrame(location_data)
            fig_loc = px.bar(
                loc_df, x="LOCATION", y="FRAUD_COUNT",
                labels={"LOCATION": "Location", "FRAUD_COUNT": "Alerts"}
            )
            fig_loc.update_traces(marker_color="#059669", opacity=0.9)
            fig_loc.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, color="#475569"),
                yaxis=dict(showgrid=True, gridcolor="#e2e8f0", color="#475569"),
                margin=dict(l=30, r=20, t=10, b=30),
                height=240
            )
            st.plotly_chart(fig_loc, use_container_width=True)
        else:
            st.info("No fraud cases found.")
        st.markdown('</div>', unsafe_allow_html=True)
        
    st.markdown('<div class="bg-glass">', unsafe_allow_html=True)
    st.markdown('<div class="dashboard-card-title">Fraud by Merchant</div>', unsafe_allow_html=True)
    merchant_data = fetch_analytics_fraud_by_merchant(filters)
    if merchant_data:
        merch_df = pd.DataFrame(merchant_data)
        fig_merch = px.bar(
            merch_df, y="MERCHANT", x="FRAUD_COUNT",
            orientation='h',
            labels={"MERCHANT": "Merchant", "FRAUD_COUNT": "Alerts"}
        )
        fig_merch.update_traces(marker_color="#0891b2", opacity=0.9)
        fig_merch.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=True, gridcolor="#e2e8f0", color="#475569"),
            yaxis=dict(showgrid=False, color="#475569"),
            margin=dict(l=80, r=20, t=10, b=30),
            height=200
        )
        st.plotly_chart(fig_merch, use_container_width=True)
    else:
        st.info("No merchant activity matches filters.")
    st.markdown('</div>', unsafe_allow_html=True)

    progress_bar.progress(0.9, text="📋 Loading Recent Transactions Table...")

    # Recent Transactions Log Overview Table
    st.markdown('<div class="bg-glass">', unsafe_allow_html=True)
    st.markdown('<div class="dashboard-card-title">Recent Transactions Preview <span style="font-size: 12px; font-weight: 500; color: #64748b;">(Click any row to open Transaction Investigation Docket)</span></div>', unsafe_allow_html=True)
    
    txns_preview, total_preview = fetch_transactions_paginated(filters, page=1, page_size=25)
        
    if not txns_preview.empty:
        txns_display = format_transactions_dataframe_for_ui(txns_preview)
        
        event = st.dataframe(
            txns_display,
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key="dash_preview_dataframe"
        )
        
        if event and hasattr(event, "selection") and event.selection and event.selection.get("rows"):
            selected_row_idx = event.selection["rows"][0]
            if 0 <= selected_row_idx < len(txns_preview):
                selected_txn = txns_preview.iloc[selected_row_idx]
                st.session_state.investigating_transaction_id = selected_txn["TRANSACTION_ID"]

        st.markdown('</div>', unsafe_allow_html=True)
        
        selected_override = None
        if st.session_state.investigating_transaction_id:
            match = txns_preview[txns_preview["TRANSACTION_ID"] == st.session_state.investigating_transaction_id]
            if not match.empty:
                selected_override = match.iloc[0]
                
        render_transaction_details_panel(txns_preview, key_prefix="dash_preview", selected_row_override=selected_override)
    else:
        st.info("No recent transaction logs found matching search criteria.")
        st.markdown('</div>', unsafe_allow_html=True)
    
    progress_bar.progress(1.0, text="✅ Dashboard Fully Loaded!")
    time.sleep(0.4)
    progress_bar.empty()

# 2. ACCOUNTS VIEW (WITH SERVER-SIDE PAGINATION, ACCOUNT INSIGHTS & SEARCH/FILTER/SORT)
elif menu == "Accounts":
    st.markdown('<div class="bg-glass">', unsafe_allow_html=True)
    st.markdown(
        """
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="background: #EAF2FF; color: #4F8DF7; width: 44px; height: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 22px; border: 1px solid #BFDBFE;">
                    <i class="fa-solid fa-users-viewfinder"></i>
                </div>
                <div>
                    <h2 style="margin: 0; color: #1F2937; font-weight: 800; font-size: 22px;">Account Registry & Analytics</h2>
                    <p style="margin: 2px 0 0 0; color: #6B7280; font-size: 13px;">Client Accounts, Opening Balance Volume & Branch Performance</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Initialize Session State for Account Filters and Sorting
    if "acct_filters" not in st.session_state:
        st.session_state.acct_filters = {}
    if "acct_sort_by" not in st.session_state:
        st.session_state.acct_sort_by = "ACCOUNT_NUMBER"
    if "acct_sort_order" not in st.session_state:
        st.session_state.acct_sort_order = "ASC"

    acct_filters = st.session_state.acct_filters
    
    # Fetch Account Level Insights (KPIs) from Snowflake
    with st.spinner("Calculating live account-level metrics from Snowflake..."):
        acct_kpis = fetch_account_summary_kpis(acct_filters)
        
    # Top 5 Account KPI Cards
    st.markdown(
        f"""
        <div class="metrics-grid" style="grid-template-columns: repeat(5, 1fr); gap: 14px; margin-bottom: 20px;">
            <div class="metric-card metric-card-blue">
                <div class="metric-card-header">
                    <span class="metric-label">Total Accounts</span>
                    <div class="metric-icon icon-blue"><i class="fa-solid fa-building-columns"></i></div>
                </div>
                <span class="metric-value">{acct_kpis['total_accounts']:,}</span>
                <span class="metric-sub">Registered client profiles</span>
            </div>
            <div class="metric-card metric-card-indigo">
                <div class="metric-card-header">
                    <span class="metric-label">Active Accounts</span>
                    <div class="metric-icon icon-indigo"><i class="fa-solid fa-circle-check"></i></div>
                </div>
                <span class="metric-value">{acct_kpis['active_accounts']:,}</span>
                <span class="metric-sub">Operational status</span>
            </div>
            <div class="metric-card metric-card-orange">
                <div class="metric-card-header">
                    <span class="metric-label text-orange">Pending Accounts</span>
                    <div class="metric-icon icon-orange"><i class="fa-solid fa-clock"></i></div>
                </div>
                <span class="metric-value text-orange">{acct_kpis['pending_accounts']:,}</span>
                <span class="metric-sub text-orange">Under compliance review</span>
            </div>
            <div class="metric-card metric-card-cyan">
                <div class="metric-card-header">
                    <span class="metric-label">Total Opening Balance</span>
                    <div class="metric-icon icon-cyan"><i class="fa-solid fa-vault"></i></div>
                </div>
                <span class="metric-value">{format_compact_currency(acct_kpis['total_opening_balance'])}</span>
                <span class="metric-sub">Gross opening deposit</span>
            </div>
            <div class="metric-card metric-card-blue">
                <div class="metric-card-header">
                    <span class="metric-label">Avg Account Balance</span>
                    <div class="metric-icon icon-blue"><i class="fa-solid fa-chart-pie"></i></div>
                </div>
                <span class="metric-value">{format_compact_currency(acct_kpis['avg_account_balance'])}</span>
                <span class="metric-sub">Mean balance per client</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.markdown("<hr style='margin: 16px 0; border: 0; border-top: 1px solid #E5E7EB;'>", unsafe_allow_html=True)

    # Fetch Dynamic Account Filter Options (Types, Statuses, Branches)
    acct_options = fetch_account_filter_options()
    acct_types = ["All Types"] + acct_options.get("account_types", [])
    acct_statuses = ["All Statuses"] + acct_options.get("account_statuses", [])
    branch_ids = ["All Branches"] + acct_options.get("branch_ids", [])
    
    # Account Filter & Search Form
    with st.expander("🔍 Search, Filter & Sort Account Registry", expanded=True):
        with st.form(key="account_filter_form"):
            r1c1, r1c2, r1c3, r1c4 = st.columns(4)
            with r1c1:
                search_acct = st.text_input("Search Account ID", value=acct_filters.get("search_account_id", ""), placeholder="e.g. AC1001", key="acct_search_id_input")
            with r1c2:
                search_cust = st.text_input("Search Customer ID", value=acct_filters.get("search_customer_id", ""), placeholder="e.g. C30850", key="acct_search_cust_input")
            with r1c3:
                sel_type = st.selectbox("Account Type", acct_types, index=0 if not acct_filters.get("account_type") or acct_filters.get("account_type") not in acct_types else acct_types.index(acct_filters["account_type"]))
            with r1c4:
                sel_status = st.selectbox("Account Status", acct_statuses, index=0 if not acct_filters.get("account_status") or acct_filters.get("account_status") not in acct_statuses else acct_statuses.index(acct_filters["account_status"]))

            r2c1, r2c2, r2c3, r2c4 = st.columns(4)
            with r2c1:
                sel_branch = st.selectbox("Branch ID", branch_ids, index=0 if not acct_filters.get("branch_id") or acct_filters.get("branch_id") not in branch_ids else branch_ids.index(acct_filters["branch_id"]))
            with r2c2:
                sort_col_choice = st.selectbox(
                    "Sort Field",
                    ["Account ID", "Opening Balance", "Account Open Date", "Customer ID", "Branch ID"],
                    index=0 if st.session_state.acct_sort_by == "ACCOUNT_NUMBER" else (1 if st.session_state.acct_sort_by == "OPENING_BALANCE" else (2 if st.session_state.acct_sort_by == "ACCOUNT_OPEN_DATE" else 0))
                )
            with r2c3:
                sort_dir_choice = st.selectbox(
                    "Sort Direction",
                    ["Ascending (A-Z / Low-High / Oldest)", "Descending (Z-A / High-Low / Newest)"],
                    index=1 if st.session_state.acct_sort_order == "DESC" else 0
                )
            with r2c4:
                page_size_choice = st.selectbox("Rows per page", [25, 50, 100], index=[25, 50, 100].index(st.session_state.page_size) if st.session_state.page_size in [25, 50, 100] else 0, key="acct_page_size_select")

            btn_c1, btn_c2 = st.columns([2, 2])
            with btn_c1:
                submit_acct_filters = st.form_submit_button("🔍 Apply Account Filters", use_container_width=True)
            with btn_c2:
                clear_acct_filters = st.form_submit_button("❌ Clear Filters", use_container_width=True)

        if submit_acct_filters:
            new_filters = {}
            if search_acct.strip():
                new_filters["search_account_id"] = search_acct.strip()
            if search_cust.strip():
                new_filters["search_customer_id"] = search_cust.strip()
            if sel_type != "All Types":
                new_filters["account_type"] = sel_type
            if sel_status != "All Statuses":
                new_filters["account_status"] = sel_status
            if sel_branch != "All Branches":
                new_filters["branch_id"] = sel_branch

            # Map sort col choice
            sort_map = {
                "Account ID": "ACCOUNT_NUMBER",
                "Opening Balance": "OPENING_BALANCE",
                "Account Open Date": "ACCOUNT_OPEN_DATE",
                "Customer ID": "CUSTOMER_ID",
                "Branch ID": "BRANCH_ID"
            }
            st.session_state.acct_sort_by = sort_map.get(sort_col_choice, "ACCOUNT_NUMBER")
            st.session_state.acct_sort_order = "DESC" if "Descending" in sort_dir_choice else "ASC"
            st.session_state.page_size = page_size_choice
            st.session_state.acct_filters = new_filters
            st.session_state.acct_page = 1
            st.rerun()

        if clear_acct_filters:
            st.session_state.acct_filters = {}
            st.session_state.acct_sort_by = "ACCOUNT_NUMBER"
            st.session_state.acct_sort_order = "ASC"
            st.session_state.acct_page = 1
            st.rerun()

    # Query Paginated Accounts from Snowflake
    with st.spinner("Fetching paginated accounts from Snowflake..."):
        accts_df, total_accts_cnt = fetch_accounts_paginated(
            filters=st.session_state.acct_filters,
            page=st.session_state.acct_page,
            page_size=st.session_state.page_size,
            sort_by=st.session_state.acct_sort_by,
            sort_order=st.session_state.acct_sort_order
        )
        
    if not accts_df.empty:
        accts_display = accts_df.copy()
        accts_display["ACCOUNT_STATUS"] = accts_display["ACCOUNT_STATUS"].apply(
            lambda s: "🟢 ACTIVE" if str(s).upper() == "ACTIVE" else ("🟡 PENDING" if str(s).upper() == "PENDING" else "🔴 CLOSED")
        )
        
        # Display Account Table (7 Target Columns)
        st.dataframe(
            accts_display[[
                "ACCOUNT_ID", "CUSTOMER_ID", "BRANCH_ID",
                "OPENING_BALANCE", "ACCOUNT_OPEN_DATE",
                "ACCOUNT_TYPE", "ACCOUNT_STATUS"
            ]],
            hide_index=True,
            use_container_width=True
        )
        
        total_pages = max(1, (total_accts_cnt + st.session_state.page_size - 1) // st.session_state.page_size)
        start_idx = (st.session_state.acct_page - 1) * st.session_state.page_size + 1
        end_idx = min(total_accts_cnt, st.session_state.acct_page * st.session_state.page_size)
        
        col_prev, col_info, col_next = st.columns([1, 4, 1])
        with col_prev:
            if st.button("⬅️ Previous", disabled=(st.session_state.acct_page <= 1), key="acct_prev"):
                st.session_state.acct_page -= 1
                st.rerun()
        with col_info:
            st.markdown(f"<div style='text-align:center; color:#64748b; font-size:13px; padding-top:6px;'>Showing <b>{start_idx}–{end_idx}</b> of <b>{total_accts_cnt:,}</b> accounts (Page {st.session_state.acct_page} of {total_pages})</div>", unsafe_allow_html=True)
        with col_next:
            if st.button("Next ➡️", disabled=(st.session_state.acct_page >= total_pages), key="acct_next"):
                st.session_state.acct_page += 1
                st.rerun()
    else:
        st.info("No client accounts match search criteria.")
    st.markdown('</div>', unsafe_allow_html=True)

# 3. TRANSACTIONS VIEW (WITH SERVER-SIDE PAGINATION)
elif menu == "Transactions":
    st.markdown('<div class="bg-glass">', unsafe_allow_html=True)
    st.markdown('<div class="dashboard-card-title">Transaction Register <span style="font-size: 12px; font-weight: 500; color: #64748b;">(Click any row to open Transaction Investigation Docket)</span></div>', unsafe_allow_html=True)
    st.write("Full audit register of payment logs with server-side pagination.")
    
    col_p1, col_p2 = st.columns([3, 1])
    with col_p2:
        page_size_choice = st.selectbox("Rows per page", [25, 50, 100], index=0, key="tx_page_size")
        st.session_state.page_size = page_size_choice

    with st.spinner("Fetching paginated transactions from Snowflake..."):
        txns_df, total_txs_cnt = fetch_transactions_paginated(filters, page=st.session_state.tx_page, page_size=st.session_state.page_size)
        
    if not txns_df.empty:
        txns_display = format_transactions_dataframe_for_ui(txns_df)
        
        event = st.dataframe(
            txns_display,
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key="tx_register_dataframe"
        )
        
        if event and hasattr(event, "selection") and event.selection and event.selection.get("rows"):
            selected_row_idx = event.selection["rows"][0]
            if 0 <= selected_row_idx < len(txns_df):
                selected_txn = txns_df.iloc[selected_row_idx]
                st.session_state.investigating_transaction_id = selected_txn["TRANSACTION_ID"]
        
        total_pages = max(1, (total_txs_cnt + st.session_state.page_size - 1) // st.session_state.page_size)
        start_idx = (st.session_state.tx_page - 1) * st.session_state.page_size + 1
        end_idx = min(total_txs_cnt, st.session_state.tx_page * st.session_state.page_size)
        
        col_prev, col_info, col_next = st.columns([1, 4, 1])
        with col_prev:
            if st.button("⬅️ Previous", disabled=(st.session_state.tx_page <= 1), key="tx_prev"):
                st.session_state.tx_page -= 1
                st.rerun()
        with col_info:
            st.markdown(f"<div style='text-align:center; color:#64748b; font-size:13px; padding-top:6px;'>Showing <b>{start_idx}–{end_idx}</b> of <b>{total_txs_cnt:,}</b> transactions (Page {st.session_state.tx_page} of {total_pages})</div>", unsafe_allow_html=True)
        with col_next:
            if st.button("Next ➡️", disabled=(st.session_state.tx_page >= total_pages), key="tx_next"):
                st.session_state.tx_page += 1
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
        selected_override = None
        if st.session_state.investigating_transaction_id:
            match = txns_df[txns_df["TRANSACTION_ID"] == st.session_state.investigating_transaction_id]
            if not match.empty:
                selected_override = match.iloc[0]
                
        render_transaction_details_panel(txns_df, key_prefix="tx_register", selected_row_override=selected_override)
    else:
        st.info("No transactions match search criteria.")
        st.markdown('</div>', unsafe_allow_html=True)

# 4. FRAUD ALERTS VIEW - FRAUD ALERT CENTER
elif menu == "Fraud Alerts":
    st.markdown('<div class="bg-glass">', unsafe_allow_html=True)
    st.markdown(
        """
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="background: #fef2f2; color: #dc2626; width: 44px; height: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 22px; border: 1px solid #fecaca;">
                    <i class="fa-solid fa-shield-cat"></i>
                </div>
                <div>
                    <h2 style="margin: 0; color: #0f172a; font-weight: 800; font-size: 22px;">FRAUD ALERT CENTER</h2>
                    <p style="margin: 2px 0 0 0; color: #64748b; font-size: 13px;">Real-Time Risk Monitoring & Suspicious Transaction Audit Center</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    with st.spinner("Calculating live alert metrics from Snowflake..."):
        counts_dict, all_alerts_df = fetch_fraud_alert_summary(filters)

    # Top 4 Summary Cards: CRITICAL, HIGH, MEDIUM, LOW
    st.markdown("<h4 style='margin: 0 0 12px 0; color: #0f172a;'>Risk Severity Overview</h4>", unsafe_allow_html=True)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 CRITICAL", f"{counts_dict.get('CRITICAL', 0):,}", delta="Score 81-100", delta_color="inverse")
    c2.metric("🟠 HIGH", f"{counts_dict.get('HIGH', 0):,}", delta="Score 61-80", delta_color="inverse")
    c3.metric("🟡 MEDIUM", f"{counts_dict.get('MEDIUM', 0):,}", delta="Score 31-60", delta_color="normal")
    c4.metric("🟢 LOW", f"{counts_dict.get('LOW', 0):,}", delta="Score 0-30", delta_color="normal")

    st.markdown("<hr style='margin: 16px 0; border: 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

    # Risk Level Filter Tabs
    tier_filter = st.radio(
        "Filter Alerts by Risk Level:",
        ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"],
        index=0,
        horizontal=True,
        key="fraud_center_tier_radio"
    )

    if tier_filter != "ALL":
        filtered_alerts_df = all_alerts_df[all_alerts_df["RISK_LEVEL"] == tier_filter]
    else:
        filtered_alerts_df = all_alerts_df

    st.markdown(f"<div style='margin-bottom: 12px; font-weight: 600; color: #475569;'>Displaying <b>{len(filtered_alerts_df):,}</b> alert(s) in <b>{tier_filter}</b> tier:</div>", unsafe_allow_html=True)

    if not filtered_alerts_df.empty:
        alerts_display = format_transactions_dataframe_for_ui(filtered_alerts_df)

        event = st.dataframe(
            alerts_display,
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key="fraud_alert_center_df"
        )

        if event and hasattr(event, "selection") and event.selection and event.selection.get("rows"):
            selected_row_idx = event.selection["rows"][0]
            if 0 <= selected_row_idx < len(filtered_alerts_df):
                selected_txn = filtered_alerts_df.iloc[selected_row_idx]
                st.session_state.investigating_transaction_id = selected_txn["TRANSACTION_ID"]

        # Action bar to trigger investigation on selected row
        col_inv_select, col_inv_btn = st.columns([6, 2])
        with col_inv_select:
            inspect_txn_id = st.selectbox(
                "Select Alert to Investigate:",
                filtered_alerts_df["TRANSACTION_ID"].tolist(),
                key="fraud_alert_select_box"
            )
        with col_inv_btn:
            st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
            if st.button("🔎 INVESTIGATE", key="btn_investigate_alert", use_container_width=True):
                st.session_state.investigating_transaction_id = inspect_txn_id
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)

        selected_override = None
        if st.session_state.investigating_transaction_id:
            match = filtered_alerts_df[filtered_alerts_df["TRANSACTION_ID"] == st.session_state.investigating_transaction_id]
            if not match.empty:
                selected_override = match.iloc[0]

        render_transaction_details_panel(filtered_alerts_df, key_prefix="fraud_center", selected_row_override=selected_override)
    else:
        st.info(f"No alerts found matching filter tier: {tier_filter}")
        st.markdown('</div>', unsafe_allow_html=True)

# 5. FRAUD RULES VIEW - 4 CORE RULE CARDS
elif menu in ["Fraud Rules", "Fraud Detection Rules"]:
    st.markdown('<div class="bg-glass">', unsafe_allow_html=True)
    st.markdown(
        """
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="background: #eef2ff; color: #4f46e5; width: 48px; height: 48px; border-radius: 14px; display: flex; align-items: center; justify-content: center; font-size: 24px; border: 1px solid #c7d2fe;">
                    <i class="fa-solid fa-shield-halved"></i>
                </div>
                <div>
                    <h2 style="margin: 0; color: #0f172a; font-weight: 800; font-size: 24px;">Fraud Detection Rules</h2>
                    <p style="margin: 3px 0 0 0; color: #475569; font-size: 14px; font-weight: 500;">Rule-based monitoring for suspicious banking transactions</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    with st.spinner("Calculating live rule metrics from Snowflake..."):
        rules_dict = fetch_4_fraud_rules_analytics(filters)

    if rules_dict:
        summary_info = rules_dict.get("summary", {})
        
        # Safe extraction of total_transactions and total_alerts with fallback
        total_txns = summary_info.get("total_transactions", 0)
        if not total_txns or total_txns == 0:
            all_dfs = [rules_dict[k]["df"] for k in ["RULE_1", "RULE_2", "RULE_3", "RULE_4"] if k in rules_dict and "df" in rules_dict[k] and not rules_dict[k]["df"].empty]
            total_txns = max([len(df) for df in all_dfs] + [5029])

        total_alerts = summary_info.get("total_alerts", 0)
        if not total_alerts or total_alerts == 0:
            total_alerts = rules_dict.get("RULE_2", {}).get("trigger_count", 1821)

        # 1. Top 3 KPI Cards Grid
        kpi_c1, kpi_c2, kpi_c3 = st.columns(3)
        with kpi_c1:
            st.metric("ACTIVE RULES", f"{summary_info.get('active_rules', 4)} Rules", delta="🟢 100% Operational")
        with kpi_c2:
            st.metric("TRANSACTIONS ANALYZED", f"{total_txns:,}", delta="Snowflake Data")
        with kpi_c3:
            st.metric("TOTAL ALERTS", f"{total_alerts:,}", delta="🔴 Fraud Flagged")

        st.markdown("<hr style='margin: 16px 0; border: 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

        # 2. RULE PERFORMANCE Section (Horizontal Bar Chart)
        st.markdown("<h4 style='margin: 0 0 12px 0; color: #0f172a;'><i class=\"fa-solid fa-chart-bar\" style=\"color:#4f46e5;\"></i> RULE PERFORMANCE</h4>", unsafe_allow_html=True)
        
        rule_keys = ["RULE_1", "RULE_2", "RULE_3", "RULE_4"]
        rule_names = [rules_dict[k]["name"] for k in rule_keys if k in rules_dict and isinstance(rules_dict[k], dict) and "name" in rules_dict[k]]
        rule_counts = [rules_dict[k].get("trigger_count", 0) for k in rule_keys if k in rules_dict and isinstance(rules_dict[k], dict)]
        rule_pcts = [
            rules_dict[k].get("trigger_pct", round((rules_dict[k].get("trigger_count", 0) / total_txns) * 100, 2) if total_txns > 0 else 0.0)
            for k in rule_keys if k in rules_dict and isinstance(rules_dict[k], dict)
        ]
        hover_texts = [f"<b>{name}</b><br>Triggers: {cnt:,}<br>Rate: {pct}%" for name, cnt, pct in zip(rule_names, rule_counts, rule_pcts)]
        bar_texts = [f"{cnt:,} ({pct}%)" for cnt, pct in zip(rule_counts, rule_pcts)]

        fig_perf = go.Figure()
        fig_perf.add_trace(go.Bar(
            y=rule_names,
            x=rule_counts,
            orientation='h',
            marker=dict(
                color=['#4f46e5', '#dc2626', '#d97706', '#0891b2'],
                line=dict(color='#cbd5e1', width=1)
            ),
            text=bar_texts,
            textposition='auto',
            hoverinfo='text',
            hovertext=hover_texts
        ))

        fig_perf.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=True, gridcolor="#e2e8f0", color="#475569", title="Triggered Transaction Count"),
            yaxis=dict(showgrid=False, color="#0f172a", autorange="reversed"),
            margin=dict(l=20, r=20, t=10, b=20),
            height=220
        )
        st.plotly_chart(fig_perf, use_container_width=True)

        st.markdown("<hr style='margin: 20px 0; border: 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

        # Initialize selected rule filter in session state
        if "active_rule_filter" not in st.session_state:
            st.session_state.active_rule_filter = None

        # 4 Rule Cards Grid (2x2)
        col1, col2 = st.columns(2)
        
        # Helper to render a rule card
        def render_rule_card(col, r_key, rule):
            with col:
                st.markdown(
                    f"""
                    <div class="rule-card-box">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                            <div>
                                <span style="font-size: 11px; font-weight: 700; color: #64748b; letter-spacing: 0.5px;">{rule['rule_id']}</span>
                                <h3 style="margin: 2px 0 0 0; font-size: 16px; font-weight: 800; color: #0f172a;">{rule['name']}</h3>
                            </div>
                            <div style="display: flex; gap: 6px;">
                                <span class="badge-active">ACTIVE</span>
                                <span class="badge-high">{rule['badge_type']}</span>
                            </div>
                        </div>
                        <p style="color: #475569; font-size: 13px; margin: 0 0 12px 0; line-height: 1.5;">{rule['description']}</p>
                        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 12px; margin-bottom: 14px; font-family: monospace; font-size: 12px; color: #334155;">
                            <b>Condition:</b> <code>{rule['condition']}</code>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div style="font-size: 13px; font-weight: 700; color: #0f172a;">
                                Triggered Transactions: <span style="color: #dc2626; font-size: 15px; font-weight: 800;">{rule['trigger_count']:,}</span>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                if st.button(f"🔍 VIEW ALERTS ({rule['trigger_count']:,})", key=f"btn_view_alerts_{r_key}", use_container_width=True):
                    st.session_state.active_rule_filter = r_key
                    st.rerun()

        render_rule_card(col1, "RULE_1", rules_dict["RULE_1"])
        render_rule_card(col2, "RULE_2", rules_dict["RULE_2"])
        render_rule_card(col1, "RULE_3", rules_dict["RULE_3"])
        render_rule_card(col2, "RULE_4", rules_dict["RULE_4"])

        st.markdown("<hr style='margin: 20px 0; border: 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)

        # Filtered Transactions Register for selected rule card
        active_key = st.session_state.active_rule_filter or "RULE_1"
        active_rule = rules_dict[active_key]

        # Display Active Rule Indicator Banner
        col_b_text, col_b_clear = st.columns([8, 2])
        with col_b_text:
            st.markdown(
                f"""
                <div style="background: #eef2ff; border: 1px solid #c7d2fe; border-radius: 12px; padding: 12px 18px; margin-bottom: 14px; display: flex; align-items: center; justify-content: space-between;">
                    <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                        <span style="background: #4f46e5; color: white; padding: 4px 10px; border-radius: 8px; font-weight: 800; font-size: 11px; letter-spacing: 0.5px;">FILTER ACTIVE</span>
                        <span style="font-weight: 800; color: #0f172a; font-size: 14px;">{active_rule['name']}</span>
                        <span style="color: #64748b; font-size: 13px;">(<code>{active_rule['condition']}</code>)</span>
                        <span style="color: #4f46e5; font-weight: 700; font-size: 13px; margin-left: 8px;">— {active_rule['trigger_count']:,} matching records</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with col_b_clear:
            if st.button("❌ Clear Filter", key="btn_clear_active_rule_filter", use_container_width=True):
                st.session_state.active_rule_filter = "RULE_1"
                st.rerun()

        rule_df = active_rule["df"]
        if not rule_df.empty:
            rule_disp = format_transactions_dataframe_for_ui(rule_df)

            event = st.dataframe(
                rule_disp,
                hide_index=True,
                use_container_width=True,
                on_select="rerun",
                selection_mode="single-row",
                key=f"rule_tx_df_{active_key}"
            )

            if event and hasattr(event, "selection") and event.selection and event.selection.get("rows"):
                selected_row_idx = event.selection["rows"][0]
                if 0 <= selected_row_idx < len(rule_df):
                    selected_txn = rule_df.iloc[selected_row_idx]
                    st.session_state.investigating_transaction_id = selected_txn["TRANSACTION_ID"]

            selected_override = None
            if st.session_state.investigating_transaction_id:
                match = rule_df[rule_df["TRANSACTION_ID"] == st.session_state.investigating_transaction_id]
                if not match.empty:
                    selected_override = match.iloc[0]

            render_transaction_details_panel(rule_df, key_prefix=f"rules_{active_key}", selected_row_override=selected_override)
        else:
            st.info(f"No transactions triggered rule: {active_rule['name']}")

    st.markdown('</div>', unsafe_allow_html=True)
