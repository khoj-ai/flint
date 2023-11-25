# Standard Packages
from collections import defaultdict
from typing import List, Dict

# External Packages
from langchain.memory import ConversationBufferMemory

from langchain.chat_models import ChatOpenAI

MODEL_NAME = "gpt-3.5-turbo-16k"
llm = ChatOpenAI(temperature=0, model_name=MODEL_NAME)
conversation_sessions = defaultdict(
    lambda: ConversationBufferMemory(memory_key="chat_history", return_messages=True, llm=llm)
)
telemetry: List[Dict[str, str]] = []
