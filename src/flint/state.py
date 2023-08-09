# Standard Packages
from collections import defaultdict

# External Packages
from langchain.chains import LLMChain
from langchain.memory import ConversationTokenBufferMemory

from langchain.chat_models import ChatOpenAI

llm = ChatOpenAI(temperature=0)
converse: LLMChain = None
conversation_sessions = defaultdict(lambda: ConversationTokenBufferMemory(memory_key="chat_history", return_messages=True, max_token_limit=4096, llm=llm))