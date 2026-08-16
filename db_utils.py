import os
import logging
import random
import datetime
from decimal import Decimal
import pandas as pd
from dotenv import load_dotenv
import streamlit as st

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=INFO if 'INFO' in dir() else logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def get_snowflake_credentials():
    """
    Retrieve Snowflake credentials from environment variables.
    """
    return {
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
        "user": os.getenv("SNOWFLAKE_USER"),
        "password": os.getenv("SNOWFLAKE_PASSWORD"),
        "role": os.getenv("SNOWFLAKE_ROLE"),
        "database": os.getenv("SNOWFLAKE_DATABASE"),
        "schema": os.getenv("SNOWFLAKE_SCHEMA"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE")
    }

def get_snowflake_connection():
    """
    Establish connection to Snowflake.
    """
    creds = get_snowflake_credentials()
    if not all([creds["account"], creds["user"], creds["password"]]):
        logger.warning("Missing core Snowflake credentials in environment.")
        return None
    try:
        import snowflake.connector
        conn = snowflake.connector.connect(
            user=creds["user"],
            password=creds["password"],
            account=creds["account"],
            role=creds["role"],
            database=creds["database"],
            schema=creds["schema"],
            warehouse=creds["warehouse"],
            client_session_keep_alive=True
        )
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to Snowflake: {e}")
        return None

def check_snowflake_health():
    """
    Dynamic health check for Snowflake backend status.
    Returns (is_healthy, status_message, last_refresh_time)
    """
    conn = get_snowflake_connection()
    if conn is None:
        return False, "Snowflake Offline", None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT CURRENT_TIMESTAMP();")
        res = cursor.fetchone()
        cursor.close()
        conn.close()
        refresh_time = res[0].strftime("%I:%M %p") if res and len(res) > 0 else datetime.datetime.now().strftime("%I:%M %p")
        return True, "Snowflake Live", refresh_time
    except Exception as e:
        logger.error(f"Snowflake health check failed: {e}")
        return False, "Snowflake Offline", None

def build_where_clause(filters):
    """
    Build WHERE clause dynamically from filters dictionary.
    """
    if not filters:
        return "", []
        
    conditions = []
    params = []
    
    if filters.get("customer_id"):
        c_val = str(filters["customer_id"]).strip()
        conditions.append("(A.CUSTOMER_ID ILIKE %s OR A.CUSTOMER_ID = %s OR T.CUSTOMER_NAME ILIKE %s)")
        params.extend([f"%{c_val}%", c_val, f"%{c_val}%"])
        
    if filters.get("transaction_type"):
        conditions.append("T.TRANSACTION_TYPE = %s")
        params.append(str(filters["transaction_type"]).strip())
        
    if filters.get("channel"):
        conditions.append("T.PAYMENT_MODE = %s")
        params.append(str(filters["channel"]).strip())
        
    if filters.get("location"):
        conditions.append("T.LOCATION = %s")
        params.append(str(filters["location"]).strip())
        
    if filters.get("fraud_status"):
        status_val = "FRAUD" if str(filters["fraud_status"]) == "1" else "NORMAL"
        conditions.append("T.FRAUD_STATUS = %s")
        params.append(status_val)
        
    if filters.get("start_date"):
        conditions.append("T.TRANSACTION_DATE >= %s")
        params.append(filters["start_date"])
        
    if filters.get("end_date"):
        conditions.append("T.TRANSACTION_DATE <= %s")
        params.append(filters["end_date"])
        
    if filters.get("min_amount"):
        try:
            conditions.append("T.AMOUNT >= %s")
            params.append(float(filters["min_amount"]))
        except ValueError:
            pass
            
    if filters.get("max_amount"):
        try:
            conditions.append("T.AMOUNT <= %s")
            params.append(float(filters["max_amount"]))
        except ValueError:
            pass
            
    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)
        
    return where_clause, params

def compute_fraud_risk_score(row):
    """
    Computes a transparent dynamic Fraud Risk Score (0-100) and risk level.
    
    Dynamic Rule Scoring Matrix:
    - FRAUD_STATUS = FRAUD (or 1) -> +40
    - AMOUNT > 50000 -> +25
    - AMOUNT > 100000 -> additional +10
    - TRANSACTION_TYPE = ONLINE TRANSFER or ATM WITHDRAWAL -> +10
    - PAYMENT_MODE = ATM or UPI -> +10
    
    Maximum score = 100.
    
    Risk Levels:
      0–30 = LOW
      31–60 = MEDIUM
      61–80 = HIGH
      81–100 = CRITICAL
    """
    score = 0
    breakdown = []

    # 1. FRAUD_STATUS = FRAUD -> +40
    fraud_status = str(row.get("FRAUD_STATUS", row.get("IS_FRAUD", "")) or "").strip().upper()
    if fraud_status in ["FRAUD", "1", "TRUE"]:
        score += 40
        breakdown.append({"rule": "Fraud Indicator Detected", "points": 40, "detail": "FRAUD_STATUS is FRAUD"})

    # 2. AMOUNT > 50000 -> +25, and AMOUNT > 100000 -> additional +10
    try:
        amt = float(row.get("AMOUNT", 0.0) or 0.0)
    except (ValueError, TypeError):
        amt = 0.0

    if amt > 100000:
        score += 35  # +25 for >50k, +10 for >100k
        breakdown.append({"rule": "Ultra High Transaction Amount (>100,000)", "points": 35, "detail": f"Amount (₹{amt:,.2f}) > 100,000"})
    elif amt > 50000:
        score += 25
        breakdown.append({"rule": "High Transaction Amount (>50,000)", "points": 25, "detail": f"Amount (₹{amt:,.2f}) > 50,000"})

    # 3. TRANSACTION_TYPE = ONLINE TRANSFER or ATM WITHDRAWAL -> +10
    tx_type = str(row.get("TRANSACTION_TYPE", "") or "").strip().upper()
    if tx_type in ["ONLINE TRANSFER", "ATM WITHDRAWAL"]:
        score += 10
        breakdown.append({"rule": "Suspicious Transaction Type", "points": 10, "detail": f"Transaction Type: '{row.get('TRANSACTION_TYPE')}'"})

    # 4. PAYMENT_MODE = ATM or UPI -> +10
    pm_mode = str(row.get("PAYMENT_MODE", row.get("CHANNEL", "")) or "").strip().upper()
    if pm_mode in ["ATM", "UPI"]:
        score += 10
        breakdown.append({"rule": "Suspicious Payment Mode", "points": 10, "detail": f"Payment Mode: '{row.get('PAYMENT_MODE')}'"})

    # Cap maximum score at 100
    final_score = min(100, max(0, score))

    if final_score >= 81:
        level = "CRITICAL"
        badge = "🔴 CRITICAL"
    elif final_score >= 61:
        level = "HIGH"
        badge = "🟠 HIGH"
    elif final_score >= 31:
        level = "MEDIUM"
        badge = "🟡 MEDIUM"
    else:
        level = "LOW"
        badge = "🟢 LOW"

    return final_score, level, badge, breakdown

    # Cap score strictly between 0 and 100
    final_score = min(100, max(0, score))

    if final_score <= 30:
        risk_level = "LOW"
        symbol = "🟢"
    elif final_score <= 60:
        risk_level = "MEDIUM"
        symbol = "🟡"
    elif final_score <= 80:
        risk_level = "HIGH"
        symbol = "🟠"
    else:
        risk_level = "CRITICAL"
        symbol = "🔴"

    risk_badge = f"{symbol} {final_score} {risk_level}"

    return final_score, risk_level, risk_badge, breakdown

