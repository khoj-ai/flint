# Standard Packages
import logging
import os
import threading

# External Packages
from fastapi import FastAPI
from rich.logging import RichHandler
import uvicorn
from fastapi import Request
import schedule


# Internal Packages
from flint.configure import configure_routes, initialize_agent, initialize_conversation_sessions
from flint import state

# Setup Logger
rich_handler = RichHandler(rich_tracebacks=True)
rich_handler.setFormatter(fmt=logging.Formatter(fmt="%(message)s", datefmt="[%X]"))
logging.basicConfig(handlers=[rich_handler], level=logging.DEBUG)

logger = logging.getLogger()


# Initialize the Application Server
if os.getenv("DEBUG", False):
    app = FastAPI()
else:
    app = FastAPI(docs_url=None, redoc_url=None)

@app.middleware("http")
async def set_scheme(request: Request, call_next):
    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    if forwarded_proto:
        request.scope["scheme"] = forwarded_proto
    response = await call_next(request)
    return response


def start_server(app: FastAPI, host="0.0.0.0", port=8488, socket=None):
    logger.info("🌖 flint is ready to use")
    if socket:
        uvicorn.run(app, proxy_headers=True, uds=socket, log_level="debug", use_colors=True, log_config=None)
    else:
        uvicorn.run(app, host=host, port=port, log_level="debug", use_colors=True, log_config=None)
    logger.info("🌒 Stopping flint")

def poll_task_scheduler():
    timer_thread = threading.Timer(interval=60.0, function=poll_task_scheduler)
    timer_thread.daemon = True
    timer_thread.start()
    schedule.run_pending()


def run():
    file_handler = logging.FileHandler("flint.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(file_handler)

    state.converse = initialize_agent()
    try:
        state.conversation_sessions = initialize_conversation_sessions()
    except Exception as e:
        logger.error(f"Failed to initialize conversation sessions: {e}. You may need to run python src/flint/manage.py migrate", exc_info=True)
    configure_routes(app)
    poll_task_scheduler()
    start_server(app)


if __name__ == "__main__":
    run()
