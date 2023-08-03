# Standard Packages
import logging

# External Packages
from fastapi import APIRouter

# Internal Packages
from velarium import state

# Initialize Router
api = APIRouter()
logger = logging.getLogger(__name__)


# Setup API Endpoints
@api.get("/chat")
def chat(q: str):
    result = state.converse({"question": q})
    return {"message": result["text"]}

