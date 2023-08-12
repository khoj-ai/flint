# Standard Packages
from functools import partial
from collections import defaultdict
import logging

# External Packages
from fastapi import FastAPI
from asgiref.sync import sync_to_async
from langchain.chains import LLMChain
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    HumanMessagePromptTemplate,
)
from langchain.memory import ConversationTokenBufferMemory
from langchain.schema import SystemMessage
import requests
import schedule

# Internal Packages
from flint.db.models import Conversation
from flint.state import llm, telemetry
from flint.constants import telemetry_server
from flint.helpers import log_telemetry
from flint.prompt import system_prompt

# Keep Django module import here to avoid import ordering errors
from django.contrib.auth.models import User


logger = logging.getLogger(__name__)


def configure_chat_prompt():
    return ChatPromptTemplate(
        messages=[
            SystemMessage(content=system_prompt.format()),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanMessagePromptTemplate.from_template("{question}")
        ]
    )


def initialize_conversation_sessions() -> defaultdict[str, ConversationTokenBufferMemory]:
    "Initialize the Conversation Sessions"
    logger.info("Initializing Conversation Sessions")
    conversation_sessions = defaultdict(lambda: ConversationTokenBufferMemory(memory_key="chat_history", return_messages=True, max_token_limit=3996, llm=llm))
    users = User.objects.all()
    for user in users:
        conversations = Conversation.objects.filter(user=user)[:10]
        conversations = conversations[::-1]
        # Reconstruct the conversation sessions from the database
        for conversation in conversations:
            conversation_sessions[conversation.user.khojuser.uuid].chat_memory.add_user_message(conversation.user_message)
            conversation_sessions[conversation.user.khojuser.uuid].chat_memory.add_ai_message(conversation.bot_message)

    return conversation_sessions
    
async def save_conversation(user, message, response, user_message_type="text"):
    "Save the conversation to the database"
    logger.info(f"💾 Saving conversation to the database and logging telemetry")

    log_telemetry(
        telemetry_type='api',
        user_guid=str(user.khojuser.uuid),
        api='chat_whatsapp',
        properties={"user_message_type": user_message_type}
    )
    await sync_to_async(Conversation.objects.create)(user=user, user_message=message, bot_message=response)


def configure_routes(app: FastAPI):
    "Configure the API Routes"
    logger.info("Including routes")
    from flint.routers.api import api

    app.include_router(api, prefix="/api")

@schedule.repeat(schedule.every(11).minutes)
def upload_telemetry():
    if len(telemetry) == 0:
        logger.debug("No telemetry to upload")
        return
    
    try:
        logger.debug(f"📡 Upload usage telemetry to {telemetry_server}")
        response = requests.post(telemetry_server, json=telemetry)
        if response.status_code == 200:
            logger.debug(f"📡 Telemetry uploaded successfully")
        else:
            logger.error(f"📡 Error uploading telemetry: {response.text}")
    except Exception as e:
        logger.error(f"📡 Error uploading telemetry: {e}", exc_info=True)
    finally:
        telemetry.clear()
