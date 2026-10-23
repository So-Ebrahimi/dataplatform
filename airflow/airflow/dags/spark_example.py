
from datetime import datetime

from airflow import DAG
from airflow.providers.apache.spark.operators.spark_submit import (
    SparkSubmitOperator,
)

with DAG(
    dag_id="spark_example",
    description="Submit a PySpark job to the Docker Spark cluster",
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    tags=["spark"],
) as dag:

    run_spark_job = SparkSubmitOperator(
        task_id="run_spark_job",
        application="/opt/airflow/dags/spark_job.py",
        conn_id="spark_default",
        deploy_mode="client",
        verbose=True,
        conf={
            "spark.driver.host": "airflow-scheduler",
            "spark.driver.bindAddress": "0.0.0.0",
        },
    )
