BANK_STATEMENT_PATH = r"C:\Users\Nader\Documents\CustomMatchingbank.xlsx"
SCREENSHOTS_DIR = r"C:\Users\Nader\Desktop\Ocr_matching"

LLM_PROMPT = """
You are an expert financial data extractor. Your task is to extract information from a bank transfer screenshot text.

EXTRACT THE FOLLOWING FIELDS:
1. Amount Transferred: The net amount sent (strictly EXCLUDE any bank/transfer fees).
2. Fee Amount: The specific cost of the transaction fee, if listed. If not listed, return "0".
3. Sender/Receiver Name: The full name identified in the transaction.
4. Email: Any email address associated with the transaction.
5. Mobile Number: Any Egyptian mobile number (usually starting with 010, 011, 012, or 015).
6. Transaction Reference: The unique ID, Ref Number, or Transaction ID.
7. Transaction Date: The date and time the transfer occurred.

OUTPUT RULES:
- Output the result strictly in valid JSON format.
- Use "null" for any field that is not found in the text.
- Do not provide any conversational filler or explanation.

The following is the text extracted via OCR:
"""