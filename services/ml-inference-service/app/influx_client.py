from app.config import settings

_write_api = None


def get_influx_write_api():
    global _write_api
    if not settings.INFLUXDB_URL:
        return None
    if _write_api is None:
        try:
            from influxdb_client import InfluxDBClient
            from influxdb_client.client.write_api import SYNCHRONOUS
            client = InfluxDBClient(
                url=settings.INFLUXDB_URL,
                token=settings.INFLUXDB_TOKEN,
                org=settings.INFLUXDB_ORG,
            )
            _write_api = client.write_api(write_options=SYNCHRONOUS)
        except Exception:
            return None
    return _write_api