def generate_flag_explanations(row):
    """
    Generates dynamic risk factor explanations derived directly from the exact same
    5 dynamic risk scoring rules used by compute_fraud_risk_score.
    Returns a list of dicts: [{"icon": str, "title": str, "desc": str, "severity": str, "points": int}]
    """
    explanations = []
    
    # 1. FRAUD_STATUS = FRAUD -> +40 points
    fraud_status = str(row.get("FRAUD_STATUS", row.get("IS_FRAUD", "")) or "").strip().upper()
    if fraud_status in ["FRAUD", "1", "TRUE"]:
        explanations.append({
            "icon": "🚨",
            "title": "Fraud Status: FRAUD (+40 points)",
            "desc": "Transaction was explicitly identified as fraudulent in bank audit log.",
            "severity": "CRITICAL",
            "points": 40
        })

    # 2. AMOUNT > 50000 (+25 points), AMOUNT > 100000 (+35 points)
    try:
        amt = float(row.get("AMOUNT", 0.0) or 0.0)
    except (ValueError, TypeError):
        amt = 0.0

    if amt > 100000:
        explanations.append({
            "icon": "💵",
            "title": "Very High Transaction Amount > ₹100,000 (+35 points)",
            "desc": f"Transaction amount of ₹{amt:,.2f} exceeds ₹100,000 monetary threshold.",
            "severity": "HIGH",
            "points": 35
        })
    elif amt > 50000:
        explanations.append({
            "icon": "💵",
            "title": "High Transaction Amount > ₹50,000 (+25 points)",
            "desc": f"Transaction amount of ₹{amt:,.2f} exceeds ₹50,000 monitoring threshold.",
            "severity": "MEDIUM",
            "points": 25
        })

    # 3. TRANSACTION_TYPE = ONLINE TRANSFER or ATM WITHDRAWAL -> +10 points
    tx_type = str(row.get("TRANSACTION_TYPE", "") or "").strip()
    if tx_type.upper() in ["ONLINE TRANSFER", "ATM WITHDRAWAL"]:
        explanations.append({
            "icon": "🔄",
            "title": f"Transaction Type: {tx_type} (+10 points)",
            "desc": f"Payment executed via risk-monitored transaction type '{tx_type}'.",
            "severity": "LOW",
            "points": 10
        })

    # 4. PAYMENT_MODE = ATM or UPI -> +10 points
    pm_mode = str(row.get("PAYMENT_MODE", row.get("CHANNEL", "")) or "").strip()
    if pm_mode.upper() in ["ATM", "UPI"]:
        explanations.append({
            "icon": "💳",
            "title": f"Payment Mode: {pm_mode} (+10 points)",
            "desc": f"Payment processed via risk-monitored payment mode '{pm_mode}'.",
            "severity": "LOW",
            "points": 10
        })

    return explanations

@st.cache_data(ttl=300)
def fetch_customer_profile(customer_id):
    """
    Fetch comprehensive customer risk profile statistics and transaction history directly from Snowflake.
    Cached with @st.cache_data(ttl=300) for fast response and zero redundant Snowflake queries.
    Returns: (stats_dict, history_df)
    """
    if not customer_id:
        return {}, pd.DataFrame()
        
    conn = get_snowflake_connection()
    if conn is None:
        return {}, pd.DataFrame()
        
    try:
        c_val = str(customer_id).strip()
        query = """
        SELECT 
            T.TRANSACTION_ID,
            T.TRANSACTION_DATE AS TIMESTAMP,
            COALESCE(A.CUSTOMER_ID, T.CUSTOMER_NAME) AS CUSTOMER_ID,
            T.CUSTOMER_NAME,
            T.TRANSACTION_TYPE,
            T.AMOUNT,
            COALESCE(A.OPENING_BALANCE, 0.0) AS OLD_BALANCE,
            GREATEST(0.0, COALESCE(A.OPENING_BALANCE, 0.0) - T.AMOUNT) AS NEW_BALANCE,
            CASE 
                WHEN T.TRANSACTION_TYPE = 'Bill Payment' THEN 'Utility Corp'
                WHEN T.TRANSACTION_TYPE = 'Online Transfer' THEN 'NetBank Portal'
                WHEN T.TRANSACTION_TYPE = 'ATM Withdrawal' THEN 'ATM Cash'
                ELSE 'Retail Store'
            END AS MERCHANT,
            T.PAYMENT_MODE AS CHANNEL,
            T.LOCATION,
            'Device' AS DEVICE,
            CASE WHEN T.FRAUD_STATUS = 'FRAUD' THEN 1 ELSE 0 END AS IS_FRAUD
        FROM TRANSACTIONS T
        LEFT JOIN ACCOUNTS A ON T.ACCOUNT_NUMBER = A.ACCOUNT_NUMBER
        WHERE (A.CUSTOMER_ID = %s OR A.CUSTOMER_ID ILIKE %s OR T.CUSTOMER_NAME ILIKE %s)
        ORDER BY T.TRANSACTION_DATE ASC, T.TRANSACTION_ID ASC
        """
        df = pd.read_sql(query, conn, params=[c_val, f"%{c_val}%", f"%{c_val}%"])
        conn.close()
        df.columns = [col.upper() for col in df.columns]
        
        if df.empty:
            return {}, pd.DataFrame()
            
        scores = []
        levels = []
        badges = []
        breakdowns = []
        
        for idx, row in df.iterrows():
            s, l, b, bd = compute_fraud_risk_score(row)
            scores.append(s)
            levels.append(l)
            badges.append(b)
            breakdowns.append(bd)
            
        df["RISK_SCORE"] = scores
        df["RISK_LEVEL"] = levels
        df["RISK_BADGE"] = badges
        df["RISK_BREAKDOWN"] = breakdowns
        
        # Calculate Customer Statistics
        total_txs = len(df)
        total_amt = float(df["AMOUNT"].sum())
        fraud_txs = int(df["IS_FRAUD"].sum())
        fraud_rate = (fraud_txs / total_txs * 100) if total_txs > 0 else 0.0
        fraud_amt = float(df[df["IS_FRAUD"] == 1]["AMOUNT"].sum()) if fraud_txs > 0 else 0.0
        avg_amt = total_amt / total_txs if total_txs > 0 else 0.0
        
        most_used_type = df["TRANSACTION_TYPE"].mode()[0] if not df["TRANSACTION_TYPE"].empty else "N/A"
        most_used_channel = df["CHANNEL"].mode()[0] if not df["CHANNEL"].empty else "N/A"
        most_frequent_location = df["LOCATION"].mode()[0] if not df["LOCATION"].empty else "N/A"
        
        # Calculate Customer Aggregate Risk Score
        max_score = int(df["RISK_SCORE"].max()) if not df.empty else 0
        avg_score = float(df["RISK_SCORE"].mean()) if not df.empty else 0.0
        customer_risk_score = min(100, int(0.6 * max_score + 0.4 * avg_score + (20 if fraud_txs > 0 else 0)))
        
        if customer_risk_score <= 30:
            customer_risk_level = "LOW"
            symbol = "🟢"
        elif customer_risk_score <= 60:
            customer_risk_level = "MEDIUM"
            symbol = "🟡"
        elif customer_risk_score <= 80:
            customer_risk_level = "HIGH"
            symbol = "🟠"
        else:
            customer_risk_level = "CRITICAL"
            symbol = "🔴"
            
        stats = {
            "customer_id": str(customer_id).strip(),
            "total_transactions": total_txs,
            "total_amount": total_amt,
            "fraud_transactions": fraud_txs,
            "fraud_rate": round(fraud_rate, 2),
            "fraud_amount": fraud_amt,
            "avg_amount": round(avg_amt, 2),
            "most_used_type": most_used_type,
            "most_used_channel": most_used_channel,
            "most_frequent_location": most_frequent_location,
            "overall_risk_score": customer_risk_score,
            "overall_risk_level": customer_risk_level,
            "risk_symbol": symbol
        }
        
        return stats, df
    except Exception as e:
        logger.error(f"Error fetching customer profile: {e}")
        return {}, pd.DataFrame()

