# Standard Packages
from datetime import datetime
import logging
from logging import Logger
import os
import time
import urllib.parse

# External Packages
import openai
import requests

# Internal Packages
from flint.state import telemetry
from flint.constants import KHOJ_API_URL, KHOJ_API_CLIENT_SECRET, KHOJ_API_CLIENT_ID

whatsapp_token = os.getenv("WHATSAPP_TOKEN")

logger = logging.getLogger(__name__)

KHOJ_CHAT_API_ENDPOINT = (
    f"{KHOJ_API_URL}/api/chat?client_id={KHOJ_API_CLIENT_ID}&client_secret={KHOJ_API_CLIENT_SECRET}"
)

COMMANDS = {
    "/online": "/online",
    "/dream": "/image",
    "/general": "/general",
}

UNIMPLEMENTED_COMMANDS = {
    "/notes": "/notes",
    "/speak": "/speak",
}


def get_date():
    return datetime.utcnow().strftime("%Y-%m-%d %A")


def make_whatsapp_payload(body, to):
    return {
        "text": {"body": body},
        "to": to,
        "type": "text",
        "messaging_product": "whatsapp",
    }


def make_whatsapp_image_payload(media_id, to):
    return {"type": "image", "image": {"id": media_id}, "to": to, "messaging_product": "whatsapp"}


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


def download_audio_message(audio_url, random_id):
    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
    }
    response = requests.get(audio_url, headers=headers)

    # Create output file path with user_id and current timestamp
    filepath = f"/tmp/{random_id}_audio_{int(time.time() * 1000)}.ogg"
    # Download the voice message OGG file
    with open(filepath, "wb") as f:
        f.write(response.content)

    # Return file path to audio message
    return os.path.join(os.getcwd(), filepath)


def transcribe_audio_message(audio_url: str, uuid: str, logger: Logger) -> str:
    "Transcribe audio message using OpenAI whisper"

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


def send_message_to_khoj_chat(user_message: str, user_number: str) -> str:
    """
    Send the user message to the backend LLM service and return the response
    """
    encoded_phone_number = urllib.parse.quote(user_number)

    if user_message.startswith(tuple(UNIMPLEMENTED_COMMANDS.keys())):
        return {
            "response": "Sorry, that command is not yet implemented. Try another one! Let us know if you want this sooner by emailing team@khoj.dev"
        }

    cmd_options = COMMANDS.keys()
    if user_message.startswith(tuple(cmd_options)):
        for cmd in cmd_options:
            if user_message.startswith(cmd):
                user_message = user_message.replace(cmd, COMMANDS[cmd])
                break
    else:
        user_message = f"/default {user_message}"

    encoded_user_message = urllib.parse.quote(user_message)

    khoj_api = f"{KHOJ_CHAT_API_ENDPOINT}&phone_number={encoded_phone_number}&q={encoded_user_message}&stream=false&create_if_not_exists=true"
    response = requests.get(khoj_api)
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 429:
        return response.json()
    else:
        logger.error(f"Failed to get response from Khoj. Error: {response.json()}")
        return {"response": "Sorry, I'm having trouble understanding you. Could you please try again?"}


def upload_media_to_whatsapp(media_filepath: str, media_type: str, phone_id: str) -> str:
    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
    }

    with open(media_filepath, "rb") as f:
        files = {
            "file": (media_filepath, f, media_type),
            "type": (None, media_type),
            "messaging_product": (None, "whatsapp"),
        }

        response = requests.post(f"https://graph.facebook.com/v18.0/{phone_id}/media", headers=headers, files=files)

    if response.status_code == 200:
        response_json = response.json()
        if "id" in response_json:
            return response_json["id"]
        else:
            raise ValueError("Response does not contain 'id'")
    else:
        response.raise_for_status()
