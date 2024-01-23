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
from django.core.management import call_command

# Internal Packages
from flint.configure import configure_routes

# Setup Logger
rich_handler = RichHandler(rich_tracebacks=True)
rich_handler.setFormatter(fmt=logging.Formatter(fmt="%(message)s", datefmt="[%X]"))
logging.basicConfig(handlers=[rich_handler], level=logging.DEBUG)

logger = logging.getLogger()


# Initialize the Application Server
if os.getenv("DEBUG", False):
    app = FastAPI()
    log_group = "flint-dev"
else:
    app = FastAPI(docs_url=None, redoc_url=None)
    log_group = "flint"

call_command("migrate", "--noinput")


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


def run(should_start_server=True):
    configure_routes(app)
    poll_task_scheduler()
    if should_start_server:
        start_server(app)


if __name__ == "__main__":
    run()

else:
    run(should_start_server=False)
