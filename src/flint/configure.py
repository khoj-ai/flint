# Standard Packages
import logging

# External Packages
from fastapi import FastAPI
import requests
import schedule

# Internal Packages
from flint.state import telemetry
from flint.constants import telemetry_server


logger = logging.getLogger(__name__)


def configure_routes(app: FastAPI):
    "Configure the API Routes"
    logger.info("Including routes")
    from flint.routers.api import api

    app.include_router(api, prefix="/api")


@schedule.repeat(schedule.every(11).minutes)
def upload_telemetry():
    if len(telemetry) == 0:
        logger.debug("No telemetry to upload")
        return

    try:
        logger.debug(f"📡 Upload usage telemetry to {telemetry_server}")
        response = requests.post(telemetry_server, json=telemetry)
        if response.status_code == 200:
            logger.debug(f"📡 Telemetry uploaded successfully")
        else:
            logger.error(f"📡 Error uploading telemetry: {response.text}")
    except Exception as e:
        logger.error(f"📡 Error uploading telemetry: {e}", exc_info=True)
    finally:
        telemetry.clear()
