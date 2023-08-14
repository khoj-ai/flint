# Standard packages
import logging
import tqdm

# External packages
from django.core.management.base import BaseCommand, CommandParser

# Internal Packages
from flint.db.models import Conversation, ConversationVector
from flint.state import embeddings_manager


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Make vector embeddings from historic conversations"
    
    def handle(self, *args, **options):
        logger.info(f"Making historic conversation vectors")
        conversations = Conversation.objects.all()

        bar = tqdm.tqdm(total=len(conversations))

        for conversation in conversations:
            logger.info(f"Creating vector for conversation {conversation.id}")
            full_document = f"{conversation.user_message} {conversation.bot_message}"
            for embedding in embeddings_manager.generate_embeddings(full_document):
                (obj, created) = ConversationVector.objects.get_or_create(
                    conversation=conversation,
                    vector=embedding.vector,
                    compiled=embedding.compiled
                )
                if created:
                    logger.info(f"Created vector for conversation {conversation.id}")
                
            bar.update(1)

        bar.close()

