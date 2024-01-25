# Standard Packages
import os
import logging

# External Packages
from fastapi import FastAPI


DEBUG = os.getenv("DEBUG", False)
logger = logging.getLogger(__name__)


def configure_routes(app: FastAPI):
    "Configure the API Routes"
    logger.info("Including routes")
    from flint.routers.api import api
    app.include_router(api, prefix="/api")

    if DEBUG:
        from flint.routers.dev import dev
        app.include_router(dev, prefix="/dev")
