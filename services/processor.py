# services/processor.py
import os
import json
import logging
from services.surya_ocr import run_surya_ocr
from services.llm_service import rephrase_output
from configs.configs import LLM_PROMPT
from services.db_service import insert_user_transfer, check_file_exists
import pandas as pd

logger = logging.getLogger(__name__)

def parse_mysql_date(date_str):
    """Helper to fix date formats"""
    if not date_str or str(date_str).lower() == "null":
        return None
    try:
        dt = pd.to_datetime(date_str, dayfirst=True)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return None

def process_single_transfer(file_path, user_id=None, user_phone=None):
    """
    Processes a single image file.
    - user_id: Passed from API (Optional for batch)
    - user_phone: Passed from API (Optional for batch)
    """
    filename = os.path.basename(file_path)
    
    # 1. Optimization: Skip if already done
    if check_file_exists(filename):
        logger.info(f"Skipping {filename} (Already processed)")
        return {"status": "skipped", "message": "Duplicate file"}

    logger.info(f"Processing Screenshot: {filename}")
    
    # 2. Run Surya OCR
    ocr_data = run_surya_ocr(file_path)
    if not ocr_data:
        return {"status": "failed", "message": "No text detected"}

    # Calculate Confidence
    confidences = [item[1] for item in ocr_data if item[1] is not None]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    ocr_text_lines = [item[0] for item in ocr_data]

    # 3. Run LLM Extraction
    json_response_str = rephrase_output(LLM_PROMPT, ocr_text_lines)
    
    if json_response_str:
        try:
            data = json.loads(json_response_str)
            
            # --- CLEANING ---
            raw_amount = str(data.get("Amount Transferred", "0"))
            clean_amount = raw_amount.replace("EGP", "").replace(",", "").strip()
            final_amount = float(clean_amount) if clean_amount != "null" else 0.0
            data['Amount Transferred'] = final_amount
            
            data['Transaction Date'] = parse_mysql_date(data.get('Transaction Date'))
            data['source_filename'] = filename
            
            # --- NEW: EXACT CONFIDENCE MATCHING ---
            amount_conf = 0.0
            phone_conf = 0.0
            
           # Loop through the raw SuryaOCR output safely
            for item in ocr_data:
                text = item[0]
                conf = item[1]
                
                if not text or not conf:
                    continue
                
                # Check if the extracted amount is inside this raw OCR text block
                # NEW: Drop the '.0' if it's a whole number before searching
                search_amount = str(int(final_amount)) if final_amount.is_integer() else str(final_amount)
                
                if search_amount in text.replace(",", ""):
                    amount_conf = round(float(conf), 4)
                
                # Check if the extracted phone number is inside this raw OCR text block
                phone_str = str(data.get('Mobile Number', ''))
                if phone_str and phone_str != "null" and phone_str in text.replace(" ", ""):
                    phone_conf = round(float(conf), 4)
        
            # Save our exact scores
            data['amount_confidence'] = amount_conf
            data['phone_confidence'] = phone_conf
            data['ocr_confidence'] = avg_confidence 
            
            # --- API OVERRIDES ---
            if user_id:
                data['user_id'] = user_id
            if user_phone:
                data['Mobile Number'] = user_phone

            # 4. Insert into DB
            insert_user_transfer(data)
            return {"status": "success", "data": data}
        except json.JSONDecodeError:
            return {"status": "failed", "message": "Invalid JSON response from LLM"}
    
    return {"status": "failed", "message": "No response from LLM"}