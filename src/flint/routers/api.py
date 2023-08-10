# Standard Packages
import logging
import os
import asyncio
from typing import Optional

# External Packages
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from fastapi.params import Form
import openai
import requests
from twilio.request_validator import RequestValidator
from twilio.rest import Client

# Internal Packages
from flint import state
from flint.configure import save_conversation
from flint.routers.helpers import download_audio_message


# Initialize Router
api = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Twilio Client
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twillio_client = Client(account_sid, auth_token)


# Setup API Endpoints
@api.post("/chat")
async def chat(
    request: Request,
    From: str = Form(...),
    Body: Optional[str] = Form(None),
    To: str = Form(...),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None),
) -> Response:
    # Authenticate Request from Twilio
    validator = RequestValidator(auth_token)
    form_ = await request.form()
    logger.debug(f"Request Headers: {request.headers}")
    if not validator.validate(str(request.url), form_, request.headers.get("X-Twilio-Signature", "")):
        logger.error("Error in Twilio Signature")
        raise HTTPException(status_code=401, detail="Unauthorized signature")

    # Get the user object
    user = await sync_to_async(User.objects.prefetch_related("khojuser").filter)(khojuser__phone_number=From)
    user_exists = await sync_to_async(user.exists)()
    if not user_exists:
        user_phone_number = From.split(":")[1]
        user = await sync_to_async(User.objects.create)(username=user_phone_number)
        user.khojuser.phone_number = user_phone_number
        await sync_to_async(user.save)()
    else:
        user = await sync_to_async(user.get)()
    uuid = user.khojuser.uuid

    # Set user message to the body of the request
    user_message = Body
    # Check if message is an audio message
    if MediaUrl0 is not None and MediaContentType0 is not None and MediaContentType0.startswith("audio/"):
        audio_url = MediaUrl0
        audio_type = MediaContentType0.split("/")[1]
        logger.info(f"Received audio message from {From} with url {audio_url} and type {audio_type}")
        user_message = transcribe_audio_message(audio_url, uuid)

    # Get Conversation History
    chat_history = state.conversation_sessions[uuid]

    # Get Response from Agent
    chat_response = state.converse(memory=chat_history)({"question": user_message})
    chat_response_text = chat_response["text"]

    asyncio.create_task(save_conversation(user, user_message, chat_response_text))

    # Split response into 1600 character chunks
    chunks = [chat_response_text[i : i + 1600] for i in range(0, len(chat_response_text), 1600)]
    for chunk in chunks:
        message = twillio_client.messages.create(body=chunk, from_=To, to=From)

    return message.sid

if os.getenv("DEBUG", False):
    # Setup API Endpoints
    @api.post("/dev/chat")
    async def chat_dev(
        request: Request,
        Body: str,
    ) -> Response:
        # Get the user object
        target_username = "dev"
        user = await sync_to_async(User.objects.prefetch_related("khojuser").filter)(username=target_username)
        user_exists = await sync_to_async(user.exists)()
        if user_exists:
            user = await sync_to_async(user.get)()
        else:
            user = await sync_to_async(User.objects.create)(username=target_username)
            await sync_to_async(user.save)()
        uuid = user.khojuser.uuid

        # Get Conversation History
        chat_history = state.conversation_sessions[uuid]

        # Get Response from Agent
        chat_response = state.converse(memory=chat_history)({"question": Body})
        chat_response_text = chat_response["text"]

        asyncio.create_task(save_conversation(user, Body, chat_response_text))

        return chat_response_text


def transcribe_audio_message(audio_url: str, uuid: str) -> str:
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