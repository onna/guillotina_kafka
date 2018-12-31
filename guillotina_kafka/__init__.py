from guillotina import configure
from .interfaces import *  # noqa
from .utilities import *  # noqa



app_settings = {
    "commands": {
        "start-producer": "guillotina_kafka.commands.kafka_producer.SendMessageCommand",
        "start-consumer": "guillotina_kafka.commands.kafka_consumer.StartConsumerCommand"
    },   
    "kafka": {
        "host": "localhost",
        "port": 9092
    }
}


def includeme(root):
    """
    custom application initialization here
    """
    configure.scan('guillotina_kafka.api')
    configure.scan('guillotina_kafka.utilities')
    configure.scan('guillotina_kafka.install')
