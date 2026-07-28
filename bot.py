import os
import re
import logging
import telebot
from datetime import datetime, timedelta
import db
import parser

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)
logger = logging.getLogger("expense-bro")

TELE_TOKEN = os.getenv("TELE_TOKEN", "")

if not TELE_TOKEN:
    raise RuntimeError("Missing TELE_TOKEN environment variable. Please configure it in your environment.")

# Initialize the Bot and Database
bot = telebot.TeleBot(TELE_TOKEN)
db.init_db()

# Load Configuration for User IDs and Billing Cycles
ALLOWED_USERS_RAW = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS = [int(uid.strip()) for uid in ALLOWED_USERS_RAW.split(",") if uid.strip().isdigit()]

try:
    BILLING_CYCLE_START_DAY = int(os.getenv("BILLING_CYCLE_START_DAY", "1"))
except ValueError:
    BILLING_CYCLE_START_DAY = 1

def is_allowed(message):
    """
    Checks if the user sending the message is authorized to use the bot.
    """
    if not ALLOWED_USER_IDS:
        # If no user IDs are configured, warn but allow the transaction so the user can easily get their ID
        return True
    
    if message.from_user.id in ALLOWED_USER_IDS:
        return True
    
    # Denied response displaying their ID for convenient copying
    bot.reply_to(
        message,
        f"🔒 *Access Denied.*\n"
        f"This bot is private and restricted to specific user accounts.\n\n"
        f"Your Telegram User ID is `{message.from_user.id}`. "
        f"Please add it to the `ALLOWED_USER_IDS` variable in your `.env` file to grant access.",
        parse_mode="Markdown"
    )
    return False

def get_billing_cycle_info(now=None):
    """
    Computes the current billing cycle label (e.g. '2026-07') and start/end dates
    based on the configured start day.
    """
    if now is None:
        now = datetime.now()
    start_day = BILLING_CYCLE_START_DAY
    
    if start_day <= 1:
        # Standard calendar month (1st to last day of current month)
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)
        end_date = (next_month - timedelta(days=1)).replace(hour=23, minute=59, second=59)
        cycle_label = end_date.strftime("%Y-%m")
    else:
        # Custom cycle starting on start_day (e.g., payday/statement date)
        if now.day >= start_day:
            start_date = now.replace(day=start_day, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=start_day)
            else:
                next_month = now.replace(month=now.month + 1, day=start_day)
            end_date = (next_month - timedelta(days=1)).replace(hour=23, minute=59, second=59)
            cycle_label = end_date.strftime("%Y-%m")
        else:
            # Belongs to cycle that started last month
            if now.month == 1:
                last_month_start = now.replace(year=now.year - 1, month=12, day=start_day)
            else:
                last_month_start = now.replace(month=now.month - 1, day=start_day)
            start_date = last_month_start.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now.replace(day=start_day) - timedelta(days=1)
            end_date = end_date.replace(hour=23, minute=59, second=59)
            cycle_label = end_date.strftime("%Y-%m")
            
    return cycle_label, start_date, end_date

def format_rupiah(value):
    """
    Formats an integer amount as Indonesian Rupiah currency text (e.g. Rp 1.500.000).
    """
    return f"Rp {value:,.0f}".replace(",", ".")

