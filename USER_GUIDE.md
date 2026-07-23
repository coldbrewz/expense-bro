# 📘 Expense Bro User Guide & FAQ

Welcome to **Expense Bro**! This bot is designed to be your personal expense tracker and credit card cashback optimizer. It tracks spending across multiple bank accounts, while isolating your **Permata Credit Card** to help you hit its **5,000,000 IDR monthly retail spend gate** without any calculations mixing up.

---

## 🚀 Quick Reference Commands

| Command | Action | Example |
| :--- | :--- | :--- |
| `/stats` | View Permata CC cashback targets, a breakdown of accounts, and detailed budget categories. | `/stats` |
| `/add` | Manually log a transaction to a specific account. | `/add 50k Starbucks`<br>`/add 1.2jt "Transfer Ibu" saqu`<br>`/add 75000 Indomaret bca` |
| `/edit` | Update any specific field of a past transaction by its ID. | `/edit 45 amount 65000`<br>`/edit 14 expense_category groceries` |
| `/undo` | Wipe the last recorded transaction. | `/undo` |
| `/export` | Download your entire history in CSV format (including account and budget categories) and backup the SQLite database. | `/export` |

---

## ✏️ Editing Past Transactions

Whenever you successfully log a transaction via SMS or manual entry, the bot will reply with a confirmation containing a unique transaction ID (e.g. `Logged successfully (ID: #45)`). 
If you make a typo or the auto-categorizer makes a mistake, you can edit it at any time:

* **Format:** `/edit <id> <field> <new_value>`
* **Allowed fields:** `amount` (or `price`), `merchant` (or `store`), `expense_category` (or `budget`), `category` (cashback), `account` (or `source`).
* **Examples:**
  * `/edit 45 amount 55000` (changes the amount of transaction #45 to 55,000 IDR).
  * `/edit 45 merchant "Starbucks Tebet"` (updates the merchant name).
  * `/edit 45 expense_category food` (updates the detailed budget category).
  * `/edit 45 account bca` (moves the transaction to your BCA account).

---

## 💻 The Secure Visual Web Dashboard

While Telegram handles on-the-go queries, you can access a beautiful, interactive web interface for monthly reviews:

* **URL:** `http://<your-oracle-server-ip>:8501`
* **Features:** 
  * **CC Targets Progress:** Visual gauge and bar charts showing Permata CC online/offline spends and how close you are to the 5jt cashback gate.
  * **Wallet Breakdown:** Interactive donut charts showing how much is allocated to `Permata CC`, `BCA`, `Bank Saqu`, and `Line Bank`.
  * **Categorized Budgeting:** Horizontal bar charts showing where your money went (Food, Groceries, Shopping, etc.).
  * **Transaction Table:** Sortable list of all logged transactions.
* **🔒 Privacy Protection:** To protect your financial data from public access, set a password in your `.env` file under `DASHBOARD_PASSWORD`. Anyone visiting the dashboard URL will be prompted with a secure login page before seeing any charts.

---

## 🏦 Accounts Supported & Mapping Aliases

The bot supports tracking transactions under four major accounts. When manually logging with `/add`, you can use the **Aliases** listed below at the end of your command:

| Account | Database Name | Commands Aliases | Purpose |
| :--- | :--- | :--- | :--- |
| **Permata Credit Card** | `permata_cc` (Default) | `permata`, `cc`, `permata_cc` | Primary spending vehicle for cashback promos. |
| **Bank Saqu** | `bank_saqu` | `saqu`, `bank_saqu`, `saqu_payroll` | Payroll/salary receiver with high-yield pockets. |
| **BCA** | `bca` | `bca` | Transactional checking, ATMs, general cash transfers. |
| **Line Bank** | `line_bank` | `line`, `line_bank` | Budget-separation "mailboxes" and digital pockets. |

---

## 🏷️ Automated Budget Categories

The bot automatically categorizes your transactions into detailed spending categories using keyword matching. When you forward an SMS or upload a PDF statement, the bot parses the merchant name and automatically assigns it to one of these:

* 🍔 **Food:** Restaurants, cafes, warungs, coffee shops (e.g. *Starbucks, McDonald's, KFC, Kopi Kenangan*).
* 🛒 **Groceries:** Supermarkets and convenience stores (e.g. *Alfamart, Indomaret, Superindo, Transmart*).
* 🚗 **Transport:** Ride-hailing, travel, fuel, toll, and parking (e.g. *Gojek, Grab, Pertamina, Shell, KAI*).
* 🎬 **Entertainment:** Streaming services, gaming, and cinemas (e.g. *Netflix, Spotify, CGV, XXI, Steam*).
* 🛍️ **Shopping:** E-commerce, apparel, and department stores (e.g. *Tokopedia, Shopee, Uniqlo, Zara, IKEA*).
* 📄 **Bills:** Subscriptions, mobile credit, internet, electricity, and taxes (e.g. *PLN, Indihome, Midtrans, Xendit*).
* 📈 **Investment:** Mutual funds, stocks, and crypto (e.g. *Bibit, Ajaib, Bareksa, Pluang*).
* ❤️ **Family:** Money transfers for family support or household assistance (contains keywords like *Ibu, Mama, Mom, Keluarga*).
* 📦 **Misc:** Default category for unmapped merchants.

---

## 📝 How to Log Expenses

### 1. Auto-Logging (Forwards)
Forward any bank transaction notification or SMS. The bot extracts the amount, merchant, **auto-detects the account**, **auto-categorizes the spending type**, and saves it.
* **Example SMS:** `EDC-Pembayaran No.Kartu ... Rp. 100.000,00 di ALFAMART - Sukses`
* **Result:** Bot automatically logs `Rp 100.000` to `permata_cc` (ID #46) under cashback category `OFFLINE` and budget category `groceries`.

### 2. Manual Commands (`/add`)
Format: `/add <amount> <merchant> [category] [account]`
* If you omit the account, it defaults to your credit card, `permata_cc`.
* If you omit the category, it automatically guesses it using cashback rules.
* **Budget categorization is fully automated based on the merchant name!**

**Examples:**
* `/add 50k Starbucks` $\rightarrow$ Logs `Rp 50.000` to `permata_cc` (ID #47) under `OFFLINE` and budget `food`.
* `/add 150000 Tokopedia bca` $\rightarrow$ Logs `Rp 150.000` to `bca` (ID #48) under `ONLINE` and budget `shopping`.
* `/add 1.2jt "Transfer Ibu" saqu` $\rightarrow$ Logs `Rp 1.200.000` to `bank_saqu` (ID #49) under `UNMAPPED` and budget `family`.

### 3. Deleting Mistakes (`/undo`)
Made a mistake? Type `/undo` and the bot will delete the most recent transaction and print the updated `/stats`.

---

## 📄 Importing E-Statements

To batch-import your history, simply **drag and drop a bank statement PDF** into the Telegram chat:
1. Ensure your PDF password is set in `.env` as `PDF_PASSWORD` (e.g. your birthdate `DDMMYYYY` for Permata).
2. Send the PDF.
3. The bot reads the PDF text, **auto-detects the bank**, **auto-categorizes both the cashback type and detailed budget category** for each transaction, and logs it. Duplicates are automatically skipped.
