import findspark
findspark.init()
from pyspark.sql import functions as F, Window
from pyspark.sql import SparkSession
import logging
import pandas as pd
from trino.dbapi import connect
import datetime as dt
logger = logging.getLogger(__name__)

def get_spark(job_name: str):
    spark = SparkSession.builder \
        .appName("opt360-instance-scoring") \
        .remote("sc://spark-connect-service.strot-spark.svc.cluster.local:15002") \
        .config("spark.sql.legacy.mysql.bitArrayMapping.enabled","true") \
        .config("spark.default.parallelism","800") \
        .config("spark.sql.shuffle.partitions", "800") \
        .getOrCreate()
    return spark

def multiple_col_to_one(
    spark: SparkSession,
    fraud_table: str,
    feature_id,
    period_in_days: float = 1,
    agg_method: str = None,
    weights: map = None,
    **kwargs
):
    print(period_in_days, type(period_in_days))
    print(agg_method, feature_id)
    
    # 1. Type Normalization & Early Validation

    if agg_method==None:
        period_in_days = 1
    agg_method_upper = agg_method.upper() if agg_method else 'SUM'
    
    if agg_method_upper == 'WEIGHTED_AVERAGE' and weights is None:
        raise ValueError("Weights mapping must be provided when agg_method is 'weighted_average'")
    
    # Convert string to a single-element list so it uses unified aggregation paths
    if isinstance(feature_id, str):
        feature_ids = [feature_id]
    elif isinstance(feature_id, list):
        feature_ids = feature_id
    else:
        raise TypeError("feature_id must be either a string or a list of strings")
        
    # Cast period_in_days safely to integer for date sub
    prev_date = F.date_sub(F.current_date(), int(float(period_in_days)))
    print("Lookback limit date:", prev_date)
    
    # 2. Extract Data & Apply Time Frame Filters once
    df_base = spark.table(fraud_table) \
        .withColumn("entity_id", F.col("entity_id").cast("string")) \
        .withColumn("feature_value", F.col("feature_value").cast("double")) \
        .filter(F.col("feature_id").isin(feature_ids)) \
        .filter(F.to_date(F.col("timestamp")) >= prev_date)

    # 3. Time Series Consolidation (Intra-Feature Aggregation)
    # Dynamically select how multiple rows of the SAME feature id are handled over time
    if agg_method_upper == 'MAX':
        pivot_agg = F.max("feature_value")
    elif agg_method_upper == 'MIN':
        pivot_agg = F.min("feature_value")
    elif agg_method_upper == 'AVERAGE':
        pivot_agg = F.avg("feature_value")
    else:
        pivot_agg = F.sum("feature_value")  # Default to sum for SUM and WEIGHTED_AVERAGE

    # Reshape the table via pivot to create dedicated columns per feature
    df_pivot = df_base.groupBy("entity_id").pivot("feature_id", feature_ids).agg(
        F.coalesce(pivot_agg, F.lit(0.0))
    )

    # Reference column markers safely
    incident_cols = [F.col(f"`{fid}`") for fid in feature_ids]

    # 4. Cross-Column Consolidation (Inter-Feature Aggregation)
    from functools import reduce
    
    if agg_method_upper == 'SUM':
        safe_cols = [F.coalesce(col, F.lit(0.0)) for col in incident_cols]
        df_combined = df_pivot.withColumn("final_value", reduce(lambda a, b: a + b, safe_cols))
        
    elif agg_method_upper == 'AVERAGE':
        # 1. Convert nulls to 0.0 for a safe sum
        safe_cols = [F.coalesce(col, F.lit(0.0)) for col in incident_cols]
        total_sum = reduce(lambda a, b: a + b, safe_cols)
        
        # 2. Count how many columns actually have values (1 if present, 0 if null)
        present_counts = [F.when(col.isNotNull(), 1).otherwise(0) for col in incident_cols]
        total_present = reduce(lambda a, b: a + b, present_counts)
        
        # 3. Divide sum by the actual count (use F.when to prevent division by zero)
        df_combined = df_pivot.withColumn(
            "final_value", 
            F.when(total_present > 0, total_sum / total_present).otherwise(F.lit(0.0))
        )
        
    elif agg_method_upper == 'MAX':
        df_combined = df_pivot.withColumn("final_value", F.greatest(*incident_cols))
        
    elif agg_method_upper == 'MIN':
        df_combined = df_pivot.withColumn("final_value", F.least(*incident_cols))
        
    elif agg_method_upper == 'WEIGHTED_AVERAGE':
        weighted_cols = [
            F.coalesce(F.col(f"`{fid}`"), F.lit(0.0)) * F.lit(float(weights.get(fid, 0.0))) 
            for fid in feature_ids
        ]
        weighted_sum = reduce(lambda a, b: a + b, weighted_cols)
        weight_total = sum(float(weights.get(fid, 0.0)) for fid in feature_ids)
        
        if weight_total == 0:
            raise ZeroDivisionError("The total sum of provided weights for the target features cannot be zero.")
            
        df_combined = df_pivot.withColumn("final_value", weighted_sum / F.lit(weight_total))
        df_combined.select(['entity_id', 'final_value']).show(30)
        # df_combined.select(['entity_id', 'final_value']).write.csv('./mfc_data.csv')
        
    else:
        raise NotImplementedError(f"Unsupported aggregation method: {agg_method}")

    return df_combined.select(['entity_id', 'final_value'])



