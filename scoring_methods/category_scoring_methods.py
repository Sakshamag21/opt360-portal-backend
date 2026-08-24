
import findspark
findspark.init()
from pyspark.sql import functions as F, Window
from pyspark.sql import SparkSession
import logging
import pandas as pd
from trino.dbapi import connect
import datetime as dt

RISK_WEIGHTAGE = {
    "sustxn_outstate_pkts_score_v1" :2,
    "work_machine_change_score_v1" : 4,
    "bio_mfc_fraud_score_v1":4,
    "bio_sfc_fraud_score_v1":1,
    "work_opt_hof_score_v1":4,
    "work_pob_declared_score_v1":2,
    "work_opt_machinesync_score_v1" : 2,
    "hardware_machine_change_score_v1" : 4,
    "sustxn_res_mobilechange_score_v1" : 2,
    "sustxn_oddhour_pkts_score_v1" : 2,
    "hardware_multiple_biodev_score_v1" : 4,
    "sustxn_res_namechange_score_v1" : 2,
    "work_multiple_optname_score_v1" : 4,  
}

def get_spark(job_name: str):
    spark = SparkSession.builder \
        .appName("opt360-catgeory-scoring") \
        .remote("sc://spark-connect-service.strot-spark.svc.cluster.local:15002") \
        .config("spark.sql.legacy.mysql.bitArrayMapping.enabled","true") \
        .config("spark.default.parallelism","800") \
        .config("spark.sql.shuffle.partitions", '800') \
        .getOrCreate()
    return spark


def softmax_scoring(
    spark: SparkSession,
    max_date: str = None,
    softmax_weightage: float = 0.9,
    risk_weightage: dict = RISK_WEIGHTAGE,
    K: float = 4.0
):
    
    print(f"Softmax weightage: {softmax_weightage}")
    print(f"Feature weightage: {risk_weightage}")
    print(f"K parameter: {K}")
    
    if max_date is None:
        max_date = dt.datetime.now().strftime('%Y-%m-%d')
    
    if risk_weightage is None or len(risk_weightage) == 0:
        raise ValueError("risk_weightage dictionary cannot be empty")
    
    if not 0 <= softmax_weightage <= 1:
        raise ValueError("softmax_weightage must be between 0 and 1")
    
    # Read from Iceberg/Hive table using Spark
    risk_df = spark.sql(f"""
        SELECT * FROM (
            SELECT 
                entity_id, 
                feature_id, 
                feature_name, 
                feature_value,
                ROW_NUMBER() OVER (
                    PARTITION BY entity_id, feature_id 
                    ORDER BY timestamp DESC
                ) AS rn 
            FROM strot.operator360.features_risk_v1
            WHERE timestamp <= DATE('{max_date}')
            and timestamp >= date(date('{max_date}') - interval '7' days)
        ) 
        WHERE rn = 1
    """)
    
    print(f"Loaded {risk_df.count()} records from features_risk_v1")
    
    # Filter for feature_ids in risk_weightage
    feature_ids = list(risk_weightage.keys())
    risk_df = risk_df.filter(F.col("feature_id").isin(feature_ids))
    
    print(f"After filtering by feature_ids: {risk_df.count()} records")
    
    # Normalize weights to sum to 1 (probability simplex)
    total_weight = sum(risk_weightage.values())
    normalized_weights = {k: v / total_weight for k, v in risk_weightage.items()}
    print(f"Total weight sum: {total_weight}")
    print(f"Normalized weights: {normalized_weights}")
    
    # Create a mapping expression for normalized weights
    weight_mapping = F.create_map([F.lit(x) for pair in normalized_weights.items() for x in pair])
    
    # Add normalized weight column
    risk_df = risk_df.withColumn("norm_weight", weight_mapping[F.col("feature_id")])
    
    risk_df = risk_df.withColumn("exp_term", F.exp(F.lit(K) * F.col("feature_value"))) \
        .withColumn("w_exp", F.col("norm_weight") * F.col("exp_term")) \
        .withColumn("weighted_exp_feature", F.col("norm_weight") * F.col("feature_value") * F.col("exp_term")) \
        .withColumn("weighted_feature", F.col("norm_weight") * F.col("feature_value"))
    
    # Aggregate by entity_id to compute softmax and weighted mean
    summary_df = risk_df.groupBy("entity_id").agg(
        F.sum("weighted_exp_feature").alias("numerator"),      # Σ w_i * x_i * exp(K*x_i)
        F.sum("w_exp").alias("denominator"),                   # Σ w_i * exp(K*x_i)
        F.sum("weighted_feature").alias("weighted_mean")       # Σ w_i * x_i
    )
    summary_df = summary_df.withColumn("softmax_avg", F.col("numerator") / F.col("denominator")) \
        .withColumn(
            "risk_value", 
            F.lit(softmax_weightage) * F.col("softmax_avg") + 
            F.lit(1 - softmax_weightage) * F.col("weighted_mean")
        ) \
        .select("entity_id", "risk_value") \
        .orderBy(F.col("risk_value").desc())
    
    # print(f"Summary DataFrame row count: {summary_df.count()}")
    # summary_df.show(10, truncate=False)
    
    return summary_df


