import re
from datetime import datetime
from pypdf import PdfReader

def extract_pdf_transactions(file_bytes, password=None, filename=""):
    """
    Decrypts (if necessary) and extracts transaction text lines from a bank statement PDF.
    Returns (parsed_transactions, account_name).
    """
    import io
    pdf_file = io.BytesIO(file_bytes)
    reader = PdfReader(pdf_file)
    
    if reader.is_encrypted:
        import os
        passwords_to_try = []
        
        # Check explicit bank-specific password environment variables
        env_vars = [
            "PDF_PASSWORD_PERMATA_CC",
            "PDF_PASSWORD_BANK_SAQU",
            "PDF_PASSWORD_BCA",
            "PDF_PASSWORD_LINE_BANK",
            "PDF_PASSWORD"
        ]
        
        if password:
            for p in str(password).split(","):
                p_clean = p.strip()
                if p_clean and p_clean not in passwords_to_try:
                    passwords_to_try.append(p_clean)
                    
        for ev in env_vars:
            val = os.getenv(ev, "")
            if val:
                for p in val.split(","):
                    p_clean = p.strip()
                    if p_clean and p_clean not in passwords_to_try:
                        passwords_to_try.append(p_clean)
                        
        # Fallback birthdate variations
        for var in ["30102002", "301002", "30Oct20022233", "021030", "20021030", "165410"]:
            if var not in passwords_to_try:
                passwords_to_try.append(var)
                
        decrypted = False
        for pwd in passwords_to_try:
            try:
                res = reader.decrypt(pwd)
                if res != 0 or not reader.is_encrypted:
                    decrypted = True
                    break
            except Exception:
                pass
        if not decrypted:
            raise ValueError("Failed to decrypt PDF. Please check your bank PDF passwords in .env.")
            
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
        
    account_name = detect_bank_from_text(text, filename)
    
    # Extract statement year from text
    now_year = datetime.now().year
    statement_year = now_year
    cetak_match = re.search(r'(?:Tanggal\s+Cetak|Periode\s+Laporan|Statement\s+Period|PERIODE\s*:?).*?(\d{2,4})', text, re.IGNORECASE)
    if cetak_match:
        y_str = cetak_match.group(1)
        y_val = int(y_str)
        if y_val < 100:
            y_val += 2000
        if 2020 <= y_val <= 2035:
            statement_year = y_val

    if account_name == "bca":
        parsed_txs = parse_bca_statement(text, statement_year)
    elif account_name == "line_bank":
        parsed_txs = parse_linebank_statement(text, statement_year)
    elif account_name == "bank_saqu":
        parsed_txs = parse_saqu_statement(text, statement_year)
    elif account_name == "permata_savings":
        if "rekening koran" in text.lower() or "permatapayroll" in text.lower():
            parsed_txs = parse_permata_noncc_statement(text, statement_year)
        else:
            parsed_txs = parse_statement_text(text)
    else:
        parsed_txs = parse_statement_text(text)
        
    return parsed_txs, account_name

def detect_bank_from_text(text, filename=""):
    """
    Scans top header text of page 1 and filename to determine bank account.
    Prevents cross-bank transfer descriptions in body lines from misdetecting bank.
    """
    header_text = text[:800].lower()
    filename_lower = filename.lower()
    
    # 1. Line Bank / KEB Hana Bank
    if "line" in filename_lower or "line bank" in header_text or "linebank" in header_text or "hana bank" in header_text or "saving deposits-digital" in header_text:
        return "line_bank"
        
    # 2. Bank Saqu
    if "saqu" in filename_lower or "bank saqu" in header_text or "pt bank saqu indonesia" in header_text or "saku gajian" in header_text:
        return "bank_saqu"
        
    # 3. BCA
    if "bca" in filename_lower or "bca" in header_text or "tahapan xpresi" in header_text or "central asia" in header_text:
        return "bca"
        
    # 4. Permata Bank
    if "permata" in filename_lower or "permata" in header_text:
        if any(kw in header_text for kw in ["rekening koran", "permatapayroll", "tabungan", "account statement"]):
            if "credit card" in header_text or "rekening tagihan" in header_text or "shopping card" in header_text:
                return "permata_cc"
            return "permata_savings" # Permata Savings / Non-CC
        elif any(kw in header_text for kw in ["credit card", "rekening tagihan", "nomor kartu", "shopping card"]):
            return "permata_cc"
        else:
            return "permata_cc"
            
    return "permata_savings"