def generate_report(stats, cycle_label, start_date, end_date):
    """
    Generates a beautifully formatted markdown report for the user's spend metrics,
    separating CC tracking from general account balances and detailed expense categories.
    """
    cc_online = stats["cc_online"]
    cc_offline = stats["cc_offline"]
    cc_unmapped = stats["cc_unmapped"]
    cc_total = stats["cc_total"]
    accounts = stats["accounts_breakdown"]
    all_total = stats["all_accounts_total"]
    expense_categories = stats.get("expense_categories", [])
    
    activation_gate = 5000000
    delta = activation_gate - cc_total
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    report = []
    report.append(f"📊 *Status Report - Cycle: {cycle_label}*")
    report.append(f"📅 *Period:* `{start_str}` to `{end_str}`\n")
    
    report.append(f"💳 *PERMATA CC TRACKER:*")
    report.append(f"━━━━━━━━━━━━━━━━━━━")
    report.append(f"🌐 *ONLINE Spend:* `{format_rupiah(cc_online)}` (cap: 4jt)")
    report.append(f"🏬 *OFFLINE Spend:* `{format_rupiah(cc_offline)}` (cap: 2jt)")
    if cc_unmapped > 0:
        report.append(f"📦 *Other Retail Spend:* `{format_rupiah(cc_unmapped)}`")
    report.append(f"━━━━━━━━━━━━━━━━━━━")
    report.append(f"💳 *CC Total Retail:* `{format_rupiah(cc_total)}`")
    
    # Activation Gate Status
    if cc_total >= activation_gate:
        report.append(f"✅ *CC Cashback Active!* (Passed 5jt gate)")
    else:
        report.append(f"❌ *CC Cashback Inactive* (`{format_rupiah(delta)}` remaining to 5jt gate)")
        
    # Optimal Threshold Warnings
    warnings = []
    if cc_online > 4000000:
        warnings.append(f"⚠️ *Warning:* ONLINE spend exceeds the 4,000,000 IDR optimal threshold by `{format_rupiah(cc_online - 4000000)}`!")
    if cc_offline > 2000000:
        warnings.append(f"⚠️ *Warning:* OFFLINE spend exceeds the 2,000,000 IDR optimal threshold by `{format_rupiah(cc_offline - 2000000)}`!")
        
    if warnings:
        report.append(f"━━━━━━━━━━━━━━━━━━━")
        report.extend(warnings)
        
    # Accounts spending overview
    report.append(f"\n💼 *ALL ACCOUNTS OVERVIEW:*")
    report.append(f"━━━━━━━━━━━━━━━━━━━")
    
    acc_icons = {
        "permata_cc": "💳 Permata CC",
        "bank_saqu": "🐷 Bank Saqu",
        "bca": "🏦 BCA",
        "line_bank": "📱 Line Bank",
        "permata_savings": "💰 Permata Savings"
    }
    
    for acc_name, total in accounts.items():
        if total > 0 or acc_name == "permata_cc":
            label = acc_icons.get(acc_name, f"💰 {acc_name}")
            report.append(f"{label}: `{format_rupiah(total)}`")
            
    report.append(f"━━━━━━━━━━━━━━━━━━━")
    report.append(f"💰 *Total Spend (All):* `{format_rupiah(all_total)}`")
    
    # Detailed expense categories overview
    if expense_categories:
        report.append(f"\n📈 *EXPENSE CATEGORIES:*")
        report.append(f"━━━━━━━━━━━━━━━━━━━")
        cat_icons = {
            "food": "🍔 Food",
            "groceries": "🛒 Groceries",
            "transport": "🚗 Transport",
            "entertainment": "🎬 Entertainment",
            "shopping": "🛍️ Shopping",
            "bills": "📄 Bills",
            "investment": "📈 Investment",
            "family": "❤️ Family",
            "misc": "📦 Misc"
        }
        for cat_name, cat_total in expense_categories:
            if cat_total > 0:
                label = cat_icons.get(cat_name, f"📦 {cat_name.capitalize()}")
                report.append(f"{label}: `{format_rupiah(cat_total)}`")
                
    return "\n".join(report)

def parse_manual_add_command(args_str):
    """
    Parses arguments for `/add <amount> <merchant> [category/budget_category/account...]` manual entry.
    Extracts amount, merchant, and automatically scans trailing words for any permutation of
    account aliases, CC cashback categories, and detailed expense categories.
    
    Returns (amount, merchant, category, account, expense_category) or None if parsing fails.
    """
    import re
    
    words = args_str.strip().split()
    if len(words) < 2:
        return None
        
    amt_raw = words[0]
    
    # Defaults
    account = "permata_cc"
    category = None
    expense_category = None
    
    acc_map = {
        'bca': 'bca',
        'saqu': 'bank_saqu',
        'saqu_payroll': 'bank_saqu',
        'line': 'line_bank',
        'line_bank': 'line_bank',
        'permata': 'permata_cc',
        'permata_cc': 'permata_cc',
        'cc': 'permata_cc'
    }
    
    cashback_cats = ['online', 'offline', 'non-cc']
    expense_cats = ['food', 'groceries', 'transport', 'entertainment', 'shopping', 'bills', 'investment', 'family', 'misc']
    
    # Scan up to 3 trailing arguments
    for _ in range(3):
        if len(words) < 2:
            break
        last_word = words[-1].lower()
        
        # Check if it matches an account alias
        if last_word in acc_map:
            account = acc_map[last_word]
            words.pop()
            continue
            
        # Check if it matches a card cashback category
        if last_word in cashback_cats:
            category = "Non-CC" if last_word == "non-cc" else last_word.upper()
            words.pop()
            continue
            
        # Check if it matches a detailed budget category
        if last_word in expense_cats:
            expense_category = last_word.lower()
            words.pop()
            continue
            
        # If the word doesn't match any option, it's part of the merchant name
        break
        
    if len(words) < 2:
        return None
        
    merchant = " ".join(words[1:]).strip()
    
    # Clean merchant name from quotes
    if (merchant.startswith('"') and merchant.endswith('"')) or (merchant.startswith("'") and merchant.endswith("'")):
        merchant = merchant[1:-1].strip()
        
    # Clean amount
    amount = None
    if amt_raw.lower().endswith("k"):
        try:
            amount = int(float(amt_raw[:-1]) * 1000)
        except ValueError:
            return None
    else:
        # Remove Rp prefix and non-digits
        digits = re.sub(r'\D', '', amt_raw)
        if digits:
            amount = int(digits)
            
    if amount is None:
        return None
        
    # Apply defaults if omitted
    if not category:
        category = parser.categorize_merchant(merchant)
    if not expense_category:
        expense_category = parser.categorize_expense(merchant)
        
    return amount, merchant, category, account, expense_category

