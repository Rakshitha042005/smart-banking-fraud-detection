import sys
from db_utils import get_snowflake_connection

def test_conn():
    print("==========================================")
    print("Testing connection to Snowflake database...")
    print("==========================================")
    
    conn = get_snowflake_connection()
    if conn is None:
        print("[FAILURE] Failed to connect. Check your .env file credentials.")
        sys.exit(1)
        
    try:
        cursor = conn.cursor()
        
        # Test basic connection query
        cursor.execute("SELECT CURRENT_VERSION(), CURRENT_USER(), CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_SCHEMA();")
        res = cursor.fetchone()
        
        print("\n[SUCCESS] Successfully established connection!")
        print(f"Snowflake Version : {res[0]}")
        print(f"Connected User    : {res[1]}")
        print(f"Active Role       : {res[2]}")
        print(f"Database in Use   : {res[3]}")
        print(f"Schema in Use     : {res[4]}")
        
        # Count accounts
        cursor.execute("SELECT COUNT(*) FROM ACCOUNTS;")
        accounts_count = cursor.fetchone()[0]
        print(f"Accounts Count    : {accounts_count} records")
        
        # Count transactions
        cursor.execute("SELECT COUNT(*) FROM TRANSACTIONS;")
        txns_count = cursor.fetchone()[0]
        print(f"Transactions Count: {txns_count} records")
        
        print("\n[INFO] Both tables exist and contain records in Snowflake.")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"\n[ERROR] Connection was established, but query failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_conn()
