import re
import pandas as pd
import pypdf
import spacy
from io import BytesIO

nlp = spacy.load("en_core_web_sm")

def extract_text_pdf(file_path):
    with open(file_path, 'rb') as f:
        reader = pypdf.PdfReader(f)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text

def parse_hdfc_statement(text):
    data = {}
    match = re.search(r'Name\s*:\s*(.+)', text)
    data['cardholder_name'] = match.group(1).strip() if match else None
    data['bank_name'] = "HDFC"
    match = re.search(r'Statement Date\s*:\s*(\d{2}/\d{2}/\d{4})', text)
    data['statement_date'] = match.group(1) if match else None

    headers_map = {
        "Payment Due Date": ["payment_due_date", "total_dues", "minimum_amount_due"],
        "Credit Limit": ["credit_limit", "available_credit", "available_cash_limit"]
    }

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    i = 0
    while i < len(lines):
        line = lines[i]
        for header, fields in headers_map.items():
            if header in line:
                value_line = re.sub(r'\s+', ' ', lines[i+1])
                numbers = re.findall(r'\d{2}/\d{2}/\d{4}|[\d,]+\.\d{2}|[\d,]+', value_line)
                for field_name, num in zip(fields, numbers):
                    if '/' in num:
                        data[field_name] = num
                    elif '.' in num:
                        data[field_name] = float(num.replace(',', ''))
                    else:
                        data[field_name] = int(num.replace(',', ''))
                i += 1
        i += 1

    pattern_txn = r'(\d{2}/\d{2}/\d{4})\s+\d{2}:\d{2}:\d{2}\s+(.+?)\s+([\d,]+\.\d{2})(Cr|Dr)?'
    transactions = []
    for m in re.finditer(pattern_txn, text):
        date, desc, amount, txn_type = m.groups()
        amount = float(amount.replace(',', ''))
        txn_type = 'credit' if txn_type == 'Cr' else 'debit'
        transactions.append({'date': date, 'description': desc.strip(), 'amount': amount, 'type': txn_type})
    data['transactions'] = transactions
    return data

def parse_chase_statement(text):
    data = {}
    match = re.search(r'\n([A-Z][A-Z ]+)\n\d{1,5} [A-Z ]+ APT \d+', text)
    data['cardholder_name'] = match.group(1).strip() if match else None
    data['bank_name'] = "Chase"

    match = re.search(r'Statement Date[: ]+(\d{2}/\d{2}/\d{2,4})', text)
    if match:
        data['statement_date'] = match.group(1)
    else:
        match = re.search(r'Opening/Closing Date (\d{2}/\d{2}/\d{2,4}) - (\d{2}/\d{2}/\d{2,4})', text)
        data['statement_date'] = match.group(2) if match else None

    match = re.search(r'Account Number:\s+XXXX XXXX XXXX (\d{4})', text)
    data['account_last4'] = match.group(1) if match else None

    match = re.search(r'Payment Due Date[: ]+(\d{2}/\d{2}/\d{2,4})', text)
    data['payment_due_date'] = match.group(1) if match else None

    match = re.search(r'New Balance[: ]+\$?([\d,]+\.\d{2})', text)
    data['new_balance'] = float(match.group(1).replace(',', '')) if match else None

    match = re.search(r'Minimum Payment Due[: ]+\$?([\d,]+\.\d{2})', text)
    data['minimum_payment_due'] = float(match.group(1).replace(',', '')) if match else None

    match = re.search(r'Credit Limit[: ]+\$?([\d,]+)\s+Available Credit[: ]+\$?([\d,]+)\s+Cash Access Line[: ]+\$?([\d,]+)', text)
    if match:
        data['credit_limit'] = int(match.group(1).replace(',', ''))
        data['available_credit'] = int(match.group(2).replace(',', ''))
        data['cash_access_line'] = int(match.group(3).replace(',', ''))

    lines = text.split("\n")
    transactions = []
    txn_pattern = r'^(\d{2}/\d{2})\s+(.+?)\s+(-?\d+\.\d{2})$'
    for line in lines:
        line = line.strip()
        m = re.match(txn_pattern, line)
        if m:
            date, desc, amount = m.groups()
            amount = float(amount)
            txn_type = 'debit' if amount < 0 else 'credit'
            transactions.append({'date': date, 'description': desc.strip(), 'amount': abs(amount), 'type': txn_type})
    data['transactions'] = transactions
    return data

def main():
    print("Credit Card Statement Parser (HDFC / Chase)")
    file_path = input("Enter path to PDF statement: ").strip()
    bank = input("Enter bank name (HDFC / Chase): ").strip().lower()

    text = extract_text_pdf(file_path)

    if bank == "hdfc":
        data = parse_hdfc_statement(text)
    elif bank == "chase":
        data = parse_chase_statement(text)
    else:
        print("Bank not supported.")
        return

    print("\nCard Info:")
    card_info = {k: v for k, v in data.items() if k != 'transactions'}
    print(pd.DataFrame([card_info]))

    if data['transactions']:
        print("\nTransactions:")
        txn_df = pd.DataFrame(data['transactions'])
        print(txn_df.head(20))

if __name__ == "__main__":
    main()
