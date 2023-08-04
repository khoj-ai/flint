# Standard Packages
import logging

# External Packages
from fastapi import FastAPI
from rich.logging import RichHandler
import uvicorn

from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

from velarium.db.models import ChatHistory

# Setup Logger
rich_handler = RichHandler(rich_tracebacks=True)
rich_handler.setFormatter(fmt=logging.Formatter(fmt="%(message)s", datefmt="[%X]"))
logging.basicConfig(handlers=[rich_handler])

logger = logging.getLogger("velarium")

# Initialize the Application Server
app = FastAPI()

# Initialize the Conversational Chain with Memory
llm = ChatOpenAI(temperature=0)
prompt = ChatPromptTemplate(
    messages=[
        SystemMessagePromptTemplate.from_template(
            f"""
You are Khoj, a friendly, smart and helpful personal assistant.
Use your general knowledge and our past conversations to provide assistance.
""".strip()
        ),
        MessagesPlaceholder(variable_name="chat_history"),
        HumanMessagePromptTemplate.from_template("{question}")
    ]
)
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
converse = LLMChain(llm=llm, prompt=prompt, memory=memory, verbose=True)


# Routes
@app.get("/chat")
def chat(q: str):
    result = converse({"question": q})
    return {"message": result["text"]}


def start_server(app, host="127.0.0.1", port=8488, socket=None):
    logger.info("🌖 Velarium is ready to use")
    if socket:
        uvicorn.run(app, proxy_headers=True, uds=socket, log_level="debug", use_colors=True, log_config=None)
    else:
        uvicorn.run(app, host=host, port=port, log_level="debug", use_colors=True, log_config=None)
    logger.info("🌒 Stopping Velarium")


def run():
    start_server(app)


if __name__ == "__main__":
    run()