@st.cache_data(ttl=60)
def fetch_fraud_alert_summary(filters=None):
    """
    Calculate dynamic count of alerts grouped by risk tier (CRITICAL, HIGH, MEDIUM, LOW)
    directly from Snowflake transaction data.
    Returns: (tier_counts_dict, full_alerts_df)
    """
    conn = get_snowflake_connection()
    if conn is None:
        return {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "TOTAL": 0}, pd.DataFrame()

    try:
        where_clause, params = build_where_clause(filters)
        query = f"""
        SELECT 
            T.TRANSACTION_ID,
            T.TRANSACTION_DATE AS TIMESTAMP,
            A.CUSTOMER_ID,
            T.CUSTOMER_NAME,
            T.TRANSACTION_TYPE,
            T.AMOUNT,
            COALESCE(A.OPENING_BALANCE, 0.0) AS OLD_BALANCE,
            GREATEST(0.0, COALESCE(A.OPENING_BALANCE, 0.0) - T.AMOUNT) AS NEW_BALANCE,
            CASE 
                WHEN T.TRANSACTION_TYPE = 'Bill Payment' THEN 'Utility Corp'
                WHEN T.TRANSACTION_TYPE = 'Online Transfer' THEN 'NetBank Portal'
                WHEN T.TRANSACTION_TYPE = 'ATM Withdrawal' THEN 'ATM Cash'
                ELSE 'Retail Store'
            END AS MERCHANT,
            T.PAYMENT_MODE AS CHANNEL,
            T.LOCATION,
            'Device' AS DEVICE,
            CASE WHEN T.FRAUD_STATUS = 'FRAUD' THEN 1 ELSE 0 END AS IS_FRAUD
        FROM TRANSACTIONS T
        LEFT JOIN ACCOUNTS A ON T.ACCOUNT_NUMBER = A.ACCOUNT_NUMBER
        {where_clause}
        ORDER BY T.TRANSACTION_DATE DESC, T.TRANSACTION_ID DESC
        """
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        df.columns = [col.upper() for col in df.columns]

        if df.empty:
            return {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "TOTAL": 0}, pd.DataFrame()

        scores = []
        levels = []
        badges = []
        breakdowns = []

        critical_count = 0
        high_count = 0
        medium_count = 0
        low_count = 0

        for idx, row in df.iterrows():
            s, l, b, bd = compute_fraud_risk_score(row)
            scores.append(s)
            levels.append(l)
            badges.append(b)
            breakdowns.append(bd)

            if l == "CRITICAL":
                critical_count += 1
            elif l == "HIGH":
                high_count += 1
            elif l == "MEDIUM":
                medium_count += 1
            else:
                low_count += 1

        df["RISK_SCORE"] = scores
        df["RISK_LEVEL"] = levels
        df["RISK_BADGE"] = badges
        df["RISK_BREAKDOWN"] = breakdowns

        counts = {
            "CRITICAL": critical_count,
            "HIGH": high_count,
            "MEDIUM": medium_count,
            "LOW": low_count,
            "TOTAL": len(df)
        }

        return counts, df
    except Exception as e:
        logger.error(f"Error fetching fraud alert summary: {e}")
        return {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "TOTAL": 0}, pd.DataFrame()