def parse_spaylater_ocr(text):
    """
    Parses Tesseract OCR text specifically looking for the SPayLater pattern:
    Offline Payment - BUCK UP BURGER-HO
    20 Jun 2026
    + Rp65.000 >
    """
    transactions = []
    lines = text.split("\n")
    cleaned_lines = [l.strip() for l in lines if l.strip()]
    
    months_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mei': 5, 'may': 5, 'jun': 6, 'june': 6,
        'jul': 7, 'july': 7, 'agu': 8, 'aug': 8, 'sep': 9, 'okt': 10, 'oct': 10, 'nov': 11, 'des': 12, 'dec': 12
    }
    
    for i, line in enumerate(cleaned_lines):
        # Anchor on the amount line e.g., "+ Rp65.000 >", "Rp65.000", or "* Rp 65.000"
        amt_match = re.search(r'(?:\+|-|\*)?\s*Rp\.?\s*([\d\.,]+)', line, re.IGNORECASE)
        if amt_match:
            amount_str = amt_match.group(1)
            digits = re.sub(r'\D', '', amount_str)
            if not digits:
                continue
            amount = int(digits)
            if amount == 0:
                continue
            
            tx_date = None
            merchant = "SPayLater Transaction"
            
            # Check if date is on the SAME line
            date_match = re.search(r'(\d{1,2})\s*([A-Za-z]{3,})(?:\s+(\d{4}))?', line)
            if date_match:
                d_str, m_str, y_str = date_match.groups()
                m_num = months_map.get(m_str.lower()[:3], 6)
                y_num = int(y_str) if y_str else 2026
                tx_date = f"{y_num}-{m_num:02d}-{int(d_str):02d}"
                
                merch_part = line[:date_match.start()].strip()
                merch_part = re.sub(r'(?i)^Offline Payment - ', '', merch_part)
                if merch_part:
                    merchant = merch_part
            else:
                # Look up to 3 lines backward for a Date
                for j in range(1, 4):
                    if i - j < 0:
                        break
                    prev_line = cleaned_lines[i-j]
                    
                    date_match = re.search(r'(\d{1,2})\s*([A-Za-z]{3,})(?:\s+(\d{4}))?', prev_line)
                    if date_match:
                        d_str, m_str, y_str = date_match.groups()
                        m_num = months_map.get(m_str.lower()[:3], 6)
                        y_num = int(y_str) if y_str else 2026
                        tx_date = f"{y_num}-{m_num:02d}-{int(d_str):02d}"
                        
                        # The line before the date is the merchant
                        if i - j - 1 >= 0:
                            merch_line = cleaned_lines[i-j-1]
                            merch_line = re.sub(r'(?i)^Offline Payment - ', '', merch_line)
                            merch_line = re.sub(r'\[\d+/\d+\]$', '', merch_line).strip()
                            if merch_line and not re.search(r'\+\s*Rp', merch_line):
                                merchant = merch_line
                        break
                        
            if not tx_date:
                tx_date = "2026-06-01"
                
            transactions.append({
                "date": tx_date,
                "merchant": merchant,
                "amount": amount
            })
            
    return transactions

