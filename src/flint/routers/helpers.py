# Standard Packages
import datetime
import os
import time
import requests
import urllib.request

# Internal Packages
from flint.state import telemetry


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
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
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