@bot.message_handler(commands=["start", "help"])
def show_help(message):
    if not is_allowed(message):
        return
        
    start_day_info = f"1st (Calendar Month)" if BILLING_CYCLE_START_DAY <= 1 else f"{BILLING_CYCLE_START_DAY}th"
    
    help_text = (
        "🤖 *Welcome to Expense Bro!*\n\n"
        "I track your credit card spend to optimize your cashback targets (5,000,000 IDR activation gate).\n\n"
        f"⚙️ *Current Billing Cycle Start Day:* `{start_day_info}`\n\n"
        "*Commands:*\n"
        "• `/stats` - View current billing cycle totals, limits, and gate status.\n"
        "• `/add <amount> <merchant> [category] [account]` - Log a transaction manually.\n"
        "• `/undo` - Remove the last logged transaction.\n"
        "• `/export` - Download transaction history (CSV) and database backup.\n\n"
        "*Accounts Supported:* `cc`/`permata`, `saqu`, `bca`, `line`\n\n"
        "*Automatic Logging:*\n"
        "Forward bank transaction SMS/notifications directly to me! I will automatically parse the amount, merchant, and route them to their respective account."
    )
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=["stats"])
def show_stats(message):
    if not is_allowed(message):
        return
        
    cycle_label, start_date, end_date = get_billing_cycle_info()
    stats = db.get_stats(cycle_label)
    report = generate_report(stats, cycle_label, start_date, end_date)
    bot.reply_to(message, report, parse_mode="Markdown")

@bot.message_handler(commands=["add"])
def add_manual(message):
    if not is_allowed(message):
        return
        
    args_str = message.text[len("/add "):].strip()
    if not args_str:
        help_msg = (
            "📝 *Manual Log Format:*\n"
            "`/add <amount> <merchant> [category] [account]`\n\n"
            "*Accounts supported:* `cc`/`permata`, `saqu`, `bca`, `line`\n\n"
            "*Examples:*\n"
            "• `/add 150000 Tokopedia` (auto ONLINE, default permata_cc)\n"
            "• `/add 50k Starbucks offline bca` (Starbucks to BCA offline)\n"
            "• `/add 1.2jt \"Transfer Ibu\" saqu` (1.2jt unmapped to Bank Saqu)"
        )
        bot.reply_to(message, help_msg, parse_mode="Markdown")
        return
        
    parsed = parse_manual_add_command(args_str)
    if not parsed:
        bot.reply_to(
            message,
            "❌ *Invalid format.*\n"
            "Use: `/add <amount> <merchant> [category] [account]`\n"
            "Examples: `/add 150k Tokopedia` or `/add 50k Starbucks offline bca`",
            parse_mode="Markdown"
        )
        return
        
    amount, merchant, category, account, expense_category = parsed
    if account != "permata_cc":
        category = "Non-CC"
        
    cycle_label, start_date, end_date = get_billing_cycle_info()
    
    # Save to database and capture the inserted transaction ID
    tx_id = db.add_transaction(merchant, amount, category, cycle_label, account=account, expense_category=expense_category)
    
    # Get updated stats
    stats = db.get_stats(cycle_label)
    report = generate_report(stats, cycle_label, start_date, end_date)
    
    cc_cat_line = ""
    if account == "permata_cc":
        label = "Non-CC" if category == "Non-CC" else category.capitalize()
        cc_cat_line = f"• *CC Cashback:* `{label}`\n"
    
    success_msg = (
        f"📝 *Manually Logged (ID: #{tx_id})!*\n"
        f"• *Merchant:* `{merchant}`\n"
        f"• *Amount:* `{format_rupiah(amount)}`\n"
        f"{cc_cat_line}"
        f"• *Budget Category:* `{expense_category.capitalize()}`\n"
        f"• *Account:* `{account}`\n\n"
        f"{report}"
    )
    bot.reply_to(message, success_msg, parse_mode="Markdown")

