import asyncio
import base64
import os
import tempfile
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ValidationError
from langchain_core.messages import HumanMessage

# Load environment variables first
load_dotenv()

from app.agent import agentic_workflow
from app.config.config import setup_groq_client
from app.config.logging import logger
from app.src.wppconnect.api import send_message, send_voice
from app.sarvam import detect_language, translate_text, text_to_speech

WAIT_TIME = os.getenv("WAIT_TIME", 2)
GROQ_CLIENT = setup_groq_client()

message_buffers = defaultdict(list)
processing_tasks = {}

# --- Robust Pydantic Model ---
# Make fields optional to handle different event types from WPPConnect gracefully
class Sender(BaseModel):
    id: str
class WebhookData(BaseModel):
    event: str
    session: Optional[str] = None
    body: Optional[str] = None
    type: Optional[str] = None
    isNewMsg: Optional[bool] = None
    sender: Optional[Sender] = None

async def transcribe_base64_audio(base64_audio: str) -> str:
    """Transcribe audio from base64 data using Groq's Whisper model"""
    try:
        audio_data = base64.b64decode(base64_audio)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_file:
            tmp_file.write(audio_data)
            tmp_file_path = tmp_file.name

        with open(tmp_file_path, "rb") as audio_file:
            transcription = GROQ_CLIENT.audio.transcriptions.create(
                model="whisper-large-v3", file=audio_file
            )
        os.unlink(tmp_file_path)
        return transcription.text
    except Exception as e:
        logger.error(f"Error during audio transcription: {e}")
        if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        raise

async def process_aggregated_messages(sender_id: str, is_voice_message: bool):
    """Process messages after waiting period."""
    try:
        await asyncio.sleep(int(WAIT_TIME))
        messages = message_buffers.get(sender_id, [])
        if not messages: return

        combined_message = " ".join(messages)
        del message_buffers[sender_id]
        
        phone_number = sender_id.split("@")[0]
        logger.info(f"Processing for {phone_number}: '{combined_message}' (Voice: {is_voice_message})")

        # 1. Detect language
        original_lang = detect_language(combined_message)
        logger.info(f"Detected language: {original_lang}")

        # 2. Translate to English for agent if needed
        input_for_agent = translate_text(combined_message, target_language='en-IN', source_language=original_lang) if original_lang != 'en-IN' else combined_message

        # 3. Invoke the multi-agent system
        thread_id = f"whatsapp_{phone_number}"
        config = {"configurable": {"thread_id": thread_id}}
        
        output = await agentic_workflow.ainvoke(
            {"messages": [HumanMessage(content=input_for_agent)]},
            config
        )
        final_response = output['messages'][-1].content
        
        logger.info(f"Final synthesized response (English): '{final_response}'")

        # 4. Translate response back to original language if needed
        final_response_translated = translate_text(final_response, target_language=original_lang, source_language='en-IN') if original_lang != 'en-IN' else final_response

        # 5. Send response (Voice or Text)
        if is_voice_message:
            audio_path = text_to_speech(final_response_translated, language_code=original_lang)
            if audio_path:
                send_voice(audio_path, phone_number)
                os.unlink(audio_path)
                logger.info(f"Sent TTS voice reply to {phone_number}")
            else:
                send_message(final_response_translated, phone_number)
                logger.error(f"TTS failed, sent text fallback to {phone_number}")
        else:
            send_message(final_response_translated, phone_number)
            logger.info(f"Sent text reply to {phone_number}")

    except Exception as e:
        logger.error(f"Error in process_aggregated_messages: {str(e)}", exc_info=True)
        send_message("Sorry, an internal error occurred. Please try again.", sender_id.split("@")[0])
    finally:
        if sender_id in processing_tasks:
            del processing_tasks[sender_id]

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AgriBot Multi-Agent WebHook service starting up...")
    yield
    logger.info("AgriBot WebHook service shutting down.")

app = FastAPI(title="AgriBot Multi-Agent Webhook", lifespan=lifespan)

@app.post("/webhook")
async def webhook_handler(data: Dict[str, Any]):
    try:
        # Gracefully handle validation
        parsed_data = WebhookData(**data)

        # --- Filter for relevant message events ---
        if not (parsed_data.event == "onmessage" and parsed_data.isNewMsg and parsed_data.type in ["chat", "ptt"] and parsed_data.sender):
            return {"status": "skipped", "reason": "Not a new user message event"}

        sender_id = parsed_data.sender.id
        is_voice = parsed_data.type == "ptt"
        message_text = ""

        if is_voice:
            message_text = await transcribe_base64_audio(parsed_data.body)
            logger.info(f"Transcribed from {sender_id}: '{message_text}'")
        else:
            message_text = parsed_data.body

        if not message_text or not message_text.strip():
            return {"status": "skipped", "reason": "Empty message"}

        message_buffers[sender_id].append(message_text)
        if sender_id not in processing_tasks:
            task = asyncio.create_task(process_aggregated_messages(sender_id, is_voice))
            processing_tasks[sender_id] = task
        
        return {"status": "aggregating"}
    
    except ValidationError as e:
        # This will catch events that don't match our model but won't crash the server
        logger.debug(f"Skipping non-message event due to validation error: {e.errors()}")
        return {"status": "skipped", "reason": "Non-message event"}
    except Exception as e:
        logger.error(f"Webhook handler crashed: {str(e)}", exc_info=True)
        # Don't raise HTTPException to prevent breaking the connection with WPPConnect
        return {"status": "error", "detail": "Internal server error"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}