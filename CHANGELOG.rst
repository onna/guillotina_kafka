Changelog
=========

2.4.0
-----

- Fix python 3.12 compatibility

2.3.7
-----

- handle partitions revoked

2.3.6
-----

- fix startup command

2.3.3
-----

- Be able to import mypy

2.3.2
-----

- Make sure to stop consumers on application exit
  [vangheem]

2.3.1
-----

- Add ConsumerGroupeRebalancer listener to start consuming from the previous offset
on every partition assignment

2.3.0
-----

- g5 compat

2.2.9
-----

- Fix asyncio concurrency issues when setting up producer object


2.2.8
-----

- handle possible issue exiting pod

2.2.7
-----

- Be able to run consumers without a singleton
  [vangheem]

- Be able to configure connection settings from consumer
  [vangheem]


2.2.6
-----

- be able configure consumers with dictionary so they can be updated with env vars
  [vangheem]

- be able to configure kafka consumer connection
  [vangheem]

2.2.5
-----

- bump

2.2.4
-----

- Remove kafka version pin
  [vangheem]

2.2.3
-----

- Fix multi consumer to work when consuming from multiple topics
  [vangheem]

2.2.2
-----

- allow providing group ids that contain the topic name in them: "{topic}-group"
  [vangheem]

2.2.1
-----

- allow regex topics for multi consumers
  [ableeb]

2.2.0
-----

- Add `guillotina_kafka.interfaces.IKafkaMessageConsumedEvent` event
  [vangheem]


2.1.8
-----

- Make consumer worker config available to the worker
- Properly exit on consumer crash

2.1.7
-----

- Multiple consumers in a single process fix
- Add consumer-stat command to have a global stat on a topic 

2.1.6
-----

- Use configured app settings

2.1.5
-----
- Now we can run multiple consumers in a single process

2.1.4
------
- Remove tasks cancelation on consumer exception.

2.1.3
------
- Really exit the consumer on exception.

2.1.2
------
- Added stat endpoint to consumer.

2.1.1
------
- Code improvement to support consumer subscription to regex topic.