def rank_scoring(
    spark: SparkSession,
    fraud_table: str,
    feature_id,
    range_start: float = 0.0,
    range_end: float = 1.0,
    is_inverse: bool = False,
    apply_threshold: bool = False,
    threshold: float = None,
    require_aggregation: bool = False,
    method: str = None,
    weights: map = None,
    **kwargs
):
    # 1. Input Sanitization
    if feature_id is None or fraud_table is None:
        raise RuntimeError('feature_id and fraud_table must be defined')
        
    # Standardize incoming string/boolean types
    req_agg = str(require_aggregation).strip().lower() == 'true'

    if req_agg:
        prev_date = F.date_sub(F.current_date(), 30)
    else:
        prev_date = F.date_sub(F.current_date(), 1)

    # 2. Extract and Align Dataframes
    # 2. Extract and Align Dataframes Dynamically
    if method == 'weighted_average' and not isinstance(feature_id, str) and weights is not None:
        print("feature_id", feature_id)
        # Weighted average tracks a custom 30-day structural period
        df = multiple_col_to_one(spark, fraud_table, feature_id, period_in_days=30, agg_method='weighted_average', weights=weights)
        print(df.count())
        df_latest = df.withColumnRenamed("final_value", "feature_value")
    else:
        # Target only rows matching our specific feature_id
        df_base = spark.table(fraud_table).filter(F.col("feature_id") == feature_id)
        
        # Guard: Check if the table yields any records for this feature_id
        if df_base.rdd.isEmpty():
            logger.warning(f"No records discovered across the cluster for feature_id: {feature_id}")
            return spark.createDataFrame([], schema="entity_id string, score double")

        if not req_agg:
            # DYNAMIC FIX: Find the most recent date this feature actually existed
            max_date = df_base.select(F.max(F.to_date(F.col("timestamp")))).collect()[0][0]
            
            if max_date is None:
                logger.warning(f"Feature ID {feature_id} exists but contains no valid timestamps.")
                return spark.createDataFrame([], schema="entity_id string, score double")
                
            # Filter specifically for that exact state snapshot day
            df_latest = df_base.filter(F.to_date(F.col("timestamp")) == F.lit(max_date)) \
                               .select('entity_id', F.col('feature_value').cast('double').alias('feature_value'))
        else:
            # Standard aggregations fallback to the relative 30 day window lookback
            df_filt = df_base.filter(F.to_date(F.col("timestamp")) > F.lit(prev_date))
            df_latest = df_filt.groupBy('entity_id').agg(F.sum('feature_value').cast('double').alias('feature_value'))

    
    # 3. Apply Threshold Logic Safely
    if apply_threshold and threshold is not None:
        if is_inverse:
            # High values are bad. Clip worst outliers (values above threshold) down to threshold
            df_latest = df_latest.withColumn(
                "adjusted_value", 
                F.when(F.col("feature_value") >= threshold, F.lit(threshold)).otherwise(F.col("feature_value"))
            )
        else:
            # High values are good. Clip worst outliers (values below threshold) up to threshold
            df_latest = df_latest.withColumn(
                "adjusted_value", 
                F.when(F.col("feature_value") <= threshold, F.lit(threshold)).otherwise(F.col("feature_value"))
            )
    else:
        df_latest = df_latest.withColumn("adjusted_value", F.col("feature_value"))

    # 4. Handle Windowing Safely
    total_count = df_latest.count()
    if total_count == 0:
        return df_latest.select('entity_id').withColumn("score", F.lit(range_start))

    # Note: Global ranking requires a single partition sequence. 
    # Ensure driver/executors have adequate memory allocated for this step.
    if is_inverse:
        w = Window.orderBy(F.col("adjusted_value").asc())
    else:
        w = Window.orderBy(F.col("adjusted_value").desc())
        
    df_ranked = df_latest.withColumn("rank", F.rank().over(w))
    
    # 5. Calculate Score safely
    if total_count <= 1:
        df_final = df_ranked.withColumn("score", F.lit(float(range_end)))
    else:
        max_rank = df_ranked.agg(F.max("rank")).collect()[0][0]
        df_final = df_ranked.withColumn(
            "score",
            F.lit(float(range_end)) - ((F.col("rank") - 1) / (max_rank - 1)) * (float(range_end) - float(range_start))
        )
        
    print(total_count)

    df_final.select('entity_id', 'score').orderBy(F.col('score').asc()).show(20)

    df_final.select('entity_id', 'score').orderBy(F.col('score').desc()).show(20)
    df_final_capped = df_final.withColumn(
        "score",
        F.greatest(F.lit(range_start), F.least(F.col("score"), F.lit(range_end)))
    )
    
    return df_final_capped.select('entity_id', 'score')

