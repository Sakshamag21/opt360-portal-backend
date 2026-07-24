from pathlib import Path

import polars as pl
import trino

from config import CONFIG


class TrinoClient:

    def __init__(self):

        cfg = CONFIG["trino"]

        self.conn = trino.dbapi.connect(
            host=cfg["host"],
            port=cfg["port"],
            user=cfg["user"],
            catalog=cfg["catalog"],
            schema=cfg["schema"],
        )

        self.sql_dir = Path(__file__).resolve().parents[1] / "sql"

    def _load_sql(self, template_name: str) -> str:
        """
        Load SQL template from sql/ directory.
        """
        with open(self.sql_dir / template_name, "r") as f:
            return f.read()

    def execute_feature(self, feature: dict) -> pl.DataFrame:
        """
        Execute SQL template for a feature.
        """

        sql = self._load_sql(feature["template"])

        # Replace placeholders from YAML
        params = feature.copy()

        # Optional defaults
        params.setdefault("window_days", 30)
        params.setdefault("year", "current_date")

        sql = sql.format(**params)

        cur = self.conn.cursor()

        cur.execute(sql)

        rows = cur.fetchall()

        columns = [col[0] for col in cur.description]

        if not rows:
            return pl.DataFrame(schema=columns)

        return pl.DataFrame(
            rows,
            schema=columns,
            orient="row",
        )