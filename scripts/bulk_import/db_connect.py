#!/usr/bin/env python3
"""
Connect to Azure SQL Database and explore the DanTest schema.
"""

import pyodbc
import struct
from azure.identity import AzureCliCredential

# Connection details from Victor
SERVER = "wwa.database.windows.net"
DATABASE = "wwa_dev"
SCHEMA = "DanTest"

def get_connection():
    """Connect to Azure SQL using Azure CLI credentials."""
    # Get token from Azure CLI
    credential = AzureCliCredential()
    token = credential.get_token("https://database.windows.net/.default")

    # Convert token to bytes for ODBC
    token_bytes = token.token.encode("UTF-16-LE")
    token_struct = struct.pack(f'<I{len(token_bytes)}s', len(token_bytes), token_bytes)

    # Connection string without auth (we'll pass token separately)
    conn_str = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server=tcp:{SERVER},1433;"
        f"Database={DATABASE};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"Connection Timeout=60;"
    )

    # SQL_COPT_SS_ACCESS_TOKEN = 1256
    conn = pyodbc.connect(conn_str, attrs_before={1256: token_struct})
    return conn

def list_tables(conn):
    """List all tables in the DanTest schema."""
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = '{SCHEMA}'
        ORDER BY TABLE_NAME
    """)

    print(f"\n=== Tables in {SCHEMA} schema ===")
    for row in cursor.fetchall():
        print(f"  - {row[0]}")

def show_reference_data(conn):
    """Show the ReferenceData table contents."""
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT CD, CodeTypeCD, Code, Name, Description
        FROM {SCHEMA}.ReferenceData
        ORDER BY CodeTypeCD, CD
    """)

    print(f"\n=== ReferenceData table ===")
    current_type = None
    for row in cursor.fetchall():
        cd, code_type, code, name, desc = row
        if code_type != current_type:
            current_type = code_type
            print(f"\n  [{code_type}]")
        print(f"    CD={cd}: {name} ({code})")

def show_blob_table_structure(conn):
    """Show the Blob table structure."""
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = '{SCHEMA}' AND TABLE_NAME = 'Blob'
        ORDER BY ORDINAL_POSITION
    """)

    print(f"\n=== Blob table structure ===")
    for row in cursor.fetchall():
        col_name, data_type, nullable, default = row
        null_str = "NULL" if nullable == "YES" else "NOT NULL"
        default_str = f" DEFAULT {default}" if default else ""
        print(f"  {col_name}: {data_type} {null_str}{default_str}")

def main():
    print("Connecting to Azure SQL Database...")
    print("(A browser window will open for authentication)")

    conn = get_connection()
    print("Connected!")

    list_tables(conn)
    show_reference_data(conn)
    show_blob_table_structure(conn)

    conn.close()
    print("\nDone!")

if __name__ == "__main__":
    main()
