import os
import json
import logging
import pandas as pd
from services.surya_ocr import run_surya_ocr
from services.llm_service import rephrase_output
from configs.configs import LLM_PROMPT
from extract.extractor import clean_and_extract
from services.db_service import insert_user_transfer, insert_bank_transfer, run_matching_logic, check_file_exists

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

def parse_mysql_date(date_str):
    """
    Converts diverse date strings (DD/MM/YYYY, etc.) into MySQL format YYYY-MM-DD HH:MM:SS
    """
    if not date_str or str(date_str).lower() == "null":
        return None
    try:
        # dayfirst=True handles the Egyptian format "08/09/2025" as Sept 8th, not Aug 9th
        dt = pd.to_datetime(date_str, dayfirst=True)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        logger.warning(f"Could not parse date: {date_str}")
        return None

def process_screenshot(image_path):
    filename = os.path.basename(image_path)
    
    # --- OPTIMIZATION: Check DB first! ---
    if check_file_exists(filename):
        print(f"Skipping {filename} (Already processed in Database)")
        return
    
    print(f"Processing Screenshot: {image_path}")
    
    # 1. Run Surya OCR
    ocr_data = run_surya_ocr(image_path)
    
    if not ocr_data:
        print("No text detected.")
        return

    # 2. Calculate Confidence
    confidences = [item[1] for item in ocr_data if item[1] is not None]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    
    # Extract text lines
    ocr_text_lines = [item[0] for item in ocr_data]

    # 3. Run LLM Extraction
    json_response_str = rephrase_output(LLM_PROMPT, ocr_text_lines)
    
    if json_response_str:
        try:
            data = json.loads(json_response_str)
            
            # Clean Amount
            raw_amount = str(data.get("Amount Transferred", "0"))
            clean_amount = raw_amount.replace("EGP", "").replace(",", "").strip()
            data['Amount Transferred'] = float(clean_amount) if clean_amount != "null" else 0.0
            
            # Clean Date (THE FIX)
            raw_date = data.get('Transaction Date')
            data['Transaction Date'] = parse_mysql_date(raw_date)

            # Add Metadata
            data['source_filename'] = os.path.basename(image_path)
            data['ocr_confidence'] = avg_confidence
            
            # 4. Insert into DB
            insert_user_transfer(data)
            
        except json.JSONDecodeError:
            logger.error("Failed to decode LLM JSON response.")
        except Exception as e:
            logger.error(f"Error processing extracted data: {e}")

if __name__ == "__main__":
    # 1. Ingest Bank Data
    bank_file = r"C:\Users\Nader\Documents\CustomMatchingbank.xlsx"
    if os.path.exists(bank_file):
        process_bank_statement(bank_file)
    
    # 2. Ingest ALL Screenshots
    screenshots_folder = r"C:\Users\Nader\Desktop\Ocr_matching"
    if os.path.exists(screenshots_folder):
        for filename in os.listdir(screenshots_folder):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                full_path = os.path.join(screenshots_folder, filename)
                print(f"--- Processing {filename} ---")
                process_screenshot(full_path)

    # 3. Run Matching Logic
    run_matching_logic()