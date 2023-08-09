# Standard Packages
import datetime

# Internal Packages
from flint.state import telemetry

def log_telemetry(
        telemetry_type: str,
        user_guid: str,
        api: str,
        properties: dict = None,
):
    row = {
        "api": api,
        "telemetry_type": telemetry_type,
        "server_id": user_guid,
        "timestamp": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "os": "whatsapp",
    }

    if properties is None:
        properties = {}

    row.update(properties)
    telemetry.append(row)

