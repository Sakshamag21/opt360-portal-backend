import polars as pl

from logger import logger
from retry import retry_feature
from trino_client import TrinoClient
from clickhouse_client import ClickHouseClient

class FeatureLoader:

    def __init__(self):

        self.trino = TrinoClient()
        self.clickhouse = ClickHouseClient()

    @retry_feature
    def load_feature(self, feature):

        logger.info(f"Loading {feature['online_name']}")

        df = self.trino.read_table(
            feature["offline_table"]
        )

        if df.height == 0:

            logger.warning(
                f"No data found for {feature['online_name']}"
            )
            return

        df = df.with_columns(
            pl.lit(feature["online_name"]).alias("feature_name")
        )

        df = df.select(
            "feature_id",
            "feature_name",
            "feature_value",
            "comments",
            pl.col("timestamp").alias("feature_ts")
        )

        self.clickhouse.insert(df)

        logger.info(
            f"{feature['online_name']} -> {df.height} rows"
        )