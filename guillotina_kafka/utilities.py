from guillotina import configure
from guillotina import app_settings
from guillotina.component import get_utility
from guillotina_kafka.interfaces import IKafkaProducerUtility
from aiokafka import AIOKafkaProducer
import asyncio


@configure.utility(provides=IKafkaProducerUtility)
class KafkaProducerUtility:
    """This defines the singleton that will hold the connection to kafka
    and allows to send messages from it.
    """
    def __init__(self, loop=None):
        # Get kafka connection details from app settings
        self.host = app_settings['kafka']['host']
        self.port = app_settings['kafka']['port']
        self.serializer = lambda msg: msg.encode()
        self.max_request_size = 104_857_600
        self.loop = loop
        self._producer = None
        self._started = False

    @property
    def producer(self):
        """Gets or creates the connection to kafka"""
        if self._producer is None:
            self._producer = AIOKafkaProducer(
                loop=self.loop or asyncio.get_event_loop(),
                max_request_size=self.max_request_size,
                bootstrap_servers=f'{self.host}:{self.port}'
            )
        return self._producer

    @property
    def is_ready(self):
        """Returns whether aiokafka producer connection is ready"""
        if self._producer is None:
            return False
        return self._started

    async def start(self):
        """Starts the producer connection if not it's not ready already
        """
        await self.producer.start()
        self._started = True

    async def send(self, topic, data):
        """
        If topic not specified, will use class attribute
        """
        if not self.is_ready:
            await self.start()

        return await self.producer.send(topic, self.serializer(data))

    async def stop(self):
        await self.producer.stop()
        self._started = False


def get_kafka_producer(loop=None):
    kafka_producer = get_utility(IKafkaProducerUtility)
    # We only need to set the loop in pytest
    kafka_producer.loop = loop
    return kafka_producer