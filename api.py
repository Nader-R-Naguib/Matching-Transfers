from fastapi import FastAPI, File, UploadFile, Form, HTTPException
import shutil
import os
import logging
from services.processor import process_single_transfer

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API")

app = FastAPI()

# Ensure we have a temp folder
os.makedirs("temp_uploads", exist_ok=True)

@app.post("/process-transfer/")
async def process_transfer(
    user_id: str = Form(...), 
    phone_number: str = Form(...), 
    file: UploadFile = File(...)
):
    temp_path = f"temp_uploads/{file.filename}"
    
    try:
        # 1. Save the uploaded file to disk
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        logger.info(f"Received file: {file.filename} from User: {user_id}")
        
        # 2. Call our shared processor
        result = process_single_transfer(
            file_path=temp_path, 
            user_id=user_id, 
            user_phone=phone_number
        )
        
        if result['status'] == 'error':
            raise HTTPException(status_code=500, detail=result['message'])
            
        return result

    except Exception as e:
        logger.error(f"API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
