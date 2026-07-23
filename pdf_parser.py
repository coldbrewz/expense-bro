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
        if password:
            try:
                reader.decrypt(password)
            except Exception as e:
                raise ValueError(f"Failed to decrypt PDF. Check your PDF_PASSWORD in .env. Error: {e}")
        else:
            raise ValueError("PDF is password-protected. Please set PDF_PASSWORD in your .env file.")
            
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
        
    account_name = detect_bank_from_text(text, filename)
    parsed_txs = parse_statement_text(text)
    
    return parsed_txs, account_name

def detect_bank_from_text(text, filename=""):
    """
    Scans PDF text and filename to determine which bank account it belongs to.
    """
    text_lower = text.lower()
    filename_lower = filename.lower()
    
    # Check Bank Saqu
    if "saqu" in text_lower or "saqu" in filename_lower or "jasa jakarta" in text_lower:
        return "bank_saqu"
    # Check Line Bank
    elif "line bank" in text_lower or "line" in filename_lower or "hana bank" in text_lower:
        return "line_bank"
    # Check BCA
    elif "bca" in text_lower or "bca" in filename_lower or "central asia" in text_lower:
        return "bca"
    # Check Permata CC
    elif "permata" in text_lower or "permata" in filename_lower:
        return "permata_cc"
        
    return "general"

def parse_statement_text(text):
    """
    Processes raw statement text line-by-line to parse transaction rows.
    """
    transactions = []
    lines = text.split("\n")
    
    # Patterns to match date at the start of a transaction line:
    # 1. 25/06 or 25-06
    # 2. 25 JUN or 25 JUN 26
    # 3. 25-JUN
    date_pattern = r'^(\d{2}/\d{2}|\d{2}-\d{2}|\d{2}\s+(?:JAN|FEB|MAR|APR|MEI|MAY|JUN|JUL|AGU|AUG|SEP|OKT|OCT|NOV|DES|DEC))'
    
    # Pattern to match numbers at the end of a transaction line (e.g. 150.000,00 or 150,000 or 150.000 CR or 150.000-)
    amount_pattern = r'([\d.,]+)\s*(CR|-)?\s*$'
    
    now = datetime.now()
    now_year = now.year
    current_month = now.month
    
    for line in lines:
        line = line.strip()
        
        # Check if line starts with a transaction date
        date_match = re.search(date_pattern, line, re.IGNORECASE)
        if not date_match:
            continue
            
        # Check if line ends with an amount
        amount_match = re.search(amount_pattern, line)
        if not amount_match:
            continue
            
        date_raw = date_match.group(0)
        amount_str = amount_match.group(1)
        suffix = amount_match.group(2) # CR or -
        
        # The merchant info resides in the middle of the line
        merchant_part = line[len(date_raw):-len(amount_match.group(0))].strip()
        
        # Clean the merchant part by removing posting dates (e.g. 26/06 or 26 JUN)
        # Often, statements list transaction date followed immediately by posting date.
        merchant_part = re.sub(r'^\d{2}/\d{2}\s+|\s+\d{2}/\d{2}\b', '', merchant_part)
        merchant_part = re.sub(r'^\d{2}\s+(?:JAN|FEB|MAR|APR|MEI|MAY|JUN|JUL|AGU|AUG|SEP|OKT|OCT|NOV|DES|DEC)\s+', '', merchant_part, flags=re.IGNORECASE)
        
        # Clean amount digits
        if re.search(r'[.,]00$', amount_str):
            amount_str = amount_str[:-3]
        digits = re.sub(r'\D', '', amount_str)
        if not digits:
            continue
        amount = int(digits)
        
        # Identify credit payments / refunds / thank-you payments
        is_payment = False
        merchant_upper = merchant_part.upper()
        if (
            suffix in ['-', 'CR'] or 
            'CR' in line or 
            'THANK YOU' in merchant_upper or 
            'PEMBAYARAN' in merchant_upper or
            'PAYMENT' in merchant_upper
        ):
            is_payment = True
            
        # Filter out bank credit card fees, interest, or billing statements if needed.
        # But we mostly just want to ignore card payments (since we are tracking retail spend).
        if is_payment:
            continue
            
        # Standardize transaction date to YYYY-MM-DD
        tx_date, tx_month = parse_date_to_yyyy_mm_dd(date_raw, now_year)
        if not tx_date:
            continue
            
        # Year-crossing adjustments: if statement contains a month that is higher than current month,
        # it belongs to the previous year (e.g., statement generated in January for December transactions).
        if tx_month > current_month:
            tx_date = tx_date.replace(str(now_year), str(now_year - 1), 1)
            
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
