from guillotina import app_settings
from guillotina.commands.server import ServerCommand
from guillotina.component import get_adapter
from guillotina.component import provide_utility
from guillotina.utils import resolve_dotted_name
from guillotina_kafka.consumer import ConsumerWorkerLookupError
from guillotina_kafka.consumer import InvalidConsumerType
from guillotina_kafka.consumer.batch import BatchConsumer
from guillotina_kafka.consumer.stream import StreamConsumer
from guillotina_kafka.interfaces import IActiveConsumer
from guillotina_kafka.interfaces import IConsumerUtility

import asyncio
import logging
import sys

logger = logging.getLogger(__name__)


class StartConsumerCommand(ServerCommand):

    description = 'Start Kafka consumer'

    def get_parser(self):
        parser = super(StartConsumerCommand, self).get_parser()

        parser.add_argument(
            '--consumer-type', type=str, default='stream',
        )
        parser.add_argument(
            '--topics', nargs='*',
            help='Kafka topics to consume from', type=str
        )
        parser.add_argument(
            '--regex-topic', type=str,
            help='Pattern to match available topics. You must provide '
            'either topics or pattern, but not both.'
        )
        parser.add_argument(
            '--consumer-worker', type=str, default='default',
            help='Application consumer that will consume messages from topics.'
        )
        parser.add_argument(
            '--consumer-group', type=str, help='Application consumer group.'
        )
        parser.add_argument(
            '--api-version', type=str,
            default='auto', help='Kafka server api version.'
        )
        parser.add_argument(
            '--take', type=int
        )
        parser.add_argument(
            '--within', type=int
        )
        return parser

    def get_worker(self, name):
        for worker in app_settings['kafka']['consumer']['workers']:
            if name == worker['name']:
                worker = {
                    **worker, "topics": list({
                        *worker.get('topics', []),
                        *app_settings['kafka']['consumer'].get('topics', [])
                    })
                }
                return worker
        return {}

    def get_consumer(self, arguments):

        worker = self.get_worker(arguments.consumer_worker)
        if not worker:
            raise ConsumerWorkerLookupError(
                'Worker has not been registered.'
            )

        try:
            consumer_worker = resolve_dotted_name(
                worker['path']
            )
        except Exception:
            raise ConsumerWorkerLookupError(
                'Worker has not been registered.'
            )

        topic_prefix = app_settings['kafka'].get('topic_prefix')
        if topic_prefix:
            worker['topics'] = [
                f'{topic_prefix}{topic}'
                for topic in worker['topics']
            ]

        # cli_topic has priority over worker['regex_topic']
        # which has priority over worker['topics']

        cli_topic = arguments.topics
        settings_topics = worker['topics']
        if worker.get('regex_topic'):
            settings_topics = f"{topic_prefix}{worker['regex_topic']}"

        if arguments.regex_topic:
            cli_topic = arguments.regex_topic

        try:
            topics = cli_topic or settings_topics
            if len(topics) == 0:
                raise Exception('No topics found')
            consumer = {
                'batch': BatchConsumer,
                'stream': StreamConsumer,
            }[arguments.consumer_type](
                topics,
                worker=consumer_worker,
                group_id=(
                    arguments.consumer_group or worker.get('group', 'default')).format(topic=topics[0]),
                bootstrap_servers=app_settings['kafka']['brokers']
            )
        except KeyError:
            raise InvalidConsumerType(
                f'{arguments.consumer_type} is not valid.')

        return get_adapter(
            consumer, IConsumerUtility, name=arguments.consumer_type)

    async def run_consumer(self, consumer, arguments):
        '''
        Run the consumer in a way that makes sure we exit
        if the consumer throws an error
        '''
        provide_utility(consumer, IActiveConsumer, '__main__')
        try:
            await consumer.consume(arguments, app_settings)
        except Exception:
            logger.error('Error running consumer', exc_info=True)
            sys.exit(1)

    def run(self, arguments, settings, app):
        consumer = self.get_consumer(arguments)
        loop = self.get_loop()
        asyncio.ensure_future(
            self.run_consumer(consumer, arguments),
            loop=loop)
        return super().run(arguments, settings, app)
