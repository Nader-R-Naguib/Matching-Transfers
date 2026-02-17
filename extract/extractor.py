import pandas as pd
import re
import json

# Regex to match Egyptian numbers with 0020 prefix
# Captures the network code (10, 11, 12, 15) and the following 8 digits.
PHONE_REGEX = r'^0020(10|11|12|15)(\d{8})$'

def clean_and_extract(row):
    """
    Parses the messy 'Description' field to extract structured data.
    """
    description = str(row['Description']) if pd.notna(row['Description']) else ""
    
    # 1. Normalize Separators
    normalized_desc = description.replace('\n', '|')
    
    # 2. Tokenize & Clean
    tokens = [t.strip() for t in normalized_desc.split('|') if t.strip()]
    
    # 3. Extraction Containers
    extracted = {
        'Ref_ID': None,
        'Phone_number': [],
        'email_or_name': [] 
    }
    
    # 4. Extract Reference ID (Position-Based)
    for i, token in enumerate(tokens):
        if "IPN Inward Transfer" in token:
            if i + 1 < len(tokens):
                candidate_id = tokens[i+1]
                # Safety check: ensure we don't grab a phone number by mistake
                if not re.match(PHONE_REGEX, candidate_id):
                    extracted['Ref_ID'] = candidate_id
            break 

    # 5. Extract Phones and Combined Name/Email
    unique_tokens = sorted(list(set(tokens)))
    
    for token in unique_tokens:
        # Skip the anchor text and the extracted ID
        if "IPN Inward Transfer" in token or token == extracted['Ref_ID']:
            continue
            
        # Check for Egyptian Phone Number
        phone_match = re.match(PHONE_REGEX, token)
        if phone_match:
            # Format: 002010... -> 010...
            formatted_number = '0' + token[4:]
            extracted['Phone_number'].append(formatted_number)
            continue
            
        # Everything else goes to email_or_name
        extracted['email_or_name'].append(token)
        
    return pd.Series(extracted)

# --- Execution ---

# # 1. Load Data
# file_path = r"C:\Users\Nader\Downloads\0001173103001_Statement.xlsx"
# df = pd.read_excel(file_path)

# # 2. Apply Extraction Logic
# extracted_columns = df.apply(clean_and_extract, axis=1)

# # 3. Merge & Filter
# # Combine original Date/Credit with extracted data
# df_final = pd.concat([df[['Date', 'Credit']], extracted_columns], axis=1)

# # FILTER 1: Keep only rows where Ref_ID was successfully found (Implies IPN Transfer)
# df_final = df_final.dropna(subset=['Ref_ID'])

# # FILTER 2: Explicitly select ordered columns (excluding Debit)
# df_final = df_final[['Date', 'Credit', 'Ref_ID', 'Phone_number', 'email_or_name']]

# # 4. Output
# json_output = df_final.to_json(orient='records', indent=4)

# print("--- DataFrame Preview ---")
# print(df_final.head())
# print("\n--- JSON Output ---")
# print(json_output)