def parse_linebank_statement(text, statement_year=2026):
    """
    Dedicated multi-line block parser for Line Bank / Hana Bank e-statements.
    """
    transactions = []
    lines = text.split("\n")
    
    months_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mei': 5, 'may': 5, 'jun': 6, 'june': 6,
        'jul': 7, 'july': 7, 'agu': 8, 'aug': 8, 'sep': 9, 'okt': 10, 'oct': 10, 'nov': 11, 'des': 12, 'dec': 12
    }
    
    date_start_regex = re.compile(r'^\s*(\d{1,2})[-/]([a-zA-Z]+|\d{1,2})[-/](\d{4})', re.IGNORECASE)
    amount_row_regex = re.compile(r'([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s*$', re.IGNORECASE)

    blocks = []
    current_block = []
    
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
            
        if date_start_regex.match(line_clean):
            if current_block:
                blocks.append(" ".join(current_block))
                current_block = []
        current_block.append(line_clean)
        
    if current_block:
        blocks.append(" ".join(current_block))
        
    for block in blocks:
        match = date_start_regex.match(block)
        if not match:
            continue
            
        d_str, month_str, y_str = match.group(1), match.group(2), match.group(3)
        if month_str.isdigit():
            m_num = int(month_str)
        else:
            m_num = months_map.get(month_str.lower(), 0)
            
        day_num, y_num = int(d_str), int(y_str)
        if not (1 <= day_num <= 31 and 1 <= m_num <= 12):
            continue
            
        amt_match = amount_row_regex.search(block)
        if not amt_match:
            continue
            
        debit_raw = amt_match.group(2)
        credit_raw = amt_match.group(3)
        
        c_no_cents = re.sub(r'\.\d{1,2}$', '', credit_raw.strip())
        c_digits = re.sub(r'\D', '', c_no_cents)
        c_val = int(c_digits) if c_digits else 0
        if c_val > 0:
            continue # Ignore incoming transfer credit
            
        d_no_cents = re.sub(r'\.\d{1,2}$', '', debit_raw.strip())
        d_digits = re.sub(r'\D', '', d_no_cents)
        if not d_digits:
            continue
            
        amount = int(d_digits)
        if amount == 0:
            continue
            
        rest = block[match.end():amt_match.start()].strip()
        clean_merchant = re.sub(r'\b\d{2}:\d{2}:\d{2}\b', '', rest)
        clean_merchant = re.sub(r'\s+', ' ', clean_merchant).strip()
        
        if not clean_merchant or len(clean_merchant) < 2:
            clean_merchant = "Line Bank Debit Transaction"
            
        tx_date = f"{y_num}-{m_num:02d}-{day_num:02d}"
        transactions.append({
            "date": tx_date,
            "merchant": clean_merchant,
            "amount": amount
        })
        
    return transactions

def parse_saqu_statement(text, statement_year=2026):
    """
    Dedicated parser for Bank Saqu e-statements.
    """
    transactions = []
    lines = text.split("\n")
    
    months_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mei': 5, 'may': 5, 'jun': 6, 'juni': 6,
        'jul': 7, 'juli': 7, 'agu': 8, 'aug': 8, 'sep': 9, 'okt': 10, 'oct': 10, 'nov': 11, 'des': 12, 'dec': 12
    }
    
    saqu_regex = re.compile(
        r'^\s*(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})\s+(.*?)\s+([-+])?Rp\s*([\d\.,]+)\s*$',
        re.IGNORECASE
    )

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
            
        match = saqu_regex.match(line_clean)
        if not match:
            continue
            
        d_str, month_str, y_str = match.group(1), match.group(2), match.group(3)
        merchant_part = match.group(4).strip()
        sign = match.group(5) or ""
        amount_raw = match.group(6)
        
        m_num = months_map.get(month_str.lower(), 0)
        day_num, y_num = int(d_str), int(y_str)
        
        if 1 <= day_num <= 31 and 1 <= m_num <= 12:
            merchant_upper = merchant_part.upper()
            if sign == '+' or 'DANA MASUK' in merchant_upper or 'BUNGA' in merchant_upper or 'DANA AWAL' in merchant_upper or 'DANA AKHIR' in merchant_upper:
                continue
                
            clean_amt_str = amount_raw
            if re.search(r'[\.,]00$', clean_amt_str):
                clean_amt_str = clean_amt_str[:-3]
            digits = re.sub(r'\D', '', clean_amt_str)
            
            if digits:
                amount = int(digits)
                if amount > 0 and len(merchant_part) >= 2:
                    transactions.append({
                        "date": f"{y_num}-{m_num:02d}-{day_num:02d}",
                        "merchant": merchant_part,
                        "amount": amount
                    })
                    
    return transactions

