import os
import uuid

from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from rich.console import Console

from app.config.logging import logger
# Change 1: We now import send_message instead of send_voice
from app.src.wppconnect.api import send_message

rich = Console()

load_dotenv()


def generate_thread_id(user_id: str) -> str:
    """Generates a deterministic thread ID based on the user ID."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"thread-{user_id}"))


def process_chunks(chunk, phone_number):
    """
    Processes a chunk from the agent, prints the answer, and sends it as a TEXT message.
    """
    if isinstance(chunk, dict):
        # Look for the 'assistant' key which holds the message content
        if "assistant" in chunk:
            message = chunk["assistant"]["messages"]

            if isinstance(message, AIMessage):
                agent_answer = message.content
                rich.print(
                    f"\nAgriBot to {phone_number}:\n{agent_answer}",
                    style="bold green",
                )
                
                # Change 2: The entire TTS audio generation block is replaced
                try:
                    # Send the agent's answer as a plain text message
                    send_message(agent_answer, phone_number)
                    logger.info(f"Sent text message to {phone_number}")

                except Exception as e:
                    logger.error(f"Failed to send text message: {e}")