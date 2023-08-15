import pytest
import factory
import random
import pytest


from flint.embeddings.manager import EmbeddingsManager
from flint.db.models import Conversation, ConversationVector
from django.contrib.auth.models import User

from pgvector.django import CosineDistance


# Create a pytest fixture for the embeddings manager
@pytest.fixture(scope="session")
def embeddings_manager():
    return EmbeddingsManager()

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Faker("name")
    email = factory.Faker("email")
    password = factory.Faker("password")

class ConversationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Conversation

    user_message = factory.Faker("sentence")
    bot_message = factory.Faker("sentence")

class ConversationVectorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ConversationVector

    conversation = factory.SubFactory(ConversationFactory)
    compiled = factory.Faker("sentence")
    vector = factory.LazyFunction(lambda: [random.uniform(-1, 1) for _ in range(100)])

TEST_CONVERSATIONS = [
    {
        "user_message": "Hello",
        "bot_message": "Hi there!"
    },
    {
        "user_message": "Are there any colors that aren't present in rainbows?",
        "bot_message": "Yes, there are colors that are not present in rainbows. The colors that we see in a rainbow are a result of the visible spectrum of light, which ranges from red to violet. However, there are colors outside of this range that are not visible to the human eye. For example, ultraviolet (UV) light has a shorter wavelength than violet light and is not visible in a rainbow. Similarly, infrared (IR) light has a longer wavelength than red light and is also not visible in a rainbow. These colors exist in the electromagnetic spectrum but are beyond the range of what our eyes can perceive. So while rainbows display a beautiful array of colors, there are other colors that exist beyond what we can see in this natural phenomenon."
    },
    {
        "user_message": "Some species of damselfly have elaborate courtship behaviours. Many species are sexually dimorphic, the males often being more brightly coloured than the females. Like dragonflies, they reproduce using indirect insemination and delayed fertilisation. A mating pair form a shape known as a 'heart' or 'wheel', the male clasping the female at the back of the head, the female curling her abdomen down to pick up sperm from secondary genitalia at the base of the male's abdomen. The pair often remain together with the male still clasping the female while she lays eggs within the tissue of plants in or near water using a robust ovipositor.",
        "bot_message": "It's also intriguing to know that damselflies have been around for a long time, with fossil evidence dating back millions of years. Molecular analysis has provided insights into their evolutionary relationships and has led to the reorganization of some damselfly families."
    }
]

def test_generates_embeddings(embeddings_manager):
    # Test that the embeddings manager generates embeddings
    embeddings = embeddings_manager.generate_embeddings("The quick brown fox jumps over the lazy dog")
    for embedding in embeddings:
        assert len(embedding.vector) == 1024
        assert embedding.compiled == "The quick brown fox jumps over the lazy dog"

def test_search_results(embeddings_manager):
    user = UserFactory()
    for msg in TEST_CONVERSATIONS:
        conversation = ConversationFactory(user=user, **msg)
        full_document = f"{msg['user_message']} {msg['bot_message']}"
        embeddings = embeddings_manager.generate_embeddings(full_document)
        for embedding in embeddings:
            ConversationVectorFactory(conversation=conversation, vector=embedding.vector, compiled=embedding.compiled)

    # Test that the embeddings generated are comprehensively searchable. I'm not able to test the actual search function because it needs to be async.
    conversations_to_search = user.conversations.all()
    formatted_query = f"query: What did we discuss about rainbows?"
    embedded_query = embeddings_manager.embeddings_model.embed_query(formatted_query)
    sorted_vectors = ConversationVector.objects.filter(conversation__in=conversations_to_search).alias(distance=CosineDistance('vector', embedded_query)).filter(distance__lte=0.2).order_by('distance').all()
    conversations = set([vector.conversation for vector in sorted_vectors])

    assert sorted_vectors.count() == 2
    assert len(conversations) == 1