def parse_bca_statement(text, statement_year=2026):
    transactions = []
    lines = text.split("\n")
    
    row_start_regex = re.compile(r'^\s*(\d{2})/(\d{2})\s+(.*)', re.IGNORECASE)
    amount_db_regex = re.compile(r'([\d\.,]{3,15})\s+DB\b', re.IGNORECASE)

    raw_blocks = []
    current_block = []
    
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        if row_start_regex.match(line_str):
            if current_block:
                raw_blocks.append(" ".join(current_block))
                current_block = []
        current_block.append(line_str)
        
    if current_block:
        raw_blocks.append(" ".join(current_block))
        
    for block in raw_blocks:
        match = row_start_regex.match(block)
        if not match:
            continue
            
        d_str, m_str, rest = match.group(1), match.group(2), match.group(3)
        day_num, m_num = int(d_str), int(m_str)
        
        if not (1 <= day_num <= 31 and 1 <= m_num <= 12):
            continue
            
        # Ignore credit lines (TRSF E-BANKING CR, SETORAN VIA CDM, or blocks without DB)
        if ' CR ' in f" {block} " or 'SETORAN' in block.upper() or 'SALDO AWAL' in block.upper():
            continue
            
        amt_match = amount_db_regex.search(block)
        if not amt_match:
            continue
            
        amount_raw = amt_match.group(1)
        clean_amt_str = amount_raw
        if re.search(r'[\.,]00$', clean_amt_str):
            clean_amt_str = clean_amt_str[:-3]
            
        digits = re.sub(r'\D', '', clean_amt_str)
        if not digits:
            continue
            
        amount = int(digits)
        if amount == 0:
            continue
            
        merchant_text = rest
        
        # Clean common BCA prefixes
        merchant_text = re.sub(r'(?i)^TRSF\s+E-BANKING\s+DB\s+\S+\s*', '', merchant_text)
        merchant_text = re.sub(r'(?i)^TRANSAKSI\s+DEBIT\s+(?:TGL:\s*\d{2}/\d{2}\s*)?(?:QRC\d+\s*)?(?:\d+\.00)?', '', merchant_text)
        merchant_text = re.sub(r'(?i)^FLAZZ\s+BCA\s+TOPUP\s*', 'FLAZZ BCA TOPUP ', merchant_text)
        merchant_text = re.sub(r'(?i)^BIAYA\s+ADM\s*\d*\s*', 'BIAYA ADM ', merchant_text)
        
        # Clean merchant suffixes
        merchant_text = re.sub(r'[\d\.,]+\s+DB.*$', '', merchant_text, flags=re.IGNORECASE)
        merchant_text = re.sub(r'[\d\.,]+\s*$', '', merchant_text)
        merchant_text = re.sub(r'\s+', ' ', merchant_text).strip()
        
        if 'BIAYA ADM' in merchant_text.upper():
            continue
            
        if not merchant_text or len(merchant_text) < 2:
            merchant_text = "BCA Debit Transaction"
            
        tx_date = f"{statement_year}-{m_num:02d}-{day_num:02d}"
        transactions.append({
            "date": tx_date,
            "merchant": merchant_text,
            "amount": amount
        })
        
    return transactions

def parse_permata_noncc_statement(text, statement_year=2026):
    """
    Dedicated multi-line block parser for Permata Savings / Rekening Koran statements.
    """
    transactions = []
    lines = text.split("\n")
    
    date_start_regex = re.compile(r'^\s*(\d{2})/(\d{2})\s+(\d{2})/(\d{2})\s+(.*)', re.IGNORECASE)
    amount_regex = re.compile(r'([\d\.,]{3,15})\s+([\d\.,]{3,15})\s*$', re.IGNORECASE)

    blocks = []
    current_block = []
    
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
            
        if date_start_regex.match(line_clean):
            if current_block:
                blocks.append(" ".join(current_block))
                current_block = []
        current_block.append(line_clean)
        
    if current_block:
        blocks.append(" ".join(current_block))
        
    for block in blocks:
        match = date_start_regex.match(block)
        if not match:
            continue
            
        d_str, m_str = match.group(1), match.group(2)
        rest = match.group(5)
        
        day_num, m_num = int(d_str), int(m_str)
        if not (1 <= day_num <= 31 and 1 <= m_num <= 12):
            continue
            
        amt_match = amount_regex.search(block)
        if not amt_match:
            continue
            
        debit_raw = amt_match.group(1)
        
        merchant_upper = block.upper()
        if any(kw in merchant_upper for kw in ['TRF INCOMING', 'INCOMING', 'PENDAPATAN BUNGA', 'BUNGA', 'SALDO AWAL']):
            continue
            
        d_no_cents = re.sub(r'[\.,]\d{1,2}$', '', debit_raw.strip())
        digits = re.sub(r'\D', '', d_no_cents)
        if not digits:
            continue
            
        amount = int(digits)
        if amount == 0:
            continue
            
        merchant_text = rest[:amt_match.start()].strip()
        merchant_text = re.sub(r'\b\d{2}:\d{2}:\d{2}\b', '', merchant_text)
        merchant_text = re.sub(r'\b\d{10,20}\b', '', merchant_text)
        merchant_text = re.sub(r'\s+', ' ', merchant_text).strip()
        
        if not merchant_text or len(merchant_text) < 2:
            merchant_text = "Permata Transaction"
            
        tx_date = f"{statement_year}-{m_num:02d}-{day_num:02d}"
        transactions.append({
            "date": tx_date,
            "merchant": merchant_text,
            "amount": amount
        })
        
    return transactions