@bot.message_handler(commands=["edit"])
def edit_manual(message):
    if not is_allowed(message):
        return
        
    args_str = message.text[len("/edit "):].strip()
    if not args_str:
        help_msg = (
            "✏️ *Edit Transaction Format:*\n"
            "`/edit <id> <field> <value>`\n\n"
            "*Allowed fields:* `amount`, `merchant`, `category`, `expense_category`, `account`\n\n"
            "*Examples:*\n"
            "• `/edit 14 amount 55000`\n"
            "• `/edit 14 merchant \"Starbucks Coffee\"`\n"
            "• `/edit 14 expense_category food`"
        )
        bot.reply_to(message, help_msg, parse_mode="Markdown")
        return
        
    # Match layout: ID, field, then the rest as value
    match = re.match(r'^(\d+)\s+([a-zA-Z_]+)\s+(.+)$', args_str)
    if not match:
        bot.reply_to(message, "❌ *Invalid format.* Use: `/edit <id> <field> <value>`", parse_mode="Markdown")
        return
        
    tx_id = int(match.group(1))
    field = match.group(2).lower()
    value = match.group(3).strip()
    
    # Strip enclosing quotes if present
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1].strip()
        
    alias_fields = {
        'budget': 'expense_category',
        'budget_category': 'expense_category',
        'expense_category': 'expense_category',
        'category': 'category',
        'amount': 'amount',
        'price': 'amount',
        'merchant': 'merchant',
        'store': 'merchant',
        'account': 'account',
        'source': 'account'
    }
    
    if field not in alias_fields:
        bot.reply_to(
            message, 
            f"❌ *Invalid field:* `{field}`.\nAllowed fields: `amount`, `merchant`, `category`, `expense_category`, `account`.", 
            parse_mode="Markdown"
        )
        return
        
    db_field = alias_fields[field]
    
    try:
        updated = db.edit_transaction(tx_id, db_field, value)
        if updated:
            cycle_label, start_date, end_date = get_billing_cycle_info()
            stats = db.get_stats(cycle_label)
            report = generate_report(stats, cycle_label, start_date, end_date)
            
            success_msg = (
                f"✏️ *Transaction #{tx_id} Updated!*\n"
                f"• *Field:* `{db_field}` $\rightarrow$ `{value}`\n"
                f"• *Current:* `{updated['merchant']}` | `{format_rupiah(updated['amount'])}` | `{updated['expense_category']}` | `{updated['account']}`\n\n"
                f"{report}"
            )
            bot.reply_to(message, success_msg, parse_mode="Markdown")
        else:
            bot.reply_to(message, f"❌ Transaction ID `#{tx_id}` not found in database.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ *Edit failed:* {e}", parse_mode="Markdown")

