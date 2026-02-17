import os
from dotenv import load_dotenv
from groq import Groq
import logging

load_dotenv()
logger = logging.getLogger(__name__)

def rephrase_output(prompt, ocr_output):
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    if not client.models.list():
            logger.error("External LLM Connection was not established.")
            return

    ocr_text = "\n".join(ocr_output)
    full_prompt = f"{prompt}\n{ocr_text}"
    
    logger.debug(f"Recieved prompt: {prompt} and ocr output: {ocr_output}")
    
    chat_completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": full_prompt}],
        response_format={"type": "json_object"}
    )
    response = chat_completion.choices[0].message.content
    
    if not response:
          logger.debug(f"Did not recieve a response. Response: {response}")
    else:
        return response
    
    