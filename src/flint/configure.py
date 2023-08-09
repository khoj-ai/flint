# Standard Packages
from functools import partial
from collections import defaultdict

# External Packages
import schedule
import requests
from fastapi import FastAPI
from asgiref.sync import sync_to_async
from langchain.chains import LLMChain
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain.memory import ConversationTokenBufferMemory

# Internal Packages
from flint.db.models import Conversation
from flint.state import llm, telemetry
from flint.constants import telemetry_server
from flint.routers.helpers import log_telemetry


from django.contrib.auth.models import User

import logging

logger = logging.getLogger(__name__)

def initialize_agent() -> LLMChain:
    "Initialize the Conversational Chain with Memory"
    prompt = ChatPromptTemplate(
        messages=[
            SystemMessagePromptTemplate.from_template(
                f"""
    You are Khoj, a friendly, smart and helpful personal thought partner.
    Use your general knowledge and past conversations to chat with your human.
    """.strip()
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanMessagePromptTemplate.from_template("{question}")
        ]
    )
    converse = partial(LLMChain, llm=llm, prompt=prompt, verbose=True)
    return converse


def initialize_conversation_sessions() -> defaultdict[str, ConversationTokenBufferMemory]:
    "Initialize the Conversation Sessions"
    logger.info("Initializing Conversation Sessions")
    conversation_sessions = defaultdict(lambda: ConversationTokenBufferMemory(memory_key="chat_history", return_messages=True, max_token_limit=4096, llm=llm))
    users = User.objects.all()
    for user in users:
        conversations = Conversation.objects.filter(user=user)[:10]
        conversations = conversations[::-1]
        # Reconstruct the conversation sessions from the database
        for conversation in conversations:
            conversation_sessions[conversation.user.khojuser.uuid].chat_memory.add_user_message(conversation.user_message)
            conversation_sessions[conversation.user.khojuser.uuid].chat_memory.add_ai_message(conversation.bot_message)

    return conversation_sessions
    
async def save_conversation(user, message, response):
    "Save the conversation to the database"
    logger.info(f"💾 Saving conversation to the database and logging telemetry")

    log_telemetry(
        telemetry_type='api',
        user_guid=str(user.khojuser.uuid),
        api='chat_whatsapp',
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