@st.cache_data(ttl=60)
def fetch_fraud_rules_analytics(filters=None):
    """
    Calculate live rule trigger counts and rates from Snowflake transaction data
    for all 6 core fraud detection rules.
    Returns: list of dicts detailing each rule's metadata and live Snowflake statistics.
    """
    conn = get_snowflake_connection()
    if conn is None:
        return []

    try:
        where_clause, params = build_where_clause(filters)
        query = f"""
        SELECT 
            T.TRANSACTION_ID,
            A.CUSTOMER_ID,
            T.CUSTOMER_NAME,
            T.AMOUNT,
            T.TRANSACTION_TYPE,
            T.PAYMENT_MODE AS CHANNEL,
            T.LOCATION,
            COALESCE(A.OPENING_BALANCE, 0.0) AS OLD_BALANCE,
            CASE WHEN T.FRAUD_STATUS = 'FRAUD' THEN 1 ELSE 0 END AS IS_FRAUD
        FROM TRANSACTIONS T
        LEFT JOIN ACCOUNTS A ON T.ACCOUNT_NUMBER = A.ACCOUNT_NUMBER
        {where_clause}
        """
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        df.columns = [col.upper() for col in df.columns]

        total_txs = len(df)
        if total_txs == 0:
            return []

        # Rule Definitions & Trigger Tracking
        r1_triggers = sum(1 for _, row in df.iterrows() if row["IS_FRAUD"] == 1)
        r2_triggers = sum(1 for _, row in df.iterrows() if float(row["AMOUNT"]) >= 2500)
        r3_triggers = sum(1 for _, row in df.iterrows() if str(row["CHANNEL"]).strip() in ['Online', 'Mobile', 'Web', 'NetBanking', 'Crypto'])
        r4_triggers = sum(1 for _, row in df.iterrows() if str(row["TRANSACTION_TYPE"]).strip() in ['Online Transfer', 'ATM Withdrawal', 'Wire Transfer', 'International Transfer', 'Crypto Transfer'])
        r5_triggers = sum(1 for _, row in df.iterrows() if (float(row["OLD_BALANCE"]) > 0 and float(row["AMOUNT"]) > float(row["OLD_BALANCE"])) or (float(row["OLD_BALANCE"]) == 0 and float(row["AMOUNT"]) >= 3000))
        r6_triggers = sum(1 for _, row in df.iterrows() if str(row["LOCATION"]).strip() in ['International', 'Unknown', 'Foreign', 'Overseas'] or float(row["AMOUNT"]) >= 10000)

        rules = [
            {
                "rule_id": "R001",
                "name": "Known Fraud Audit Flag",
                "category": "Audit Log",
                "description": "Triggered when transaction is explicitly flagged as fraudulent in the bank audit log database.",
                "condition": "IS_FRAUD == 1 OR FRAUD_STATUS == 'FRAUD'",
                "points": 40,
                "status": "ACTIVE",
                "trigger_count": r1_triggers,
                "trigger_rate": round((r1_triggers / total_txs) * 100, 2)
            },
            {
                "rule_id": "R002",
                "name": "High Value Transaction Volume",
                "category": "Monetary",
                "description": "Triggered when transaction volume exceeds high-risk monetary threshold (₹5,000 for +25 pts, ₹2,500 for +15 pts).",
                "condition": "AMOUNT >= ₹5,000 (+25 pts) OR AMOUNT >= ₹2,500 (+15 pts)",
                "points": 25,
                "status": "ACTIVE",
                "trigger_count": r2_triggers,
                "trigger_rate": round((r2_triggers / total_txs) * 100, 2)
            },
            {
                "rule_id": "R003",
                "name": "High Risk Payment Channel",
                "category": "Channel",
                "description": "Triggered when payment is processed through unverified or digital channels.",
                "condition": "CHANNEL IN ('Online', 'Mobile', 'Web', 'NetBanking', 'Crypto')",
                "points": 10,
                "status": "ACTIVE",
                "trigger_count": r3_triggers,
                "trigger_rate": round((r3_triggers / total_txs) * 100, 2)
            },
            {
                "rule_id": "R004",
                "name": "High Risk Transaction Method",
                "category": "Payment Method",
                "description": "Triggered when payment is executed via high-velocity transfer methods.",
                "condition": "TYPE IN ('Online Transfer', 'ATM Withdrawal', 'Wire Transfer', 'International', 'Crypto')",
                "points": 10,
                "status": "ACTIVE",
                "trigger_count": r4_triggers,
                "trigger_rate": round((r4_triggers / total_txs) * 100, 2)
            },
            {
                "rule_id": "R005",
                "name": "Account Balance Anomaly",
                "category": "Balance",
                "description": "Triggered when transfer amount exceeds starting account balance or causes account overdraft.",
                "condition": "AMOUNT > OLD_BALANCE OR (OLD_BALANCE == 0 AND AMOUNT >= ₹3,000)",
                "points": 10,
                "status": "ACTIVE",
                "trigger_count": r5_triggers,
                "trigger_rate": round((r5_triggers / total_txs) * 100, 2)
            },
            {
                "rule_id": "R006",
                "name": "High Risk Geo-Location & High Volume",
                "category": "Geography",
                "description": "Triggered when transaction originates from foreign geo-location or exceeds ₹10,000 volume.",
                "condition": "LOCATION IN ('International', 'Unknown', 'Foreign') OR AMOUNT >= ₹10,000",
                "points": 5,
                "status": "ACTIVE",
                "trigger_count": r6_triggers,
                "trigger_rate": round((r6_triggers / total_txs) * 100, 2)
            }
        ]

        return rules
    except Exception as e:
        logger.error(f"Error fetching fraud rules analytics: {e}")
        return []

