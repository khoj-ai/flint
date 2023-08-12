# Standard Packages
from datetime import datetime
from logging import Logger
import os
import time
import openai
import requests
import urllib.request

# Internal Packages
from flint.state import telemetry


def get_date():
    return datetime.utcnow().strftime('%Y-%m-%d %A')


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
    # Get the url of the voice message file
    url = requests.get(audio_url).url
    # Create output file path with user_id and current timestamp
    filepath = f"/tmp/{user_id}_audio_{int(time.time() * 1000)}.ogg"
    # Download the voice message OGG file
    urllib.request.urlretrieve(url, filepath)
    # Return file path to audio message
    return os.path.join(os.getcwd(), filepath)


def transcribe_audio_message(audio_url: str, uuid: str, logger: Logger) -> str:
    "Transcribe audio message from twilio using OpenAI whisper"
    # Download audio file
    audio_message_file = download_audio_message(audio_url, uuid)

    # Transcribe the audio message using WhisperAPI
    logger.info(f"Transcribing audio file {audio_message_file}")
    try:
        # Read the audio message from MP3
        with open(audio_message_file, "rb") as audio_file:
            # Call the OpenAI API to transcribe the audio using Whisper API
            transcribed = openai.Audio.translate(model="whisper-1", file=audio_file)
            user_message = transcribed.get("text")
    except:
        logger.error(f"Failed to transcribe audio by {uuid}")
    finally:
        # Delete the audio MP3 file
        os.remove(audio_message_file)

    return user_message
