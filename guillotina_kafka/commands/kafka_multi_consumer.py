from aiokafka import AIOKafkaConsumer
from functools import partial
from aiokafka import ConsumerRebalanceListener
from aiokafka.errors import IllegalStateError
from aiokafka.structs import TopicPartition
from guillotina import app_settings
from guillotina import task_vars
from guillotina.commands.server import ServerCommand
from guillotina.component import get_utility
from guillotina.component import provide_utility
from guillotina.tests.utils import get_mocked_request
from guillotina.tests.utils import login
from guillotina.utils import resolve_dotted_name
from guillotina_kafka.consumer import ConsumerWorkerLookupError
from guillotina_kafka.interfaces import IActiveConsumer
from guillotina_kafka.interfaces import IKafkaProducerUtility
from typing import List

import asyncio
import inspect
import logging
import os

logger = logging.getLogger(__name__)


class StopConsumerException(Exception):
    pass


class StartConsumersCommand(ServerCommand):

    description = "Start Kafka consumer"

    def get_parser(self):
        parser = super(StartConsumersCommand, self).get_parser()
        parser.add_argument(
            "--consumer-worker",
            type=str,
            default="default",
            nargs="+",
            help="Application consumer that will consume messages from topics.",
        )
        parser.add_argument(
            "--api-version", type=str, default="auto", help="Kafka server api version."
        )
        return parser

    def get_worker_conf(self, name):
        for worker in app_settings["kafka"]["consumer"]["workers"]:
            if name == worker["name"]:
                worker = {
                    **worker,
                    "topics": list(
                        {
                            *worker.get("topics", []),
                            *app_settings["kafka"]["consumer"].get("topics", []),
                        }
                    ),
                }
                return worker
        return {}

    async def run_consumer(self, worker, consumer, worker_conf):
        """
        Run the consumer in a way that makes sure we exit
        if the consumer throws an error
        """
        request = get_mocked_request()
        login()
        task_vars.request.set(request)

        try:
            await worker(consumer, request, worker_conf, app_settings)
        except Exception:
            logger.error("Error running consumer", exc_info=True)
        finally:
            util = get_utility(IKafkaProducerUtility)
            try:
                await util.stop_active_consumers()
            except Exception:
                pass
            os._exit(1)

    def init_worker_conf(self, worker_name, arguments):
        worker = self.get_worker_conf(worker_name)
        if not worker:
            raise ConsumerWorkerLookupError(
                f"{worker_name}: Worker has not been registered."
            )
        try:
            worker["handler"] = resolve_dotted_name(worker["path"])
        except KeyError:
            raise ConsumerWorkerLookupError(
                f"{worker_name}: Worker has not been registered."
            )
        return worker

    def _get_worker(self, consumer, worker_conf):
        worker = worker_conf["handler"]
        if inspect.isclass(worker):
            worker = worker()
        # store __consumer__ here so we can shut this consumer down on exit
        # by looking up the utiltiy
        worker.__consumer__ = consumer
        provide_utility(worker, IActiveConsumer, worker_conf["name"])
        return worker

    async def _run(self, arguments, app):
        self.tasks = []
        worker_names = arguments.consumer_worker
        if isinstance(worker_names, str):
            # we could just specify one here
            worker_names = [worker_names]

        conn_settings = {
            "api_version": arguments.api_version,
            "bootstrap_servers": app_settings["kafka"]["brokers"],
            "loop": self.get_loop(),
        }
        conn_settings.update(
            app_settings["kafka"].get("consumer_connection_settings", {})
        )

        for worker_name in worker_names:
            worker_conf = self.init_worker_conf(worker_name, arguments)
            topic_prefix = app_settings["kafka"].get("topic_prefix", "")
            worker_conn_settings = {
                **conn_settings,
                **(getattr(worker_conf["handler"], "connection_settings", {}) or {}),
                **(worker_conf.get("connection_settings") or {}),
            }
            if worker_conf.get("regex_topic"):
                consumer = AIOKafkaConsumer(
                    group_id=worker_conf.get("group", "default"), **worker_conn_settings
                )
                self.tasks.append(
                    self.run_consumer(
                        self._get_worker(consumer, worker_conf), consumer, worker_conf
                    )
                )
            else:
                for topic in worker_conf["topics"]:
                    topic_id = f"{topic_prefix}{topic}"
                    group_id = worker_conf.get("group", "default").format(
                        topic=topic_id
                    )
                    consumer = AIOKafkaConsumer(
                        group_id=group_id, **worker_conn_settings
                    )
                    worker = self._get_worker(consumer, worker_conf)
                    listener = ConsumerGroupeRebalancer(
                        consumer=consumer, worker=worker
                    )
                    consumer.subscribe(topics=[topic_id], listener=listener)
                    self.tasks.append(self.run_consumer(worker, consumer, worker_conf))
        
        # Start all consumers as background tasks
        for consumer_coro in self.tasks:
            asyncio.create_task(consumer_coro)

    def run(self, arguments, settings, app):
        app.on_startup.append(partial(self._run, arguments))
        return super().run(arguments, settings, app)


class BaseConsumerWorker:
    def __init__(self, msg_deserializer=lambda data: data.decode("utf-8")):
        self.msg_deserializer = msg_deserializer
        self.ready = False

    async def seek(self, topic, step):
        for tp in topic.assignment():
            try:
                position = await topic.position(tp)
            except IllegalStateError:
                position = 0

            if position > 0:
                topic.seek(tp, position + step)
        return topic

    async def reposition_offset(self, topic, position):

        try:
            position = int(position)
        except ValueError:
            pass
        else:
            return await self.seek(topic, position)

        try:
            await {"beginning": topic.seek_to_beginning, "end": topic.seek_to_end}[
                position
            ]()
        except KeyError:
            raise Exception("Invalid offset position")

        return topic

    async def setup(self):
        raise NotImplementedError()

    async def __call__(self, topic, request, worker_conf, settings):
        raise NotImplementedError()


class ConsumerGroupeRebalancer(ConsumerRebalanceListener):
    def __init__(self, consumer: AIOKafkaConsumer, worker):
        self.consumer = consumer
        self.worker = worker

    async def on_partitions_revoked(self, revoked):
        """
        There is a difficult relationship between guillotina_kafka and how
        a consumer/worker is setup right now.

        The rebalance listener is composed in guillotina_kafka and not
        accessible for the worker implementation where we do the manual
        commit handling in canonical.

        Long term, this should be moved to kafkaesk and done correctly; however,
        right now, we have to
        """
        if revoked:
            if (
                not self.consumer._enable_auto_commit
                and getattr(self.worker, "flush", None) is not None
            ):
                async with self.worker.lock:
                    await self.worker.flush()

    async def on_partitions_assigned(self, assigned: List[TopicPartition]) -> None:
        """This method will be called after partition
           re-assignment completes and before the consumer
           starts fetching data again.

        Arguments:
            assigned {TopicPartition} -- List of topics and partitions assigned
            to a given consumer.
        """
        for tp in assigned:
            try:
                position = await self.consumer.position(tp)
                offset = position - 1
            except IllegalStateError:
                offset = -1

            if offset > 0:
                self.consumer.seek(tp, offset)
            else:
                self.consumer.seek_to_beginning(tp)