@st.cache_data(ttl=60)
def fetch_4_fraud_rules_analytics(filters=None):
    """
    Calculates live trigger counts and filtered transaction DataFrames from SMART_BANKING.FRAUD.TRANSACTIONS:
    Rule 1: High Transaction Amount (AMOUNT > 50000)
    Rule 2: Fraud Indicator (FRAUD_STATUS = FRAUD)
    Rule 3: High Risk Transaction (Risk Score > 80)
    Rule 4: High Risk Method/Payment Mode (ONLINE TRANSFER/ATM WITHDRAWAL or ATM/UPI)
    Returns: dict mapping rule_id to rule details, counts, and transaction DataFrames.
    """
    conn = get_snowflake_connection()
    if conn is None:
        return {}

    try:
        where_clause, params = build_where_clause(filters)
        query = f"""
        SELECT 
            T.TRANSACTION_ID,
            A.CUSTOMER_ID,
            T.CUSTOMER_NAME,
            T.ACCOUNT_NUMBER,
            T.TRANSACTION_TYPE,
            T.AMOUNT,
            T.LOCATION,
            T.TRANSACTION_DATE,
            T.PAYMENT_MODE,
            T.FRAUD_STATUS
        FROM SMART_BANKING.FRAUD.TRANSACTIONS T
        LEFT JOIN ACCOUNTS A ON T.ACCOUNT_NUMBER = A.ACCOUNT_NUMBER
        {where_clause}
        ORDER BY T.TRANSACTION_DATE DESC, T.TRANSACTION_ID DESC
        """
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        df.columns = [col.upper() for col in df.columns]

        if df.empty:
            return {}

        scores = []
        levels = []
        badges = []
        breakdowns = []

        for idx, row in df.iterrows():
            s, l, b, bd = compute_fraud_risk_score(row)
            scores.append(s)
            levels.append(l)
            badges.append(b)
            breakdowns.append(bd)

        df["FRAUD_RISK_SCORE"] = scores
        df["RISK_LEVEL"] = levels
        df["RISK_BADGE"] = badges
        df["RISK_BREAKDOWN"] = breakdowns

        # Rule 1: High Transaction Amount (AMOUNT > 50000)
        r1_df = df[df["AMOUNT"] > 50000]
        # Rule 2: Fraud Indicator (FRAUD_STATUS = FRAUD)
        r2_df = df[df["FRAUD_STATUS"].str.upper() == "FRAUD"]
        # Rule 3: High Risk Transaction (Risk Score > 80)
        r3_df = df[df["FRAUD_RISK_SCORE"] > 80]
        # Rule 4: High Risk Payment Method / Channel with FRAUD_RISK_SCORE > 60
        r4_df = df[
            (
                df["TRANSACTION_TYPE"].astype(str).str.upper().isin(["ONLINE TRANSFER", "ATM WITHDRAWAL"]) |
                df["PAYMENT_MODE"].astype(str).str.upper().isin(["ATM", "UPI"])
            ) &
            (df["FRAUD_RISK_SCORE"] > 60)
        ]

        total_txns = len(df)
        total_alerts = len(r2_df)

        rules_dict = {
            "summary": {
                "active_rules": 4,
                "total_transactions": total_txns,
                "total_alerts": total_alerts
            },
            "RULE_1": {
                "rule_id": "RULE 1",
                "name": "HIGH TRANSACTION AMOUNT",
                "condition": "AMOUNT > 50000",
                "description": "Flags transactions where the transaction amount exceeds ₹50,000.",
                "status": "ACTIVE",
                "badge_type": "HIGH",
                "trigger_count": len(r1_df),
                "trigger_pct": round((len(r1_df) / total_txns) * 100, 2) if total_txns > 0 else 0,
                "df": r1_df
            },
            "RULE_2": {
                "rule_id": "RULE 2",
                "name": "FRAUD INDICATOR",
                "condition": "FRAUD_STATUS = FRAUD",
                "description": "Flags transactions already identified as fraudulent.",
                "status": "ACTIVE",
                "badge_type": "HIGH",
                "trigger_count": len(r2_df),
                "trigger_pct": round((len(r2_df) / total_txns) * 100, 2) if total_txns > 0 else 0,
                "df": r2_df
            },
            "RULE_3": {
                "rule_id": "RULE 3",
                "name": "HIGH RISK TRANSACTION",
                "condition": "Risk Score > 80",
                "description": "Flags transactions with a calculated risk score above 80.",
                "status": "ACTIVE",
                "badge_type": "HIGH",
                "trigger_count": len(r3_df),
                "trigger_pct": round((len(r3_df) / total_txns) * 100, 2) if total_txns > 0 else 0,
                "df": r3_df
            },
            "RULE_4": {
                "rule_id": "RULE 4",
                "name": "HIGH RISK PAYMENT METHOD",
                "condition": "(TYPE IN ('Online Transfer', 'ATM Withdrawal') OR MODE IN ('ATM', 'UPI')) AND Risk Score > 60",
                "description": "Flags high or critical risk transactions executed via monitored payment channels or methods.",
                "status": "ACTIVE",
                "badge_type": "HIGH",
                "trigger_count": len(r4_df),
                "trigger_pct": round((len(r4_df) / total_txns) * 100, 2) if total_txns > 0 else 0,
                "df": r4_df
            }
        }

        return rules_dict
    except Exception as e:
        logger.error(f"Error fetching 4 fraud rules analytics: {e}")
        return {}

@st.cache_data(ttl=60)
def fetch_summary_kpis(filters=None):
    """
    Fetch pre-aggregated KPI cards values from Snowflake with caching.
    """
    conn = get_snowflake_connection()
    if conn is None:
        return {
            "total_accounts": 0, "total_transactions": 0, "total_amount": 0.0,
            "fraud_transactions": 0, "fraud_rate": 0.0, "fraud_amount": 0.0,
            "high_risk_transactions": 0
        }
    try:
        where_clause, params = build_where_clause(filters)
        
        acct_where = ""
        acct_params = []
        if filters and filters.get("customer_id"):
            c_val = str(filters["customer_id"]).strip()
            acct_where = "WHERE (CUSTOMER_ID = %s OR CUSTOMER_ID ILIKE %s)"
            acct_params = [c_val, f"%{c_val}%"]
            
        query = f"""
        SELECT 
            (SELECT COUNT(*) FROM ACCOUNTS {acct_where}) AS TOTAL_ACCOUNTS,
            COUNT(*) AS TOTAL_TRANSACTIONS,
            COALESCE(SUM(T.AMOUNT), 0.0) AS TOTAL_AMOUNT,
            SUM(CASE WHEN T.FRAUD_STATUS = 'FRAUD' THEN 1 ELSE 0 END) AS FRAUD_TRANSACTIONS,
            COALESCE(SUM(CASE WHEN T.FRAUD_STATUS = 'FRAUD' THEN T.AMOUNT ELSE 0.0 END), 0.0) AS FRAUD_AMOUNT,
            SUM(CASE WHEN (
                (CASE WHEN T.FRAUD_STATUS = 'FRAUD' THEN 40 ELSE 0 END) +
                (CASE WHEN T.AMOUNT >= 5000 THEN 25 WHEN T.AMOUNT >= 2500 THEN 15 ELSE 0 END) +
                (CASE WHEN T.TRANSACTION_TYPE IN ('Online Transfer', 'ATM Withdrawal', 'Wire Transfer', 'International Transfer', 'Crypto Transfer') THEN 10 ELSE 0 END) +
                (CASE WHEN T.PAYMENT_MODE IN ('Online', 'Mobile', 'Web', 'NetBanking', 'Crypto') THEN 10 ELSE 0 END) +
                (CASE WHEN (T.AMOUNT > COALESCE(A.OPENING_BALANCE, 0) OR (COALESCE(A.OPENING_BALANCE, 0) = 0 AND T.AMOUNT >= 3000)) THEN 10 ELSE 0 END) +
                (CASE WHEN (T.LOCATION IN ('International', 'Unknown', 'Foreign', 'Overseas') OR T.AMOUNT >= 10000) THEN 5 ELSE 0 END)
            ) >= 61 THEN 1 ELSE 0 END) AS HIGH_RISK_TRANSACTIONS
        FROM TRANSACTIONS T
        LEFT JOIN ACCOUNTS A ON T.ACCOUNT_NUMBER = A.ACCOUNT_NUMBER
        {where_clause}
        """
        cursor = conn.cursor()
        cursor.execute(query, acct_params + params)
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not row:
            return {
                "total_accounts": 0, "total_transactions": 0, "total_amount": 0.0,
                "fraud_transactions": 0, "fraud_rate": 0.0, "fraud_amount": 0.0,
                "high_risk_transactions": 0
            }
            
        total_accts = int(row[0]) if row[0] is not None else 0
        total_txs = int(row[1]) if row[1] is not None else 0
        total_amt = float(row[2]) if row[2] is not None else 0.0
        fraud_txs = int(row[3]) if row[3] is not None else 0
        fraud_amt = float(row[4]) if row[4] is not None else 0.0
        high_risk_txs = int(row[5]) if row[5] is not None else 0
        
        fraud_rate = (fraud_txs / total_txs * 100) if total_txs > 0 else 0.0
        
        return {
            "total_accounts": total_accts,
            "total_transactions": total_txs,
            "total_amount": total_amt,
            "fraud_transactions": fraud_txs,
            "fraud_rate": round(fraud_rate, 2),
            "fraud_amount": fraud_amt,
            "high_risk_transactions": high_risk_txs
        }
    except Exception as e:
        logger.error(f"Error fetching summary KPIs: {e}")
        return {
            "total_accounts": 0, "total_transactions": 0, "total_amount": 0.0,
            "fraud_transactions": 0, "fraud_rate": 0.0, "fraud_amount": 0.0,
            "high_risk_transactions": 0
        }

