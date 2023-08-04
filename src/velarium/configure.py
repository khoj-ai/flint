# Standard Packages
from functools import partial

# External Packages
from fastapi import FastAPI
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)


def initialize_agent() -> LLMChain:
    "Initialize the Conversational Chain with Memory"
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
    converse = partial(LLMChain, llm=llm, prompt=prompt, verbose=True)
    return converse


def configure_routes(app: FastAPI):
    "Configure the API Routes"
    from velarium.routers.api import api

    app.include_router(api, prefix="/api")