@bot.message_handler(commands=["undo"])
def undo_last(message):
    if not is_allowed(message):
        return
        
    deleted = db.delete_last_transaction()
    if deleted:
        cycle_label, start_date, end_date = get_billing_cycle_info()
        stats = db.get_stats(cycle_label)
        report = generate_report(stats, cycle_label, start_date, end_date)
        
        # Format the deletion log nicely depending on whether it is a CC transaction
        if deleted['account'] == 'permata_cc':
            cc_label = "Non-CC" if deleted['category'] == 'Non-CC' else deleted['category']
            meta_str = f"({cc_label}/{deleted['expense_category'].capitalize()})"
        else:
            meta_str = f"({deleted['expense_category'].capitalize()})"
            
        reply_msg = (
            f"🗑️ *Undone last transaction!*\n"
            f"• *Removed:* `{deleted['merchant']}` | `{format_rupiah(deleted['amount'])}` {meta_str} from `{deleted['account']}`\n\n"
            f"{report}"
        )
        bot.reply_to(message, reply_msg, parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ No transactions found to undo in database.", parse_mode="Markdown")

@bot.message_handler(commands=["card"])
def recommend_card(message):
    if not is_allowed(message):
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        bot.reply_to(
            message,
            "💡 *Smart Card Recommender*\nUsage: `/card Shopee 150000` or `/card SPBU 300000` or `/card Grab 50000`",
            parse_mode="Markdown"
        )
        return
        
    merchant = args[1].strip()
    amount = 0
    if len(args) >= 3:
        parsed_amt = parser.parse_amount_input(args[2])
        if parsed_amt:
            amount = parsed_amt
            
    current_cycle, _, _ = get_billing_cycle_info()
    stats = db.get_stats(current_cycle)
    
    total_cc_spend = stats["cc_online"] + stats["cc_offline"] + stats["cc_unmapped"]
    activation_gate = 5000000
    needed = activation_gate - total_cc_spend
    
    cc_category = parser.categorize_merchant(merchant, account="permata_cc")
    expense_cat = parser.categorize_expense(merchant)
    
    if total_cc_spend < activation_gate:
        rec_title = "💳 RECOMMENDED CARD: Permata Credit Card"
        rec_reason = (
            f"Your Permata CC is at *{format_rupiah(total_cc_spend)}* / *5.0M IDR*.\n"
            f"You need *{format_rupiah(needed)}* more to unlock your 10% cashback gate!\n"
            f"This transaction matches *{cc_category}* category ({expense_cat.capitalize()})."
        )
    else:
        rec_title = "🏦 RECOMMENDED ACCOUNT: Bank Saqu or Line Bank"
        rec_reason = (
            f"🎉 Your Permata CC 5M Cashback Gate is ALREADY UNLOCKED (*{format_rupiah(total_cc_spend)}* spent)!\n"
            f"Save your credit card limit and pay via **Bank Saqu** or **Line Bank** to keep your funds earning 5% interest yield."
        )
        
    reply = (
        f"🎯 *{rec_title}*\n\n"
        f"• *Item/Merchant:* `{merchant}`\n"
        f"{f'• *Amount:* `{format_rupiah(amount)}`' if amount > 0 else ''}\n\n"
        f"{rec_reason}"
    )
    bot.reply_to(message, reply, parse_mode="Markdown")

@bot.message_handler(commands=["budget"])
def budget_status_command(message):
    if not is_allowed(message):
        return
    current_cycle, _, _ = get_billing_cycle_info()
    statuses = db.get_budget_status(current_cycle)
    summary = db.get_total_budget_summary(current_cycle)
    
    lines = [
        f"🎯 *TOTAL BUDGET SUMMARY ({current_cycle})*",
        f"• *Target Budget:* `{format_rupiah(summary['total_budget_target'])}`",
        f"• *Realization (Spent):* `{format_rupiah(summary['total_realization'])}` ({summary['pct_realized']}%)",
        f"• *Remaining Budget:* `{format_rupiah(summary['remaining_budget'])}`\n",
        f"📊 *Category Realization Breakdown:*"
    ]
    
    for s in statuses:
        cat_name = s["category"].capitalize()
        spent_str = format_rupiah(s["spent"])
        target_str = format_rupiah(s["target"])
        pct = s["pct"]
        
        badge = "🟢"
        if s["warning"] == "OVER":
            badge = "🔴 OVER BUDGET!"
        elif s["warning"] == "WARN":
            badge = "🟡 NEAR LIMIT"
            
        lines.append(f"{badge} *{cat_name}:* `{spent_str}` / `{target_str}` ({pct}%)")
        
    bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")

@bot.message_handler(commands=["income"])
def handle_set_income(message):
    if not is_allowed(message):
        return
    args = message.text.split(maxsplit=2)
    current_cycle, _, _ = get_billing_cycle_info()
    
    if len(args) < 2:
        inc_summary = db.get_income_summary(current_cycle)
        total_amt = inc_summary["total_amount"]
        entries = inc_summary["entries"]
        
        lines = [
            f"💵 *INCOME LOG ({current_cycle})*",
            f"• *Total Monthly Income:* `{format_rupiah(total_amt)}`\n"
        ]
        
        if entries:
            lines.append("📋 *Itemized Sources:*")
            for e in entries:
                lines.append(f"• `{format_rupiah(e['amount'])}` — *{e['source'].capitalize()}*")
        else:
            lines.append("ℹ️ *No income logged for this cycle yet.*")
            
        lines.append("\n💡 *To add income:* `/income 12m Salary` or `/income 5m Freelance`")
        lines.append("💡 *To reset income:* `/income clear`")
        bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")
        return
        
    if args[1].lower() == "clear":
        db.clear_income(current_cycle)
        bot.reply_to(message, f"🗑️ *Cleared all income entries for cycle `{current_cycle}`.*", parse_mode="Markdown")
        return
        
    amt = parser.parse_amount_input(args[1])
    if not amt:
        bot.reply_to(message, "❌ Please enter a valid income amount (e.g. `/income 12m Salary` or `/income 5000k Bonus`).", parse_mode="Markdown")
        return
        
    source = args[2].strip().title() if len(args) >= 3 else "Income"
    db.add_income_entry(current_cycle, amt, source)
    
    inc_summary = db.get_income_summary(current_cycle)
    bot.reply_to(
        message,
        f"💵 *Income Logged!*\n"
        f"• *Added:* `{format_rupiah(amt)}` (*{source}*)\n"
        f"• *Total Monthly Income:* `{format_rupiah(inc_summary['total_amount'])}`",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["transfer", "trf"])
def handle_transfer(message):
    if not is_allowed(message):
        return
    args = message.text.split()
    if len(args) < 4:
        bot.reply_to(
            message,
            "💡 *Internal Transfer (0 Expense Created)*\nUsage: `/transfer <amount> <from_account> <to_account>`\nE.g.: `/transfer 5m bank_saqu line_bank` or `/transfer 2.5m bank_saqu bca`",
            parse_mode="Markdown"
        )
        return
        
    amt = parser.parse_amount_input(args[1])
    if not amt:
        bot.reply_to(message, "❌ Invalid amount. E.g. `/transfer 5m bank_saqu line_bank`", parse_mode="Markdown")
        return
        
    from_acc = args[2].strip().lower()
    to_acc = args[3].strip().lower()
    
    new_from, new_to = db.execute_internal_transfer(from_acc, to_acc, amt)
    
    bot.reply_to(
        message,
        f"🔄 *Internal Transfer Executed!*\n"
        f"• *Transferred:* `{format_rupiah(amt)}` from `{from_acc.upper()}` ➔ `{to_acc.upper()}`\n\n"
        f"🏦 *Updated Balances:*\n"
        f"• `{from_acc.upper()}`: `{format_rupiah(new_from)}`\n"
        f"• `{to_acc.upper()}`: `{format_rupiah(new_to)}`\n\n"
        f"✨ *0 expense recorded* — your net savings calculation stays 100% accurate!",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["saldo", "cashflow"])
def handle_saldo(message):
    if not is_allowed(message):
        return
    args = message.text.split(maxsplit=2)
    if len(args) >= 3:
        acc = args[1].strip().lower()
        amt = parser.parse_amount_input(args[2])
        if amt is not None:
            db.set_balance(acc, amt)
            bot.reply_to(message, f"🏦 *Balance Updated!*\nAccount `{acc.upper()}` saldo set to `{format_rupiah(amt)}`.", parse_mode="Markdown")
            return
            
    current_cycle, _, _ = get_billing_cycle_info()
    inc_summary = db.get_income_summary(current_cycle)
    summary = db.get_total_budget_summary(current_cycle)
    balances = db.get_all_balances()
    
    total_spent = summary["total_realization"]
    income_amt = inc_summary["total_amount"]
    net_savings = income_amt - total_spent
    savings_pct = (net_savings / income_amt * 100) if income_amt > 0 else 0
    
    total_liquid = sum(b["balance"] for k, b in balances.items() if k != "permata_cc")
    
    lines = [
        f"💵 *CASH FLOW & SALDO SUMMARY ({current_cycle})*",
        f"• *Monthly Income:* `{format_rupiah(income_amt)}`",
        f"• *Total Realization (Spent):* `{format_rupiah(total_spent)}`",
        f"• *Net Monthly Savings:* `{format_rupiah(net_savings)}` ({savings_pct:.1f}% Savings Rate)\n",
        f"🏦 *LIQUID BALANCES (SALDO):*"
    ]
    
    for acc_name, b_info in balances.items():
        if acc_name == "permata_cc":
            continue
        lines.append(f"• *{acc_name.upper()}:* `{format_rupiah(b_info['balance'])}`")
        
    lines.append(f"\n💰 *Total Liquid Cash Saldo:* `{format_rupiah(total_liquid)}`")
    lines.append("\n💡 *To add income:* `/income 12m Salary` or `/income 5m Freelance`\n💡 *To update balance:* `/saldo bank_saqu 5m`")
    
    bot.reply_to(message, "\n".join(lines), parse_mode="Markdown")

@bot.message_handler(commands=["setbudget"])
def handle_set_budget(message):
    if not is_allowed(message):
        return
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        bot.reply_to(
            message,
            "⚠️ *Usage:* `/setbudget <category> <amount>`\nE.g.: `/setbudget food 300k` or `/setbudget food 3000k` or `/setbudget food 3m`\nCategories: `food`, `groceries`, `transport`, `shopping`, `entertainment`, `bills`, `investment`, `family`, `misc`",
            parse_mode="Markdown"
        )
        return
        
    category = args[1].strip().lower()
    amount_str = args[2].strip()
    parsed_amt = parser.parse_amount_input(amount_str)
    if not parsed_amt:
        bot.reply_to(message, "❌ *Please enter a valid amount (e.g. 300k, 1000k, 3m, or 3000000).*", parse_mode="Markdown")
        return
        
    amount = parsed_amt
    db.set_budget(category, amount)
    
    bot.reply_to(
        message,
        f"🎯 *Budget Target Updated!*\nMonthly target for *{category.capitalize()}* set to `{format_rupiah(amount)}`.",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=["export"])
def export_data(message):
    if not is_allowed(message):
        return
        
    try:
        import io
        
        # 1. Export CSV
        csv_data = db.export_transactions_to_csv()
        csv_file = io.BytesIO(csv_data)
        csv_file.name = f"expenses_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        bot.send_document(
            message.chat.id, 
            csv_file, 
            caption="📊 *CSV Transaction Export*\nHere is a list of all your recorded transactions."
        )
        
        # 2. Export Database File
        if os.path.exists(db.DB_PATH):
            with open(db.DB_PATH, "rb") as db_file:
                bot.send_document(
                    message.chat.id, 
                    db_file, 
                    caption="💾 *SQLite DB Backup*\nSave this file to restore your database later."
                )
    except Exception as e:
        logger.exception("Export failed: %s", e)