def parse_statement_text(text):
    """
    Processes raw statement text line-by-line to parse transaction rows.
    Supports Permata CC (DDMM format), Permata Savings, BCA, Bank Saqu, and Line Bank.
    """
    transactions = []
    lines = text.split("\n")
    
    now = datetime.now()
    now_year = now.year
    current_month = now.month
    
    # Try to extract statement year
    statement_year = now_year
    cetak_match = re.search(r'(?:Tanggal\s+Cetak|Periode\s+Laporan|Statement\s+Period|PERIODE\s*:?).*?(\d{2,4})', text, re.IGNORECASE)
    if cetak_match:
        y_str = cetak_match.group(1)
        y_val = int(y_str)
        if y_val < 100:
            y_val += 2000
        if 2020 <= y_val <= 2035:
            statement_year = y_val

    # Month map for name matching
    months_map = {
        'jan': 1, 'januari': 1, 'january': 1,
        'feb': 2, 'februari': 2, 'february': 2,
        'mar': 3, 'maret': 3, 'march': 3,
        'apr': 4, 'april': 4,
        'mei': 5, 'may': 5,
        'jun': 6, 'juni': 6, 'june': 6,
        'jul': 7, 'juli': 7, 'july': 7,
        'agu': 8, 'agustus': 8, 'aug': 8, 'august': 8,
        'sep': 9, 'september': 9,
        'okt': 10, 'oktober': 10, 'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'des': 12, 'desember': 12, 'dec': 12, 'december': 12
    }
    
    # 1. Bank Saqu Pattern: e.g. "18 Juni 2026 Transfer Keluar BANK BNI -Rp47.250" or "25 Juni 2026 Pembayaran QRIS -Rp5.000"
    saqu_regex = re.compile(
        r'^\s*(\d{1,2})\s+([a-zA-Z]+)\s+(\d{4})\s+(.*?)\s+([-+])?Rp\s*([\d\.,]+)\s*$',
        re.IGNORECASE
    )

    # 2. Line Bank Pattern: e.g. "1-June-2026 21:11:02 QRIS: Renville Burger 853,462.03 53,000.00 0.00 800,462.03"
    linebank_regex = re.compile(
        r'^\s*(\d{1,2})[-/]([a-zA-Z]+|\d{1,2})[-/](\d{4})\s+(?:\d{2}:\d{2}:\d{2}\s+)?(.*?)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)\s*$',
        re.IGNORECASE
    )

    # 3. Permata CC 4-digit DDMM pattern: e.g. "2506 2706 SHOPEE Jakarta IDN 41,400"
    permata_ddmm_regex = re.compile(
        r'^\s*(\d{2})(\d{2})\s+(?:(\d{2})(\d{2})\s+)?(.*?)\s+([\d\.,]{3,15})\s*(CR|-|DB)?\s*$',
        re.IGNORECASE
    )

    # 4. Standard flexible date regex: DD/MM, DD/MM/YY, DD-MM-YY, DD.MM, DD MMM
    date_regex = re.compile(
        r'\b(\d{1,2})[/\.\-]([0-9]{1,2}|[a-zA-Z]{3,9})(?:[/\.\-]([0-9]{2,4}))?\b',
        re.IGNORECASE
    )
    
    amount_regex = re.compile(
        r'([\d\.,]{3,15})\s*(CR|-|DB)?\s*$',
        re.IGNORECASE
    )

    for line in lines:
        line_clean = line.strip()
        if not line_clean or len(line_clean) < 10:
            continue
            
        # A. Try Bank Saqu pattern (-Rp = Debit / Expense, +Rp = Incoming / Ignore)
        saqu_match = saqu_regex.match(line_clean)
        if saqu_match:
            d_str, month_str, y_str = saqu_match.group(1), saqu_match.group(2), saqu_match.group(3)
            merchant_part = saqu_match.group(4).strip()
            sign = saqu_match.group(5) or ""
            amount_raw = saqu_match.group(6)
            
            m_num = months_map.get(month_str.lower(), 0)
            day_num, y_num = int(d_str), int(y_str)
            
            if 1 <= day_num <= 31 and 1 <= m_num <= 12:
                # If sign is '+' or contains 'Dana Masuk' / 'Bunga', it is incoming money -> ignore
                merchant_upper = merchant_part.upper()
                if sign == '+' or 'DANA MASUK' in merchant_upper or 'BUNGA' in merchant_upper or 'DANA AWAL' in merchant_upper or 'DANA AKHIR' in merchant_upper:
                    continue
                    
                clean_amt_str = amount_raw
                if re.search(r'[\.,]00$', clean_amt_str):
                    clean_amt_str = clean_amt_str[:-3]
                digits = re.sub(r'\D', '', clean_amt_str)
                
                if digits:
                    amount = int(digits)
                    if amount > 0 and len(merchant_part) >= 2:
                        transactions.append({
                            "date": f"{y_num}-{m_num:02d}-{day_num:02d}",
                            "merchant": merchant_part,
                            "amount": amount
                        })
                        continue

        # B. Try Line Bank pattern (Debit column > 0 = Expense, Credit > 0 = Ignore)
        line_match = linebank_regex.match(line_clean)
        if line_match:
            d_str, month_str, y_str = line_match.group(1), line_match.group(2), line_match.group(3)
            merchant_part = line_match.group(4).strip()
            debit_raw = line_match.group(6)
            credit_raw = line_match.group(7)
            
            if month_str.isdigit():
                m_num = int(month_str)
            else:
                m_num = months_map.get(month_str.lower(), 0)
                
            day_num, y_num = int(d_str), int(y_str)
            if 1 <= day_num <= 31 and 1 <= m_num <= 12:
                # Clean credit digits
                c_digits = re.sub(r'\D', '', re.sub(r'[\.,]00$', '', credit_raw))
                c_val = int(c_digits) if c_digits else 0
                if c_val > 0:
                    continue # Ignore credit/incoming transfer
                    
                d_digits = re.sub(r'\D', '', re.sub(r'[\.,]00$', '', debit_raw))
                if d_digits:
                    amount = int(d_digits)
                    if amount > 0 and len(merchant_part) >= 2:
                        transactions.append({
                            "date": f"{y_num}-{m_num:02d}-{day_num:02d}",
                            "merchant": merchant_part,
                            "amount": amount
                        })
                        continue

        # C. Try Permata CC DDMM pattern
        permata_match = permata_ddmm_regex.match(line_clean)
        if permata_match:
            d_str, m_str = permata_match.group(1), permata_match.group(2)
            merchant_part = permata_match.group(5).strip()
            amount_raw = permata_match.group(6)
            suffix = (permata_match.group(7) or "").upper()
            
            day_num, m_num = int(d_str), int(m_str)
            if 1 <= day_num <= 31 and 1 <= m_num <= 12:
                y_num = statement_year
                if m_num > current_month and statement_year == now_year:
                    y_num = now_year - 1
                    
                tx_date = f"{y_num}-{m_num:02d}-{day_num:02d}"
                
                clean_amt_str = amount_raw
                if re.search(r'[\.,]00$', clean_amt_str):
                    clean_amt_str = clean_amt_str[:-3]
                digits = re.sub(r'\D', '', clean_amt_str)
                
                if digits:
                    amount = int(digits)
                    merchant_upper = merchant_part.upper()
                    
                    is_payment_or_fee = (
                        suffix in ['-', 'CR'] or 
                        'CR' in line_clean.upper() or 
                        'THANK YOU' in merchant_upper or 
                        'PEMBAYARAN' in merchant_upper or
                        'PAYMENT' in merchant_upper or
                        'TAGIHAN BULAN' in merchant_upper or
                        'BIAYA E-BILLING' in merchant_upper or
                        'BIAYA NOTIFIKASI' in merchant_upper or
                        'BIAYA ADMINISTRASI' in merchant_upper or
                        ('KREDIT' in merchant_upper and 'BUNGA' not in merchant_upper)
                    )
                    
                    if not is_payment_or_fee and amount > 0 and len(merchant_part) >= 2:
                        transactions.append({
                            "date": tx_date,
                            "merchant": merchant_part,
                            "amount": amount
                        })
                        continue

        # D. Fallback to standard date formats (BCA, Permata Savings, general DD/MM)
        date_matches = list(date_regex.finditer(line_clean))
        if not date_matches:
            continue
            
        first_date_match = date_matches[0]
        if first_date_match.start() > 20:
            continue
            
        amt_match = amount_regex.search(line_clean)
        if not amt_match:
            continue
            
        day_str = first_date_match.group(1)
        month_str = first_date_match.group(2)
        year_str = first_date_match.group(3)
        
        amount_raw = amt_match.group(1)
        suffix = (amt_match.group(2) or "").upper()
        
        if month_str.isdigit():
            m_num = int(month_str)
        else:
            m_num = months_map.get(month_str.lower(), 0)
            
        if m_num < 1 or m_num > 12:
            continue
            
        day_num = int(day_str)
        if day_num < 1 or day_num > 31:
            continue
            
        if year_str:
            y_num = int(year_str)
            if y_num < 100:
                y_num += 2000
        else:
            y_num = statement_year
            if m_num > current_month and statement_year == now_year:
                y_num = now_year - 1
                
        tx_date = f"{y_num}-{m_num:02d}-{day_num:02d}"
        
        start_pos = first_date_match.end()
        if len(date_matches) > 1 and date_matches[1].start() < (start_pos + 15):
            start_pos = date_matches[1].end()
            
        end_pos = amt_match.start()
        merchant_part = line_clean[start_pos:end_pos].strip()
        merchant_part = re.sub(r'^[/\.\-\s]+|[/\.\-\s]+$', '', merchant_part)
        
        # Check BCA / Credit transfer filters:
        # BCA incoming transfers: TRSF E-BANKING CR, SETORAN VIA CDM (no DB marker)
        merchant_upper = merchant_part.upper()
        if 'CR' in line_clean.upper() or 'INCOMING' in merchant_upper or 'SETORAN' in merchant_upper or 'PENDAPATAN BUNGA' in merchant_upper or 'SALDO AWAL' in merchant_upper:
            continue
            
        clean_amt_str = amount_raw
        if re.search(r'[\.,]00$', clean_amt_str):
            clean_amt_str = clean_amt_str[:-3]
            
        digits = re.sub(r'\D', '', clean_amt_str)
        if not digits:
            continue
        amount = int(digits)
        
        if amount == 0:
            continue
            
        is_payment_or_fee = (
            suffix in ['-', 'CR'] or 
            'THANK YOU' in merchant_upper or 
            'PEMBAYARAN' in merchant_upper or
            'PAYMENT' in merchant_upper or
            'TAGIHAN BULAN' in merchant_upper or
            'BIAYA E-BILLING' in merchant_upper or
            'BIAYA NOTIFIKASI' in merchant_upper or
            'BIAYA ADMINISTRASI' in merchant_upper or
            ('KREDIT' in merchant_upper and 'BUNGA' not in merchant_upper)
        )
        
        if is_payment_or_fee:
            continue
            
        if not merchant_part or merchant_part.isdigit() or len(merchant_part) < 2:
            continue
            
        transactions.append({
            "date": tx_date,
            "merchant": merchant_part,
            "amount": amount
        })
        
    return transactions

def parse_date_to_yyyy_mm_dd(date_str, now_year):
    """
    Parses DD/MM or DD MMM formats into a standard YYYY-MM-DD string and returns the month number.
    """
    date_str = date_str.strip()
    
    # Format: 25/06 or 25-06
    match1 = re.match(r'^(\d{2})[/\-](\d{2})$', date_str)
    if match1:
        day = int(match1.group(1))
        month = int(match1.group(2))
        return f"{now_year}-{month:02d}-{day:02d}", month
        
    # Format: 25 JUN or 25 Jun / 25-JUN
    months_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mei': 5, 'may': 5, 'jun': 6,
        'jul': 7, 'agu': 8, 'aug': 8, 'sep': 9, 'okt': 10, 'oct': 10, 'nov': 11, 'des': 12, 'dec': 12
    }
    match2 = re.match(r'^(\d{2})[\s\-]([a-z]{3})$', date_str, re.IGNORECASE)
    if match2:
        day = int(match2.group(1))
        month_name = match2.group(2).lower()
        month = months_map.get(month_name, 1)
        return f"{now_year}-{month:02d}-{day:02d}", month
        
    return None, None