def weighted_average(
    spark: SparkSession,
    max_date: str = None,
    risk_weightage: dict = None
):
    print(f"Risk weightage: {risk_weightage}")
    
    if max_date is None:
        max_date = dt.datetime.now().strftime('%Y-%m-%d')
    
    if risk_weightage is None or len(risk_weightage) == 0:
        raise ValueError("risk_weightage dictionary cannot be empty")
    
    # Read from Iceberg/Hive table using Spark
    risk_df = spark.sql(f"""
        SELECT * FROM (
            SELECT 
                entity_id, 
                feature_id, 
                feature_name, 
                feature_value,
                ROW_NUMBER() OVER (
                    PARTITION BY entity_id, feature_name 
                    ORDER BY timestamp DESC
                ) AS rn 
            FROM strot.operator360.features_risk_v1
            WHERE timestamp <= DATE('{max_date}')
            and timestamp>= date(date('{max_date}') - interval '7' days)
        ) 
        WHERE rn = 1
    """)
    
    print(f"Loaded {risk_df.count()} records from features_risk_v1")
    # risk_df.show(5, truncate=False)
    
    # Filter for feature_ids in risk_weightage
    feature_ids = list(risk_weightage.keys())
    risk_df = risk_df.filter(F.col("feature_id").isin(feature_ids))
    
    print(f"After filtering by feature_ids: {risk_df.count()} records")
    
    # Calculate total sum of weights
    total_sum = sum(risk_weightage.values())
    print(f"Total weight sum: {total_sum}")
    
    # Create a mapping expression for weights
    weight_mapping = F.create_map([F.lit(x) for pair in risk_weightage.items() for x in pair])
    
    # Add weight column and calculate weighted/normalized risk
    risk_df = risk_df.withColumn("weight", weight_mapping[F.col("feature_id")]) \
        .withColumn("weighted_risk_value", F.col("feature_value") * F.col("weight")) \
        .withColumn("normalized_risk_value", F.col("weighted_risk_value") / F.lit(total_sum))
    
    # Aggregate by entity_id
    summary_df = risk_df.groupBy("entity_id") \
        .agg(F.sum("normalized_risk_value").alias("risk_value")) \
        .orderBy(F.col("risk_value").desc())
    
    # print(f"Summary DataFrame row count: {summary_df.count()}")
    # summary_df.show(10, truncate=False)
    
    return summary_df


def max_scoring(
    spark: SparkSession,
    max_date: str = None,
    risk_weightage: dict = None
):
    print(f"Risk weightage: {risk_weightage}")
    
    if max_date is None:
        max_date = dt.datetime.now().strftime('%Y-%m-%d')
    
    if risk_weightage is None or len(risk_weightage) == 0:
        raise ValueError("risk_weightage dictionary cannot be empty")
    print(max_date)
    
    risk_df = spark.sql(f"""
        SELECT * FROM (
            SELECT 
                entity_id, 
                feature_id, 
                feature_name, 
                feature_value,
                ROW_NUMBER() OVER (
                    PARTITION BY entity_id, feature_id 
                    ORDER BY timestamp DESC
                ) AS rn 
            FROM strot.operator360.features_risk_v1
            WHERE date(timestamp) = DATE('{max_date}')
            and timestamp>= date(date('{max_date}') - interval '7' days)
        ) 
        WHERE rn = 1
    """)

    
    print(f"Loaded {risk_df.count()} records from features_risk_v1")
    # risk_df.show(5, truncate=False)
    
    # Filter for feature_ids in risk_weightage
    feature_ids = list(risk_weightage.keys())
    print(feature_ids)
    print(feature_ids)
    risk_df = risk_df.filter(F.col("feature_id").isin(feature_ids))
    print(risk_df.show())
    print(f"After filtering by feature_ids: {risk_df.count()} records")

    risk_df= risk_df.groupby("entity_id") \
            .agg(F.max("feature_value").alias("risk_value"))
    
    # risk_df.show(10, truncate=False)

    return risk_df
    









