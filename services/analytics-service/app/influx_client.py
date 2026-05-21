import logging
from functools import lru_cache
from typing import Optional

from app.config import settings

_logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _build_write_api():
    """Construct the InfluxDB write API once. Returns None if Influx isn't
    configured or if the client cannot be built at startup."""
    if not settings.INFLUXDB_URL:
        return None
    try:
        from influxdb_client import InfluxDBClient
        from influxdb_client.client.write_api import SYNCHRONOUS

        client = InfluxDBClient(
            url=settings.INFLUXDB_URL,
            token=settings.INFLUXDB_TOKEN,
            org=settings.INFLUXDB_ORG,
        )
        return client.write_api(write_options=SYNCHRONOUS)
    except Exception:
        _logger.warning(
            "Failed to initialise InfluxDB client (url=%s)",
            settings.INFLUXDB_URL, exc_info=True,
        )
        return None


def get_influx_write_api() -> Optional[object]:
    """Return cached Influx write API if configured, else None."""
    return _build_write_api()
