# Standard Packages
from collections import defaultdict
import logging
from datetime import timedelta, datetime

# External Packages
from fastapi import FastAPI
from asgiref.sync import sync_to_async
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    HumanMessagePromptTemplate,
)
from langchain.memory import ConversationBufferMemory
from langchain.schema import SystemMessage
import requests
import schedule

# Internal Packages
from flint.db.models import Conversation, ConversationVector
from flint.state import llm, telemetry, embeddings_manager
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
            HumanMessagePromptTemplate.from_template("{question}"),
        ]
    )


def initialize_conversation_sessions() -> defaultdict[str, ConversationBufferMemory]:
    "Initialize the Conversation Sessions"
    logger.info("Initializing Conversation Sessions")
    conversation_sessions = defaultdict(
        lambda: ConversationBufferMemory(memory_key="chat_history", return_messages=True, llm=llm)
    )
    # Get Conversations from the database within the last 24 hours
    conversations = Conversation.objects.filter(created_at__gte=datetime.now() - timedelta(hours=24))
    users = User.objects.filter(conversations__in=conversations).distinct()

    for user in users:
        conversations = Conversation.objects.filter(user=user)[:10]
        conversations = conversations[::-1]
        # Reconstruct the conversation sessions from the database
        for conversation in conversations:
            conversation_sessions[conversation.user.khojuser.uuid].chat_memory.add_user_message(
                conversation.user_message
            )
            conversation_sessions[conversation.user.khojuser.uuid].chat_memory.add_ai_message(conversation.bot_message)

    return conversation_sessions


async def get_recent_conversations(user: User, uuid: str) -> ConversationBufferMemory:
    "Get the recent conversations for the user and construct a new ConversationBufferMemory object"
    conversation_buffer_memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True, llm=llm)
    conversations = Conversation.objects.filter(user=user)[:10]
    conversations = await sync_to_async(list)(conversations.all())
    # Reconstruct the conversation sessions from the database
    for conversation in conversations[::-1]:
        if len(conversation.user_message) > 0:
            conversation_buffer_memory.chat_memory.add_user_message(conversation.user_message)
        if len(conversation.bot_message) > 0:
            conversation_buffer_memory.chat_memory.add_ai_message(conversation.bot_message)

    return conversation_buffer_memory


async def save_conversation(user, message, response, user_message_type="text"):
    "Save the conversation to the database"

    start_time = datetime.now()

    log_telemetry(
        telemetry_type="api",
        user_guid=str(user.khojuser.uuid),
        api="chat_whatsapp",
        properties={"user_message_type": user_message_type},
    )

    conversation = await sync_to_async(Conversation.objects.create)(
        user=user,
        user_message=message,
        bot_message=response,
    )

    full_document = f"{message} {response}"

    embeddings = [embedding for embedding in embeddings_manager.generate_embeddings(full_document)]

    await sync_to_async(ConversationVector.objects.bulk_create)(
        [
            ConversationVector(
                conversation=conversation,
                vector=embedding.vector,
                compiled=embedding.compiled,
            )
            for embedding in embeddings
        ]
    )

    logger.info(
        f"💾 Saved conversation vector to the database for user {user.id}. Generating conversation embeddings and saving {datetime.now() - start_time}"
    )


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


@schedule.repeat(schedule.every(1439).minutes)
def clear_conversations():
    from flint import state

    start_time = datetime.now()
    logger.info("Re-initializing conversation sessions")
    state.conversation_sessions = initialize_conversation_sessions()
    logger.info(f"Re-initializing conversation sessions took {datetime.now() - start_time}")
