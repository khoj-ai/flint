# Standard Packages
import logging
from datetime import datetime

# External Packages
from fastapi import FastAPI
from asgiref.sync import sync_to_async
import requests
import schedule

# Internal Packages
from flint.db.models import Conversation
from flint.state import telemetry
from flint.constants import telemetry_server
from flint.helpers import log_telemetry

# Keep Django module import here to avoid import ordering errors
from django.contrib.auth.models import User


logger = logging.getLogger(__name__)


async def save_conversation(user, message, response, user_message_type="text"):
    "Save the conversation to the database"

    start_time = datetime.now()

    log_telemetry(
        telemetry_type="api",
        user_guid=str(user.khojuser.uuid),
        api="chat_whatsapp",
        properties={"user_message_type": user_message_type},
    )

    await sync_to_async(Conversation.objects.create)(
        user=user,
        user_message=message,
        bot_message=response,
    )

    logger.info(f"💾 Saved conversation vector to the database for user {user.id} at {datetime.now() - start_time}")


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
