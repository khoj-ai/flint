# Standard Packages
import asyncio
import logging
import os
import requests
from typing import Optional

# External Packages
from asgiref.sync import sync_to_async
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from fastapi.params import Form
from langchain.chains import LLMChain

# Internal Packages
from flint import state
from flint.configure import configure_chat_prompt, save_conversation, get_recent_conversations
from flint.helpers import transcribe_audio_message, prepare_prompt, make_whatsapp_payload
from flint.constants import (
    KHOJ_INTRO_MESSAGE,
    KHOJ_PROMPT_EXCEEDED_MESSAGE,
    KHOJ_FAILED_AUDIO_TRANSCRIPTION_MESSAGE,
    KHOJ_UNSUPPORTED_MEDIA_TYPE_MESSAGE,
)

# Keep Django module import here to avoid import ordering errors
from django.contrib.auth.models import User


# Initialize Router
api = APIRouter()
logger = logging.getLogger(__name__)

MAX_CHARACTERS_TWILIO = 1600
MAX_CHARACTERS_PROMPT = 1000

DEBUG = os.getenv("DEBUG", False)

whatsapp_token = os.getenv("WHATSAPP_TOKEN")

verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "verify_token")


@api.get("/health")
async def health() -> Response:
    return Response(status_code=200)


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


@api.get("/whatsapp_chat")
async def whatsapp_chat(
    request: Request,
):
    return verify(request)


@api.post("/whatsapp_chat")
async def whatsapp_chat_post(
    request: Request,
):
    await handle_message(request)
    return Response(status_code=200)


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
async def handle_message(request: Request):
    # Parse Request body in json format
    body = await request.json()
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

    # Get the user object
    user = await sync_to_async(User.objects.prefetch_related("khojuser").filter)(
        khojuser__phone_number=formatted_number
    )
    user_exists = await user.aexists()
    logger.info(f"{value['messages'][0]['type']} message received from {formatted_number}")
    intro_message = value["messages"][0]["type"] == "request_welcome"

    if not user_exists:
        user = await User.objects.acreate(username=formatted_number)
        user.khojuser.phone_number = formatted_number
        await user.asave()
    else:
        user = await user.aget()

    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    if message["type"] == "text":
        logger.info("text message received")
        message_body = message["text"]["body"]
    elif message["type"] == "audio":
        logger.info("audio message received")
        audio_id = message["audio"]["id"]
        try:
            message_body = handle_audio_message(audio_id, user.khojuser.uuid)
        except ValueError as e:
            logger.error(f"Failed to handle audio message: {e}", exc_info=True)
            raise HTTPException(status_code=400, detail=KHOJ_FAILED_AUDIO_TRANSCRIPTION_MESSAGE)
    await response_to_user_whatsapp(message_body, user, from_number, body, intro_message)


# handle audio messages
def handle_audio_message(audio_id, uuid):
    audio_url = get_media_url(audio_id)
    return transcribe_audio_message(audio_url, uuid, logger)


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


if DEBUG:
    # Setup API Endpoints
    @api.post("/dev/chat")
    async def chat_dev(
        request: Request,
        Body: str,
        username: Optional[str] = Form(None),
    ) -> Response:
        # Get the user object
        target_username = username if username is not None else "dev"
        user = await sync_to_async(User.objects.prefetch_related("khojuser").filter)(username=target_username)
        user_exists = await sync_to_async(user.exists)()
        if user_exists:
            user = await sync_to_async(user.get)()
        else:
            user = await sync_to_async(User.objects.create)(username=target_username)
            await sync_to_async(user.save)()
        uuid = user.khojuser.uuid

        # Get Conversation History
        chat_history = state.conversation_sessions.get(uuid, None)
        if chat_history is None:
            logger.info(f"Attempting to retrieve conversation history for user {uuid}")
            state.conversation_sessions[uuid] = await get_recent_conversations(user, uuid)
            chat_history = state.conversation_sessions[uuid]

        try:
            user_message, formatted_history_message, adjusted_memory_buffer = prepare_prompt(
                chat_history=chat_history,
                relevant_previous_conversations=[],
                user_message=Body,
                model_name=state.MODEL_NAME,
            )
        except ValueError as e:
            logger.error(f"Prompt exceeded maximum length: {e}", exc_info=True)

        if formatted_history_message != None:
            asyncio.create_task(save_conversation(user, "", formatted_history_message, "text"))

        # Get Response from Agent
        chat_response = LLMChain(llm=state.llm, prompt=configure_chat_prompt(), memory=adjusted_memory_buffer)(
            {"question": user_message}
        )
        chat_response_text = chat_response["text"]

        asyncio.create_task(save_conversation(user, user_message, chat_response_text, "text"))

        return chat_response_text


async def response_to_user_whatsapp(message: str, user: User, from_number: str, body, intro_message=False):
    # Initialize user message to the body of the request
    uuid = user.khojuser.uuid
    user_message = message
    user_message_type = "text"

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
        asyncio.create_task(
            save_conversation(user=user, message="", response=KHOJ_INTRO_MESSAGE, user_message_type="system")
        )
        return Response(status_code=200)

    # Get Conversation History
    logger.info(f"Retrieving conversation history for {uuid}")

    # Get Conversation History
    chat_history = state.conversation_sessions.get(uuid, None)
    if chat_history is None:
        logger.info(f"Attempting to retrieve conversation history for user {uuid}")
        state.conversation_sessions[uuid] = await get_recent_conversations(user, uuid)
        chat_history = state.conversation_sessions[uuid]

    try:
        logger.info(f"Preparing prompt for {uuid}")
        user_message, formatted_history_message, adjusted_memory_buffer = prepare_prompt(
            chat_history=chat_history,
            relevant_previous_conversations=[],
            user_message=user_message,
            model_name=state.MODEL_NAME,
        )
    except Exception as e:
        logger.error(f"Failed to prepare prompt: {e}", exc_info=True)
        return

    if formatted_history_message != None:
        asyncio.create_task(save_conversation(user, "", formatted_history_message, user_message_type="system"))

    # Get Response from Agent
    logger.info(f"Sending prompt to LLM for user {uuid}")
    chat_response = LLMChain(llm=state.llm, prompt=configure_chat_prompt(), memory=adjusted_memory_buffer)(
        {"question": user_message}
    )
    chat_response_text = chat_response["text"]

    asyncio.create_task(
        save_conversation(
            user=user, message=user_message, response=chat_response_text, user_message_type=user_message_type
        )
    )

    # Split response into 1600 character chunks
    data = make_whatsapp_payload(chat_response_text, from_number)
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()

    return Response(status_code=200)
