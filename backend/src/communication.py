import time
import json
import pandas as pd
import os
import configparser

from kafka import KafkaConsumer, KafkaProducer
from src.db import save_to_db


def _get_server_info():
    """
    Retrieves the Kafka bootstrap servers information from the configuration file.
    This function reads the 'config.ini' file using the ConfigParser module and
    accesses the 'bootstrap_servers' setting under the 'Kafka' section.
    Returns:
        str: The Kafka bootstrap servers as specified in the configuration file.
    """

    # Create a ConfigParser instance
    config = configparser.ConfigParser()

    # Read the config.ini file
    config.read("config.ini")

    # Access Kafka settings
    return config["Kafka"]["bootstrap_servers"]


def make_producers_info(root: str = "../data/"):
    """
    Generates a list of tuples containing information about renewable energy producers,
    as well as synthetic load and market price data.
    Args:
        root (str): The root directory where the data files are located. Defaults to "../data/".
    Returns:
        list: A list of tuples, each containing:
            - topic (str): The topic name for the producer or data type.
            - source_id (str or None): The source ID for the producer, or None for load and market data.
            - data (pd.DataFrame): The data read from the corresponding CSV file.
    """

    renewable_sources = [
        file
        for file in os.listdir(root)
        if file.split("_")[0].isnumeric() and "weather" not in file
    ]

    producers_info = [
        (
            source.split("_")[1] + "-topic",  # topic
            source.split("_")[0],  # source_id
            pd.read_csv(root + source, index_col=0),  # data
        )
        for source in renewable_sources
    ]

    # for load and price
    producers_info.extend(
        [
            (
                "load-topic",
                None,
                pd.read_csv(root + "synthetic_load_data.csv", index_col=0),
            ),
            (
                "market-topic",
                None,
                pd.read_csv(root + "synthetic_market_price.csv", index_col=0),
            ),
        ]
    )

    return producers_info


def kafka_produce(producer_info: tuple):
    """
    Produces messages to a Kafka topic.
    Args:
        producer_info (tuple): A tuple containing the topic name (str), source ID (str),
                               and a DataFrame (pandas.DataFrame) with the data to be sent.
    The DataFrame should have a datetime index and a single column of values. Each row in the
    DataFrame will be sent as a separate message to the specified Kafka topic.
    The function serializes the message as JSON and sends it to the Kafka topic with a delay
    of 5 seconds between each message.
    Example:
        producer_info = ("my_topic", "source_1", df)
        kafka_produce(producer_info)
    """

    topic, source_id, df = producer_info

    producer = KafkaProducer(
        bootstrap_servers=_get_server_info(),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    for _, row in df.iterrows():
        message = {"source_id": source_id, "timestamp": row.name, "data": row.values[0]}
        producer.send(topic, value=message)
        print(
            f"Message from {source_id} at {row.name} sent to topic {topic} with value {row.values[0]}"
        )
        time.sleep(1)


def kafka_consume_centralized():
    """
    Consumes messages from multiple Kafka topics and processes them.
    This function connects to a Kafka cluster, subscribes to the specified topics,
    and processes incoming messages. Each message is deserialized from JSON format,
    and relevant details such as source ID, timestamp, and data are extracted.
    The extracted information is then saved to a database.
    Topics:
        - "solar-topic"
        - "wind-topic"
        - "load-topic"
        - "market-topic"
    Kafka Consumer Configuration:
        - bootstrap_servers: Obtained from _get_server_info()
        - auto_offset_reset: "earliest"
        - group_id: "my-group"
        - value_deserializer: JSON deserialization
    Message Processing:
        - Extracts topic, source_id, timestamp, and data from each message
        - Converts timestamp to a pandas datetime object
        - Saves the extracted information to a database using save_to_db()
    Prints:
        - A message indicating the receipt of a message, including the topic, source_id, and timestamp
    Note:
        - Assumes that the message value contains a "data" field holding the value(s) to be saved.
    """

    consumer = KafkaConsumer(
        "solar-topic",
        "wind-topic",
        "load-topic",
        "market-topic",
        bootstrap_servers=_get_server_info(),
        auto_offset_reset="earliest",
        group_id="my-group",
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
    )

    for msg in consumer:
        topic = msg.topic

        # Extract message details
        message = msg.value
        source_id = message.get("source_id")
        timestamp = message.get("timestamp")
        value = message.get("data")  # Assuming 'data' holds the value(s)

        print(f"Received {topic} message from {source_id} at {timestamp}")

        time_obj = pd.to_datetime(timestamp)

        save_to_db(topic, time_obj, source_id, value)
