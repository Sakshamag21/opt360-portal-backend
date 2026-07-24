import clickhouse_connect

from config import CONFIG

class ClickHouseClient:

    def __init__(self):

        cfg = CONFIG["clickhouse"]

        self.client = clickhouse_connect.get_client(
            host=cfg["host"],
            port=cfg["port"],
            username=cfg["username"],
            password=cfg["password"],
            database=cfg["database"]
        )

    def insert(self, df):

        if df.height == 0:
            return

        self.client.insert(
            "online_features",
            df.to_dicts()
        )