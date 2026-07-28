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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            category TEXT PRIMARY KEY,
            target_amount INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS income (
            billing_cycle TEXT PRIMARY KEY,
            amount INTEGER NOT NULL,
            source TEXT NOT NULL DEFAULT 'Salary'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS income_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            billing_cycle TEXT NOT NULL,
            amount INTEGER NOT NULL,
            source TEXT NOT NULL DEFAULT 'Income',
            timestamp TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS balances (
            account TEXT PRIMARY KEY,
            balance INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
    """)
    
    # Pre-populate default budget targets if empty
    cursor.execute("SELECT COUNT(*) FROM budgets")
    if cursor.fetchone()[0] == 0:
        default_budgets = [
            ("food", 2500000),
            ("groceries", 1500000),
            ("transport", 1000000),
            ("shopping", 1500000),
            ("entertainment", 500000),
            ("bills", 1500000),
            ("investment", 2000000),
            ("family", 1000000),
            ("misc", 500000)
        ]
        cursor.executemany("INSERT INTO budgets (category, target_amount) VALUES (?, ?)", default_budgets)

    # Migration: check if 'account' or 'expense_category' columns exist
    cursor.execute("PRAGMA table_info(transactions)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'account' not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN account TEXT NOT NULL DEFAULT 'permata_cc'")
    if 'expense_category' not in columns:
        cursor.execute("ALTER TABLE transactions ADD COLUMN expense_category TEXT NOT NULL DEFAULT 'misc'")
        
    # Auto-fix: re-categorize any Permata CC transactions previously saved as Non-CC
    cursor.execute("SELECT id, merchant FROM transactions WHERE account = 'permata_cc' AND category NOT IN ('ONLINE', 'OFFLINE')")
    rows_to_fix = cursor.fetchall()
    if rows_to_fix:
        import parser
        for tx_id, merchant in rows_to_fix:
            new_cat = parser.categorize_merchant(merchant, account='permata_cc')
            cursor.execute("UPDATE transactions SET category = ? WHERE id = ?", (new_cat, tx_id))
            
    # Auto-fix: re-evaluate budget expense categories for existing 'misc' rows
    cursor.execute("SELECT id, merchant FROM transactions WHERE expense_category = 'misc'")
    misc_rows = cursor.fetchall()
    if misc_rows:
        import parser
        for tx_id, merchant in misc_rows:
            new_exp_cat = parser.categorize_expense(merchant)
            if new_exp_cat != 'misc':
                cursor.execute("UPDATE transactions SET expense_category = ? WHERE id = ?", (new_exp_cat, tx_id))
                
    conn.commit()
    conn.close()

def check_duplicate_transaction(date_str, merchant, amount, account):
    """
    Checks if an identical transaction (same YYYY-MM-DD date, merchant, amount, account) already exists.
    Returns True if duplicate, False otherwise.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM transactions 
        WHERE strftime('%Y-%m-%d', timestamp) = ? AND merchant = ? AND amount = ? AND account = ?
    """, (date_str, merchant, amount, account))
    row = cursor.fetchone()
    conn.close()
    return True if row else False

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

def delete_transactions_by_account(account, billing_cycle=None):
    """
    Deletes transactions for a specific account, optionally filtered by billing cycle.
    Returns the count of deleted rows.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if billing_cycle:
        cursor.execute("DELETE FROM transactions WHERE account = ? AND billing_cycle = ?", (account, billing_cycle))
    else:
        cursor.execute("DELETE FROM transactions WHERE account = ?", (account,))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count

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
        WHERE billing_cycle = ? AND category NOT IN ('ONLINE', 'OFFLINE') AND account = 'permata_cc'
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
        "permata_savings": 0
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

def get_budgets():
    """
    Returns a dictionary of category -> target_amount.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT category, target_amount FROM budgets")
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

def set_budget(category, target_amount):
    """
    Sets or updates the target budget for a given expense category.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO budgets (category, target_amount) VALUES (?, ?)
        ON CONFLICT(category) DO UPDATE SET target_amount = excluded.target_amount
    """, (category.lower(), target_amount))
    conn.commit()
    conn.close()

def get_budget_status(billing_cycle):
    """
    Computes budget status (spent vs target, % used, and warning status) for all categories.
    """
    budgets = get_budgets()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT expense_category, SUM(amount) FROM transactions
        WHERE billing_cycle = ?
        GROUP BY expense_category
    """, (billing_cycle,))
    spent_dict = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    
    status_list = []
    for cat, target in budgets.items():
        spent = spent_dict.get(cat, 0)
        pct = (spent / target * 100) if target > 0 else 0
        warning = None
        if pct >= 100:
            warning = "OVER"
        elif pct >= 80:
            warning = "WARN"
        status_list.append({
            "category": cat,
            "spent": spent,
            "target": target,
            "pct": round(pct, 1),
            "warning": warning
        })
    return status_list

def get_recurring_subscriptions(billing_cycle):
    """
    Scans transactions for recurring payments, subscriptions, and installments (e.g. SPayLater, Game Pass, Telkomsel, etc.).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timestamp, merchant, amount, account, expense_category FROM transactions
        WHERE billing_cycle = ? AND (
            merchant LIKE '%SPAYLATER%' OR merchant LIKE '%GAME PASS%' OR 
            merchant LIKE '%NETFLIX%' OR merchant LIKE '%SPOTIFY%' OR 
            merchant LIKE '%TELKOMSEL%' OR merchant LIKE '%INDIHOME%' OR 
            merchant LIKE '%KOST%' OR merchant LIKE '%BPJS%' OR merchant LIKE '%HALODOC%'
        )
        ORDER BY amount DESC
    """, (billing_cycle,))
    rows = cursor.fetchall()
    conn.close()
    
    subscriptions = []
    for row in rows:
        subscriptions.append({
            "id": row[0],
            "date": row[1][:10],
            "merchant": row[2],
            "amount": row[3],
            "account": row[4],
            "category": row[5]
        })
    return subscriptions

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

