import os
import logging
import pandas as pd
from extract.extractor import clean_and_extract
from services.db_service import insert_bank_transfer, run_matching_logic
from services.processor import process_single_transfer
from configs.configs import BANK_STATEMENT_PATH, SCREENSHOTS_DIR

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_bank_statement(file_path):
    print(f"Processing Bank Statement: {file_path}")
    
    # DETECT FILE TYPE
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)
    
    # Apply extraction logic
    extracted_columns = df.apply(clean_and_extract, axis=1)
    df_final = pd.concat([df[['Date', 'Credit']], extracted_columns], axis=1)
    
    # Filter for valid IPN transfers
    df_final = df_final.dropna(subset=['Ref_ID'])

    count = 0
    for index, row in df_final.iterrows():
        # Ensure bank date is also formatted correctly for MySQL
        try:
            dt = pd.to_datetime(row['Date'], dayfirst=True)
            row['Date'] = dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass # Keep original if parse fails

        insert_bank_transfer(row)
        count += 1
    
    print(f"Successfully inserted {count} bank records.")

def main():
    # 1. Process Bank Statement
    if os.path.exists(BANK_STATEMENT_PATH):
        process_bank_statement(BANK_STATEMENT_PATH)
    else:
        logger.warning(f"Bank statement not found at {BANK_STATEMENT_PATH}")

    # 2. Process Screenshots (Batch Mode)
    print(f"Scanning folder: {SCREENSHOTS_DIR}")
    if os.path.exists(SCREENSHOTS_DIR):
        files = [f for f in os.listdir(SCREENSHOTS_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

        for filename in files:
            file_path = os.path.join(SCREENSHOTS_DIR, filename)
            
            print(f"--- Processing {filename} ---")
            
            # We reuse the EXACT same function the API uses!
            # We don't pass user_id or phone because we don't know them in batch mode.
            result = process_single_transfer(file_path)
            
            if result['status'] == 'skipped':
                print(f"Skipping {filename} (Already processed in Database)")
            elif result['status'] == 'error' or result['status'] == 'failed':
                print(f"Failed {filename}: {result.get('message', 'Unknown Error')}")
            else:
                print(f"Success: Inserted {filename}")

    # 3. Run Matching Logic
    print("--- Running Matching Logic ---")
    run_matching_logic()
    print("Reconciliation complete.")

if __name__ == "__main__":
    main()