import re

def parse_transaction(text):
    """
    Parses transaction amount and merchant name from raw SMS/notification text.
    Returns (amount, merchant) where amount is an int (or None) and merchant is a string (or None).
    """
    amount = None
    
    # 1. Find amount
    # Search for common Indonesian currency indicators (e.g. Rp 150.000,00, Rp. 100.000, IDR 50,000)
    amt_match = re.search(r'(?i)(?:Rp\.?|IDR\.?)\s*([\d.,]+)', text)
    if amt_match:
        amt_str = amt_match.group(1)
        # remove cents if they end with .00 or ,00
        if re.search(r'[.,]00$', amt_str):
            amt_str = amt_str[:-3]
        # remove all non-digits to get integer amount
        digits = re.sub(r'\D', '', amt_str)
        if digits:
            amount = int(digits)
    else:
        # Fallback: look for general thousands-separated numbers or plain 4-9 digit numbers
        # E.g. 150.000 or 1.500.000 or 50000
        matches = re.findall(r'\b\d{1,3}(?:[.,]\d{3})+\b|\b\d{4,9}\b', text)
        if matches:
            # take the first match that is likely an amount
            amt_str = matches[0]
            digits = re.sub(r'\D', '', amt_str)
            if digits:
                amount = int(digits)

    # 2. Find merchant name
    merchant = None
    
    # Search for typical location/action keywords: di, at, merchant, ke, store
    # Support consecutive prefix keywords (e.g., "di merchant", "at store")
    merchant_match = re.search(r'(?i)\b(?:di|at|merchant|ke|store)(?:\s+(?:di|at|merchant|ke|store))*\s+([a-z0-9\s\-&\'’]+)', text)
    if merchant_match:
        raw_merchant = merchant_match.group(1).strip()
        # Split and discard when we hit Indonesian/English billing SMS suffix keywords
        stop_words = r'\b(pada|tanggal|pd|pukul|sukses|berhasil|dengan|kartu|via|menggunakan|no|ref|id|dr|dtg|date|time|card|ending)\b'
        parts = re.split(stop_words, raw_merchant, flags=re.IGNORECASE)
        merchant = parts[0].strip()
        # Clean trailing and leading punctuation/spaces
        merchant = re.sub(r'[\s.,\-#]+$', '', merchant)
        merchant = re.sub(r'^[\s.,\-#]+', '', merchant)
        
    # If merchant wasn't found or is too generic, run a fallback to search for known keywords in the entire text
    if not merchant or len(merchant) < 2:
        merchant = extract_merchant_fallback(text)
        
    return amount, merchant

def extract_merchant_fallback(text):
    """
    Scans the text directly for any known merchants if standard prefix patterns fail.
    """
    text_lower = text.lower()
    known_merchants = [
        # ONLINE
        "tokopedia", "shopee", "gojek", "grab", "midtrans", "xendit", "netflix", "spotify", "google", "apple",
        # OFFLINE
        "edc", "alfamart", "indomaret", "starbucks", "superindo", "transmart", "mcdonalds", "kfc", "cgv", "xxi"
    ]
    for m in known_merchants:
        if m in text_lower:
            start_idx = text_lower.find(m)
            # return exactly the casing used in the message
            return text[start_idx:start_idx+len(m)]
    return None

def categorize_merchant(merchant):
    """
    Categorizes the merchant based on the exact specified regex sets.
    """
    if not merchant:
        return "UNMAPPED"
        
    merchant_lower = merchant.lower()
    online_pattern = r'(tokopedia|shopee|gojek|grab|midtrans|xendit|netflix|spotify|google|apple)'
    offline_pattern = r'(edc|alfamart|indomaret|starbucks|superindo|transmart|mcdonalds|kfc|cgv|xxi)'
    
    if re.search(online_pattern, merchant_lower):
        return "ONLINE"
    elif re.search(offline_pattern, merchant_lower):
        return "OFFLINE"
    else:
        return "UNMAPPED"

def detect_account(text):
    """
    Detects which bank account an incoming notification belongs to based on text keywords.
    """
    text_lower = text.lower()
    if "saqu" in text_lower:
        return "bank_saqu"
    elif "bca" in text_lower:
        return "bca"
    elif "line bank" in text_lower or "hana bank" in text_lower:
        return "line_bank"
    elif "permata" in text_lower or "cc" in text_lower or "kartu kredit" in text_lower:
        return "permata_cc"
    return "permata_cc" # Default to CC since it is the primary target

def categorize_expense(merchant, text=""):
    """
    Categorizes the transaction into detailed budget categories:
    food, groceries, transport, entertainment, shopping, bills, investment, family, misc.
    """
    if not merchant:
        return "misc"
        
    merchant_lower = merchant.lower()
    text_lower = text.lower() if text else ""
    
    # Detailed expense categories rules
    rules = {
        'food': r'(starbucks|mcdonalds|kfc|coffee|resto|bakery|food|burger|pizza|dunkin|jco|sushi|kopi|warung|kuliner|bakso|mie|kantin)',
        'groceries': r'(alfamart|indomaret|superindo|transmart|hypermart|lotte|mart|minimarket|market|sayur|toko kelontong)',
        'transport': r'(gojek|grab|go-car|go-ride|taxi|bluebird|kereta|kai|flight|tiket|traveloka|mrt|lrt|bensin|pertamina|shell|toll|parkir)',
        'entertainment': r'(netflix|spotify|cgv|xxi|cinema|bioskop|disney|youtube|game|steam|playstation|ticket)',
        'shopping': r'(tokopedia|shopee|lazada|blibli|bukalapak|uniqlo|zara|h&m|mall|decathlon|ikea|ace hardware|clothing|fashion|baju)',
        'bills': r'(midtrans|xendit|pln|pdam|telkom|indihome|wifi|listrik|pulsa|bpjs|pajak|asuransi|billing|subscription|tagihan)',
        'investment': r'(ajaib|bibit|bareksa|pluang|crypto|binance|stockbit|saham|reksadana|emas|gold|investasi)'
    }
    
    for category, pattern in rules.items():
        if re.search(pattern, merchant_lower) or (text_lower and re.search(pattern, text_lower)):
            return category
            
    # Check for transfer to mother / family
    if any(keyword in merchant_lower for keyword in ['ibu', 'mama', 'mom', 'bunda', 'family', 'keluarga']):
        return 'family'
        
    return "misc"


