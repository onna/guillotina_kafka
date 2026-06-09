from guillotina.commands import Command
from guillotina_kafka.producer import SERIALIZER
from guillotina_kafka.utilities import get_kafka_producer

class SendMessageCommand(Command):

    description = 'Start Kafka producer'

    def get_parser(self):
        parser = super(SendMessageCommand, self).get_parser()
        parser.add_argument(
            '-i', '--interactive', action='store_true', default=False
        )
        parser.add_argument(
            '--serializer', type=str, default='bytes'
        )
        parser.add_argument(
            '--topic', type=str, help='Kafka topic to produce to.'
        )
        parser.add_argument(
            '--data', type=str, help='Data to send to the topic.'
        )
        parser.add_argument(
            '--api-version', type=str,
            default='auto', help='Kafka server api version.'
        )
        return parser

    async def send(self, arguments, settings):

        serializer = SERIALIZER.get(
            arguments.serializer, lambda data: data.encode('utf-8')
        )
        producer = get_kafka_producer()
        await producer.setup(
            bootstrap_servers=settings['kafka']['brokers'],
            value_serializer=serializer,
        )

        if arguments.interactive:
            while True:
                message = input("> ")
                if not message:
                    break
                result = await producer.send(arguments.topic, value=message)
                print(await result)
        else:
            result = await producer.send(arguments.topic, value=arguments.data)
            print(await result)

        await producer.stop()

    async def run(self, arguments, settings, app):
        await self.send(arguments, settings)
