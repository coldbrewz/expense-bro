import re

def parse_amount_input(text):
    """
    Parses any input string containing amounts or shorthand 'k'/'m' (e.g. '300k' -> 300000, '1000k' -> 1000000, '2.5m' -> 2500000).
    Returns integer amount or None.
    """
    if not text:
        return None
    text_clean = str(text).strip()
    
    # 1. Handle million 'm' / 'M' shorthand (e.g. "3m" -> 3000000, "2.5m" -> 2500000)
    m_match = re.search(r'(\d+(?:\.\d+)?)\s*m\b', text_clean, flags=re.IGNORECASE)
    if m_match:
        return int(float(m_match.group(1)) * 1000000)
        
    # 2. Handle thousand 'k' / 'K' shorthand (e.g. "300k" -> 300000, "1000k" -> 1000000, "2.5k" -> 2500)
    k_match = re.search(r'(\d+(?:\.\d+)?)\s*k\b', text_clean, flags=re.IGNORECASE)
    if k_match:
        return int(float(k_match.group(1)) * 1000)
        
    # 3. Fallback to standard integer / currency parsing
    digits = re.sub(r'\D', '', text_clean)
    if digits:
        return int(digits)
    return None

def parse_transaction(text):
    """
    Parses transaction amount and merchant name from raw SMS or shorthand text (e.g. 'gofood 45k').
    Returns (amount, merchant) where amount is an int (or None) and merchant is a string (or None).
    """
    # 0. Convert shorthand 'm' and 'k' into full numbers
    text_norm = re.sub(r'(\d+(?:\.\d+)?)\s*m\b', lambda m: str(int(float(m.group(1)) * 1000000)), text, flags=re.IGNORECASE)
    text_norm = re.sub(r'(\d+(?:\.\d+)?)\s*k\b', lambda m: str(int(float(m.group(1)) * 1000)), text_norm, flags=re.IGNORECASE)
    
    amount = None
    
    # 1. Find amount
    amt_match = re.search(r'(?i)(?:Rp\.?|IDR\.?)\s*([\d.,]+)', text_norm)
    if amt_match:
        amt_str = amt_match.group(1)
        if re.search(r'[.,]00$', amt_str):
            amt_str = amt_str[:-3]
        digits = re.sub(r'\D', '', amt_str)
        if digits:
            amount = int(digits)
    else:
        # Fallback: look for general thousands-separated numbers or plain 4-9 digit numbers
        matches = re.findall(r'\b\d{1,3}(?:[.,]\d{3})+\b|\b\d{4,9}\b', text_norm)
        if matches:
            amt_str = matches[0]
            digits = re.sub(r'\D', '', amt_str)
            if digits:
                amount = int(digits)

    # 2. Find merchant name
    merchant = None
    
    merchant_match = re.search(r'(?i)\b(?:di|at|merchant|ke|store)(?:\s+(?:di|at|merchant|ke|store))*\s+([a-z0-9\s\-&\'’]+)', text_norm)
    if merchant_match:
        raw_merchant = merchant_match.group(1).strip()
        stop_words = r'\b(pada|tanggal|pd|pukul|sukses|berhasil|dengan|kartu|via|menggunakan|no|ref|id|dr|dtg|date|time|card|ending)\b'
        parts = re.split(stop_words, raw_merchant, flags=re.IGNORECASE)
        merchant = parts[0].strip()
        merchant = re.sub(r'[\s.,\-#]+$', '', merchant)
        merchant = re.sub(r'^[\s.,\-#]+', '', merchant)
        
    if not merchant or len(merchant) < 2:
        merchant = extract_merchant_fallback(text_norm)

    # 3. Shorthand Fallback (e.g. "gofood 45000" or "45000 gofood")
    if not merchant and amount:
        rem = re.sub(r'\b' + str(amount) + r'\b', '', text_norm, flags=re.IGNORECASE)
        rem = re.sub(r'\b(rp|idr)\b', '', rem, flags=re.IGNORECASE)
        rem = re.sub(r'[^\w\s]', '', rem).strip()
        if rem and len(rem) >= 2:
            merchant = rem.title()
            
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

def categorize_merchant(merchant, account="permata_cc"):
    """
    Categorizes the merchant for Permata CC as ONLINE or OFFLINE.
    For non-CC accounts (bank_saqu, bca, line_bank, general), returns 'Non-CC'.
    """
    if account != "permata_cc":
        return "Non-CC"
        
    if not merchant:
        return "OFFLINE"
        
    merchant_lower = merchant.lower()
    
    # Comprehensive ONLINE merchants pattern
    online_pattern = r'(tokopedia|shopee|gojek|gopay|grab|traveloka|midtrans|xendit|dana|ovo|linkaja|blibli|lazada|bukalapak|tikettokopedia|tiket\.com|netflix|spotify|google|apple|youtube|steam|playstation|disney|aws|cloud|agoda|airbnb|booking|finnet|telkomsel|halodoc|kereta api|kai)'
    
    if re.search(online_pattern, merchant_lower):
        return "ONLINE"
    else:
        # Permata CC transactions are strictly ONLINE or OFFLINE retail spends
        return "OFFLINE"

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
        'food': r'(starbucks|mcdonalds|kfc|coffee|resto|bakery|food|burger|pizza|dunkin|jco|sushi|kopi|warung|kuliner|bakso|mie|kantin|fuego|roasthouse|tarobun|ngopi|rmu)',
        'groceries': r'(alfamart|indomaret|superindo|transmart|hypermart|lotte|mart|minimarket|market|sayur|toko kelontong|midi|alfamidi)',
        'transport': r'(gojek|grab|go-car|go-ride|taxi|bluebird|kereta|kai|flight|tiket|traveloka|mrt|lrt|bensin|pertamina|shell|toll|parkir|spbu|bp ahmad|bp\s+)',
        'entertainment': r'(netflix|spotify|cgv|xxi|cinema|bioskop|disney|youtube|game|steam|playstation|ticket|karaoke|studio karaoke)',
        'shopping': r'(tokopedia|shopee|lazada|blibli|bukalapak|uniqlo|zara|h&m|mall|decathlon|ikea|ace hardware|clothing|fashion|baju)',
        'bills': r'(midtrans|xendit|pln|pdam|telkom|indihome|wifi|listrik|pulsa|bpjs|pajak|asuransi|billing|subscription|tagihan|finnet|telkomsel|halodoc)',
        'investment': r'(ajaib|bibit|bareksa|pluang|crypto|binance|stockbit|saham|reksadana|emas|gold|investasi)'
    }
    
    for category, pattern in rules.items():
        if re.search(pattern, merchant_lower) or (text_lower and re.search(pattern, text_lower)):
            return category
            
    # Check for transfer to mother / family
    if any(keyword in merchant_lower for keyword in ['ibu', 'mama', 'mom', 'bunda', 'family', 'keluarga']):
        return 'family'
        
    return "misc"


