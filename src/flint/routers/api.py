# Standard Packages
import logging
import os
import requests
import time
import base64
import uuid

# External Packages
from fastapi import APIRouter, status, Request, BackgroundTasks
from fastapi.responses import Response
from fastapi import Body

# Internal Packages
from flint.helpers import (
    transcribe_audio_message,
    make_whatsapp_payload,
    send_message_to_khoj_chat,
    make_whatsapp_image_payload,
    upload_media_to_whatsapp,
)
from flint.constants import (
    KHOJ_INTRO_MESSAGE,
    KHOJ_FAILED_AUDIO_TRANSCRIPTION_MESSAGE,
)


# Initialize Router
whatsapp_token = os.getenv("WHATSAPP_TOKEN")
verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "verify_token")
logger = logging.getLogger(__name__)
api = APIRouter()


@api.get("/health")
async def health() -> Response:
    return Response(status_code=200)


@api.get("/whatsapp_chat")
async def whatsapp_chat(request: Request):
    return verify(request)


@api.post("/whatsapp_chat", status_code=status.HTTP_200_OK)
async def whatsapp_chat_post(
    request: Request,
    background_tasks: BackgroundTasks,
    body=Body(...),
):
    background_tasks.add_task(handle_message, body)
    return


# Required webhook verification for WhatsApp
# info on verification request payload:
# https://developers.facebook.com/docs/graph-api/webhooks/getting-started#verification-requests
def verify(request):
    # Parse query params from the webhook verification request. Looking for hub.mode, hub.challenge, and hub.verify_token
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    # Check if a token and mode were sent
    if mode and token:
        # Check the mode and token sent are correct
        if mode == "subscribe" and token == verify_token:
            # Respond with 200 OK and challenge token from the request
            logger.info("WEBHOOK_VERIFIED")
            return Response(challenge, status_code=200)
        else:
            # Responds with '403 Forbidden' if verify tokens do not match
            logger.error("VERIFICATION_FAILED")
            return Response(status_code=403)
    else:
        # Responds with '400 Bad Request' if verify tokens do not match
        logger.error("MISSING_PARAMETER")
        return Response(status_code=400)


def verified_body(body):
    entry = body.get("entry")
    if not entry:
        return False
    changes = entry[0].get("changes")
    if not changes:
        return False
    value = changes[0].get("value")
    if not value:
        return False
    messages = value.get("messages")
    if not messages:
        return False
    return True


# handle incoming webhook messages
async def handle_message(body):
    # Parse Request body in json format
    logger.info(f"request body: {body}")

    try:
        # info on WhatsApp text message payload:
        # https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples#text-messages
        if body.get("object"):
            if verified_body(body):
                await handle_whatsapp_message(body)
            return Response(status_code=200)
        else:
            # if the request is not a WhatsApp API event, return an error
            return Response(status_code=404)
    # catch all other errors and return an internal server error
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        return Response(status_code=500)


# handle WhatsApp messages of different type
async def handle_whatsapp_message(body):
    value = body["entry"][0]["changes"][0]["value"]
    from_number = value["messages"][0]["from"]

    formatted_number = f"+{from_number}"

    logger.info(f"{value['messages'][0]['type']} message received from {formatted_number}")
    intro_message = value["messages"][0]["type"] == "request_welcome"

    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    if message["type"] == "text":
        logger.info("text message received")
        message_body = message["text"]["body"]
    elif message["type"] == "audio":
        logger.info("audio message received")
        audio_id = message["audio"]["id"]
        try:
            message_body = handle_audio_message(audio_id)
        except ValueError as e:
            logger.error(f"Failed to handle audio message: {e}", exc_info=True)
            await response_to_user_whatsapp(KHOJ_FAILED_AUDIO_TRANSCRIPTION_MESSAGE, from_number, body, intro_message)
            return
    await response_to_user_whatsapp(message_body, from_number, body, intro_message)


# handle audio messages
def handle_audio_message(audio_id):
    random_uuid = uuid.uuid4()
    audio_url = get_media_url(audio_id)
    return transcribe_audio_message(audio_url, random_uuid, logger)


# get the media url from the media id
def get_media_url(media_id):
    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
    }
    url = f"https://graph.facebook.com/v16.0/{media_id}/"
    response = requests.get(url, headers=headers).json()
    file_size = response["file_size"]
    # If the audio message is larger than 10 MB, return None
    if int(file_size) > 10 * 1024 * 1024:
        logger.info(f"Audio message is larger than 10 MB, skipping")
        raise ValueError(f"Audio message is larger than 10 MB")
    return response["url"]


async def response_to_user_whatsapp(message: str, from_number: str, body, intro_message=False):
    # Initialize user message to the body of the request
    user_message = message

    value = body["entry"][0]["changes"][0]["value"]
    phone_number_id = value["metadata"]["phone_number_id"]
    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
        "Content-Type": "application/json",
    }
    url = "https://graph.facebook.com/v17.0/" + phone_number_id + "/messages"

    # Send Intro Message
    if intro_message:
        data = make_whatsapp_payload(KHOJ_INTRO_MESSAGE, from_number)
        response = requests.post(url, json=data, headers=headers)
        logger.info(f"Intro message sent to {from_number}")
        response.raise_for_status()

    # Get Response from Agent
    chat_response = send_message_to_khoj_chat(user_message, from_number)

    if chat_response.get("response"):
        chat_response_text = chat_response["response"]
        data = make_whatsapp_payload(chat_response_text, from_number)
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
    elif chat_response.get("image"):
        encoded_img = chat_response["image"]
        if encoded_img:
            # Write the file to a tmp directory
            filepath = f"/tmp/{int(time.time() * 1000)}.png"
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(encoded_img))

                media_id = upload_media_to_whatsapp(filepath, "image/png", phone_number_id)
                data = make_whatsapp_image_payload(media_id, from_number)
                response = requests.post(url, json=data, headers=headers)
                response.raise_for_status()
            os.remove(filepath)
    elif chat_response.get("detail"):
        chat_response_text = chat_response["detail"]
        data = make_whatsapp_payload(chat_response_text, from_number)
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
    else:
        logger.error(f"Unsupported response type: {chat_response}", exc_info=True)