@bot.message_handler(commands=["clear"])
def handle_clear(message):
    if not is_allowed(message):
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(
            message,
            "⚠️ *Please specify account to clear.*\nUsage:\n`/clear line_bank` (clears ALL cycles)\n`/clear line_bank 2026-06` (clears specific cycle)",
            parse_mode="Markdown"
        )
        return
    acc_to_clear = args[1].strip().lower()
    
    cycle_to_clear = None
    if len(args) >= 3 and args[2].lower() != "all":
        cycle_to_clear = args[2].strip()
        
    count = db.delete_transactions_by_account(acc_to_clear, cycle_to_clear)
    
    cycle_msg = f"in cycle `{cycle_to_clear}`" if cycle_to_clear else "across *ALL billing cycles*"
    bot.reply_to(
        message,
        f"🗑️ *Account Cleared!*\nDeleted `{count}` transactions for account `{acc_to_clear.upper()}` {cycle_msg}.",
        parse_mode="Markdown"
    )

@bot.message_handler(content_types=["document"])
def handle_document(message):
    if not is_allowed(message):
        return
        
    document = message.document
    if not document.file_name.lower().endswith(".pdf"):
        bot.reply_to(message, "❌ *Only PDF bank statements are supported.*", parse_mode="Markdown")
        return
        
    status_msg = bot.reply_to(message, "⏳ *Downloading and parsing bank statement PDF...*", parse_mode="Markdown")
    
    try:
        # Download PDF file
        file_info = bot.get_file(document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Get PDF Password from environment if available
        pdf_password = os.getenv("PDF_PASSWORD", None)
        
        # Parse transactions from PDF
        import pdf_parser
        parsed_txs, account_name = pdf_parser.extract_pdf_transactions(downloaded_file, pdf_password, document.file_name)
        
        if not parsed_txs:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=status_msg.message_id,
                text=f"⚠️ *No retail transactions found in the PDF.*\nDetected Bank: `{account_name}`.\nVerify that the statement matches supported formats.",
                parse_mode="Markdown"
            )
            return
            
        inserted_count = 0
        duplicate_count = 0
        
        for tx in parsed_txs:
            tx_date_obj = datetime.strptime(tx["date"], "%Y-%m-%d")
            cycle_label, _, _ = get_billing_cycle_info(tx_date_obj)
            
            # Check for duplicates (e.g. from previously forwarded SMS)
            if db.check_duplicate(tx["merchant"], tx["amount"], tx["date"]):
                duplicate_count += 1
                continue
                
            category = parser.categorize_merchant(tx["merchant"], account=account_name)
            if account_name != "permata_cc":
                category = "Non-CC"
            expense_category = parser.categorize_expense(tx["merchant"])
            # Format timestamp as YYYY-MM-DD 00:00:00 for e-statement transactions
            timestamp = f"{tx['date']} 00:00:00"
            
            # Save to SQLite database with the detected bank account and detailed category!
            db.add_transaction(tx["merchant"], tx["amount"], category, cycle_label, timestamp=timestamp, account=account_name, expense_category=expense_category)
            inserted_count += 1
            
        # Get stats for the current billing cycle to display in summary
        current_cycle, start_date, end_date = get_billing_cycle_info()
        stats = db.get_stats(current_cycle)
        report = generate_report(stats, current_cycle, start_date, end_date)
        
        summary = (
            f"📄 *E-Statement Imported Successfully!*\n"
            f"• *Detected Bank:* `{account_name.upper()}`\n"
            f"• *Parsed Transactions:* `{len(parsed_txs)}`\n"
            f"• *New Transactions Added:* `{inserted_count}`\n"
            f"• *Duplicates Skipped:* `{duplicate_count}`\n\n"
            f"{report}"
        )
        
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            text=summary,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.exception("E-statement import failed: %s", e)
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            text=f"❌ *Failed to import E-statement:*\n`{e}`",
            parse_mode="Markdown"
        )

