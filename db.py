import os
import sqlite3
from datetime import datetime

DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "expenses.db")

def init_db():
    """
    Initializes the SQLite database and creates the transactions table if it doesn't exist.
    Also handles incremental migration if 'account' or 'expense_category' columns are missing.
    """
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            merchant TEXT NOT NULL,
            amount INTEGER NOT NULL,
            category TEXT NOT NULL,
            billing_cycle TEXT NOT NULL,
            account TEXT NOT NULL DEFAULT 'permata_cc',
            expense_category TEXT NOT NULL DEFAULT 'misc'
        )
    """)
    # Migration: check if 'account' column exists in existing database
    cursor.execute("PRAGMA table_info(transactions)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'account' not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN account TEXT NOT NULL DEFAULT 'permata_cc'")
    if 'expense_category' not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN expense_category TEXT NOT NULL DEFAULT 'misc'")
    conn.commit()
    conn.close()

def add_transaction(merchant, amount, category, billing_cycle, timestamp=None, account="permata_cc", expense_category="misc"):
    """
    Adds a transaction to the database, specifying the account and detailed expense category.
    Returns the ID of the newly inserted transaction.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if not timestamp:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO transactions (timestamp, merchant, amount, category, billing_cycle, account, expense_category)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (timestamp, merchant, amount, category, billing_cycle, account, expense_category))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def delete_last_transaction():
    """
    Deletes the most recently added transaction.
    Returns the details of the deleted transaction if successful, else None.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Retrieve the last transaction to return it for user confirmation
    cursor.execute("""
        SELECT id, merchant, amount, category, billing_cycle, account, expense_category FROM transactions
        ORDER BY id DESC LIMIT 1
    """)
    row = cursor.fetchone()
    if row:
        tx_id, merchant, amount, category, billing_cycle, account, expense_category = row
        cursor.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        conn.commit()
        conn.close()
        return {
            "id": tx_id,
            "merchant": merchant,
            "amount": amount,
            "category": category,
            "billing_cycle": billing_cycle,
            "account": account,
            "expense_category": expense_category
        }
    conn.close()
    return None

def get_stats(billing_cycle):
    """
    Calculates CC-specific statistics (ONLINE/OFFLINE/UNMAPPED for permata_cc),
    provides a breakdown of spending across all other accounts, and sums up spending by expense category.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Sum Permata CC specific totals
    cursor.execute("""
        SELECT SUM(amount) FROM transactions
        WHERE billing_cycle = ? AND category = 'ONLINE' AND account = 'permata_cc'
    """, (billing_cycle,))
    cc_online = cursor.fetchone()[0] or 0
    
    cursor.execute("""
        SELECT SUM(amount) FROM transactions
        WHERE billing_cycle = ? AND category = 'OFFLINE' AND account = 'permata_cc'
    """, (billing_cycle,))
    cc_offline = cursor.fetchone()[0] or 0
    
    cursor.execute("""
        SELECT SUM(amount) FROM transactions
        WHERE billing_cycle = ? AND category = 'UNMAPPED' AND account = 'permata_cc'
    """, (billing_cycle,))
    cc_unmapped = cursor.fetchone()[0] or 0
    
    # 2. Sum spending grouped by account
    cursor.execute("""
        SELECT account, SUM(amount) FROM transactions
        WHERE billing_cycle = ?
        GROUP BY account
    """, (billing_cycle,))
    account_rows = cursor.fetchall()
    
    # 3. Sum spending grouped by detailed expense category
    cursor.execute("""
        SELECT expense_category, SUM(amount) FROM transactions
        WHERE billing_cycle = ?
        GROUP BY expense_category
        ORDER BY SUM(amount) DESC
    """, (billing_cycle,))
    expense_rows = cursor.fetchall()
    
    conn.close()
    
    cc_total = cc_online + cc_offline + cc_unmapped
    
    # Initialize all potential accounts to 0 for display
    accounts_breakdown = {
        "permata_cc": 0,
        "bank_saqu": 0,
        "bca": 0,
        "line_bank": 0,
        "general": 0
    }
    for row in account_rows:
        acc_name, total = row
        accounts_breakdown[acc_name] = total
        
    all_accounts_total = sum(accounts_breakdown.values())
    
    return {
        "cc_online": cc_online,
        "cc_offline": cc_offline,
        "cc_unmapped": cc_unmapped,
        "cc_total": cc_total,
        "accounts_breakdown": accounts_breakdown,
        "all_accounts_total": all_accounts_total,
        "expense_categories": expense_rows
    }

def export_transactions_to_csv():
    """
    Exports all transactions in the database as CSV byte data, including account and expense category.
    """
    import csv
    import io
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timestamp, merchant, amount, category, billing_cycle, account, expense_category 
        FROM transactions 
        ORDER BY id ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp", "Merchant", "Amount", "Category", "Billing Cycle", "Account", "Expense Category"])
    writer.writerows(rows)
    
    csv_data = output.getvalue().encode('utf-8')
    output.close()
    return csv_data

def check_duplicate(merchant, amount, date_str):
    """
    Checks if a transaction with the same merchant, amount, and date already exists.
    date_str should be in 'YYYY-MM-DD' format.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Check for same merchant, amount, and date (either starting timestamp prefix or direct date match)
    cursor.execute("""
        SELECT id FROM transactions 
        WHERE merchant = ? AND amount = ? AND (
            timestamp LIKE ? OR date(timestamp) = ?
        )
    """, (merchant, amount, f"{date_str}%", date_str))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def edit_transaction(tx_id, field, value):
    """
    Edits a specific field of a transaction by ID.
    Valid fields: merchant, amount, category, billing_cycle, account, expense_category.
    Returns the updated transaction dict or None if not found.
    """
    import re
    
    valid_fields = ['merchant', 'amount', 'category', 'billing_cycle', 'account', 'expense_category']
    if field not in valid_fields:
        raise ValueError(f"Invalid field: {field}. Allowed fields: {valid_fields}")
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if transaction exists
    cursor.execute("SELECT id FROM transactions WHERE id = ?", (tx_id,))
    if not cursor.fetchone():
        conn.close()
        return None
        
    # Process types
    if field == 'amount':
        try:
            if isinstance(value, str):
                # Clean currency symbols and dots/commas
                cleaned = re.sub(r'\D', '', value)
                value = int(cleaned)
            else:
                value = int(value)
        except ValueError:
            conn.close()
            raise ValueError("Amount must be a valid integer.")
            
    if field == 'category':
        value = value.upper()
        
    if field == 'expense_category':
        value = value.lower()
        
    # Update row
    cursor.execute(f"UPDATE transactions SET {field} = ? WHERE id = ?", (value, tx_id))
    conn.commit()
    
    # Retrieve updated transaction
    cursor.execute("""
        SELECT id, timestamp, merchant, amount, category, billing_cycle, account, expense_category 
        FROM transactions WHERE id = ?
    """, (tx_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "timestamp": row[1],
            "merchant": row[2],
            "amount": row[3],
            "category": row[4],
            "billing_cycle": row[5],
            "account": row[6],
            "expense_category": row[7]
        }
    return None

