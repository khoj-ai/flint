# Standard Packages
import base64
import time
from typing import Optional

# External Packages
from fastapi import APIRouter, Request, Body
from fastapi.responses import Response
from fastapi.params import Form

# Internal Packages
from flint.helpers import send_message_to_khoj_chat


# Initialize Router
dev = APIRouter()


# Setup Dev API Endpoints
@dev.post("/chat")
async def chat_dev(
    request: Request,
    body=Body(...),
    phone_number: Optional[str] = Form(None),
) -> Response:
    chat_response = send_message_to_khoj_chat(body, phone_number)

    if chat_response.get("response"):
        response = chat_response.get("response")
        if response.get("image"):
            encoded_img = response["image"]
            if encoded_img:
                # Write the file to a tmp directory
                filepath = f"/tmp/{int(time.time() * 1000)}.png"
                with open(filepath, "wb") as f:
                    f.write(base64.b64decode(encoded_img))
            chat_response_text = f"Image saved to {filepath}"
        else:
            chat_response_text = chat_response["response"]
    elif chat_response.get("detail"):
        chat_response_text = chat_response["detail"]

    return chat_response_text