def winsorized_zscoring(
    spark: SparkSession,
    fraud_table: str,
    feature_id,
    is_multiple_col: bool= False,
    period_in_days:float= 30.0,
    aggregation_method: str= None,
    weights: map=None,
    winsorize_percentile: float=0.99,
    sigmoid_scale: float=0.5,
    **kwargs
):
    value_col='final_value'
    df_combined= multiple_col_to_one(spark=spark,
                                    fraud_table=fraud_table,
                                    feature_id=feature_id,
                                    period_in_days=period_in_days,
                                    agg_method=aggregation_method if is_multiple_col else None,
                                    weights= weights if is_multiple_col else None
                                )
    print('df_combined')
    print(df_combined.show())
    
    
    stats = df_combined.select(
        F.mean(value_col).alias("mean_val"),
        F.stddev_pop(value_col).alias("stddev_val"),
        F.min(value_col).alias("min_val"),
        F.max(value_col).alias("max_val"),
        F.expr(f"percentile_approx({value_col}, {winsorize_percentile})").alias("percentile_threshold")
    ).collect()[0]
    
    mean_val = stats["mean_val"]
    stddev_val = stats["stddev_val"] if stats["stddev_val"] and stats["stddev_val"] > 0 else 1.0
    percentile_threshold = stats["percentile_threshold"]
    min_val = stats["min_val"]
    max_val = stats["max_val"]
    
    
    df_capped = df_combined.withColumn(
        f"{value_col}_capped",
        F.when(F.col(value_col) > percentile_threshold, percentile_threshold)
         .otherwise(F.col(value_col))
    )
    
    df_capped = df_capped.withColumn(
        "is_extreme_outlier",
        F.when(F.col(value_col) > percentile_threshold, True).otherwise(False)
    )
    df_with_zscore = df_capped.withColumn(
        "zscore",
        (F.col(f"{value_col}_capped") - F.lit(mean_val)) / F.lit(stddev_val)
    )
    
    df_normalized = df_with_zscore.withColumn(
        "score_sigmoid",
        F.lit(1.0) / (F.lit(1.0) + F.exp(-F.lit(sigmoid_scale) * F.col("zscore")))
    )
    
    df_normalized = df_normalized.withColumn(
        "score",
        F.when(F.col("is_extreme_outlier") == True, 0.99)
         .otherwise(F.col("score_sigmoid"))
    )
    
    df_normalized = df_normalized.drop(f"{value_col}_capped", "score_sigmoid")
    
    df_normalized = df_normalized.withColumn(
        "score",
        F.when(F.col("score") < 0, 0.0)
         .when(F.col("score") > 1, 1.0)
         .otherwise(F.col("score"))
    )
    
    return df_normalized



