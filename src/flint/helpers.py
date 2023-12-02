# Standard Packages
from datetime import datetime
import logging
from logging import Logger
import os
import time

# External Packages
import openai
import tiktoken
import requests
from langchain.memory import ConversationBufferMemory

# Internal Packages
from flint.state import telemetry
from flint.db.models import Conversation
from flint.constants import MAX_TOKEN_LIMIT_PROMPT

whatsapp_token = os.getenv("WHATSAPP_TOKEN")

logger = logging.getLogger(__name__)


def get_date():
    return datetime.utcnow().strftime("%Y-%m-%d %A")


def make_whatsapp_payload(body, to):
    return {
        "text": {"body": body},
        "to": to,
        "type": "text",
        "messaging_product": "whatsapp",
    }


def log_telemetry(
    telemetry_type: str,
    user_guid: str,
    api: str,
    properties: dict = None,
):
    row = {
        "api": api,
        "telemetry_type": telemetry_type,
        "server_id": user_guid,
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "os": "whatsapp",
    }

    if properties is None:
        properties = {}

    row.update(properties)
    telemetry.append(row)


def download_audio_message(audio_url, user_id):
    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
    }
    response = requests.get(audio_url, headers=headers)

    # Create output file path with user_id and current timestamp
    filepath = f"/tmp/{user_id}_audio_{int(time.time() * 1000)}.ogg"
    # Download the voice message OGG file
    with open(filepath, "wb") as f:
        f.write(response.content)

    # Return file path to audio message
    return os.path.join(os.getcwd(), filepath)


def transcribe_audio_message(audio_url: str, uuid: str, logger: Logger) -> str:
    "Transcribe audio message from twilio using OpenAI whisper"

    start_time = time.time()

    try:
        # Download audio file
        audio_message_file = download_audio_message(audio_url, uuid)
    except Exception as e:
        logger.error(f"Failed to download audio by {uuid} with error {e}", exc_info=True)
        return None

    # Transcribe the audio message using WhisperAPI
    logger.info(f"Transcribing audio file {audio_message_file}")
    try:
        # Read the audio message from MP3
        with open(audio_message_file, "rb") as audio_file:
            transcribed = openai.Audio.translate(model="whisper-1", file=audio_file)
            # Call the OpenAI API to transcribe the audio using Whisper API
            transcribed = openai.audio.translations.create(
                model="whisper-1",
                file=audio_file,
            )
            user_message = transcribed.text
    except Exception as e:
        logger.error(f"Failed to transcribe audio by {uuid} with error {e}", exc_info=True)
        return None
    finally:
        # Delete the audio MP3 file
        os.remove(audio_message_file)

    logger.info(f"Transcribed audio message by {uuid} in {time.time() - start_time} seconds")

    return user_message


def get_num_tokens(message: str, model_name: str) -> int:
    encoder = tiktoken.encoding_for_model(model_name)
    num_tokens = len(encoder.encode(message))
    return num_tokens


def prepare_prompt(
    chat_history: ConversationBufferMemory,
    relevant_previous_conversations: list[Conversation],
    user_message,
    model_name,
):
    """
    Prepare the prompt for the LLM by adding the most recent query, preparing relevant messages from the conversation history, and including the most recent messages from the chat memory.
    That also denotes the order of priority, when preparing the prompt with respect to the token limit.
    """
    from flint.prompt import previous_conversations_prompt, CONVERSATION_HISTORY_PROMPT

    # Count the number of tokens in the user message
    user_message_tokens = get_num_tokens(user_message, model_name)
    if user_message_tokens > MAX_TOKEN_LIMIT_PROMPT:
        raise ValueError(f"User message exceeds token limit of {MAX_TOKEN_LIMIT_PROMPT} tokens")

    tokens_remaining = MAX_TOKEN_LIMIT_PROMPT - user_message_tokens
    previous_conversations = ""

    for c in relevant_previous_conversations:
        message_date_utc = c.created_at.strftime("%Y-%m-%d %H:%M:%S")
        if len(c.user_message) == 0:
            next_message = f"{message_date_utc}\nKhoj:{c.bot_message}\n"
        else:
            next_message = f"{message_date_utc}\nHuman:{c.user_message}\nKhoj:{c.bot_message}\n"

        next_message_num_tokens = get_num_tokens(next_message, model_name)

        # If the next message exceeds the token limit, try to see if we can include just the human message. If not, break.
        if tokens_remaining - next_message_num_tokens < 0 and len(c.user_message) > 0:
            human_message = f"{message_date_utc}\nHuman:{c.user_message}\n"
            if tokens_remaining - get_num_tokens(human_message, model_name) < 0:
                break
            else:
                next_message = human_message

        next_message_num_tokens = get_num_tokens(next_message, model_name)

        previous_conversations += next_message
        tokens_remaining -= next_message_num_tokens

    formatted_history_message = None
    if previous_conversations != "":
        formatted_history_message = previous_conversations_prompt.format(
            conversation_history=previous_conversations, conversation_history_prompt=CONVERSATION_HISTORY_PROMPT
        )
        chat_history.chat_memory.add_ai_message(formatted_history_message)

    adjusted_memory_buffer = []
    # Messages are stored in order of oldest to newest, so we need to reverse the list to give newer messages priority
    current_memory = chat_history.chat_memory.messages[::-1]
    for m in current_memory:
        content_tokens = get_num_tokens(m.content, model_name)
        if tokens_remaining - content_tokens < 0:
            break
        else:
            adjusted_memory_buffer.append(m)
            tokens_remaining -= content_tokens

    chat_history.chat_memory.messages = adjusted_memory_buffer[::-1]

    return user_message, formatted_history_message, chat_history
