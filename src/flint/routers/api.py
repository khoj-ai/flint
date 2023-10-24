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
from langchain import LLMChain
from twilio.request_validator import RequestValidator
from twilio.rest import Client

# Internal Packages
from flint import state
from flint.configure import configure_chat_prompt, save_conversation, get_recent_conversations
from flint.helpers import transcribe_audio_message, prepare_prompt, make_whatsapp_payload
from flint.state import embeddings_manager
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

# Initialize Twilio Client
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twillio_client = Client(account_sid, auth_token)

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

    # Get the user object
    user = await sync_to_async(User.objects.prefetch_related("khojuser").filter)(khojuser__phone_number=from_number)
    user_exists = await user.aexists()
    intro_message = False
    if not user_exists:
        user = await User.objects.acreate(username=from_number)
        user.khojuser.phone_number = from_number
        await user.asave()
        intro_message = True
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


# download the media file from the media url
def download_media_file(media_url):
    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
    }
    return requests.get(media_url, headers=headers)


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
    print(f"media id response: {response}")
    return response["url"]


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

    # Return OK if empty message is received. This is usually a message reaction
    if Body is None and MediaUrl0 is None:
        logger.warning("Received empty message. This could be a simple message reaction.")
        return Response(status_code=200)

    # Get the user object
    user = await sync_to_async(User.objects.prefetch_related("khojuser").filter)(khojuser__phone_number=From)
    user_exists = await sync_to_async(user.exists)()
    intro_message = False
    if not user_exists:
        user_phone_number = From.split(":")[1]
        user = await sync_to_async(User.objects.create)(username=user_phone_number)
        user.khojuser.phone_number = user_phone_number
        await sync_to_async(user.save)()
        intro_message = True
    else:
        user = await sync_to_async(user.get)()

    asyncio.create_task(respond_to_user(Body, user, MediaUrl0, MediaContentType0, From, To, intro_message))
    return Response(status_code=200)


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

        relevant_previous_conversations = await embeddings_manager.search(Body, user)
        relevant_previous_conversations = await sync_to_async(list)(relevant_previous_conversations.all())

        try:
            user_message, formatted_history_message, adjusted_memory_buffer = prepare_prompt(
                chat_history=chat_history,
                relevant_previous_conversations=relevant_previous_conversations,
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

    @api.post("/dev/search")
    async def search_dev(
        request: Request,
        query: str,
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

        relevant_previous_conversations = await embeddings_manager.search(query, user, debug=True)
        relevant_previous_conversations = await sync_to_async(list)(relevant_previous_conversations.all())

        conversation_history = ""
        for c in relevant_previous_conversations:
            conversation_history += f"Human: {c.user_message}\nKhoj:{c.bot_message}\n\n"

        conversation_history = "none" if conversation_history == "" else conversation_history

        return Response(content=conversation_history, media_type="text/plain")


async def respond_to_user(message: str, user: User, MediaUrl0, MediaContentType0, From, To, intro_message=False):
    # Initialize user message to the body of the request
    uuid = user.khojuser.uuid
    user_message = message
    user_message_type = "text"

    if MediaUrl0 is not None and MediaContentType0 is not None:
        # Check if message is an audio message
        if MediaContentType0.startswith("audio/"):
            audio_url = MediaUrl0
            audio_type = MediaContentType0.split("/")[1]
            user_message_type = "voice_message"
            logger.info(f"Received audio message from {uuid} with url {audio_url} and type {audio_type}")
            user_message = transcribe_audio_message(audio_url, uuid, logger)
            if user_message is None:
                logger.error(f"Failed to transcribe audio by {uuid}")
                message = twillio_client.messages.create(
                    body=KHOJ_FAILED_AUDIO_TRANSCRIPTION_MESSAGE, from_=To, to=From
                )
                asyncio.create_task(
                    save_conversation(
                        user=user,
                        message="",
                        response=KHOJ_FAILED_AUDIO_TRANSCRIPTION_MESSAGE,
                        user_message_type="system",
                    )
                )
                return message.sid
        else:
            logger.warning(f"Received media of unsupported type {MediaContentType0} from {uuid}")
            message = twillio_client.messages.create(body=KHOJ_UNSUPPORTED_MEDIA_TYPE_MESSAGE, from_=To, to=From)
            asyncio.create_task(
                save_conversation(
                    user=user, message="", response=KHOJ_UNSUPPORTED_MEDIA_TYPE_MESSAGE, user_message_type="system"
                )
            )
            return message.sid

    # Get Conversation History
    logger.info(f"Retrieving conversation history for {uuid}")

    # Get Conversation History
    chat_history = state.conversation_sessions.get(uuid, None)
    if chat_history is None:
        logger.info(f"Attempting to retrieve conversation history for user {uuid}")
        state.conversation_sessions[uuid] = await get_recent_conversations(user, uuid)
        chat_history = state.conversation_sessions[uuid]

    logger.info(f"Searching for relevant previous conversations for {uuid}")
    relevant_previous_conversations = await embeddings_manager.search(user_message, user)

    logger.info(f"Retrieved relevant previous conversations for {uuid}")
    relevant_previous_conversations = await sync_to_async(list)(relevant_previous_conversations.all())

    try:
        logger.info(f"Preparing prompt for {uuid}")
        user_message, formatted_history_message, adjusted_memory_buffer = prepare_prompt(
            chat_history=chat_history,
            relevant_previous_conversations=relevant_previous_conversations,
            user_message=user_message,
            model_name=state.MODEL_NAME,
        )
    except ValueError as e:
        logger.error(f"Prompt exceeded maximum length: {e}", exc_info=True)
        message = twillio_client.messages.create(
            body=KHOJ_PROMPT_EXCEEDED_MESSAGE,
            from_=To,
            to=From,
        )
        asyncio.create_task(
            save_conversation(user=user, message="", response=KHOJ_PROMPT_EXCEEDED_MESSAGE, user_message_type="system")
        )
        return message.sid
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
    chunks = [
        chat_response_text[i : i + MAX_CHARACTERS_TWILIO]
        for i in range(0, len(chat_response_text), MAX_CHARACTERS_TWILIO)
    ]
    for chunk in chunks:
        message = twillio_client.messages.create(body=chunk, from_=To, to=From)

    # Send Intro Message
    if intro_message:
        message = twillio_client.messages.create(
            body=KHOJ_INTRO_MESSAGE,
            from_=To,
            to=From,
        )
        asyncio.create_task(
            save_conversation(user=user, message="", response=KHOJ_INTRO_MESSAGE, user_message_type="system")
        )

    return message.sid


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
    chunks = [
        chat_response_text[i : i + MAX_CHARACTERS_TWILIO]
        for i in range(0, len(chat_response_text), MAX_CHARACTERS_TWILIO)
    ]
    for chunk in chunks:
        data = make_whatsapp_payload(chunk, from_number)
        response = requests.post(url, json=data, headers=headers)
        print(f"whatsapp message response: {response.json()}")
        response.raise_for_status()

    # Send Intro Message
    if intro_message:
        data = make_whatsapp_payload(KHOJ_INTRO_MESSAGE, from_number)
        response = requests.post(url, json=data, headers=headers)
        asyncio.create_task(
            save_conversation(user=user, message="", response=KHOJ_INTRO_MESSAGE, user_message_type="system")
        )

    return Response(status_code=200)
