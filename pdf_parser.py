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
    Supports a wide variety of Indonesian bank formats (Permata, BCA, Saqu, Line Bank).
    """
    transactions = []
    lines = text.split("\n")
    
    # Month map for name matching
    months_map = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'mei': 5, 'may': 5, 'jun': 6,
        'jul': 7, 'agu': 8, 'aug': 8, 'sep': 9, 'okt': 10, 'oct': 10, 'nov': 11, 'des': 12, 'dec': 12
    }
    
    now = datetime.now()
    now_year = now.year
    current_month = now.month

    # Flexible Regex for Dates:
    # Matches: DD/MM, DD/MM/YY, DD/MM/YYYY, DD-MM-YY, DD.MM.YYYY, DD MMM, DD-MMM-YY, DD MMM YYYY
    date_regex = re.compile(
        r'\b(\d{1,2})[/\.\-]([0-9]{1,2}|[a-zA-Z]{3})(?:[/\.\-]([0-9]{2,4}))?\b',
        re.IGNORECASE
    )
    
    # Flexible Regex for Amounts at or near the end of a line:
    # Matches: 150.000,00 | 150,000.00 | 150.000 | 150000 | 150.000,00 CR | 150.000,00-
    amount_regex = re.compile(
        r'([\d\.,]{3,15})\s*(CR|-|DB)?\s*$',
        re.IGNORECASE
    )

    for line in lines:
        line_clean = line.strip()
        if not line_clean or len(line_clean) < 10:
            continue
            
        # Find all date occurrences in the line
        date_matches = list(date_regex.finditer(line_clean))
        if not date_matches:
            continue
            
        # Take the first date match (Transaction Date)
        first_date_match = date_matches[0]
        # Ensure the date occurs near the beginning of the line (index < 20)
        if first_date_match.start() > 20:
            continue
            
        # Find amount match at end of line
        amt_match = amount_regex.search(line_clean)
        if not amt_match:
            continue
            
        date_str_raw = first_date_match.group(0)
        day_str = first_date_match.group(1)
        month_str = first_date_match.group(2)
        year_str = first_date_match.group(3)
        
        amount_raw = amt_match.group(1)
        suffix = (amt_match.group(2) or "").upper()
        
        # Parse Month
        if month_str.isdigit():
            m_num = int(month_str)
        else:
            m_num = months_map.get(month_str.lower(), 0)
            
        if m_num < 1 or m_num > 12:
            continue
            
        day_num = int(day_str)
        if day_num < 1 or day_num > 31:
            continue
            
        # Parse Year
        if year_str:
            y_num = int(year_str)
            if y_num < 100:
                y_num += 2000
        else:
            y_num = now_year
            if m_num > current_month:
                y_num = now_year - 1
                
        tx_date = f"{y_num}-{m_num:02d}-{day_num:02d}"
        
        # Extract merchant string (everything between date(s) and amount)
        start_pos = first_date_match.end()
        if len(date_matches) > 1 and date_matches[1].start() < (start_pos + 15):
            start_pos = date_matches[1].end()
            
        end_pos = amt_match.start()
        merchant_part = line_clean[start_pos:end_pos].strip()
        
        # Clean merchant string
        merchant_part = re.sub(r'^[/\.\-\s]+|[/\.\-\s]+$', '', merchant_part)
        
        # Clean amount digits
        clean_amt_str = amount_raw
        if re.search(r'[\.,]00$', clean_amt_str):
            clean_amt_str = clean_amt_str[:-3]
        
        digits = re.sub(r'\D', '', clean_amt_str)
        if not digits:
            continue
        amount = int(digits)
        
        if amount == 0:
            continue
            
        # Check if credit payment / refund / thank-you payment
        merchant_upper = merchant_part.upper()
        is_payment = False
        if (
            suffix in ['-', 'CR'] or 
            'CR' in line_clean.upper() or 
            'THANK YOU' in merchant_upper or 
            'PEMBAYARAN' in merchant_upper or
            'PAYMENT' in merchant_upper or
            ('KREDIT' in merchant_upper and 'BUNGA' not in merchant_upper)
        ):
            is_payment = True
            
        if is_payment:
            continue
            
        # If merchant name is empty or just numbers, skip
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
