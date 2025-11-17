import pytest
from guillotina import app_settings
from guillotina import testing


base_kafka_settings = {
    "brokers": ["localhost:9092"]
}


def base_settings_configurator(settings):
    if 'applications' in settings:
        settings['applications'].append('guillotina_kafka')
    else:
        settings['applications'] = ['guillotina_kafka']
    settings['kafka'] = base_kafka_settings


testing.configure_with(base_settings_configurator)


@pytest.fixture(name="function")
def kafka_container(kafka):
    app_settings.setdefault('kafka', {})
    app_settings['kafka'].update({
        "brokers": [f"{kafka[0]}:{kafka[1]}"]
    })
    yield kafka