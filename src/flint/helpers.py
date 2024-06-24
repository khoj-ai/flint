# Standard Packages
from datetime import datetime
import logging
from logging import Logger
import os
import time
import urllib.parse

# External Packages
import openai
from requests import Session

# Internal Packages
from flint.constants import KHOJ_API_URL, KHOJ_API_CLIENT_SECRET, KHOJ_API_CLIENT_ID

whatsapp_cloud_api_session = Session()
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
whatsapp_cloud_api_session.headers.update({"Authorization": f"Bearer {WHATSAPP_TOKEN}"})

logger = logging.getLogger(__name__)

KHOJ_CHAT_API_ENDPOINT = f"{KHOJ_API_URL}/api/chat?client_id={KHOJ_API_CLIENT_ID}"
KHOJ_INDEX_API_ENDPOINT = f"{KHOJ_API_URL}/api/v1/index/update?client_id={KHOJ_API_CLIENT_ID}&client=whatsapp"

KHOJ_CLOUD_API_SESSION = Session()
KHOJ_CLOUD_API_SESSION.headers.update({"Authorization": f"Bearer {KHOJ_API_CLIENT_SECRET}"})

COMMANDS = {
    "/online": "/online",
    "/dream": "/image",
    "/general": "/general",
    "/notes": "/notes",
}

UNIMPLEMENTED_COMMANDS = {
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


def download_media(url, filepath):
    response = whatsapp_cloud_api_session.get(url)

    # Download the voice message OGG file
    with open(filepath, "wb") as f:
        f.write(response.content)

    # Return file path to audio message
    return os.path.join(os.getcwd(), filepath)


def upload_document_to_khoj(document_url, random_id, phone_id, mime_type):
    file_ending = mime_type.split("/")[1]
    document_filepath = download_media(
        document_url, f"/tmp/{random_id}_document_{int(time.time() * 1000)}.{file_ending}"
    )

    encoded_phone_number = urllib.parse.quote(phone_id)

    with open(document_filepath, "rb") as f:
        files = [
            ("files", (document_filepath, f, mime_type)),
        ]
        khoj_api = f"{KHOJ_INDEX_API_ENDPOINT}&phone_number={encoded_phone_number}&create_if_not_exists=true"
        response = KHOJ_CLOUD_API_SESSION.post(khoj_api, files=files)

    if response.status_code == 200:
        return "Document uploaded successfully"
    else:
        response.raise_for_status()


def transcribe_audio_message(audio_url: str, uuid: str, logger: Logger) -> str:
    "Transcribe audio message using OpenAI whisper"

    start_time = time.time()

    try:
        # Download audio file
        audio_message_file = download_media(audio_url, f"/tmp/{uuid}_audio_{int(time.time() * 1000)}.ogg")
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
    start_time = time.time()
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
    response = KHOJ_CLOUD_API_SESSION.get(khoj_api)

    end_time = time.time()
    response_time = end_time - start_time
    formatted_response_time = "{:.2f}".format(response_time)
    logger.info(f"Khoj chat response time: {formatted_response_time} seconds")

    try:
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            # Handle rate limiting specifically
            return {
                "response": "We're so happy you're loving Khoj! If you'd like to chat more frequently, please subscribe: https://khoj.dev/pricing."
            }
        else:
            # Attempt to parse error details from the response
            try:
                error_details = response.json()
            except ValueError:
                # If response is not JSON, use the status text
                error_details = response.text or response.reason

            logger.error(
                f"Failed to get response from Khoj. Status code: {response.status_code}, Error: {error_details}"
            )
            return {"response": "Sorry, I'm having trouble understanding you. Could you please try again?"}
    except Exception as e:
        logger.exception("An unexpected error occurred while processing the response from Khoj.")
        return {"response": "I encountered an unexpected issue. Could you please try again?"}


def upload_media_to_whatsapp(media_filepath: str, media_type: str, phone_id: str) -> str:
    with open(media_filepath, "rb") as f:
        files = {
            "file": (media_filepath, f, media_type),
            "type": (None, media_type),
            "messaging_product": (None, "whatsapp"),
        }

        response = whatsapp_cloud_api_session.post(f"https://graph.facebook.com/v18.0/{phone_id}/media", files=files)

    if response.status_code == 200:
        response_json = response.json()
        if "id" in response_json:
            return response_json["id"]
        else:
            raise ValueError("Response does not contain 'id'")
    else:
        response.raise_for_status()
