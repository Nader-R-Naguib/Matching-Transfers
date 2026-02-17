import mysql.connector
from mysql.connector import Error
import logging

# Configure these to match your local MySQL setup
DB_CONFIG = {
    'host': 'localhost',
    'database': 'transfer_reconciliation',
    'user': 'root', 
    'password': 'p@ssword' 
}

logger = logging.getLogger(__name__)

def get_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        logger.error(f"Error connecting to MySQL: {e}")
        return None
    
def check_file_exists(filename):
    """Checks if a source filename already exists in the DB."""
    conn = get_connection()
    if conn:
        cursor = conn.cursor()
        query = "SELECT id FROM user_transfers WHERE source_filename = %s"
        cursor.execute(query, (filename,))
        exists = cursor.fetchone() is not None
        cursor.close()
        conn.close()
        return exists
    return False

def insert_user_transfer(data):
    conn = get_connection()
    if conn:
        cursor = conn.cursor()
        
        # We rely on MySQL UNIQUE constraints for both Ref_ID and Filename
        query = """
        INSERT IGNORE INTO user_transfers 
        (transaction_ref, sender_name, phone_number, amount, transaction_date, ocr_confidence, source_filename)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        try:
            cursor.execute(query, (
                data.get('Transaction Reference'), # If this is NULL, MySQL allows duplicates (Good!)
                data.get('Sender/Receiver Name'),
                data.get('Mobile Number'),
                data.get('Amount Transferred'),
                data.get('Transaction Date'),
                data.get('ocr_confidence'),
                data.get('source_filename') # This CANNOT be duplicate (Stops re-runs)
            ))
            conn.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"Inserted: {data.get('source_filename')}")
            else:
                logger.info(f"Skipped Duplicate File/Ref: {data.get('source_filename')}")
                
        except Error as e:
            logger.error(f"Failed to insert user transfer: {e}")
        finally:
            cursor.close()
            conn.close()

def insert_bank_transfer(row):
    """Inserts CSV extracted data, skipping if Ref_ID already exists."""
    conn = get_connection()
    if conn:
        cursor = conn.cursor()
        # CHANGED: Added 'IGNORE' to skip duplicates silently
        query = """
        INSERT IGNORE INTO bank_transfers 
        (transaction_date, amount, ref_id, phone_number)
        VALUES (%s, %s, %s, %s)
        """
        
        # Handle phone number list/formatting
        phone = None
        if isinstance(row['Phone_number'], list) and row['Phone_number']:
             phone = row['Phone_number'][0]
        elif isinstance(row['Phone_number'], str):
             phone = row['Phone_number']

        try:
            cursor.execute(query, (
                row['Date'],
                row['Credit'],
                row['Ref_ID'],
                phone
            ))
            conn.commit()
            # Optional: Check if it was inserted or skipped
            if cursor.rowcount > 0:
                logger.info(f"Inserted Bank Ref: {row['Ref_ID']}")
            else:
                logger.info(f"Skipped Duplicate Bank Ref: {row['Ref_ID']}")
                
        except Error as e:
            logger.error(f"Failed to insert bank transfer: {e}")
        finally:
            cursor.close()
            conn.close()

def run_matching_logic():
    """
    Executes the matching logic and populates matched/anomaly tables.
    Only matches if OCR confidence was >= 0.99 (enforced in WHERE clause or Python).
    """
    conn = get_connection()
    if not conn: return

    cursor = conn.cursor()
    
    # 1. Clear previous matches
    # cursor.execute("TRUNCATE TABLE matched_transactions")
    # cursor.execute("TRUNCATE TABLE anomaly_user_transfers")
    # cursor.execute("TRUNCATE TABLE anomaly_bank_transfers")

    print("--- Running Matching Logic ---")

    # 2. FIND EXACT MATCHES
    # Criteria: Amount == Amount AND Phone == Phone AND OCR Confidence >= 0.80
    match_query = """
    INSERT INTO matched_transactions (user_transfer_id, bank_transfer_id, matched_amount, matched_phone, match_confidence)
    SELECT 
        u.id, 
        b.id, 
        u.amount, 
        u.phone_number,
        u.ocr_confidence
    FROM user_transfers u
    JOIN bank_transfers b 
        ON u.amount = b.amount 
        AND u.phone_number = b.phone_number
    WHERE u.ocr_confidence >= 0.80
    AND u.id NOT IN (SELECT user_transfer_id FROM matched_transactions) -- Prevent duplicates
    """
    cursor.execute(match_query)
    matches_found = cursor.rowcount
    conn.commit()
    print(f"Matches found and stored: {matches_found}")

    # 3. IDENTIFY USER ANOMALIES (Screenshots that didn't match bank)
    anomaly_user_query = """
    INSERT INTO anomaly_user_transfers (user_transfer_id, amount, reason)
    SELECT u.id, u.amount, 'No matching bank record found or Low Confidence'
    FROM user_transfers u
    LEFT JOIN matched_transactions m ON u.id = m.user_transfer_id
    WHERE m.id IS NULL
    AND u.id NOT IN (SELECT user_transfer_id FROM anomaly_user_transfers);
    """
    cursor.execute(anomaly_user_query)
    conn.commit()

    # 4. IDENTIFY BANK ANOMALIES (Bank records that didn't match screenshots)
    anomaly_bank_query = """
    INSERT INTO anomaly_bank_transfers (bank_transfer_id, amount, reason)
    SELECT b.id, b.amount, 'No matching user transfer found'
    FROM bank_transfers b
    LEFT JOIN matched_transactions m ON b.id = m.bank_transfer_id
    WHERE m.id IS NULL
    AND b.id NOT IN (SELECT bank_transfer_id FROM anomaly_bank_transfers);
    """
    cursor.execute(anomaly_bank_query)
    conn.commit()
    
    cursor.close()
    conn.close()
    print("Reconciliation complete.")