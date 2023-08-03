# Standard Packages
import logging

# External Packages
from fastapi import FastAPI
from rich.logging import RichHandler
import uvicorn

# Setup Logger
rich_handler = RichHandler(rich_tracebacks=True)
rich_handler.setFormatter(fmt=logging.Formatter(fmt="%(message)s", datefmt="[%X]"))
logging.basicConfig(handlers=[rich_handler])

logger = logging.getLogger("velarium")

# Initialize the Application Server
app = FastAPI()

# Routes
@app.get("/chat")
def chat():
    return {"message": "Hello World"}

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
