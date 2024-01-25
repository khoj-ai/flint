# Standard Packages
import logging

# External Packages
from fastapi import FastAPI


logger = logging.getLogger(__name__)


def configure_routes(app: FastAPI):
    "Configure the API Routes"
    logger.info("Including routes")
    from flint.routers.api import api

    app.include_router(api, prefix="/api")

