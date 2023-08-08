# Standard Packages
from collections import defaultdict

# External Packages
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory

converse: LLMChain = None
conversation_sessions = defaultdict(lambda: ConversationBufferMemory(memory_key="chat_history", return_messages=True))