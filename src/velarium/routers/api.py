# Standard Packages
import logging
import os
import asyncio
from typing import Optional

# External Packages
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from fastapi.params import Form
from django.contrib.auth.models import User
from asgiref.sync import sync_to_async
from twilio.request_validator import RequestValidator
from twilio.rest import Client

# Internal Packages
from velarium import state
from velarium.configure import save_conversation

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

    # Get Conversation History
    chat_history = state.conversation_sessions[uuid]

    # Get Response from Agent
    chat_response = state.converse(memory=chat_history)({"question": Body})
    chat_response_text = chat_response["text"]

    asyncio.create_task(save_conversation(user, Body, chat_response_text))

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
