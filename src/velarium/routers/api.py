# Standard Packages
import logging
import os
from typing import List, Optional, Union

# External Packages
from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import Response
from fastapi.params import Form
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
from twilio.rest import Client

# Internal Packages
from velarium import state

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
    if not validator.validate(str(request.url), form_, request.headers.get("X-Twilio-Signature", "")):
        logger.error("Error in Twilio Signature")
        raise HTTPException(status_code=401, detail="Unauthorized signature")

    # Get Conversation History
    chat_history = state.conversation_sessions[From]

    # Get Response from Agent
    chat_response = state.converse(memory=chat_history)({"question": Body})
    chat_response_text = chat_response["text"]

    # Split response into 1600 character chunks
    chunks = [chat_response_text[i : i + 1600] for i in range(0, len(chat_response_text), 1600)]
    for chunk in chunks:
        message = twillio_client.messages.create(body=chunk, from_=To, to=From)

    return message.sid