@st.cache_data(ttl=600)
def fetch_filter_options():
    """
    Fetch unique dropdown choices dynamically from the database with caching.
    """
    conn = get_snowflake_connection()
    if conn is None:
        return {"types": [], "channels": [], "locations": []}
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT TRANSACTION_TYPE FROM TRANSACTIONS WHERE TRANSACTION_TYPE IS NOT NULL ORDER BY TRANSACTION_TYPE")
        types = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT PAYMENT_MODE FROM TRANSACTIONS WHERE PAYMENT_MODE IS NOT NULL ORDER BY PAYMENT_MODE")
        channels = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT LOCATION FROM TRANSACTIONS WHERE LOCATION IS NOT NULL ORDER BY LOCATION")
        locations = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        return {
            "types": types,
            "channels": channels,
            "locations": locations
        }
    except Exception as e:
        logger.error(f"Error fetching filter options: {e}")
        return {"types": [], "channels": [], "locations": []}

def build_account_where_clause(filters):
    """
    Build WHERE clause dynamically for ACCOUNTS queries.
    """
    if not filters:
        return "", []
        
    conditions = []
    params = []
    
    if filters.get("account_id") or filters.get("search_account_id"):
        acct_id = str(filters.get("account_id") or filters.get("search_account_id")).strip()
        conditions.append("(ACCOUNT_NUMBER ILIKE %s)")
        params.append(f"%{acct_id}%")
        
    if filters.get("customer_id") or filters.get("search_customer_id"):
        cust_id = str(filters.get("customer_id") or filters.get("search_customer_id")).strip()
        conditions.append("(CUSTOMER_ID ILIKE %s)")
        params.append(f"%{cust_id}%")
        
    if filters.get("account_type"):
        conditions.append("(ACCOUNT_TYPE = %s)")
        params.append(str(filters["account_type"]).strip())
        
    if filters.get("account_status"):
        conditions.append("(ACCOUNT_STATUS = %s)")
        params.append(str(filters["account_status"]).strip())
        
    if filters.get("branch_id"):
        conditions.append("(BRANCH_ID = %s)")
        params.append(str(filters["branch_id"]).strip())
        
    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)
        
    return where_clause, params

@st.cache_data(ttl=60)
def fetch_account_summary_kpis(filters=None):
    """
    Calculate account-level insights from Snowflake:
    Total Accounts, Active Accounts, Pending Accounts, Total Opening Balance, Average Account Balance.
    """
    conn = get_snowflake_connection()
    if conn is None:
        return {
            "total_accounts": 0, "active_accounts": 0, "pending_accounts": 0,
            "total_opening_balance": 0.0, "avg_account_balance": 0.0
        }
    try:
        where_clause, params = build_account_where_clause(filters)
        query = f"""
        SELECT 
            COUNT(*) AS TOTAL_ACCOUNTS,
            SUM(CASE WHEN UPPER(ACCOUNT_STATUS) = 'ACTIVE' THEN 1 ELSE 0 END) AS ACTIVE_ACCOUNTS,
            SUM(CASE WHEN UPPER(ACCOUNT_STATUS) = 'PENDING' THEN 1 ELSE 0 END) AS PENDING_ACCOUNTS,
            COALESCE(SUM(OPENING_BALANCE), 0.0) AS TOTAL_OPENING_BALANCE,
            COALESCE(AVG(OPENING_BALANCE), 0.0) AS AVG_ACCOUNT_BALANCE
        FROM ACCOUNTS
        {where_clause}
        """
        cursor = conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not row:
            return {
                "total_accounts": 0, "active_accounts": 0, "pending_accounts": 0,
                "total_opening_balance": 0.0, "avg_account_balance": 0.0
            }
            
        return {
            "total_accounts": int(row[0]) if row[0] is not None else 0,
            "active_accounts": int(row[1]) if row[1] is not None else 0,
            "pending_accounts": int(row[2]) if row[2] is not None else 0,
            "total_opening_balance": float(row[3]) if row[3] is not None else 0.0,
            "avg_account_balance": float(row[4]) if row[4] is not None else 0.0
        }
    except Exception as e:
        logger.error(f"Error fetching account summary KPIs: {e}")
        return {
            "total_accounts": 0, "active_accounts": 0, "pending_accounts": 0,
            "total_opening_balance": 0.0, "avg_account_balance": 0.0
        }

@st.cache_data(ttl=600)
def fetch_account_filter_options():
    """
    Fetch unique dropdown filter choices for ACCOUNTS dynamically.
    """
    conn = get_snowflake_connection()
    if conn is None:
        return {"account_types": [], "account_statuses": [], "branch_ids": []}
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT ACCOUNT_TYPE FROM ACCOUNTS WHERE ACCOUNT_TYPE IS NOT NULL ORDER BY ACCOUNT_TYPE")
        account_types = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT ACCOUNT_STATUS FROM ACCOUNTS WHERE ACCOUNT_STATUS IS NOT NULL ORDER BY ACCOUNT_STATUS")
        account_statuses = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT DISTINCT BRANCH_ID FROM ACCOUNTS WHERE BRANCH_ID IS NOT NULL ORDER BY BRANCH_ID")
        branch_ids = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        return {
            "account_types": account_types,
            "account_statuses": account_statuses,
            "branch_ids": branch_ids
        }
    except Exception as e:
        logger.error(f"Error fetching account filter options: {e}")
        return {"account_types": [], "account_statuses": [], "branch_ids": []}

