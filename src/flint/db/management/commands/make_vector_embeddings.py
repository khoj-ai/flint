# Standard packages
import logging
import tqdm
from datetime import datetime

# External packages
from django.core.management.base import BaseCommand, CommandParser

# Internal Packages
from flint.db.models import Conversation, ConversationVector
from flint.state import embeddings_manager


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Make vector embeddings from historic conversations"

    def add_arguments(self, parser: CommandParser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force re-embedding of historic conversations",
            default=False
        )

    def handle(self, *args, **options):
        logger.info(f"Making historic conversation vectors")
        start_time = datetime.now()
        conversations = Conversation.objects.all()
        force = options["force"]

        bar = tqdm.tqdm(total=len(conversations))

        for conversation in conversations:
            full_document = f"{conversation.user_message} {conversation.bot_message}"

            if not force and ConversationVector.objects.filter(conversation=conversation).exists():
                logger.info(f"Conversation {conversation.id} already has associated vectors, skipping")
                bar.update(1)
                continue
            
            ConversationVector.objects.filter(conversation=conversation).delete()
            for embedding in embeddings_manager.generate_embeddings(full_document):
                logger.info(f"Creating vector for conversation {conversation.id}")
                ConversationVector.objects.get_or_create(
                    conversation=conversation,
                    vector=embedding.vector,
                    compiled=embedding.compiled
                )
                
            bar.update(1)
        logger.info(f"Finished making historic conversation vectors in {datetime.now() - start_time}")

        bar.close()

