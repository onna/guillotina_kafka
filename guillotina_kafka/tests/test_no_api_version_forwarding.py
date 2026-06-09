import asyncio
from argparse import Namespace
from unittest.mock import patch

import pytest

from guillotina import app_settings
from guillotina_kafka.commands import kafka_multi_consumer


class RecordingConsumer:
    instances = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        RecordingConsumer.instances.append(self)

    def subscribe(self, *args, **kwargs):
        pass


class _Worker:
    connection_settings = {}

    async def __call__(self, *args, **kwargs):
        return


class _App:
    def __init__(self):
        self.on_startup = []


@pytest.mark.asyncio
async def test_start_consumers_does_not_forward_api_version_to_aiokafka():
    app_settings["kafka"] = {
        "brokers": ["localhost:9092"],
        "consumer": {
            "topics": [],
            "workers": [
                {
                    "name": "test-worker",
                    "path": (
                        "guillotina_kafka.tests."
                        "test_no_api_version_forwarding._Worker"
                    ),
                    "topics": ["test-topic"],
                }
            ],
        },
    }
    RecordingConsumer.instances = []

    command = kafka_multi_consumer.StartConsumersCommand()
    command.loop = asyncio.get_running_loop()
    arguments = Namespace(consumer_worker=["test-worker"], api_version="auto")

    with patch.object(
        kafka_multi_consumer, "AIOKafkaConsumer", RecordingConsumer
    ), patch.object(
        kafka_multi_consumer.StartConsumersCommand,
        "run_consumer",
        lambda self, *a, **k: None,
    ), patch.object(
        kafka_multi_consumer.asyncio, "create_task", lambda *a, **k: None
    ):
        await command._run(arguments, _App())

    assert RecordingConsumer.instances, "expected an AIOKafkaConsumer to be constructed"
    for consumer in RecordingConsumer.instances:
        assert "api_version" not in consumer.kwargs, (
            "api_version must not be forwarded to AIOKafkaConsumer; "
            f"got {consumer.kwargs}"
        )


class RecordingSingleConsumer:
    instances = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        RecordingSingleConsumer.instances.append(self)


def test_start_consumer_does_not_forward_api_version_to_aiokafka():
    from guillotina_kafka.commands import kafka_consumer

    app_settings["kafka"] = {
        "brokers": ["localhost:9092"],
        "consumer": {
            "topics": [],
            "workers": [
                {
                    "name": "test-worker",
                    "path": (
                        "guillotina_kafka.tests."
                        "test_no_api_version_forwarding._Worker"
                    ),
                    "topics": ["test-topic"],
                }
            ],
        },
    }
    RecordingSingleConsumer.instances = []

    command = kafka_consumer.StartConsumerCommand()
    arguments = Namespace(
        consumer_type="stream",
        consumer_worker="test-worker",
        topics=None,
        regex_topic=None,
        consumer_group=None,
        api_version="auto",
        take=None,
        within=None,
    )

    with patch.object(
        kafka_consumer, "StreamConsumer", RecordingSingleConsumer
    ), patch.object(
        kafka_consumer, "get_adapter", lambda consumer, *a, **k: consumer
    ):
        command.get_consumer(arguments)

    assert RecordingSingleConsumer.instances, "expected a consumer to be constructed"
    for consumer in RecordingSingleConsumer.instances:
        assert "api_version" not in consumer.kwargs, (
            f"api_version must not be forwarded; got {consumer.kwargs}"
        )


class RecordingProducer:
    def __init__(self):
        self.setup_kwargs = None

    async def setup(self, **kwargs):
        self.setup_kwargs = kwargs

    async def send(self, topic, value=None):
        async def _result():
            return None

        return _result()

    async def stop(self):
        return None


@pytest.mark.asyncio
async def test_send_message_does_not_forward_api_version_to_aiokafka():
    from guillotina_kafka.commands import kafka_producer

    producer = RecordingProducer()
    command = kafka_producer.SendMessageCommand()
    arguments = Namespace(
        serializer="bytes",
        topic="test-topic",
        data="hello",
        interactive=False,
        api_version="auto",
    )
    settings = {"kafka": {"brokers": ["localhost:9092"]}}

    with patch.object(kafka_producer, "get_kafka_producer", lambda: producer):
        await command.send(arguments, settings)

    assert producer.setup_kwargs is not None, "producer.setup was not called"
    assert "api_version" not in producer.setup_kwargs, (
        "api_version must not be forwarded to producer.setup; "
        f"got {producer.setup_kwargs}"
    )