@st.cache_data(ttl=30)
def fetch_accounts_paginated(filters=None, page=1, page_size=25, sort_by="ACCOUNT_NUMBER", sort_order="ASC"):
    """
    Fetch accounts with server-side pagination (LIMIT/OFFSET), filtering, sorting, and total count.
    """
    conn = get_snowflake_connection()
    if conn is None:
        return pd.DataFrame(), 0
    try:
        where_clause, params = build_account_where_clause(filters)
            
        cursor = conn.cursor()
        count_query = f"SELECT COUNT(*) FROM ACCOUNTS {where_clause}"
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()[0]
        cursor.close()
        
        # Validate sort parameters safely
        valid_sort_cols = {
            "ACCOUNT_NUMBER": "ACCOUNT_NUMBER",
            "ACCOUNT_ID": "ACCOUNT_NUMBER",
            "OPENING_BALANCE": "OPENING_BALANCE",
            "ACCOUNT_OPEN_DATE": "ACCOUNT_OPEN_DATE",
            "CUSTOMER_ID": "CUSTOMER_ID",
            "BRANCH_ID": "BRANCH_ID",
            "ACCOUNT_TYPE": "ACCOUNT_TYPE",
            "ACCOUNT_STATUS": "ACCOUNT_STATUS"
        }
        order_col = valid_sort_cols.get(str(sort_by).upper(), "ACCOUNT_NUMBER")
        order_dir = "DESC" if str(sort_order).upper() in ["DESC", "DESCENDING"] else "ASC"
        
        offset = (page - 1) * page_size
        data_query = f"""
        SELECT 
            ACCOUNT_NUMBER AS ACCOUNT_ID,
            CUSTOMER_ID,
            BRANCH_ID,
            OPENING_BALANCE,
            ACCOUNT_OPEN_DATE,
            ACCOUNT_TYPE,
            ACCOUNT_STATUS
        FROM ACCOUNTS
        {where_clause}
        ORDER BY {order_col} {order_dir}
        LIMIT {page_size} OFFSET {offset}
        """
        df = pd.read_sql(data_query, conn, params=params)
        conn.close()
        df.columns = [col.upper() for col in df.columns]
        return df, total_records
    except Exception as e:
        logger.error(f"Error fetching paginated accounts: {e}")
        return pd.DataFrame(), 0

def fetch_accounts(filters=None):
    df, _ = fetch_accounts_paginated(filters=filters, page=1, page_size=500)
    return df

@st.cache_data(ttl=30)
def fetch_transactions_paginated(filters=None, page=1, page_size=25):
    """
    Fetch transactions matching search filters from SMART_BANKING.FRAUD.TRANSACTIONS.
    Adds calculated FRAUD_RISK_SCORE, RISK_LEVEL, RISK_BADGE, and RISK_BREAKDOWN.
    """
    conn = get_snowflake_connection()
    if conn is None:
        return pd.DataFrame(), 0
    try:
        where_clause, params = build_where_clause(filters)
        
        cursor = conn.cursor()
        count_query = f"""
        SELECT COUNT(*) 
        FROM SMART_BANKING.FRAUD.TRANSACTIONS T
        LEFT JOIN ACCOUNTS A ON T.ACCOUNT_NUMBER = A.ACCOUNT_NUMBER
        {where_clause}
        """
        cursor.execute(count_query, params)
        total_records = cursor.fetchone()[0]
        cursor.close()
        
        offset = (page - 1) * page_size
        data_query = f"""
        SELECT 
            T.TRANSACTION_ID,
            A.CUSTOMER_ID AS CUSTOMER_ID,
            T.CUSTOMER_NAME,
            T.ACCOUNT_NUMBER,
            T.TRANSACTION_TYPE,
            T.AMOUNT,
            T.LOCATION,
            T.TRANSACTION_DATE,
            T.PAYMENT_MODE,
            T.FRAUD_STATUS
        FROM SMART_BANKING.FRAUD.TRANSACTIONS T
        LEFT JOIN ACCOUNTS A ON T.ACCOUNT_NUMBER = A.ACCOUNT_NUMBER
        {where_clause}
        ORDER BY T.TRANSACTION_DATE DESC, T.TRANSACTION_ID DESC
        LIMIT {page_size} OFFSET {offset}
        """
        df = pd.read_sql(data_query, conn, params=params)
        conn.close()
        df.columns = [col.upper() for col in df.columns]
        
        # Compute dynamic Fraud Risk Score for every row
        scores = []
        levels = []
        badges = []
        breakdowns = []
        
        for idx, row in df.iterrows():
            s, l, b, bd = compute_fraud_risk_score(row)
            scores.append(s)
            levels.append(l)
            badges.append(b)
            breakdowns.append(bd)
            
        df["FRAUD_RISK_SCORE"] = scores
        df["RISK_LEVEL"] = levels
        df["RISK_BADGE"] = badges
        df["RISK_BREAKDOWN"] = breakdowns
        
        # In-memory risk level filtering if specified
        if filters and filters.get("risk_level") and filters["risk_level"] != "All Risk Levels":
            target_level = filters["risk_level"].split()[0].upper()
            df = df[df["RISK_LEVEL"] == target_level].reset_index(drop=True)
            
        return df, total_records
    except Exception as e:
        logger.error(f"Error fetching paginated transactions: {e}")
        return pd.DataFrame(), 0

def fetch_transactions(filters=None, limit=100):
    df, _ = fetch_transactions_paginated(filters=filters, page=1, page_size=limit)
    return df

@st.cache_data(ttl=60)
def fetch_analytics_transactions_over_time(filters=None):
    """
    Count transactions and fraud cases grouped by transaction date with caching.
    """
    conn = get_snowflake_connection()
    if conn is None:
        return []
    try:
        where_clause, params = build_where_clause(filters)
        query = f"""
        SELECT 
            DATE(T.TRANSACTION_DATE) AS TIMESTAMP,
            COUNT(*) AS TX_COUNT,
            SUM(CASE WHEN T.FRAUD_STATUS = 'FRAUD' THEN 1 ELSE 0 END) AS FRAUD_COUNT
        FROM TRANSACTIONS T
        LEFT JOIN ACCOUNTS A ON T.ACCOUNT_NUMBER = A.ACCOUNT_NUMBER
        {where_clause}
        GROUP BY DATE(T.TRANSACTION_DATE)
        ORDER BY DATE(T.TRANSACTION_DATE) ASC
        """
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        df.columns = [col.upper() for col in df.columns]
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error fetching transactions over time: {e}")
        return []