def set_income(billing_cycle, amount, source="Salary"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO income (billing_cycle, amount, source) VALUES (?, ?, ?)
        ON CONFLICT(billing_cycle) DO UPDATE SET amount = excluded.amount, source = excluded.source
    """, (billing_cycle, amount, source))
    conn.commit()
    conn.close()

def get_income(billing_cycle):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT amount, source FROM income WHERE billing_cycle = ?", (billing_cycle,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"amount": row[0], "source": row[1]}
    return {"amount": 0, "source": "Salary"}

def add_income_entry(billing_cycle, amount, source="Income"):
    """
    Adds a new itemized income entry (e.g. Salary, Freelance, Bonus, Dividends) for a billing cycle.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO income_entries (billing_cycle, amount, source, timestamp)
        VALUES (?, ?, ?, ?)
    """, (billing_cycle, amount, source, now_str))
    conn.commit()
    conn.close()

def get_income_summary(billing_cycle):
    """
    Returns total income sum and list of itemized income entries for a billing cycle.
    Also falls back to old 'income' table if legacy data exists.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, amount, source, timestamp FROM income_entries
        WHERE billing_cycle = ?
        ORDER BY id ASC
    """, (billing_cycle,))
    rows = cursor.fetchall()
    
    entries = []
    total = 0
    for r in rows:
        entries.append({"id": r[0], "amount": r[1], "source": r[2], "timestamp": r[3]})
        total += r[1]
        
    # Check legacy table if no entries found
    if not entries:
        cursor.execute("SELECT amount, source FROM income WHERE billing_cycle = ?", (billing_cycle,))
        legacy = cursor.fetchone()
        if legacy and legacy[0] > 0:
            total = legacy[0]
            entries.append({"id": 0, "amount": legacy[0], "source": legacy[1], "timestamp": ""})
            
    conn.close()
    return {"total_amount": total, "entries": entries}

def clear_income(billing_cycle):
    """
    Clears all income entries for a billing cycle.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM income_entries WHERE billing_cycle = ?", (billing_cycle,))
    cursor.execute("DELETE FROM income WHERE billing_cycle = ?", (billing_cycle,))
    conn.commit()
    conn.close()

def set_balance(account, balance):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO balances (account, balance, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(account) DO UPDATE SET balance = excluded.balance, updated_at = excluded.updated_at
    """, (account.lower(), balance, now_str))
    conn.commit()
    conn.close()

def execute_internal_transfer(from_account, to_account, amount):
    """
    Transfers liquid balance from one bank account to another without creating an expense.
    """
    balances = get_all_balances()
    from_acc = from_account.lower()
    to_acc = to_account.lower()
    
    from_bal = balances.get(from_acc, {}).get("balance", 0)
    to_bal = balances.get(to_acc, {}).get("balance", 0)
    
    new_from_bal = max(0, from_bal - amount)
    new_to_bal = to_bal + amount
    
    set_balance(from_acc, new_from_bal)
    set_balance(to_acc, new_to_bal)
    
    return new_from_bal, new_to_bal

def get_all_balances():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT account, balance, updated_at FROM balances")
    rows = cursor.fetchall()
    conn.close()
    
    defaults = {"bank_saqu": 0, "line_bank": 0, "bca": 0, "permata_savings": 0, "permata_cc": 0}
    res = {}
    for r in rows:
        res[r[0]] = {"balance": r[1], "updated_at": r[2]}
    for k in defaults:
        if k not in res:
            res[k] = {"balance": 0, "updated_at": "Never"}
    return res

def get_total_budget_summary(billing_cycle):
    budgets = get_budgets()
    total_budget_target = sum(budgets.values())
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE billing_cycle = ?", (billing_cycle,))
    total_realization = cursor.fetchone()[0] or 0
    conn.close()
    
    remaining_budget = total_budget_target - total_realization
    pct_realized = (total_realization / total_budget_target * 100) if total_budget_target > 0 else 0
    
    return {
        "total_budget_target": total_budget_target,
        "total_realization": total_realization,
        "remaining_budget": remaining_budget,
        "pct_realized": round(pct_realized, 1)
    }

