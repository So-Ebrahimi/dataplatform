
FROM apache/airflow:2.10.5-python3.11

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       openjdk-17-jre-headless curl ca-certificates tar \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV SPARK_HOME=/opt/spark
ENV PATH="${SPARK_HOME}/bin:${PATH}"

RUN curl -fL \
      https://archive.apache.org/dist/spark/spark-4.0.1/spark-4.0.1-bin-hadoop3.tgz \
      -o /tmp/spark.tgz \
    && mkdir -p /opt \
    && tar -xzf /tmp/spark.tgz -C /opt \
    && mv /opt/spark-4.0.1-bin-hadoop3 /opt/spark \
    && rm /tmp/spark.tgz \
    && chown -R airflow:root /opt/spark

USER airflow

RUN pip install \
    "apache-airflow-providers-apache-spark" \
    --constraint \
    "https://raw.githubusercontent.com/apache/airflow/constraints-2.10.5/constraints-3.11.txt"


RUN pip install \
    deltalake \
    pyarrow \
    pandas