def zscore(
    spark: SparkSession,
    fraud_table: str,
    feature_id,
    is_multiple_col: bool = False,
    period_in_days: float = 30.0,
    aggregation_method: str = None,
    weights: map = None,
    require_aggregation=False,
    range_start: float = 0.0,  # Added for ecosystem parity
    range_end: float = 1.0,    # Added for ecosystem parity
    **kwargs
):
    value_col = 'final_value'
    
    # 1. Gather aggregated dataframe

    print("agg_method:",aggregation_method)
    if require_aggregation=='True' or require_aggregation==True:
    
        df_combined = multiple_col_to_one(
            spark=spark,
            fraud_table=fraud_table,
            feature_id=feature_id,
            period_in_days=period_in_days,
            agg_method=aggregation_method if is_multiple_col else "SUM",
            weights=weights if is_multiple_col else None
        )
    else:
        df_combined = multiple_col_to_one(
            spark=spark,
            fraud_table=fraud_table,
            feature_id=feature_id,
            period_in_days=period_in_days,
            agg_method= None,
            weights= None
        )

    print(df_combined.count())
    print(df_combined.select(F.count_distinct("entity_id")).show())

    
    # Check if data frame is empty to prevent .collect()[0] IndexError
    if df_combined.rdd.isEmpty():
        logger.warning("No data found for the given feature constraints.")
        return df_combined.withColumn("score", F.lit(range_start))

    print('df_combined')
    df_combined.show()
    
    # 2. Collect statistical definitions safely
    stats = df_combined.select(
        F.mean(value_col).alias("mean_val"),
        F.stddev_pop(value_col).alias("stddev_val")
    ).collect()[0]
    
    mean_val = stats["mean_val"] if stats["mean_val"] is not None else 0.0
    
    # Critical Handle: Check for both Null and Zero standard deviations
    stddev_val = stats["stddev_val"]
    if stddev_val is None or stddev_val == 0.0:
        stddev_val = 1.0 
    
    # 3. Calculate regular Z-score (Using df_combined directly instead of missing df_capped)
    df_with_zscore = df_combined.withColumn(
        "zscore",
        (F.col(value_col) - F.lit(mean_val)) / F.lit(stddev_val)
    )
    
    # 4. Clean and scale if needed, or simply map it to a final 'score' column
    # For regular zscore, we map 'zscore' directly to 'score' to maintain compatibility.
    df_final = df_with_zscore.withColumn("score", F.col("zscore")).drop("zscore")
    
    return df_final




def log_based_scoring(
    spark: SparkSession,
    fraud_table: str ,
    feature_id: str,
    range_start: float = 0,
    range_end: float = 1,
    period_in_days: int = 30,
    threshold: int = 0,
    **kwargs
):
    cutoff_date = F.date_sub(F.current_date(), int(period_in_days))
    
    df_feature = spark.table(fraud_table).filter(F.col("feature_id") == feature_id)
    df_filtered = df_feature.filter(F.to_date(F.col("timestamp")) >= cutoff_date)
    
    df_agg = df_filtered.groupBy("entity_id").agg(
        F.sum("feature_value").alias("feature_val")
    )
    
    df_agg = df_agg.filter(F.col("feature_val") > threshold)
    
    max_val_row = df_agg.select(F.max("feature_val").alias("max_val")).collect()[0]
    global_max = max_val_row["max_val"] if max_val_row["max_val"] is not None else 1.0
    
    df_scored = df_agg.withColumn(
        "score",
        F.lit(range_start) + (F.lit(range_end) - F.lit(range_start)) * 
        (F.log1p(F.col("feature_val")) / F.log1p(F.lit(global_max)))
    )
    df_final_capped = df_scored.withColumn(
        "score",
        F.greatest(F.lit(range_start), F.least(F.col("score"), F.lit(range_end)))
    )

    return df_final_capped.select('entity_id', 'score')
    
    # return df_scored

def wilson_fraud_scoring(
    spark: SparkSession,
    fraud_table: str,
    feature_id_numerator: str,   # e.g., 'auth_failure_txn_count'
    feature_id_denominator: str, # e.g., 'total_txn_count'
    range_start: float = 0,
    range_end: float = 1,
    period_in_days: int = 30,
    **kwargs
):
    cutoff_date = F.date_sub(F.current_date(), int(period_in_days))
    
    df_num = (spark.table(fraud_table)
              .filter(F.col("feature_id") == feature_id_numerator)
              .filter(F.to_date(F.col("timestamp")) >= cutoff_date)
              .groupBy("entity_id").agg(F.sum("feature_value").alias("ups")))
    print("numerator")
    print(df_num.show())
    
    df_den = (spark.table(fraud_table)
              .filter(F.col("feature_id") == feature_id_denominator)
              .filter(F.to_date(F.col("timestamp")) >= cutoff_date)
              .groupBy("entity_id").agg(F.sum("feature_value").alias("n")))
    print("denominator")
    print(df_den.show())
    
    df_joined = df_num.join(df_den, on="entity_id", how="inner").filter(F.col("n") > 0)
    z = 1.96 
    df_scored = df_joined.withColumn("p", F.col("ups") / F.col("n"))
    
    # Calculate the lower bound of the Wilson Score Interval
    df_scored = df_scored.withColumn(
        "wilson_lower_bound",
        (F.col("p") + (z**2 / (2 * F.col("n"))) - 
         z * F.sqrt((F.col("p") * (1 - F.col("p")) / F.col("n")) + (z**2 / (4 * F.col("n")**2)))) / 
        (1 + (z**2 / F.col("n")))
    )

    # 4. Final Scaling
    df_final = df_scored.withColumn(
        "score",
        F.lit(range_start) + (F.lit(range_end) - F.lit(range_start)) * F.col("wilson_lower_bound")
    ).select("entity_id", "ups", "n", "p", "score")

    df_final_capped = df_final.withColumn(
        "score",
        F.greatest(F.lit(range_start), F.least(F.col("score"), F.lit(range_end)))
    )
    
    return df_final_capped.select('entity_id', 'score')
    

