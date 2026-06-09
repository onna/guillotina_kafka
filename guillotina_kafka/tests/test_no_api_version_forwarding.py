import asyncio
from argparse import Namespace
from unittest.mock import MagicMock, patch

import pytest

from guillotina import app_settings
from guillotina_kafka.commands import kafka_consumer
from guillotina_kafka.commands import kafka_multi_consumer
from guillotina_kafka.commands import kafka_producer


class _Worker:
    connection_settings = {}

    async def __call__(self, *args, **kwargs):
        return


def _kafka_settings():
    return {
        "brokers": ["localhost:9092"],
        "consumer": {
            "topics": [],
            "workers": [
                {
                    "name": "test-worker",
                    "path": f"{__name__}._Worker",
                    "topics": ["test-topic"],
                }
            ],
        },
    }


def _assert_not_forwarded(fake):
    assert fake.call_args_list, "expected an aiokafka constructor to be called"
    for call in fake.call_args_list:
        assert "api_version" not in call.kwargs, (
            f"api_version must not be forwarded; got {call.kwargs}"
        )


@pytest.mark.asyncio
async def test_start_consumers_does_not_forward_api_version(monkeypatch):
    monkeypatch.setitem(app_settings, "kafka", _kafka_settings())

    command = kafka_multi_consumer.StartConsumersCommand()
    command.loop = asyncio.get_running_loop()
    arguments = Namespace(consumer_worker=["test-worker"], api_version="auto")

    fake = MagicMock()
    with patch.object(
        kafka_multi_consumer, "AIOKafkaConsumer", fake
    ), patch.object(
        kafka_multi_consumer.StartConsumersCommand,
        "run_consumer",
        lambda self, *a, **k: None,
    ), patch.object(
        kafka_multi_consumer.asyncio, "create_task", lambda *a, **k: None
    ):
        await command._run(arguments, None)

    _assert_not_forwarded(fake)


def test_start_consumer_does_not_forward_api_version(monkeypatch):
    monkeypatch.setitem(app_settings, "kafka", _kafka_settings())

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

    fake = MagicMock()
    with patch.object(
        kafka_consumer, "StreamConsumer", fake
    ), patch.object(
        kafka_consumer, "get_adapter", lambda consumer, *a, **k: consumer
    ):
        command.get_consumer(arguments)

    _assert_not_forwarded(fake)


class _RecordingProducer:
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
async def test_send_message_does_not_forward_api_version():
    producer = _RecordingProducer()
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
        f"api_version must not be forwarded to producer.setup; got {producer.setup_kwargs}"
    )
