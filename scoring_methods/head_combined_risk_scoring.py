import boto3
import yaml
import subprocess
import sys
import logging

logger = logging.getLogger(__name__)
try:
    if len(sys.argv)>=2:
        instance_feature_name = sys.argv[1]
        instance_feature_version = sys.argv[2]
        logger.info(f"CLI override: feature_name imported successfully in head_combined_scoring.py {instance_feature_name}")
        logger.info(f"CLI override: feature_version imported successfully in head_combined_scoring.py {instance_feature_version}")
except Exception as e:
    logger.warning(f"CLI args parsing failed: f{sys.argv}")

    

spark_submit_command = f"""
            /opt/spark/bin/spark-submit \
            --master k8s://https://10.10.102.220:443 \
            --deploy-mode cluster \
            --name zzz-{instance_feature_name} \
            --class org.apache.spark.deploy.SparkSubmit \
            --conf spark.kubernetes.container.image=harbor-registry-prod.uidai.gov.in/data-platform/pyspark:3.4.2_3 \
            --conf spark.kubernetes.namespace=strot-spark \
            --conf spark.serializer=org.apache.spark.serializer.KryoSerializer \
            --conf spark.kubernetes.executor.pod.affinity='{{"nodeAffinity": {{"requiredDuringSchedulingIgnoredDuringExecution": {{"nodeSelectorTerms": [{{"matchExpressions": [{{"key": "env", "operator": "In", "values": ["strot"]}}]}}]}}}}}}' \
            --conf spark.kubernetes.driver.pod.affinity='{{"nodeAffinity": {{"requiredDuringSchedulingIgnoredDuringExecution": {{"nodeSelectorTerms": [{{"matchExpressions": [{{"key": "env", "operator": "In", "values": ["strot"]}}]}}]}}}}}}' \
            --conf spark.kubernetes.executor.pod.tolerations='[{{"key": "env", "operator": "Equal", "value": "strot", "effect": "NoSchedule"}}]' \
            --conf spark.kubernetes.driver.pod.tolerations='[{{"key": "env", "operator": "Equal", "value": "strot", "effect": "NoSchedule"}}]' \
            --conf spark.driver.cores=4 \
            --conf spark.executor.cores=4 \
            --conf spark.executor.instances=5 \
            --conf spark.driver.memory=8g \
            --conf spark.executor.memory=64g \
            --conf spark.driver.maxResultSize=16g \
            --conf spark.kubernetes.driver.limit.cores=4 \
            --conf spark.kubernetes.executor.limit.cores=4 \
            --conf spark.kubernetes.driver.request.cores=4 \
            --conf spark.kubernetes.executor.request.cores=4 \
            --conf spark.driver.memoryOverhead=32g \
            --conf spark.executor.memoryOverhead=32g \
            --conf spark.executor.extraJavaOptions=-XX:+UseG1GC \
            --conf spark.hadoop.fs.s3a.aws.credentials.provider=org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider \
            --conf spark.kubernetes.driver.ownPersistentVolumeClaim=true \
            --conf spark.kubernetes.driver.reusePersistentVolumeClaim=true \
            --conf spark.kubernetes.local.dirs.tmpfs=true \
            --conf spark.shuffle.sort.io.plugin.class=org.apache.spark.shuffle.KubernetesLocalDiskShuffleDataIO \
            --conf spark.kubernetes.executor.volumes.persistentVolumeClaim.spark-local-dir-1.options.claimName=OnDemand \
            --conf spark.kubernetes.executor.volumes.persistentVolumeClaim.spark-local-dir-1.options.storageClass=gpu-ceph-ext4 \
            --conf spark.kubernetes.executor.volumes.persistentVolumeClaim.spark-local-dir-1.options.sizeLimit=1Gi \
            --conf spark.kubernetes.executor.volumes.persistentVolumeClaim.spark-local-dir-1.mount.path=/data \
            --conf spark.kubernetes.executor.volumes.persistentVolumeClaim.spark-local-dir-1.mount.readOnly=false \
            --conf spark.local.dir=/data/temp \
            --conf spark.sql.warehouse.dir=/data/sqlwarehouse \
            --conf hadoop.tmp.dir=/data/hadoop_temp \
            --conf spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem \
            --conf spark.hadoop.fs.s3a.path.style.access=true \
            --conf spark.hadoop.fs.s3a.secret.key=XKlE3EeEQ7MHsvz2O9AXuDEJJDyTFhhCcxSnxtk4 \
            --conf spark.hadoop.fs.s3a.access.key=9S0KLIQO7T2XCNGH4P4A \
            --conf spark.hadoop.fs.s3a.endpoint=http://10.10.103.12:425 \
            --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
            --conf spark.sql.catalog.strot=org.apache.iceberg.spark.SparkCatalog \
            --conf spark.sql.catalog.strot.type=hive \
            --conf spark.sql.catalog.strot.uri=thrift://10.10.116.77:9083 \
            --conf spark.sql.catalog.flink_stream=org.apache.iceberg.spark.SparkCatalog \
            --conf spark.sql.catalog.flink_stream.type=hive \
            --conf spark.sql.catalog.flink_stream.uri=thrift://10.10.118.15:9083 \
            --conf spark.kubernetes.authenticate.driver.serviceAccountName=strot-service-account \
            --jars local:///opt/spark/jars/clickhouse-jdbc-0.6.3-all.jar,local:///opt/spark/jars/clickhouse-spark-runtime-3.4_2.12-0.8.1.jar,local:///opt/spark/jars/hadoop-aws-3.3.4.jar,local:///opt/spark/jars/iceberg-spark-runtime-3.4_2.12-1.5.2.jar,local:///opt/spark/jars/mysql-connector-java-8.0.30.jar \
            --py-files s3a://prd-bi-data-platform-uploads/sparkjobs/operator360/category_risk_scoring_combined/category_scoring_methods.py \
            s3a://prd-bi-data-platform-uploads/sparkjobs/operator360/category_risk_scoring_combined/category_main.py {instance_feature_name} {instance_feature_version}
"""


subprocess.run(spark_submit_command, shell=True, check=True)
            # s3a://prd-bi-data-platform-uploads/sparkjobs/operator360/category_risk_scoring_combined/scoring_methods.py \


