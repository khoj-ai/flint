# Standard Packages
import datetime
import os
import requests
import urllib.request

# External Packages
from pydub import AudioSegment

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


def ogg2mp3(audio_url, user_id):
    # Get the response of the OGG file
    response = requests.get(audio_url)
    # Get the redirect URL result
    url = response.url # `url` value something like this: "https://s3-external-1.amazonaws.com/media.twiliocdn.com/<some-hash>/<some-other-hash>"
    # Set file path
    filepath = f"/tmp/{user_id}_audio"
    # Download the OGG file
    urllib.request.urlretrieve(url, f"{filepath}.ogg")
    # Load the OGG file
    audio_file = AudioSegment.from_ogg(f"{filepath}.ogg")
    # Export the file as MP3
    audio_file.export(f"{filepath}.mp3", format="mp3")
    # Delete OGG file
    os.remove(f"{filepath}.ogg")
    # Return path to message mp3
    return os.path.join(os.getcwd(), f"{filepath}.mp3")
