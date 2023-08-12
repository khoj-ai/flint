# Standard packages
import logging
from enum import Enum
from datetime import datetime, timedelta
import asyncio
import os
import tqdm

# External packages
from django.core.management.base import BaseCommand, CommandError
from twilio.rest import Client

# Internal Packages
from flint.db.models import KhojUser, Conversation
from flint.constants import KHOJ_WHATSAPP_PROD, KHOJ_WHATSAPP_DEBUG
from flint.configure import save_conversation


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Initialize Twilio Client
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twillio_client = Client(account_sid, auth_token)

class UserFilterTypes(Enum):
    ALL = "all"
    ACTIVE_LAST_DAY = "active_last_day"

class MessageType(Enum):
    DEBUG = "debug"
    PROD = "prod"

class Command(BaseCommand):
    help = "test management commands"

    def add_arguments(self, parser):
        parser.add_argument("--user_filter_type", type=str, help="user filter type: all, active_last_day", default=UserFilterTypes.ACTIVE_LAST_DAY.value, required=False, choices=[e.value for e in UserFilterTypes])
        parser.add_argument("bot_message", type=str, help="bot message to send")
        parser.add_argument("--message_type", type=str, help="message type: debug, prod", default=MessageType.DEBUG.value, choices=[e.value for e in MessageType])

    def handle(self, *args, **options):
        user_filter_type = options["user_filter_type"]
        bot_message = options["bot_message"]
        message_type = options["message_type"]

        from_number = KHOJ_WHATSAPP_DEBUG if message_type == MessageType.DEBUG.value else KHOJ_WHATSAPP_PROD

        if user_filter_type == UserFilterTypes.ALL.value:
            logger.warn(f"Sending message '{bot_message}' to all users. This must match a template in the WhatsApp template manager")
            khoj_users = KhojUser.objects.all()
        
        elif user_filter_type == UserFilterTypes.ACTIVE_LAST_DAY.value:
            logger.warn(f"Sending message '{bot_message}' to all users active in the last 24 hours. This must match a template in the WhatsApp template manager")
            curr_time = datetime.now()
            conversations = Conversation.objects.filter(created_at__gte=curr_time - timedelta(days=1))
            khoj_users = conversations.values_list("user", flat=True).distinct()
            khoj_users = KhojUser.objects.filter(id__in=khoj_users)

        else:
            raise CommandError(f"Invalid user filter type: {user_filter_type}")
        
        logger.info(f"Sending message '{bot_message}' to {len(khoj_users)} users")

        bar = tqdm.tqdm(total=len(khoj_users))

        for khoj_user in khoj_users:
            user = khoj_user.user
            logger.info(f"Sending message '{bot_message}' to user {user.id}")
            asyncio.run(save_conversation(user, '', bot_message, user_message_type='system'))
            try:
                message = twillio_client.messages.create(
                    body=bot_message,
                    from_=from_number,
                    to=f'whatsapp:{khoj_user.phone_number}'
                )
                logger.info(f"Sent message '{bot_message}' to user {khoj_user.id}, {khoj_user.phone_number}, from number {from_number} with Twilio message id {message.sid}")
            except Exception as e:
                logger.error(f"Failed to send message '{bot_message}' to user {khoj_user.id}, {khoj_user.phone_number} with error {e}")
            bar.update(1)

        bar.close()

