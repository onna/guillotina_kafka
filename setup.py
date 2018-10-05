from setuptools import find_packages
from setuptools import setup


try:
    README = open('README.rst').read()
except IOError:
    README = None

setup(
    name='guillotina_kafka',
    version="1.0.0",
    description='Guillotina server application python project',
    long_description=README,
    install_requires=[
        'guillotina==3.2.16',
        'kafka-python==1.4.3',
        'aiokafka==0.4.2',
        'backoff==1.6.0',
    ],
    author='Guillotina Kafa',
    author_email='sekou@onna.com',
    url='',
    packages=find_packages(exclude=['demo']),
    include_package_data=True,
    tests_require=[
        'pytest',
    ],
    extras_require={
        'test': [
            'pytest'
        ]
    },
    classifiers=[],
    entry_points={
    }
)