@st.cache_data(ttl=60)
def fetch_analytics_fraud_by_type(filters=None):
    """
    Count fraud transactions grouped by transaction type.
    """
    conn = get_snowflake_connection()
    if conn is None:
        return []
    try:
        where_clause, params = build_where_clause(filters)
        
        where_clause_with_fraud = where_clause
        if where_clause_with_fraud:
            where_clause_with_fraud += " AND T.FRAUD_STATUS = 'FRAUD'"
        else:
            where_clause_with_fraud = "WHERE T.FRAUD_STATUS = 'FRAUD'"
            
        query = f"""
        SELECT 
            T.TRANSACTION_TYPE,
            COUNT(*) AS FRAUD_COUNT
        FROM TRANSACTIONS T
        LEFT JOIN ACCOUNTS A ON T.ACCOUNT_NUMBER = A.ACCOUNT_NUMBER
        {where_clause_with_fraud}
        GROUP BY T.TRANSACTION_TYPE
        ORDER BY FRAUD_COUNT DESC
        """
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        df.columns = [col.upper() for col in df.columns]
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error fetching fraud by type: {e}")
        return []

@st.cache_data(ttl=60)
def fetch_analytics_fraud_by_channel(filters=None):
    """
    Count fraud transactions grouped by payment mode (channel).
    """
    conn = get_snowflake_connection()
    if conn is None:
        return []
    try:
        where_clause, params = build_where_clause(filters)
        
        where_clause_with_fraud = where_clause
        if where_clause_with_fraud:
            where_clause_with_fraud += " AND T.FRAUD_STATUS = 'FRAUD'"
        else:
            where_clause_with_fraud = "WHERE T.FRAUD_STATUS = 'FRAUD'"
            
        query = f"""
        SELECT 
            T.PAYMENT_MODE AS CHANNEL,
            COUNT(*) AS FRAUD_COUNT
        FROM TRANSACTIONS T
        LEFT JOIN ACCOUNTS A ON T.ACCOUNT_NUMBER = A.ACCOUNT_NUMBER
        {where_clause_with_fraud}
        GROUP BY T.PAYMENT_MODE
        ORDER BY FRAUD_COUNT DESC
        """
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        df.columns = [col.upper() for col in df.columns]
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error fetching fraud by channel: {e}")
        return []

@st.cache_data(ttl=60)
def fetch_analytics_fraud_by_location(filters=None):
    """
    Count fraud transactions grouped by location.
    """
    conn = get_snowflake_connection()
    if conn is None:
        return []
    try:
        where_clause, params = build_where_clause(filters)
        
        where_clause_with_fraud = where_clause
        if where_clause_with_fraud:
            where_clause_with_fraud += " AND T.FRAUD_STATUS = 'FRAUD'"
        else:
            where_clause_with_fraud = "WHERE T.FRAUD_STATUS = 'FRAUD'"
            
        query = f"""
        SELECT 
            T.LOCATION,
            COUNT(*) AS FRAUD_COUNT
        FROM TRANSACTIONS T
        LEFT JOIN ACCOUNTS A ON T.ACCOUNT_NUMBER = A.ACCOUNT_NUMBER
        {where_clause_with_fraud}
        GROUP BY T.LOCATION
        ORDER BY FRAUD_COUNT DESC
        """
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        df.columns = [col.upper() for col in df.columns]
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error fetching fraud by location: {e}")
        return []

@st.cache_data(ttl=60)
def fetch_analytics_fraud_by_merchant(filters=None):
    """
    Count fraud transactions grouped by merchant.
    """
    conn = get_snowflake_connection()
    if conn is None:
        return []
    try:
        where_clause, params = build_where_clause(filters)
        
        where_clause_with_fraud = where_clause
        if where_clause_with_fraud:
            where_clause_with_fraud += " AND T.FRAUD_STATUS = 'FRAUD'"
        else:
            where_clause_with_fraud = "WHERE T.FRAUD_STATUS = 'FRAUD'"
            
        query = f"""
        SELECT 
            CASE 
                WHEN T.TRANSACTION_TYPE = 'Bill Payment' THEN 'Utility Corp'
                WHEN T.TRANSACTION_TYPE = 'Online Transfer' THEN 'NetBank Portal'
                WHEN T.TRANSACTION_TYPE = 'ATM Withdrawal' THEN 'ATM Cash'
                ELSE 'Retail Store'
            END AS MERCHANT,
            COUNT(*) AS FRAUD_COUNT
        FROM TRANSACTIONS T
        LEFT JOIN ACCOUNTS A ON T.ACCOUNT_NUMBER = A.ACCOUNT_NUMBER
        {where_clause_with_fraud}
        GROUP BY MERCHANT
        ORDER BY FRAUD_COUNT DESC
        """
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        df.columns = [col.upper() for col in df.columns]
        return df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error fetching fraud by merchant: {e}")
        return []

def add_transaction(txn_data):
    """
    Insert a simulated transaction record into Snowflake.
    """
    conn = get_snowflake_connection()
    if conn is None:
        logger.error("No database connection available for adding transaction.")
        return False, "Database connection failed"
    
    try:
        acct_cursor = conn.cursor()
        acct_cursor.execute("SELECT ACCOUNT_NUMBER FROM ACCOUNTS WHERE CUSTOMER_ID = %s LIMIT 1", (str(txn_data["CUSTOMER_ID"]),))
        acct_row = acct_cursor.fetchone()
        
        if acct_row:
            account_number = acct_row[0]
        else:
            account_number = f"AC{random.randint(100000, 999999)}"
            
        acct_cursor.execute("""
            SELECT T.CUSTOMER_NAME 
            FROM TRANSACTIONS T
            JOIN ACCOUNTS A ON T.ACCOUNT_NUMBER = A.ACCOUNT_NUMBER
            WHERE A.CUSTOMER_ID = %s LIMIT 1
        """, (str(txn_data["CUSTOMER_ID"]),))
        name_row = acct_cursor.fetchone()
        customer_name = name_row[0] if name_row else "Simulated Customer"
        acct_cursor.close()
        
        cursor = conn.cursor()
        
        sql = """
        INSERT INTO TRANSACTIONS (
            TRANSACTION_ID, CUSTOMER_NAME, ACCOUNT_NUMBER, TRANSACTION_TYPE, 
            AMOUNT, LOCATION, TRANSACTION_DATE, PAYMENT_MODE, FRAUD_STATUS
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        fraud_status = "FRAUD" if int(txn_data["IS_FRAUD"]) == 1 else "NORMAL"
        
        params = (
            str(txn_data["TRANSACTION_ID"]),
            str(customer_name),
            str(account_number),
            str(txn_data["TRANSACTION_TYPE"]),
            float(txn_data["AMOUNT"]),
            str(txn_data["LOCATION"]),
            txn_data["TIMESTAMP"].strftime("%Y-%m-%d"),
            str(txn_data["CHANNEL"]),
            fraud_status
        )
        
        cursor.execute(sql, params)
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Transaction {txn_data['TRANSACTION_ID']} added successfully to Snowflake.")
        # Invalidate caches
        st.cache_data.clear()
        return True, "Success"
    except Exception as e:
        logger.error(f"Failed to add transaction to Snowflake: {e}")
        return False, str(e)