@bot.message_handler(content_types=["text"], func=lambda m: True)
def process_message(message):
    if not is_allowed(message):
        return
        
    text = message.text
    amount, merchant = parser.parse_transaction(text)
    
    if amount is None or merchant is None:
        err_msg = (
            "⚠️ *Parsing failed!*\n"
            "I couldn't identify the amount or merchant in the message.\n\n"
            "Please make sure it contains a valid currency pattern (e.g. `Rp 150.000` or `IDR 50.000`) "
            "and a merchant name preceded by `di`, `at`, `merchant`, or `ke`."
        )
        bot.reply_to(message, err_msg, parse_mode="Markdown")
        return
        
    account = parser.detect_account(text) # Auto-detect account (BCA, Saqu, Line Bank, or default to Permata CC)
    category = parser.categorize_merchant(merchant, account=account)
    if account != "permata_cc":
        category = "Non-CC"
    expense_category = parser.categorize_expense(merchant, text)
    cycle_label, start_date, end_date = get_billing_cycle_info()
    
    # Save to SQLite database and capture ID
    tx_id = db.add_transaction(merchant, amount, category, cycle_label, account=account, expense_category=expense_category)
    
    # Get updated stats
    stats = db.get_stats(cycle_label)
    report = generate_report(stats, cycle_label, start_date, end_date)
    
    cc_cat_line = ""
    if account == "permata_cc":
        label = "Non-CC" if category == "Non-CC" else category.capitalize()
        cc_cat_line = f"• *CC Cashback:* `{label}`\n"
        
    success_msg = (
        f"✅ *Logged successfully (ID: #{tx_id})!*\n"
        f"• *Merchant:* `{merchant}`\n"
        f"• *Amount:* `{format_rupiah(amount)}`\n"
        f"{cc_cat_line}"
        f"• *Budget Category:* `{expense_category.capitalize()}`\n"
        f"• *Account:* `{account}`\n\n"
        f"{report}"
    )
    bot.reply_to(message, success_msg, parse_mode="Markdown")

def run_bot():
    logger.info("Starting Telegram polling")
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=20)
        except Exception as exc:
            logger.exception("Polling crashed: %s", exc)
            import time
            time.sleep(5)

if __name__ == "__main__":
    run_bot()