def exponential_decay_scoring(
    spark: SparkSession,
    fraud_table: str ,
    feature_id: str ,
    period_in_days: float,
    range_start: float = 0,
    range_end: float = 1,
    time_unit: str='days',
    decay_rate: float=0.1,
    **kwargs
):
    df = spark.table(fraud_table).filter(F.col("feature_id") == feature_id)
    cutoff_date = F.date_sub(F.current_date(), int(period_in_days))

    df = df.filter(
        (F.to_date(F.col("timestamp")) >= F.lit(cutoff_date).cast('date')) 
    )
    
    df = df.withColumn(
        'timestamp',
        F.when(F.col('timestamp').cast('string').isNotNull(), 
               F.to_timestamp(F.col('timestamp')))
        .otherwise(F.col('timestamp'))
    )

    df = df.withColumn('date', F.to_date(F.col('timestamp')))
    
    df = df.groupBy('entity_id', 'date').agg(
        F.max('feature_value').alias('feature_value'),
        F.max('timestamp').alias('timestamp')  # Use the latest timestamp of that day
    )    
    
    current_time = df.agg(F.max('timestamp')).collect()[0][0]
    
    if time_unit == 'days':
        time_divisor = 86400 

    print(df.show())
    
    df = df.withColumn(
        'time_elapsed',
        (F.unix_timestamp(F.lit(current_time)) - F.unix_timestamp(F.col('timestamp'))) / time_divisor
    ).withColumn(
        'decay_weight',
        F.exp(-decay_rate * F.col('time_elapsed'))
    ).withColumn(
        'weighted_score',
        F.col('feature_value') * F.col('decay_weight')
    )
    
    risk_scores = df.groupBy('entity_id').agg(
        F.sum('weighted_score').alias('raw_risk_score'),
        F.count('feature_value').alias('event_count'),
        F.min('time_elapsed').alias('days_since_last_event')
    )
    
    min_max = risk_scores.agg(
        F.min('raw_risk_score').alias('min_score'),
        F.max('raw_risk_score').alias('max_score')
    ).collect()[0]
    
    min_score = min_max['min_score']
    max_score = min_max['max_score']
    
    if max_score > min_score:
        # Normalize risk score
        risk_scores = risk_scores.withColumn(
            'score',
            range_start + ((F.col('raw_risk_score') - min_score) / (max_score - min_score))* (range_end-range_start)
        )
        
        # Calculate rank using window function
        total_opt_ids = risk_scores.count()
        w = Window.orderBy(F.col('score').asc())
        
        risk_scores = risk_scores.withColumn(
            'rank',
            F.row_number().over(w)
        ).withColumn(
            'rank_score',
            (F.col('rank') / F.lit(total_opt_ids))
        )
    else:
        risk_scores = risk_scores.withColumn('risk_score', F.lit(0.5))
        risk_scores = risk_scores.withColumn('rank', F.lit(1))
        risk_scores = risk_scores.withColumn('rank_score', F.lit(0.5))
        
    
    risk_scores = risk_scores.select(
        'entity_id', 'score', 'raw_risk_score', 'rank', 'rank_score',
        'event_count', 'days_since_last_event'
    )

    df_final_capped = risk_scores.withColumn(
        "score",
        F.greatest(F.lit(range_start), F.least(F.col("score"), F.lit(range_end)))
    )
    
    return df_final_capped.select('entity_id', 'score')
    
    # return risk_scores

    
    
    