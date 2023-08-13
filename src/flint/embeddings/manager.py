# Standard Packages
from dataclasses import dataclass
from typing import List
import logging

# External Packages
from langchain.embeddings import HuggingFaceEmbeddings
from pgvector.django import CosineDistance
from asgiref.sync import sync_to_async


# Internal Packages
from flint.db.models import ConversationVector, Conversation
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)

@dataclass
class Embedding:
    compiled: str
    vector: List[float]


class EmbeddingsManager():
    def __init__(self):
        model_name = "intfloat/multilingual-e5-large"
        encode_kwargs = {'normalize_embeddings': True}
        self.embeddings_model = HuggingFaceEmbeddings(
            model_name=model_name,
            encode_kwargs=encode_kwargs
        )
        self.max_tokens = 512

    def generate_embeddings(self, text: str):
        # Split into chunks of 512 tokens
        for chunk_index in range(0, len(text), self.max_tokens):
            chunk = text[chunk_index:chunk_index+self.max_tokens]
            embedding_chunk = f"passage: {chunk}"
            embeddings = self.embeddings_model.embed_documents([embedding_chunk])
            yield Embedding(chunk, embeddings[0])

    async def search(self, query: str, user: User, top_n: int = 3, debug: bool = False):
        conversations_to_search = user.conversations.all()
        formatted_query = f"query: {query}"
        embedded_query = self.embeddings_model.embed_query(formatted_query)
        sorted_vectors = ConversationVector.objects.filter(conversation__in=conversations_to_search).alias(distance=CosineDistance('vector', embedded_query)).filter(distance__lte=0.20).order_by('distance')

        num_vectors = await sync_to_async(sorted_vectors.count)()
        if num_vectors == 0:
            return Conversation.objects.none()
        
        if num_vectors > top_n:
            sorted_vectors = sorted_vectors[:top_n]

        if debug:
            annotated_result = ConversationVector.objects.filter(conversation__in=conversations_to_search).annotate(distance=CosineDistance('vector', embedded_query)).order_by('distance')[:10]
            debugging_vectors = await sync_to_async(list)(annotated_result.all())

            for vector in debugging_vectors:
                logger.debug(f"Compiled: {vector.compiled}")
                logger.debug(f"Distance: {vector.distance}")

        n_matching_conversations = sorted_vectors.values_list('conversation', flat=True)
        return Conversation.objects.filter(id__in=n_matching_conversations).distinct()
