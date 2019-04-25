from guillotina.commands.server import ServerCommand
from guillotina.component import get_adapter
from guillotina.tests.utils import get_mocked_request
from guillotina.tests.utils import login
from guillotina.utils import resolve_dotted_name
from guillotina_kafka.consumer import ConsumerWorkerLookupError
from guillotina_kafka.consumer import InvalidConsumerType
from guillotina_kafka.consumer.batch import BatchConsumer
from guillotina_kafka.consumer.stream import StreamConsumer
from guillotina_kafka.interfaces import IConsumerUtility

import aiotask_context
import asyncio
import inspect
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
            '--consumer-worker', type=str, default='default', nargs='+',
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

    def get_worker(self, name, settings):
        for worker in settings['kafka']['consumer']['workers']:
            if name == worker['name']:
                worker = {
                    **worker, "topics": list({
                        *worker.get('topics', []),
                        *settings['kafka']['consumer'].get('topics', [])
                    })
                }
                return worker
        return {}

    async def get_consumer(self, worker, arguments, settings):
        if not worker:
            raise ConsumerWorkerLookupError(
                'Worker has not been registered.'
            )

        try:
            consumer_worker = resolve_dotted_name(
                worker['path']
            )
        except KeyError:
            raise ConsumerWorkerLookupError(
                'Worker has not been registered.'
            )

        if inspect.isclass(consumer_worker):
            handler = consumer_worker()
        if hasattr(handler, 'initialize'):
            await handler.initialize()

        topic_prefix = settings['kafka'].get('topic_prefix')
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
            consumer = {
                'batch': BatchConsumer,
                'stream': StreamConsumer,
            }[arguments.consumer_type](
                cli_topic or settings_topics,
                worker=consumer_worker,
                group_id=arguments.consumer_group or worker.get('group', 'default'),
                api_version=arguments.api_version,
                bootstrap_servers=settings['kafka']['brokers']
            )
        except KeyError:
            raise InvalidConsumerType(f'{arguments.consumer_type} is not valid.')

        return get_adapter(consumer, IConsumerUtility, name=arguments.consumer_type)

    async def run_consumer(self, consumer, arguments, settings):
        '''
        Run the consumer in a way that makes sure we exit
        if the consumer throws an error
        '''
        request = get_mocked_request()
        login(request)
        aiotask_context.set('request', request)
        try:
            await consumer.consume(arguments, settings)
        except Exception:
            if hasattr(consumer.consumer, 'finalize'):
                try:
                    await consumer.consumer.finalize()
                except Exception:
                    logger.error('Error calling cleanup', exc_info=True)
            logger.error('Error running consumer', exc_info=True)
            sys.exit(1)

    def run(self, arguments, settings, app):
        loop = self.get_loop()
        for consumer_worker in arguments.consumer_worker:
            worker = self.get_worker(consumer_worker, settings)
            consumer = self.get_consumer(worker, arguments, settings)
            asyncio.ensure_future(
                self.run_consumer(consumer, arguments, settings),
                loop=loop)
        return super().run(arguments, settings, app)
